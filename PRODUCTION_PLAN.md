# GoldMine → Production Plan

**Companion to:** `CRITICAL_REVIEW.md` (read it first; this plan operationalizes its findings)
**Written for:** an execution agent of moderate capability ("the Executor") supervised by the repo owner ("the Owner")
**Rule of engagement for the Executor:** follow the steps literally, in order, one phase at a time. Every phase has acceptance checks — do not begin a phase until the previous phase's checks pass. Where a step is tagged **[OWNER]**, stop and wait; do not attempt it yourself.

---

## Part A — Strategic assessment (context for humans; the Executor may skip to Part B)

### A.1 Local ↔ cloud alignment

The GitHub repo is an **incomplete subset** of the system on the Owner's machine. Evidence in the committed history:

- HEAD imports six modules (`authority`, `entity_registry`, `assembler`, `spotify_resolver`, `youtube_enricher`, `regional_pipeline`) that exist in no commit — they live only on the Mac.
- The runtime's primary data file `data/universe.jsonl` is not committed (only `universe.jsonl.bak` is); the LanceDB store was deleted from git in `8aa1e11`; the Voyager index and `.env` were never committed.
- Committed one-off scripts hardcode `/Users/craigmccosker/Developer/podcast-catalogue`, and the Makefile targets sibling app directories (`../Daisy-Podcasts`, `../AI Podcast/sota-app`, `../The-Sentinel`) that exist only locally.

**Conclusion:** the cloud repo cannot reproduce the local system. Until Phase 0 lands, GitHub is a broken mirror, and nothing in Phases 1–7 can start.

### A.2 Is it worth continuing? — Yes, with a narrowed thesis

**Assets (real):**
1. **Timing** — an MCP-native media-intelligence server is well-positioned in 2026; agent-accessible catalogues are becoming table stakes for publishers.
2. **The trust layer is the differentiator** — `ClaimStatus` / `SourceAnchor` / `AIProvenance` / `ContentRisk` is exactly the vocabulary public-service broadcasters need before they let AI touch editorial content. Competitors (consumer snipping apps, generic transcription APIs) do not have this framing.
3. **Working media machinery** — clip extraction, stitching, and audiogram generation (`clipper.py`) are demo gold and genuinely hard to fake.
4. **A substantial enriched corpus** (~450 ABC shows) proving the pipeline end-to-end.

**Liabilities (also real):**
1. **Rights** — the corpus is scraped ABC content. It cannot be sold, redistributed, or hosted publicly as a product. This is the binding constraint on the business model.
2. **Credibility gap** — docs claim a hardened v6.20 production system; the repo doesn't import. Any technical stakeholder who clones it today walks away.
3. **Bus factor of one**, Apple-Silicon lock-in, no CI, no runnable tests.

**Directional verdict:** continue, but reposition. Kill the "Neural Operating System / multi-ecosystem (Connect, Daisy, Sentinel, PRISM)" framing. The saleable thesis is:

> **A provenance-anchored podcast-intelligence engine that a broadcaster deploys on its own catalogue.** Agents (Claude, internal tools) get MCP access to search, vibes, guests, claims-with-provenance, and instant clip/audiogram generation. The ABC corpus is the *demo*, not the product.

Target stakeholder: innovation / digital teams at public-service or commercial broadcasters (ABC first, given the corpus), pitched as a **pilot on their catalogue with their blessing** — which simultaneously resolves the rights problem. Secondary path: open-source the engine (MIT, no data) as a credibility and inbound channel.

What "production ready" means for this plan: **a stranger can clone, install, test, run the demo in under 15 minutes on macOS or Linux; the security surface is closed; the docs are true.** It does not mean SaaS-scale infrastructure.

---

## Part B — Execution plan

### Global rules for the Executor

- **DO NOT** run `inject_referrals.py` or `refactor_async.py` under any circumstances.
- **DO NOT** perform bulk refactors, renames, or "improvements" not listed here.
- **DO NOT** delete or rewrite files under `data/` except where a step explicitly says so.
- **DO NOT** force-push, rebase published history, or run `git filter-repo` (Phase 6 flags it for the Owner only).
- Work on branch `production-hardening` off `main` (after Phase 0 merges). One commit per numbered task, message format: `P<phase>.<task>: <summary>`.
- If a step's acceptance check fails twice, stop and report; do not improvise a workaround.

