# GoldMine / podcast-catalogue — Critical System Review

**Date:** 2026-07-18 · **Scope:** entire repository at `8aa1e11` (main) · **Method:** full read of the Python package, tests, build config, data directory, and frontend; test suite executed; import graph and git history verified.

---

## Verdict

The repository contains genuinely good ideas — a staged pipeline, a thoughtful Pydantic ontology with an editorial-trust layer, tiered exports, MCP-first design — but **as committed, the system does not run at all**: core modules were never committed, the package cannot be installed, every test fails at import, and the flagship `server.py` contains code that is unreachable, mangled by a committed regex-rewrite script, or crashes on first use. The README describes a "Hardened v6.20" production system; the code is a demo that was last known to work only on the author's machine, in a state that no longer exists in git.

This is fixable, and the fixes are mostly mechanical. But right now the gap between what the documentation claims and what the repository can do is the single biggest risk of this project — for anyone who clones it, and for any downstream consumer ("Connect", "Daisy") told to depend on it.

---

## 1. Blocking: the system cannot be built, imported, or tested

These issues are not style problems. Each one, alone, prevents the repo from working on any machine other than the author's.

### 1.1 Six imported modules were never committed

`pipeline.py` and `server.py` import modules that do not exist in the package — and `git log --all` confirms they have **never existed in any commit**:

| Missing module | Imported by | Effect |
|---|---|---|
| `authority` | `pipeline.py:19` | `import podcast_catalogue` fails → CLI, pipeline, FastAPI bridge all dead |
| `entity_registry` | `pipeline.py:20`, `server.py:12` | MCP server fails at startup |
| `spotify_resolver` | `pipeline.py:32` | pipeline dead |
| `youtube_enricher` | `pipeline.py:33` | pipeline dead |
| `assembler` | `server.py:857` | MCP server dead |
| `regional_pipeline` | `pipeline.py:770` (lazy) | regional synthesis always fails — and it is **on by default** (`CatalogueConfig.regional_synthesis: bool = True`) |

Because `podcast_catalogue/__init__.py` eagerly imports `catalogue` → `pipeline`, **nothing in the package can be imported**. The last commit message ("exclude large files") suggests selective staging; source files got excluded along with data.

### 1.2 The entire test suite fails at collection

All 9 test files (66 test functions) error out on `ModuleNotFoundError: No module named 'podcast_catalogue.authority'`. **Zero tests can execute.** There is also no test file at all for `server.py` — the 2,204-line module that is the product's main surface. Tests that cannot run are worse than no tests: they provide false confidence in the README's "Hardened" claims.

### 1.3 The package cannot be installed

`pyproject.toml:3` declares `build-backend = "setuptools.backends._legacy:_Backend"` — this module does not exist in setuptools (the real names are `setuptools.build_meta` / `setuptools.build_meta:__legacy__`). `pip install .` fails before dependencies are even considered.

### 1.4 Dependency manifests contradict each other and the code

- `pyproject.toml` says `speechbrain`, `scikit-learn`, `chromadb`; `requirements.txt` says `ollama`, `pyannote.audio`, `lancedb`, `voyager`. The code actually uses **lancedb + voyager + pyannote** (`vector_store.py`, `transcriber.py`); chromadb/speechbrain/scikit-learn appear nowhere.
- Actually-imported packages missing from **both** manifests: `python-dotenv` (`server.py:11`, `ai_enricher.py:6`), `fastapi`/`uvicorn` (`prism_http.py`), `google-genai` (`ai_enricher.py:285`), `yt-dlp` (`transcriber.py:130`), `numpy`. External binary requirement: `ffmpeg` (undocumented outside `--check-env`).
- Nothing is version-pinned; there is no lockfile.

### 1.5 Hard platform lock-in, undeclared

`transcriber.py:5` imports `mlx_whisper` at module level, and `pipeline.py:21` imports `transcriber` unconditionally — so even a metadata-only crawl requires **MLX, which only exists on Apple Silicon**. `pip install` of the declared dependencies fails outright on Linux/Windows. If macOS-only is intentional, say so in the README; if not, the import must become lazy and the dependency optional.

