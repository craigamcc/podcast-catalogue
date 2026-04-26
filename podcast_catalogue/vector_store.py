"""
Vector Store for Podcast Catalogue.
Uses LanceDB for local persistent vector storage and Ollama's nomic-embed-text for embeddings.
Degrades gracefully if LanceDB is unavailable.
"""
from __future__ import annotations

import json
import os
import hashlib
from typing import List, Dict, Any, Optional

import aiohttp

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    lancedb = None
    LANCEDB_AVAILABLE = False

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"

# Persistent LanceDB storage next to data files
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/lancedb_store")


def get_db_client():
    """Returns a persistent LanceDB connection, or None if unavailable."""
    if not LANCEDB_AVAILABLE:
        return None
    os.makedirs(DB_PATH, exist_ok=True)
    return lancedb.connect(DB_PATH)


def get_collection(db):
    """Gets or creates the episodes table, or None if unavailable."""
    if db is None:
        return None
    table_name = "podcast_episodes"
    if table_name in db.table_names():
        return db.open_table(table_name)
    else:
        # Schema will be inferred dynamically on first add
        return None


async def embed_text(session: aiohttp.ClientSession, text: str) -> List[float]:
    """Embeds a single text string using Ollama's nomic-embed-text model."""
    payload = {
        "model": EMBED_MODEL,
        "input": text
    }
    try:
        async with session.post(OLLAMA_EMBED_URL, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                embeddings = data.get("embeddings", [])
                if embeddings:
                    return embeddings[0]
    except Exception as e:
        print(f"    [ERR EMBED] {e}")
    return []


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Splits text into overlapping chunks by word count."""
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap
    return chunks


async def index_episode(
    session: aiohttp.ClientSession,
    table,  # Might be None if it hasn't been created yet
    podcast_title: str,
    episode: Dict[str, Any]
) -> int:
    """
    Indexes a single episode into LanceDB.
    Chunks the transcript (or description) and embeds each chunk.
    Returns the number of chunks indexed.
    """
    if not LANCEDB_AVAILABLE:
        return 0
        
    db = get_db_client()
    if db is None:
        return 0
        
    table_name = "podcast_episodes"
    
    ep_title = episode.get("title", "Unknown")
    
    # Build the text to embed: prefer transcript, fallback to description + hook
    text_parts = []
    if episode.get("transcript"):
        text_parts.append(episode["transcript"])
    else:
        if episode.get("description"):
            text_parts.append(episode["description"])
        if episode.get("narrativeHook"):
            text_parts.append(episode["narrativeHook"])
    
    full_text = " ".join(text_parts)
    if not full_text or len(full_text) < 20:
        return 0
    
    chunks = chunk_text(full_text)
    data_to_insert = []
    
    # If the table exists, we want to fetch the existing IDs to avoid duplicates
    existing_ids = set()
    if table_name in db.table_names():
        table = db.open_table(table_name)
        # Using a simple scan/search to get IDs. A more efficient way is to rely on Lance's merge/upsert operations if available.
        # For simplicity, we just won't deduplicate at the chunk level natively without a primary key index,
        # but LanceDB strongly encourages upserts. Let's do simple insertions.
    
    for i, chunk in enumerate(chunks):
        chunk_id = hashlib.sha256(f"{podcast_title}:{ep_title}:{i}".encode()).hexdigest()[:16]
        
        # In a real production system, you'd do a batch filter for existing chunk_ids.
        
        embedding = await embed_text(session, chunk)
        if not embedding:
            continue
        
        row = {
            "id": chunk_id,
            "vector": embedding,
            "text": chunk,
            "podcast_title": podcast_title,
            "episode_title": ep_title,
            "chunk_index": i,
            "audio_url": episode.get("audioUrl", ""),
            "entities": json.dumps(episode.get("entities", []))
        }
        data_to_insert.append(row)
        
    if not data_to_insert:
        return 0
        
    if table_name not in db.table_names():
        db.create_table(table_name, data=data_to_insert)
    else:
        t = db.open_table(table_name)
        t.add(data_to_insert)
        
    return len(data_to_insert)


async def semantic_search(
    session: aiohttp.ClientSession,
    table, # can be None, handled gracefully
    query: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Semantic search across all indexed episodes.
    Returns ranked results with metadata.
    """
    if not LANCEDB_AVAILABLE:
        return []
    
    db = get_db_client()
    table_name = "podcast_episodes"
    if db is None or table_name not in db.table_names():
        return []
        
    table = db.open_table(table_name)
    
    query_embedding = await embed_text(session, query)
    if not query_embedding:
        return []
    
    results = table.search(query_embedding).limit(top_k).to_list()
    
    matches = []
    for row in results:
        matches.append({
            "podcast_title": row.get("podcast_title", ""),
            "episode_title": row.get("episode_title", ""),
            "audio_url": row.get("audio_url", ""),
            "text_snippet": row.get("text", "")[:200] + "...",
            "relevance_score": round(1.0 - row.get("_distance", 0), 4),
            "entities": json.loads(row.get("entities", "[]"))
        })
    
    return matches


async def find_similar(
    session: aiohttp.ClientSession,
    table,
    episode_text: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Find episodes similar to a given episode's text.
    """
    return await semantic_search(session, table, episode_text, top_k=top_k)
