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

try:
    import voyager
    VOYAGER_AVAILABLE = True
except ImportError:
    voyager = None
    VOYAGER_AVAILABLE = False

from .config import OLLAMA_EMBED_URL, EMBED_MODEL

# Persistent storage paths
from .config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "lancedb_store")
VOYAGER_INDEX_PATH = os.path.join(DATA_DIR, "voyager_index.voy")
VOYAGER_MAP_PATH = os.path.join(DATA_DIR, "voyager_map.json")

# Shared state for Voyager index and ID mapping
_voyager_index = None
_voyager_map = []  # Index in list matches Voyager ID, value is LanceDB chunk_id


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


def _load_voyager():
    """Initializes or loads the Voyager index and ID map."""
    global _voyager_index, _voyager_map
    if not VOYAGER_AVAILABLE:
        return None, []

    if _voyager_index is not None:
        return _voyager_index, _voyager_map

    # Load mapping
    if os.path.exists(VOYAGER_MAP_PATH):
        try:
            with open(VOYAGER_MAP_PATH, "r") as f:
                _voyager_map = json.load(f)
        except Exception as e:
            print(f"    [ERR VOYAGER MAP] {e}")
            _voyager_map = []
    else:
        _voyager_map = []

    # Load or create index
    # Note: nomic-embed-text is 768 dimensions
    if os.path.exists(VOYAGER_INDEX_PATH):
        try:
            _voyager_index = voyager.Index.load(VOYAGER_INDEX_PATH)
        except Exception as e:
            print(f"    [ERR VOYAGER LOAD] {e}")
            _voyager_index = voyager.Index(voyager.Space.Cosine, num_dimensions=768)
    else:
        _voyager_index = voyager.Index(voyager.Space.Cosine, num_dimensions=768)

    return _voyager_index, _voyager_map


def _save_voyager():
    """Persists Voyager index and mapping to disk."""
    if _voyager_index is not None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _voyager_index.save(VOYAGER_INDEX_PATH)
        with open(VOYAGER_MAP_PATH, "w") as f:
            json.dump(_voyager_map, f)


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
    db,  # LanceDB connection — pass one per stage run; None opens a fresh one
    podcast_title: str,
    episode: Dict[str, Any]
) -> int:
    """
    Indexes a single episode into LanceDB (idempotently, keyed on chunk_id).
    Chunks the transcript (or description) and embeds each chunk.
    Returns the number of chunks indexed.
    """
    if not LANCEDB_AVAILABLE:
        return 0

    # Reuse the caller-provided connection; only open a fresh one as a
    # fallback (previously every episode opened its own connection).
    if db is None or not hasattr(db, "table_names"):
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
    
    # Also index guest info if available
    for guest in episode.get("guests", []):
        if guest.get("name"):
            text_parts.append(f"Guest: {guest['name']}")
        if guest.get("bio"):
            text_parts.append(guest["bio"])
    
    full_text = " ".join(text_parts)
    if not full_text or len(full_text) < 20:
        return 0
    
    chunks = chunk_text(full_text)
    data_to_insert = []

    for i, chunk in enumerate(chunks):
        chunk_id = hashlib.sha256(f"{podcast_title}:{ep_title}:{i}".encode()).hexdigest()[:16]

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
            "primary_genre": episode.get("primary_genre", ""),
            "is_popular": bool(episode.get("is_popular", False)),
            "entities": json.dumps(episode.get("entities", []))
        }
        data_to_insert.append(row)
        
    if not data_to_insert:
        return 0

    if table_name not in db.table_names():
        db.create_table(table_name, data=data_to_insert)
    else:
        # Idempotent upsert: delete any prior rows for these deterministic
        # chunk IDs before inserting, so re-indexing the same episode can
        # never accumulate duplicates (previously every re-index duplicated
        # every chunk until a manual rebuild).
        t = db.open_table(table_name)
        id_list = ", ".join(f"'{row['id']}'" for row in data_to_insert)
        try:
            t.delete(f"id IN ({id_list})")
        except Exception:
            pass  # table may predate the id column; insert proceeds regardless
        t.add(data_to_insert)
    
    # Sync with Voyager
    v_index, v_map = _load_voyager()
    if v_index is not None:
        import numpy as np
        vectors = np.array([row["vector"] for row in data_to_insert], dtype=np.float32)
        ids = [row["id"] for row in data_to_insert]
        
        # Voyager's add_items returns the first ID assigned
        v_index.add_items(vectors)
        v_map.extend(ids)
        _save_voyager()
        
    return len(data_to_insert)


async def sync_voyager():
    """Rebuilds the Voyager index from the ground up using LanceDB data."""
    if not LANCEDB_AVAILABLE or not VOYAGER_AVAILABLE:
        return False
    
    db = get_db_client()
    table = get_collection(db)
    if table is None:
        return False
    
    print("    [VOYAGER SYNC] Rebuilding index from LanceDB...")
    all_data = table.to_pandas()
    if all_data.empty:
        return False
        
    global _voyager_index, _voyager_map
    _voyager_index = voyager.Index(voyager.Space.Cosine, num_dimensions=768)
    _voyager_map = []
    
    import numpy as np
    vectors = np.array(all_data["vector"].tolist(), dtype=np.float32)
    ids = all_data["id"].tolist()
    
    _voyager_index.add_items(vectors)
    _voyager_map = ids
    _save_voyager()
    print(f"    [VOYAGER SYNC] Done. Indexed {len(ids)} chunks.")
    return True


async def semantic_search(
    session: aiohttp.ClientSession,
    table, # can be None, handled gracefully
    query: str,
    top_k: int = 5,
    genre: Optional[str] = None
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
    
    v_index, v_map = _load_voyager()
    results = []
    
    # Try Voyager first
    if v_index is not None and len(v_map) > 0:
        import numpy as np
        try:
            indices, distances = v_index.query(np.array(query_embedding, dtype=np.float32), k=top_k)
            # Fetch full metadata from LanceDB using mapped IDs
            matched_ids = [v_map[idx] for idx in indices]
            
            # Efficiently query LanceDB for the specific IDs
            # Note: LanceDB's `search` is for vectors. For metadata lookup, we use a filter or SQL.
            id_list_str = ", ".join([f"'{i}'" for i in matched_ids])
            rows = table.search(None).where(f"id IN ({id_list_str})").to_list()
            
            # Pair each ID with its distance BEFORE any filtering, so scores
            # stay attached to the right row even when IDs are missing from
            # LanceDB or removed by the genre filter (previously distances
            # were assigned by position against the filtered list).
            distance_by_id = {mid: float(d) for mid, d in zip(matched_ids, distances)}

            row_map = {row["id"]: row for row in rows}
            results = [row_map[mid] for mid in matched_ids if mid in row_map]

            if genre:
                results = [r for r in results if genre.lower() in r.get("primary_genre", "").lower()]

            for row in results:
                row["_distance"] = distance_by_id[row["id"]]
                
        except Exception as e:
            print(f"    [WARN VOYAGER SEARCH] {e}. Falling back to native search.")
            v_index = None # Trigger fallback below
            
    # Fallback to native LanceDB search
    if not results:
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
