"""Central configuration for the podcast_catalogue package.

DATA_DIR is the single data root used by the MCP server, vector store,
HTTP bridge, and DJ triage. Override with the GOLDMINE_DATA_DIR environment
variable; the default is ./data relative to the current working directory.
"""
from __future__ import annotations

import os

DATA_DIR = os.environ.get("GOLDMINE_DATA_DIR", os.path.join(os.getcwd(), "data"))


def data_path(*parts: str) -> str:
    return os.path.join(DATA_DIR, *parts)


# --- AI model configuration (single source of truth) ---
# CRITICAL_REVIEW.md §3 found model names hardcoded in four places, none
# agreeing (gemma4 / qwen3.5 / qwen3:14b / "Qwen 3.5" in docs). These env-
# driven values are the only authority; modules must not hardcode their own.
OLLAMA_URL = os.environ.get("GOLDMINE_OLLAMA_URL", "http://localhost:11434")
OLLAMA_GENERATE_URL = f"{OLLAMA_URL}/api/generate"
OLLAMA_EMBED_URL = f"{OLLAMA_URL}/api/embed"
OLLAMA_MODEL = os.environ.get("GOLDMINE_OLLAMA_MODEL", "qwen3.5:latest")
GEMINI_MODEL = os.environ.get("GOLDMINE_GEMINI_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.environ.get("GOLDMINE_EMBED_MODEL", "nomic-embed-text")