---

### Phase 0 — Sync the real system to GitHub · **[OWNER, on the Mac]**

The cloud repo must first become truthful. On the local machine:

**0.1 Audit the drift.** In `/Users/craigmccosker/Developer/podcast-catalogue`:
```bash
git fetch origin
git status --short --branch
git ls-files --others --exclude-standard          # untracked (candidates never pushed)
git diff --stat origin/main                        # tracked-but-modified
ls podcast_catalogue/{authority,entity_registry,assembler,spotify_resolver,youtube_enricher,regional_pipeline}.py
```

**0.2 Commit the missing source.** Add, at minimum, the six modules above plus any other `podcast_catalogue/*.py` that appears untracked. Source code only — no data, no indexes, no `.env`:
```bash
git checkout -b sync-missing-modules
git add podcast_catalogue/*.py
git commit -m "Add modules referenced by pipeline/server but never committed"
git push -u origin sync-missing-modules
```
Open a PR, merge to `main`.

**0.3 Do NOT commit:** `data/universe.jsonl` (contains fabricated fields — Phase 3 handles data), `.env`, LanceDB/Voyager stores, `.venv`.

**Acceptance (run in a fresh clone, any machine):**
```bash
python3 -m venv v && . v/bin/activate && pip install aiohttp beautifulsoup4 pydantic certifi python-dotenv
python3 -c "import ast,glob; [ast.parse(open(f).read()) for f in glob.glob('podcast_catalogue/*.py')]"
python3 -c "from podcast_catalogue import models"   # must not raise
```
(The full package import still fails until Phase 1 makes `mlx_whisper` optional — that is expected here.)

---

### Phase 1 — Installable, testable, CI-guarded

**1.1 Fix the build backend.** `pyproject.toml:3` → `build-backend = "setuptools.build_meta"`.

**1.2 Consolidate dependencies.** In `pyproject.toml`, set core deps to exactly what core code imports: `aiohttp`, `beautifulsoup4`, `pydantic>=2`, `certifi`, `python-dotenv`. Add extras:
- `[project.optional-dependencies]`
  - `transcribe = ["mlx-whisper", "pyannote.audio>=3.1", "torchaudio", "yt-dlp"]`
  - `index = ["lancedb", "voyager", "numpy"]`
  - `ai = ["google-genai"]`
  - `http = ["fastapi", "uvicorn"]`
  - `mcp = ["mcp"]`
  - `dev = ["pytest", "pytest-asyncio"]`

Delete `requirements.txt`. Pin minimum versions the Owner confirms from the working Mac env (`pip freeze` there) — **[OWNER]** supplies that list.

**1.3 Make heavy imports lazy.**
- `transcriber.py`: move `import mlx_whisper` from module level (line 5) into `transcribe_audio()`.
- `pipeline.py:21`: move `from .transcriber import process_episode_transcription` inside `TranscribeStage.process`.
- Verify no other module-level import pulls transcribe/index/ai extras into the core path (`grep -n "^import\|^from" podcast_catalogue/*.py` and inspect).

**1.4 Add CI.** `.github/workflows/ci.yml`: on push/PR — Python 3.11 and 3.12, `pip install -e .[dev]`, `python -c "import podcast_catalogue"`, `pytest -q`. macOS runner optional-later; Linux must pass.

**1.5 Make the test suite runnable.** Run `pytest -q`. Fix collection errors only by (a) the lazy imports above, and (b) marking tests that require missing services with `pytest.importorskip` / `@pytest.mark.skipif`. Do not delete test assertions to force green; report any test whose *assertion* (not import) fails.

**Acceptance:** on Linux with no extras: `pip install -e .[dev]` succeeds; `python -c "import podcast_catalogue"` succeeds; `pytest -q` runs with **0 collection errors** and 0 failures (skips allowed); CI badge green on `main`.

---

