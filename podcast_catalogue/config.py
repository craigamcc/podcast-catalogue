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