**Bottom line for §1:** the committed repo has plausibly never been run end-to-end. `bridge.log` — itself accidentally committed — records the server failing to launch (`uvicorn: No such file or directory`).

---

## 2. Advertised features that are façades

The README markets capabilities that the code stubs out or hardcodes:

- **The "Semantic Audio Extraction Suite" is empty.** `ai_enricher.py:653-660`: `identify_speakers`, `find_topic_segments`, `detect_emotional_peaks`, `detect_disagreements`, `detect_data_claims`, `generate_summary_points`, `identify_qa_pairs` all return `{}`/`[]` unconditionally. The MCP tools built on them (`extract_topic_segment`, `extract_emotional_peaks`, `extract_disagreements`, `extract_data_claims`, `extract_question_answers`, `extract_summary_clip`) can never return a positive result, and speaker naming in the transcribe stage (`pipeline.py:445`) is a no-op.
- **"Topic expansion" and the "Coverage Bridge" are 5 hardcoded dictionary entries** (`server.py:378-390`) matched only on exact lowercase query. `_search_cache` (`server.py:367`) is declared and never used.
- **`ingest_social_telemetry` reports `"status": "success"` but persists nothing** — the save call is commented out (`server.py:911-912`).
- **`--concurrency` does nothing.** `CatalogueBuilder(limit_concurrency=...)` stores it (`catalogue.py:48-49`); `ParseStage` hardcodes `Semaphore(10)` (`pipeline.py:175`).
- **The "Industrial-Noir UI in Claude" hook is likely inert.** `wrap_with_ui` (`server.py:364-365`) hand-builds a raw MCP response with `_meta.ui` inside the tool's *return value*; FastMCP serializes returned dicts to text content, so the UI resource pointer arrives as literal JSON text, not protocol metadata.
- **`demo_extractor.py` imports `search_transcripts` from `server.py`** — a tool that no longer exists. The showcase demo is broken.
- The README roadmap marks Phase 1 and Phase 2 "✅ done". Given the above, neither is.

---

## 3. Concrete bugs in the code that does exist

### `server.py` (the MCP server)