### Phase 2 — Remove the broken and the fake (server surface)

Every item below is documented in `CRITICAL_REVIEW.md` §2–3 with file:line references valid at `8aa1e11`; re-locate by symbol name if lines have shifted.

**2.1 Delete the mangled/unreachable code in `server.py`:**
- Dead block after `return` inside `extract_audio_clip` (was lines 1587–1609).
- Truncated `re` statement terminating `extract_summary_clip` (was line 2151) → restore `return await _process()`.
- Duplicate nested `GOLDMINE_LEGACY_TOOLS` gate (was line 2156) → single gate.

**2.2 Fix the async breakage in `server.py`:** replace every `asyncio.run(...)` inside `async def` tools (`extract_speaker_reel`, `extract_dialogue`, `create_audiogram`) with `await ...`; make `extract_speaker_intro`, `extract_quote_clip`, `extract_cold_open` `async` and `await extract_audio_clip(...)`.

**2.3 Fix `walkie_talkie_pivot`:** highlights are dicts — use `h.get("reason","")`, `h.get("startTime")`, `h.get("endTime")`; drop the nonexistent `transcript_snippet` field.

**2.4 Remove façade tools.** Delete the MCP tools whose backing functions are stubs (`extract_topic_segment`, `extract_emotional_peaks`, `extract_disagreements`, `extract_data_claims`, `extract_question_answers`, `extract_summary_clip`) **and** the stub functions in `ai_enricher.py:653-660`, **unless** the Owner supplies working implementations from the Mac in Phase 0 — **[OWNER]** decides which, in writing, before this task runs. A tool that cannot succeed must not be registered.

**2.5 Delete or quarantine the legacy block** (`GOLDMINE_LEGACY_TOOLS` section): it contains `timeline_set` (`self` NameError), `generate_daily_briefing` (awaits a sync function with wrong args), and object-vs-dict mismatches throughout. Default action: delete the entire gated section. If the Owner wants any tool kept, it must be fixed and tested individually.

**2.6 Single episode-lookup helper.** Implement one `find_episode(podcast_title, episode_title)` (exact-match first, then unique-substring; ambiguous → error listing candidates) and use it in every tool. Remove the ~10 divergent copies.

**2.7 Mechanical fixes:** guard `get_catalogue_stats` division by zero; unify vibe thresholds into module constants used by both `find_podcast_by_vibe` and `find_episodes_by_vibe`; remove unused `_search_cache`; remove `recommend_episodes`' silent `audio_url` filter (return items without audio, flagged `"audio": false`).

**2.8 Repo-root cleanup.** Delete: `refactor_async.py`, `inject_referrals.py`, `debug_dates.py`, `test_hf.py`, `test_export.py`, `trial_prism.py`, `demo_extractor.py`, `verify_audio.mp3`, `verify_audio_trimmed.mp3`, `report.txt`, `bridge.log`, `scripts/temp.jsonl`, `data/universe.jsonl.bak`, `data/clips/*`, `data/*.log`. Extend `.gitignore` with `data/clips/`, `*.log`, `*.bak`, `*.mp3`, `*.mp4`, `data/lancedb_store/`, `*.voy`. Keep `scripts/` debug files only if the Owner objects to deletion — **[OWNER]** confirms the deletion list before this commit.

**Acceptance:** `python -m podcast_catalogue.server` starts and stays up on a machine with only core+mcp extras; a scripted MCP client (add `tests/test_server_tools.py`) calls `search_catalogue`, `get_podcast_details`, `get_episode_details`, `walkie_talkie_pivot`, `get_catalogue_stats` against a 3-show fixture file and asserts non-error responses; `grep -rn "asyncio.run(" podcast_catalogue/server.py` returns nothing.

---

### Phase 3 — Data integrity

**3.1 One configurable data root.** Add `podcast_catalogue/config.py` exposing `DATA_DIR` (env `GOLDMINE_DATA_DIR`, default `./data` relative to CWD). Replace every `os.path.join(os.path.dirname(__file__), "../data/...")` (`server.py`, `vector_store.py`, `prism_http.py`, `dj_triage.py`) with paths built from `config.DATA_DIR`.

