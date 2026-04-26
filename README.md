# 🏆 GoldMine: The Intelligence Hub

GoldMine is a high-performance, autonomous intelligence engine that transforms unstructured media into a high-fidelity semantic graph. Built for extreme narrative density, GoldMine powers the **Connect** and **Daisy** situational intelligence ecosystems.

---

## 🚀 2026 Semantic Tech Stack

| Component | Technology | Impact |
|:---|:---|:---|
| **Transcription** | MLX Whisper Large v3 Turbo | 809M parameter accuracy at bare-metal speeds. |
| **Local Scout** | **Qwen 3.5** (Default) | State-of-the-art JSON extraction and narrative logic. |
| **Cloud Strike** | **Gemini 1.5 Flash** | Zero-latency, zero-error "Deep Scout" intelligence extraction. |
| **Diarization** | Pyannote.audio 4.0 | Neural end-to-end speaker tracking with native STT alignment. |
| **Bridge** | **FastAPI + MCP** | Unified intelligence backend serving the GoldMine intelligence feed. |

---

## 🛠 Hardened v6.15 Features

1.  **Gold Run Pipeline**: A multi-stage intelligence pass (Download -> Transcribe -> Scout) designed for high-fidelity extraction.
2.  **Merge-on-Write Safety**: Filtered scouting passes now merge results into the existing catalogue instead of truncating it, protecting the 451-show foundation.
3.  **The Engagement Layer (v5.9)**: Moves beyond simple summarization to extract **Takeaways**, **Key Statistics**, **Verbatim Quotes**, and **Audiogram Blueprints**.
4.  **Stage-Only Execution**: Ability to run specific parts of the pipeline (e.g., `--stage scout-enrich`) to refine intelligence on existing data.

---

## 📦 Data Model: `podcasts_450_full_intelligence.jsonl`
The canonical "Golden Record" contains fully hydrated `Podcast` objects with:
- **Narrative Hooks & Vibes** (Tone, Complexity, Pace)
- **Semantic Chapters** (with auto-generated summaries)
- **Engagement Layer**: Verbatim quotes, stats, andProvocative social posts.
- **Audio Context**: Digitally extracted transcripts with timestamped segments.

---

## 🎮 Operations

### ⛏️ The "Gold Run" (Full Strike)
Execute the complete end-to-end cycle for the entire network.
```bash
python3 -m podcast_catalogue.cli --input data/goldmine_alpha.jsonl --output data/goldmine_alpha.jsonl --deep-crawl --transcribe --scout-enrich --provider gemini --force
```

### 🎯 The "Flagship Scout" (Filtered)
Target specific high-value shows without clobbering the foundation.
```bash
python3 -m podcast_catalogue.cli --input data/goldmine_alpha.jsonl --stage scout-enrich --filter "Conversations|Mind|Health" --force
```

### 📡 Start the Intelligence Bridge (Port 8000)
```bash
python3 -m podcast_catalogue.server
```

---

## 🎯 Strategic Use Cases

GoldMine is designed to serve as the "Neural Backbone" for media organizations, enabling:

1.  **Agentic Access & Discovery**: Agents can search spoken content, auto-generate summaries, and create "related listening" bundles tied to breaking news.
2.  **Generative Augmentation**: Automated assembly of "Bonus Segments" or briefings by remixing the existing catalogue.
3.  **Production Monitoring**: Real-time monitoring of new episodes to auto-produce show notes, social assets, and SEO metadata.
4.  **Living Knowledge Base**: A structured, semantic repository that agents can remix and repurpose at scale without manual effort.
5.  **Video as First-Class Data**: Querying via DAM metadata and transcripts to generate clip reels and video briefs.
6.  **Content Creation Flywheel**: Instantly surfacing B-roll and suggesting edits for promo versions tailored to different audiences.
7.  **Headless Unlock**: An API-first surface (FastAPI + MCP) that agents can call directly for any media intelligence task.
8.  **Dynamic Live Blog Enrichment**: Auto-enriching live blogs with fresh clips, archive context, and fact-checks.
9.  **Human-in-the-Loop Scrutiny**: "Machine-speed" grunt work that flags discrepancies for editors, ensuring high-fidelity reporting with less manual overhead.
10. **Personalization at Scale**: Automated generation of audience-specific versions (e.g., simplified for younger viewers or localized for different regions) without additional staff.

---

## 🗺 Roadmap

- [x] **Phase 1: Hardening** - Multi-stage pipeline, engagement layer, and semantic search.
- [ ] **Phase 2: Multimodal Expansion** - Integration of Video/DAM data and multimodal reasoning (Gemini 1.5 Pro).
- [ ] **Phase 3: Generative Assembly** - Automated "Remix" service for creating new media assets from the catalogue.
- [ ] **Phase 4: Global Agentic Bridge** - Full MCP standardization for seamless integration into any AI ecosystem.

---

## 🏗 Architecture

```
podcast_catalogue/
├── cli.py            # GoldMine Commander (Unified CLI)
├── server.py         # FastAPI + MCP Intelligence Bridge
├── ai_enricher.py    # Scout Logic (Qwen/Gemini Integration)
├── pipeline.py       # Multi-Stage Orchestration Logic
├── models.py         # GoldMine Core Ontology (Pydantic)
```

---

*Powered by GoldMine & MLX.*