- **`walkie_talkie_pivot` crashes whenever it finds a match** (`server.py:825`, `:842`): highlights are dicts, but the code reads `h.reason`, `h.transcript_snippet` (a field that doesn't exist in *any* schema), `h.start_time` → `AttributeError`. The "Sub-500ms" tool has clearly never been called on real data.
- **`asyncio.run()` inside async tools** (`server.py:1677`, `:1717`, `:1898`): `extract_speaker_reel`, `extract_dialogue`, `create_audiogram` call `asyncio.run(...)` from within the server's running event loop → guaranteed `RuntimeError` on every invocation.
- **Async tools called synchronously** (`server.py:1756`, `:1948`, `:1974`): `extract_speaker_intro`, `extract_quote_clip`, `extract_cold_open` call `extract_audio_clip(...)` without `await`, producing a coroutine object; `extract_quote_clip` then calls `.startswith()` on it → `AttributeError`, and the coroutine is never executed.
- **Truncated statement** (`server.py:2151`): `extract_summary_clip` ends with a bare `re` — the remains of `return await _process()`. The tool silently returns `None`. The committed `refactor_async.py` (a regex-based in-place rewriter of `server.py`, hardcoded to `/Users/craigmccosker/...`) is almost certainly the culprit; running codegen scripts over your main module and committing the result unreviewed and untested is how this file got into its current state.
- **22 lines of unreachable code** after `return` in `extract_audio_clip` (`server.py:1587-1609`) — the corpse of a `get_episode_highlights` tool that lost its decorator and signature.
- **`timeline_set` references `self` in a module-level function** (`server.py:1284`) → `NameError`; the same function treats store entries as Pydantic objects (`p.title`, `ep.timeline`) when the store holds plain dicts. The whole legacy block was written against a different data layer and never ported.
- **`get_catalogue_stats` divides by zero** on an empty catalogue (`server.py:1210`).
- **Legacy `generate_daily_briefing` awaits a sync function with the wrong arguments** (`server.py:2183`): `generate_editorial_report(session, podcasts)` — the real signature is `(podcasts, lookback_hours)` and it returns `str`, not an awaitable.
- **Nested/duplicated legacy gating**: `if GOLDMINE_LEGACY_TOOLS == "1"` appears *inside* the identical outer `if` (`server.py:1215` → `:2156`), and the fuzzy find-episode-by-title loop is copy-pasted ~10 times with subtly different matching rules (exact-then-partial vs. partial-only), so the same title resolves differently per tool.
- **`DataStore.save_data` is lossy** (`server.py:134-143`): `load_data` silently drops malformed JSONL lines (`except Exception: continue`, `:126-127`) and keys shows by lowercased title (case-variant duplicates collapse); `save_data` then rewrites the *entire* file from that reduced in-memory state — and `ingest_snipd_markdown` triggers save+reload on **every ingest** (`server.py:203-204`). One bad line in `universe.jsonl` plus one Snipd ingest equals permanent data loss, with no backup and no atomic write.
- **`get_details` bidirectional substring matching** (`server.py:303-305`): querying "the" returns an arbitrary show; match quality depends on dict insertion order.
- **The "Hallucination Shield" pollutes search**: invalid transcripts are replaced with the sentinel string `"[TRANSCRIPT UNAVAILABLE: DATA QUALITY ISSUE DETECTED]"` (`server.py:98`), which then participates in substring search (`search_catalogue` scans `transcript`), so queries like "data" match the sentinel.
- **Inconsistent vibe thresholds**: `find_podcast_by_vibe` says Medium = (0.4, 0.6) (`server.py:739-741`); `find_episodes_by_vibe` says Medium = (0.3, 0.7) (`server.py:1155-1157`). Same concept, different answers.
- **`recommend_episodes` silently discards every episode without an `audio_url`** (`server.py:1103`) — for a catalogue where most episodes lack resolved audio, the recommender ignores most of the catalogue, with no indication.
- **camelCase/snake_case split-brain everywhere**: the store writes `audio_url` while the pipeline writes `audioUrl`; half the tools defensively read both (`ep.get("audioUrl") or ep.get("audio_url")`), half don't (`_require_audio`, `server.py:1639`, checks only `audioUrl`). The Media Bridge in `play_episode` updates `episode["audio_url"]` (`server.py:524`) on a dict whose canonical key is `audioUrl` — the fetched URL is then invisible to `_require_audio`.

### Pipeline & CLI

- **Forced re-enrichment destroys data** (`pipeline.py:301-305`): `EnrichStage` unconditionally assigns `podcast.itunes_id = itunes_id` etc. — when the iTunes lookup fails under `--force`, previously-good ratings/genres are overwritten with `None`.
- **`except Exception as re:`** (`pipeline.py:547`) shadows the `re` module inside the method scope — a latent `UnboundLocalError` for anyone who later adds a regex to that function, and a smell of unreviewed code.
- **Incremental output can duplicate rows**: `on_podcast_processed` *appends* the podcast to the output file once per stage (`cli.py:110-113`); the file is only deduplicated by the final full rewrite — crash mid-run and the output contains up to N copies of every show.
- **`DEFAULT_STAGE_ORDER` omits `correction` and `youtube-enrich`** (`pipeline.py:801`) — the "Editorial Safety Net" never runs unless explicitly invoked; meanwhile stage comments label two different stages "6C" and two "7".
- **Merging is keyed by title** (`catalogue.py:112`, `pipeline.py:196`, `cli.py:129`): shows or episodes with duplicate titles silently overwrite each other.

### Vector store

- **Every re-index duplicates every chunk** (`vector_store.py:186-192`): the dedup branch is abandoned mid-comment ("we just won't deduplicate"), then rows with *deterministic* chunk IDs are inserted anyway — LanceDB and the Voyager index accumulate copies on each pipeline run, degrading search quality permanently until a manual rebuild.
- **Relevance scores misalign after filtering** (`vector_store.py:313-321`): `_distance` is assigned by enumerating the *filtered* results against the *unfiltered* distance array — wrong scores whenever an ID is missing or genre-filtered.
- **A fresh DB connection per episode** (`index_episode` ignores the `table` argument and calls `get_db_client()` every time, `vector_store.py:154`).

### AI layer

- **Two classes named `EngagementSchema`** in the same module (`ai_enricher.py:74` and `:151`); the second silently shadows the first, so the "required fields" contract of the first is dead code.
- **Ollama ignores structured schemas entirely** (`ai_enricher.py:430`): `_generate(prompt, schema)` drops the schema, relies on regex JSON-scraping, and hides 4xx responses (no branch for them → silent `None` after 3 retries). Only Gemini gets `response_schema`. So "Local Scout: state-of-the-art JSON extraction" is prompt-and-pray.
- **Model naming chaos**: `OllamaEngine` defaults to `gemma4:latest` (`ai_enricher.py:390`), `get_engine` overrides to `qwen3.5:latest` (`:560`), `router.py:12` hardcodes `qwen3:14b`, the CLI help says "Qwen3:14b", the README says "Qwen 3.5". Four sources of truth, none authoritative.
- **`datetime.utcnow()`** (`ai_enricher.py:247`) — deprecated, naive-UTC footgun.

---

## 4. Security & trust-model concerns

For a system whose selling point is an *Editorial Trust Layer*, the trust posture of the software itself is weak:

1. **Unauthenticated state mutation from any connected agent.** `register_entity_correction` (`server.py:656`) lets any MCP client write arbitrary regex→replacement pairs into a persistent registry that is later applied to *all* titles, transcripts, quotes and guest names (`CorrectionStage`). That is a content-poisoning primitive (silently rewrite any name in the corpus) and a ReDoS primitive (malicious pattern), with no review, no audit trail, no undo.
2. **The FastAPI bridge is wide open** (`prism_http.py:50-56`): `allow_origins=["*"]` *with* `allow_credentials=True` (an invalid, browsers-reject-it combination that signals CORS wasn't reasoned about), no auth on any route, and `POST /api/v1/ingest` will crawl **any URL you hand it** in a background task — an SSRF surface and a free crawl-scheduler for anyone who can reach the port.
3. **`get_dj_session_bundle` is prompt injection by design** (`server.py:787-796`): a data tool that returns `"directive": "SYSTEM_STATE_FLUSH"` *instructing the calling agent to flush its conversation history* "to prevent … radicalization". Tools must return data, not directives; downstream agents that obey tool-embedded instructions are exactly the vulnerability class MCP consumers are told to defend against. (The same philosophy powers `sanitize_dj_output` — a regex "guardrail" that strips `<think>` tags and nothing else.)
4. **Fabricated data is injected into the canonical dataset.** `inject_referrals.py` (repo root) overwrites `applePodcastPage` for *every* show — real-looking Apple links for 5 hardcoded shows, synthesized search URLs for the rest — then `os.replace`s the production file "for the demo". Nothing marks these fields as fabricated; the exporter and JSON-LD generator then publish them as fact.
5. **The trust layer's provenance is itself unverified LLM output.** `claimStatus`, `contentRisk`, `expires` are whatever Gemini/Qwen emit; `claim_interpreter` is set to a model name; nothing downstream distinguishes "confirmed" (an LLM guessed the word "confirmed") from human-verified. Presenting this as an "Epistemic Flagging" system (`get_catalogue_context`) to other agents invites over-trust; `AIProvenance.human_reviewed` defaults to `False` and nothing ever sets it to `True`.
6. **No rate limiting, no input length caps** on any tool or endpoint; `search_catalogue` substring-scans every full transcript per query (`server.py:403-408`) — a single agent in a loop is a CPU DoS.
7. Minor: shared `aiohttp` fetches in `play_episode` skip the certifi SSL context and timeouts used elsewhere (`server.py:516`); MD5-truncated-to-12-hex episode IDs (`server.py:93`) are fine for 450 episodes but have no collision handling at the scale the project aspires to ("global signal bridge").

---

## 5. Architecture

- **`server.py` is a 2,204-line god-module**: data store, JSONL persistence, Snipd markdown parser, ~40 MCP tools, legacy tool museum, and two `if __name__` blocks. The store (`DataStore`) is a global singleton that loads data **at import time** (`server.py:309-310`) — importing the module for any reason (as `prism_http.py` does) performs file I/O and prints to stderr. Nothing here is unit-testable, which is presumably why nothing here is unit-tested.
- **Two parallel data models with no bridge discipline.** The pipeline speaks typed Pydantic (`models.py`); the server speaks raw dicts with alias-key roulette. Every feature pays the tax twice (`contentRisk` or `content_risk`? `startTime` or `start_time`?), and bugs like §3's `audio_url` mismatch are the structural consequence. Pick one: load the store through `Podcast.model_validate` and serve `model_dump(by_alias=True)`.
- **JSONL files as a multi-writer database.** The MCP server, the FastAPI bridge, the CLI pipeline, and ad-hoc scripts all read/write `data/universe.jsonl` and friends with no locking, no atomic writes, no schema versioning, and full-file rewrites. The `data/` directory — 27 MB of overlapping snapshots (`podcasts.jsonl`, `podcasts_enriched.jsonl`, `podcasts_enriched_calibrated.jsonl`, `podcasts_450_full_intelligence.jsonl`, `universe.jsonl.bak`, …) — is the visible archaeology of that choice. A single SQLite file would eliminate the whole class of problems and the four-way fallback chain at `server.py:22-33`.
- **Paths resolve relative to the installed package** (`server.py:22-26`, `vector_store.py:33`, `prism_http.py:21` — `.../__file__/../data`): correct only in an editable checkout; broken the moment the wheel installs to site-packages. Meanwhile `dj_triage.py:9` uses CWD-relative `"data/universe.jsonl"` — a third convention.
- **Config sprawl**: model names in 4 places, Ollama endpoints hardcoded in 3 modules (`ai_enricher.py:390`, `vector_store.py:29`, `router.py:11`), TTS server hardcoded (`prism_http.py:269`), Makefile pointing at sibling directories on the author's disk (`../AI Podcast/sota-app/public`). There is no settings module; `.env` handling exists only for `GEMINI_API_KEY`/`HF_TOKEN`.
- **The frontend is a separate app with a second copy of the data** (`goldmine/public/data.jsonl`, 12 MB, committed) and its own TypeScript types (`goldmine/src/types.ts`, plus a *third* type set in `types/index.ts` and a *fourth* in `packages/prism-types/`). Four hand-maintained schemas for one ontology guarantee drift; generate TS types from the Pydantic models instead.
- **Branding noise**: GoldMine, PRISM/Prism, Daisy, Connect, Sentinel, SoTA, "Neural Operating System" — six-plus names for one hobby-scale system, several of which (`Makefile`, `daisy_adapter.py`, `prism_http.py`) refer to apps that don't exist in this repo. Every name is cognitive overhead for a new contributor and a credibility cost in review.

---

## 6. Repository hygiene

- **~51 MB of committed files, most of it generated artifacts**: 12 MB `goldmine/public/data.jsonl`, 12 MB `data/podcasts_450_full_intelligence.jsonl`, **9.5 MB `scripts/temp.jsonl`**, ~10 MB of `.mp3`/`.mp4` clips (`data/clips/`, `verify_audio.mp3`, `verify_audio_trimmed.mp3`), a dozen `phase2_*.log` run logs, `report.txt`, `bridge.log`, `universe.jsonl.bak`. The `.gitignore` gestures at this (`debug_*.json`, `test_*.jsonl`) but the actual junk is committed anyway. History already carried a full LanceDB store (hundreds of `.txn` files removed in `8aa1e11`), so `.git` is 24 MB and growing.
- **One-off scripts with absolute paths to the author's machine committed at root**: `inject_referrals.py`, `refactor_async.py` (both `/Users/craigmccosker/...`), plus `debug_dates.py`, `test_hf.py`, `test_export.py`, `trial_prism.py`, `demo_extractor.py`, `verify_diarization.py` and a `scripts/` directory of 18 more debug/repair one-offs. These are not tooling; they are shell history.
- **No CI of any kind.** A single GitHub Actions job running `pip install -e . && python -c "import podcast_catalogue" && pytest` would have caught §1 on the day it happened.
- **No LICENSE file** despite `license = {text = "MIT"}` in `pyproject.toml`; no CHANGELOG; version is `1.0.0` while the README says `v6.20` — a third versioning scheme, `5.0.0`, lives in `prism_http.py:46`.

---

## 7. What is genuinely good

Credit where due — these are worth preserving through any cleanup:

- **`models.py` is a thoughtful ontology.** The editorial-trust vocabulary (`ClaimStatus`, `SourceAnchor` with schema.org `Clip` semantics, `AIProvenance`, `ContentRisk`) is ahead of most media-AI projects in *intent*, and the alias discipline is consistent.
- **The staged-pipeline design** (`Stage` base class, registry, `--stage` single-stage runs, incremental merge with existing data) is the right shape for this problem, and transcription priority scoring (authority + recency + guest signals) is a sensible idea.
- **`clipper.py` is the best file in the repo**: input validation, deterministic cache filenames, HTTP-seek streaming instead of full downloads, correct error propagation and cleanup.
- **`transcriber.py`** is pragmatic: lazy pyannote loading, the `use_auth_token`→`token` compatibility shim, WAV normalization, temp-file cleanup in `finally`, maximum-overlap speaker mapping.
- **`recommender.py`** is small, pure, testable, and honest about being heuristic — more shippable than most of `server.py`.
- **Tiered exports** (Tier 0/1/2 in `exporter.py`) and the parser's NEXT_DATA-first-then-meta-tags fallback strategy are both sound engineering.
- Real test fixtures (`tests/fixtures/*.html`) exist and the test files are substantive — they just can't run.

---

## 8. Prioritized recommendations

**P0 — make the repo true (days):**
1. Commit the six missing modules — or delete every feature that needs them. Either is fine; the current state is neither.
2. Fix `build-backend` to `setuptools.build_meta`; consolidate `requirements.txt` into `pyproject.toml` with the dependencies the code actually imports; make `mlx-whisper`/`pyannote`/`lancedb` optional extras (`[transcribe]`, `[index]`) with lazy imports so the core package imports on Linux.
3. Add CI: `pip install -e .[dev] && pytest`. Green before any new feature.
4. Delete `refactor_async.py` and repair its damage in `server.py` (`:2151` truncated return, `:1587-1609` dead block, the sync-calls-to-async-tools, the `asyncio.run`-in-event-loop calls). None of the audio-suite tools work today.
5. Purge generated artifacts from the tree (clips, logs, `temp.jsonl`, `verify_audio*`, `report.txt`, `bridge.log`, `.bak`), extend `.gitignore`, and consider `git filter-repo` if the 24 MB history matters.

**P1 — make the server honest and safe (1–2 weeks):**
6. Split `server.py`: `store.py` (typed, loading through `models.py`, atomic writes), `tools/` by domain, delete or quarantine the legacy block (it is not gated dead weight — it is *broken* gated dead weight).
7. Remove or rewrite the stub-backed tools; where a capability doesn't exist, the tool must not exist. Same for the README: strip "Hardened", "Zero-error", "sub-500ms", and un-tick the roadmap boxes.
8. Auth + write-protection: `register_entity_correction` and `/api/v1/ingest` need an allowlist/token and audit logging; fix CORS; validate correction patterns (no arbitrary regex from clients). Drop the `SYSTEM_STATE_FLUSH` directive pattern entirely.
9. Replace the JSONL multi-writer pattern with SQLite (or at minimum: single writer, atomic temp-file-rename writes, quarantine-not-drop for bad lines).
10. Fix the vector store duplication and score misalignment; add an idempotent upsert keyed on the chunk ID that already exists.

**P2 — make it a system (ongoing):**
11. One config module (paths, models, endpoints) sourced from env; one schema source of truth with generated TypeScript.
12. Real evaluation for the AI layer: golden transcripts, extraction accuracy checks, and a place where `human_reviewed` can actually become `True` — otherwise rename the trust layer to what it is: model output.
13. Decide the project's actual scope. A personal ABC-podcast catalogue with great clipping tools is a strong, finishable project. A "Neural Operating System for media" serving the "Connect and Daisy situational intelligence ecosystems" is marketing debt that this codebase — 7 kLOC, one contributor, zero runnable tests — cannot service. The gap is where all of the above problems came from.

---

*Review generated from a full-source read; every file/line reference was verified against `8aa1e11`. Test-run evidence: `pytest` → 9/9 files error at collection, 0 tests executed.*