**3.2 Atomic, non-lossy persistence.** In `DataStore`: write to `<file>.tmp` then `os.replace`; on load, copy unparseable lines to `<file>.quarantine.jsonl` with a stderr warning instead of dropping them; never auto-save on ingest without this path. Log counts loaded/quarantined.

**3.3 Purge fabricated fields.** One-off migration script `scripts/migrate_strip_fabricated.py` (committed, idempotent): for every record in the canonical JSONL, null any `applePodcastPage` matching `podcasts.apple.com/au/search?term=` (the `inject_referrals.py` pattern); count and report. **[OWNER]** runs it against the Mac's `universe.jsonl` and commits a cleaned, rights-cleared *sample* dataset (5–10 shows) as `data/sample_catalogue.jsonl` for tests/demo. The full corpus stays private.

**3.4 Honest provenance defaults.** In `server.py` loading: if an episode has AI enrichment but no `aiProvenance`, synthesize `{"modelName": "unknown", "humanReviewed": false}` so downstream consumers can never mistake unlabeled output for verified content.

**Acceptance:** `GOLDMINE_DATA_DIR=/tmp/gm pytest tests/test_store.py` (new) proves: atomic save, quarantine-not-drop, fabricated-link migration on a fixture containing one poisoned record.

---

### Phase 4 — Close the security surface

**4.1 FastAPI bridge (`prism_http.py`):** require `Authorization: Bearer $GOLDMINE_API_TOKEN` (middleware; 401 otherwise; refuse to start if env var unset); CORS → `allow_origins` from env `GOLDMINE_CORS_ORIGINS` (comma-sep, no wildcard-with-credentials), `allow_credentials=False` by default; `/api/v1/ingest` → allowlist: reject any URL whose host is not `www.abc.net.au` (env-extensible), and cap `content` payloads at 256 KB.

**4.2 `register_entity_correction`:** literal strings only — `re.escape` the pattern (reject inputs containing regex metacharacters with a clear error); append every accepted correction to `data/corrections_audit.log` (timestamp, pattern, replacement); cap registry size (1,000 entries) and pattern length (200 chars).

**4.3 Remove agent-directive output.** `get_dj_session_bundle`: delete the `SYSTEM_STATE_FLUSH` directive and "instruction" fields; return context data only.

**4.4 Network hygiene:** every `aiohttp` call in `server.py`/`prism_http.py` gets `timeout=aiohttp.ClientTimeout(total=30)` and the certifi SSL context already used elsewhere; cap `search_catalogue` query length (500 chars) and `limit` (50).

**Acceptance:** new `tests/test_security.py` asserts: 401 without token; ingest rejects `http://169.254.169.254/`; correction tool rejects `.*` and accepts a literal name; DJ bundle response contains no `directive`/`instruction` keys.

---

### Phase 5 — Consistency & test depth

**5.1 One schema at the boundary.** `DataStore.load_data` normalizes every record through `Podcast.model_validate` → `model_dump(by_alias=True)` so the store contains exactly one key convention (camelCase). Delete all `x.get("a") or x.get("a_b")` dual reads in `server.py` (grep for `") or ep.get("`, `") or hl.get("`, `") or episode.get("`). Records failing validation go to quarantine (Phase 3.2).

**5.2 Vector store:** in `index_episode`, delete-then-insert by `chunk_id` (or LanceDB `merge_insert`) so re-indexing is idempotent; fix the distance/result misalignment by zipping distances to IDs *before* filtering; reuse one DB connection per stage run.

**5.3 AI layer:** delete the dead first `EngagementSchema` (`ai_enricher.py:74`); single model-config source in `config.py` (`OLLAMA_MODEL`, `OLLAMA_URL`, `GEMINI_MODEL` env-driven) consumed by `ai_enricher.py`, `router.py`, `vector_store.py`; replace `datetime.utcnow()` with `datetime.now(timezone.utc)`; rename the `except Exception as re:` binding (`pipeline.py:547`) to `err`.

