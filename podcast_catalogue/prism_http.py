from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import aiohttp
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

# Import existing backend logic from server.py (via store)
from .server import store, semantic_search_episodes
+from .recommender import calculate_jtbd_affinities
 from .dj_triage import triage_service
 from .catalogue import CatalogueBuilder, CatalogueConfig

app = FastAPI(
    title="PRISM Intelligence API",
    description="HTTP Bridge for the Prism Podcast Intelligence Hub. Enables browser-based discovery and AI integration.",
    version="5.0.0"
)

# Enable CORS for browser-based consumer apps (SoTA, Daisy, Sentinel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "PRISM Intelligence Engine",
        "version": "5.0.0",
        "stats": {
            "total_podcasts": len(store.podcasts),
            "total_episodes": len(store.episodes_index)
        }
    }

@app.get("/api/v1/shows")
async def list_shows(
    genre: Optional[str] = None, 
    min_rating: Optional[float] = None, 
    popular: bool = False
):
    """List podcasts with filtering support."""
    results = []
    for p in store.podcasts.values():
        if popular and not p.get("isPopular"):
            continue
        if min_rating and (p.get("averageRating") or 0) < min_rating:
            continue
        if genre:
            genres = [g.lower() for g in (p.get("appleGenres") or [])]
            if genre.lower() not in genres:
                continue
        
        results.append({
            "title": p.get("title"),
            "rating": p.get("averageRating"),
            "genres": p.get("appleGenres"),
            "hook": p.get("narrativeHook"),
            "imageUrl": p.get("imageUrl"),
            "episodes_count": len(p.get("episodes", []))
        })
    
    results.sort(key=lambda x: x.get("rating") or 0, reverse=True)
    return results

@app.get("/api/v1/shows/{title}")
async def get_show(title: str):
    """Get full details for a specific show."""
    p = store.get_details(title)
    if not p:
        raise HTTPException(status_code=404, detail=f"Podcast '{title}' not found.")
    
    # Inject JTBD affinities
    res = p.copy()
    res["jtbd_affinities"] = calculate_jtbd_affinities(p.get("vibe", {}))
    return res

class IngestRequest(BaseModel):
    url: str
    deep_crawl: bool = True
    transcribe: bool = False

@app.post("/api/v1/ingest")
async def ingest_signal(req: IngestRequest, background_tasks: BackgroundTasks):
    """
    Trigger discovery and enrichment for a new signal (Spotify/Apple/RSS).
    Runs asynchronously in the background.
    """
    builder = CatalogueBuilder()
    config = CatalogueConfig(
        sitemap_url=req.url, # Using URL as sitemap entry point
        filter_pattern=req.url,
        fetch_audio=req.deep_crawl,
        transcribe=req.transcribe,
        content_enrich=True,
        scout_enrich=False, # Breadth pass by default
        limit=1
    )
    
    background_tasks.add_task(builder.build, config)
    
    return {
        "status": "ingestion_triggered",
        "url": req.url,
        "message": "PRISM pipeline activated. High-fidelity enrichment in progress."
    }

@app.get("/api/v1/search")
async def search(q: str = Query(..., min_length=2), top_k: int = 5):
    """Semantic search across all episode transcripts and hooks."""
    try:
        results_json = await semantic_search_episodes(q, top_k=top_k)
        return json.loads(results_json)
    except Exception as e:
        # Fallback to keywork search if semantic fails
        return store.search(q)

@app.get("/api/v1/recommend")
async def recommend_shows(
    interests: Optional[List[str]] = Query(None),
    tone: Optional[str] = None,
    scenario: Optional[str] = None
):
    """Recommend shows based on interests and vibe."""
    # This delegates to the chat intent logic
    from .recommender import recommend
    results = recommend(
        store.podcasts,
        interests=interests,
        scenario=scenario,
        tone=tone,
        top_k=5
    )
    return results

class CurateRequest(BaseModel):
    prompt: Optional[str] = None
    history: Optional[List[str]] = []

@app.post("/api/v1/dj/curate")
async def curate_dj_session(req: CurateRequest):
    """Triage Pipeline: Curate a personalized sequence of snips."""
    try:
        session = await triage_service.curate_session(prompt=req.prompt)
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