**5.4 Test floor:** minimum new coverage — store load/save/normalize (fixtures incl. bad lines), every registered MCP tool smoke-tested against `data/sample_catalogue.jsonl`, recommender ranking determinism, clipper filename/validation logic (no network). Target: ≥ 60 passing tests, 0 skips on Linux core.

**Acceptance:** `pytest -q` ≥ 60 passed; `grep -rn '") or ep.get("' podcast_catalogue/server.py` → empty; indexing the sample twice yields identical row counts.

---

### Phase 6 — True documentation & runnable demo

**6.1 Rewrite `README.md`** (Owner approves final text): what it is (one paragraph, no "Neural OS"), feature matrix marked ✅ working / 🚧 planned (nothing shipped may sit in 🚧), quickstart (clone → install → run MCP server on sample data → example Claude/MCP session), platform notes (core: any OS; transcription: Apple Silicon), architecture diagram of the real stages. Delete "Hardened v6.20", "zero-error", "sub-500ms", fictional ecosystem names. Rewrite `VISION.md` to a half-page roadmap or delete it.

**6.2 Ship the demo path:** `make demo` → starts the MCP server on `data/sample_catalogue.jsonl` and prints a copy-paste `claude mcp add` line; `docs/DEMO_SCRIPT.md` — a 5-minute stakeholder walkthrough (search → vibe discovery → trust report → clip extraction) with expected outputs and screenshots.

**6.3 Legal/housekeeping:** add `LICENSE` (MIT, matching pyproject); align version strings (pyproject = single source; remove `5.0.0`/`v6.20` variants); `CHANGELOG.md` started at the new baseline. **[OWNER]**: decide whether to `git filter-repo` the ~24 MB of historical data blobs (optional; do not let the Executor do this).

**Acceptance:** a fresh-machine run of the README quickstart, timed: clone → working MCP demo in ≤ 15 minutes with no undocumented steps. CI green. Repo clone size < 5 MB (excluding history if not rewritten).

---

### Phase 7 — Stakeholder package · **[OWNER-led; Executor drafts]**

**7.1 One-pager** (`docs/PITCH.md`): problem (catalogues invisible to agents; AI output untrusted in editorial settings), solution (provenance-anchored MCP engine, deployed on the customer's catalogue), demo proof-points with real metrics pulled from the corpus (shows, episodes, % transcribed, % enriched, clip latency), ask (scoped pilot).
**7.2 Rights memo** (`docs/RIGHTS.md`): plain-language statement that the ABC corpus is demonstration-only, not redistributed; product model = customer-hosted on customer content. **[OWNER]** reviews with a qualified adviser before any external use — the Executor must not present legal conclusions as settled.
**7.3 Pilot cost model** (`docs/COSTS.md`): per-episode pipeline cost (transcription minutes, LLM tokens local vs Gemini, storage) measured — not estimated — by running the pipeline on 10 sample episodes and recording actuals.
**7.4 Known-limitations register:** honest list (single-network parser, heuristic search, no auth beyond token, diarization licensing/HF gating). Stakeholders trust teams who know their gaps.

**Acceptance:** Owner can run the demo script end-to-end cold and present the one-pager without any claim the repo can't substantiate live.

---

## Definition of Done (whole plan)

- [ ] Fresh clone → install → import → tests green on Linux and macOS (CI-proven)
- [ ] MCP server runs on sample data; every registered tool returns valid output or a typed error; no façade tools remain
- [ ] Data writes atomic; no silent drops; fabricated fields purged; provenance always labeled
- [ ] HTTP surface token-authed, CORS sane, SSRF closed; corrections audited and literal-only
- [ ] README/feature matrix contains no claim a stakeholder could falsify in a live demo
- [ ] ≤ 15-minute cold-start demo; pitch, rights memo, and measured cost model in `docs/`

**Sequencing note:** Phases 0–1 are strictly ordered. Phases 2–5 may interleave at task granularity but respect their listed acceptance gates. Phases 6–7 last. Estimated effort at moderate-executor pace with Owner checkpoints: Phases 0–1 ≈ days; 2–5 ≈ 2–3 weeks; 6–7 ≈ 1 week.
