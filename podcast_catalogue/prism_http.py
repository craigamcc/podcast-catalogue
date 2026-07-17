from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import aiohttp
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

# Import existing backend logic from server.py (via store)
from .server import store
try:
    from .server import semantic_search_episodes
except ImportError:
    semantic_search_episodes = None

from .recommender import calculate_jtbd_affinities
from .dj_triage import triage_service
from .catalogue import CatalogueBuilder, CatalogueConfig

REGIONAL_PULSE_FILE = os.path.join(os.path.dirname(__file__), "../data/regional_pulses.jsonl")

def get_latest_regional_pulse(region_id: str) -> Optional[Dict]:
    """Helper to retrieve the most recent master pulse for a region."""
    if not os.path.exists(REGIONAL_PULSE_FILE):
        return None
    
    latest = None
    try:
        with open(REGIONAL_PULSE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get("regionId") == region_id:
                        latest = data
                except:
                    continue
    except Exception as e:
        print(f"Error reading regional pulses: {e}")
    return latest


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
    url: Optional[str] = None
    content: Optional[str] = None
    deep_crawl: bool = True
    transcribe: bool = False

@app.post("/api/v1/ingest")
async def ingest_signal(req: IngestRequest, background_tasks: BackgroundTasks):
    """
    Trigger discovery and enrichment for a new signal.
    Supports URLs (automated crawl) or Markdown content (Snipd exports).
    """
    if req.content:
        # Snipd Reverse Ingestion path
        background_tasks.add_task(store.ingest_snipd_markdown, req.content)
        return {
            "status": "ingestion_triggered",
            "type": "snipd_markdown",
            "message": "Snipd intelligence ingestion activated. Processing highlights and transcript."
        }

    if not req.url:
        raise HTTPException(status_code=400, detail="Either 'url' or 'content' must be provided.")

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
    if semantic_search_episodes:
        try:
            results_json = await semantic_search_episodes(q, top_k=top_k)
            return json.loads(results_json)
        except Exception as e:
            print(f"Semantic Search Error: {e}")
            # Fallback to keyword search
    
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
    mode: str = "DEFAULT"

@app.post("/api/v1/dj/curate")
async def curate_dj_session(req: CurateRequest):
    """Triage Pipeline: Curate a personalized sequence of snips."""
    try:
        session = await triage_service.curate_session(prompt=req.prompt, mode=req.mode)
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/pulse/audio")
async def get_pulse_audio(region: str = "seqld", sub_region: Optional[str] = None):
    """
    Generate synthesized Pulse briefing audio. 
    Efficiency: Checks for a pre-computed Regional Master Pulse before falling back to expensive synthesis.
    Lens Filtering: If a sub_region is provided, prioritizes narrative shifts tagged with that location.
    """
    # 1. Check for Regional Master Pulse (The "Substrate" layer)
    master_pulse = get_latest_regional_pulse(region)
    
    if master_pulse:
        # Use the pre-computed summary
        region_name = region.upper()
        script = f"Good morning. This is your GoldMine Intelligence Pulse for {region_name}. "
        
        if sub_region:
            script += f"Targeting your local profile in {sub_region.title()}. "
            
        script += master_pulse.get("masterSummary", "")
        
        all_shifts = master_pulse.get("narrativeShifts", [])
        
        # 1a. Lens Filtering: Prioritize shifts with matching tags
        relevant_shifts = []
        if sub_region:
            sub_region_lower = sub_region.lower()
            relevant_shifts = [s for s in all_shifts if any(sub_region_lower in str(t).lower() for t in s.get("tags", []))]
        
        # Combine relevant first, then others, up to a limit
        other_shifts = [s for s in all_shifts if s not in relevant_shifts]
        final_shifts = (relevant_shifts + other_shifts)[:3]
        
        if final_shifts:
            if relevant_shifts:
                script += f" We have identified {len(relevant_shifts)} shifts directly impacting your area. "
            else:
                script += f" We are tracking {len(all_shifts)} key narrative shifts across the broader region. "
                
            for s in final_shifts:
                title = s.get("title", "")
                shift_desc = s.get("shift", s.get("rationale", ""))
                source = s.get("source", "unspecified sources")
                experts = s.get("experts", [])
                
                expert_mention = f" featuring insights from {', '.join(experts)}" if experts else ""
                script += f" Regarding {title}: {shift_desc}{expert_mention}. This was tracked in {source}. "
        
        script += "Stay sharp. End of briefing."
    else:
        # 2. Fallback: On-the-fly curation (Original logic)
        try:
            prompt = f"Daily Intelligence Briefing for {region}"
            if sub_region: prompt += f" and specifically {sub_region}"
            
            session = await triage_service.curate_session(prompt=prompt)
            script = f"Good morning. This is your situational GoldMine Intelligence Pulse for {region}. "
            snips = session.get("snips", [])
            if not snips:
                script += "Global signals are currently stable. PRISM is monitoring the network for new narrative shifts."
            else:
                script += f"Today's intelligence focuses on {len(snips)} key narrative shifts. "
                for snip in snips[:3]:
                    script += f"In {snip['podcastTitle']}, we're tracking a shift: {snip['rationale']}. "
            script += "Stay sharp. End of briefing."
        except Exception as e:
            script = f"PRISM Intelligence Pulse is active for {region}. Narrative shifts are being monitored. Stay sharp."
    
    
    # 2. Call TTS server (SoundScope)
    tts_url = "http://localhost:8001/tts"
    try:
        async with aiohttp.ClientSession() as client_session:
            payload = {
                "text": script,
                "language": "English",
                "speaker": "Ryan",
                "instruct": "Professional male broadcaster, warm baritone, confident and engaging"
            }
            async with client_session.post(tts_url, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    audio_url = data.get("audio_url")
                    
                    # Fetch the actual wav data from the TTS server
                    async with client_session.get(f"http://localhost:8001{audio_url}") as audio_resp:
                        if audio_resp.status == 200:
                            from fastapi.responses import Response
                            content = await audio_resp.read()
                            return Response(content=content, media_type="audio/wav")
    except Exception as e:
        print(f"TTS Synthesis Error: {e}")
        raise HTTPException(status_code=503, detail="TTS Engine is currently offline or loading.")
    
    raise HTTPException(status_code=500, detail="Briefing synthesis failed.")

@app.get("/api/v1/pulse/audio-script")
async def get_pulse_audio_script(region: str = "seqld", sub_region: Optional[str] = None):
    """
    Orientation Job: Generate a highly structured, 90-second TTS script from the regional pulse.
    Instead of synthesizing the audio directly, this returns the script payload so third-party
    DJ apps can use their own TTS models.
    """
    master_pulse = get_latest_regional_pulse(region)
    
    if master_pulse:
        region_name = region.upper()
        script = f"Good morning. This is your GoldMine Intelligence Pulse for {region_name}. "
        
        if sub_region:
            script += f"Targeting your local profile in {sub_region.title()}. "
            
        script += master_pulse.get("masterSummary", "")
        
        all_shifts = master_pulse.get("narrativeShifts", [])
        
        relevant_shifts = []
        if sub_region:
            sub_region_lower = sub_region.lower()
            relevant_shifts = [s for s in all_shifts if any(sub_region_lower in str(t).lower() for t in s.get("tags", []))]
        
        other_shifts = [s for s in all_shifts if s not in relevant_shifts]
        final_shifts = (relevant_shifts + other_shifts)[:3]
        
        if final_shifts:
            if relevant_shifts:
                script += f" We have identified {len(relevant_shifts)} shifts directly impacting your area. "
            else:
                script += f" We are tracking {len(all_shifts)} key narrative shifts across the broader region. "
                
            for s in final_shifts:
                title = s.get("title", "")
                shift_desc = s.get("shift", s.get("rationale", ""))
                
                # Enforce Provenance (Phase 2 requirement)
                source = s.get("source", "unspecified sources")
                script += f" According to {source}, regarding {title}: {shift_desc} "
        
        script += "Stay sharp. End of briefing."
        
        return {
            "status": "success",
            "region": region,
            "sub_region": sub_region,
            "tts_script": script,
            "estimated_duration_seconds": len(script.split()) * 0.4 # Roughly 150 words per minute
        }
        
    raise HTTPException(status_code=404, detail=f"No regional pulse available for {region} to generate script.")

@app.get("/api/v1/pulse/regional/{region_id}")
async def get_regional_pulse(region_id: str):
    """Retrieve the latest pre-computed regional briefing data."""
    pulse = get_latest_regional_pulse(region_id)
    if not pulse:
        raise HTTPException(status_code=404, detail=f"No master pulse found for region '{region_id}'.")
    return pulse


@app.get("/api/status")
async def get_catalogue_status():
    """Retrieve runtime catalog stats and show-by-show gap analysis."""
    total_shows = len(store.podcasts)
    total_episodes = 0
    episodes_with_transcript = 0
    episodes_with_audio = 0
    
    shows_list = []
    
    for p in store.podcasts.values():
        title = p.get("title", "Unknown")
        eps = p.get("episodes", [])
        num_eps = len(eps)
        total_episodes += num_eps
        
        show_transcripts = 0
        show_audio = 0
        
        for ep in eps:
            if ep.get("transcript"):
                show_transcripts += 1
            if ep.get("audioUrl") or ep.get("audio_url"):
                show_audio += 1
                
        episodes_with_transcript += show_transcripts
        episodes_with_audio += show_audio
        
        enriched_perc = (show_transcripts / num_eps * 100) if num_eps > 0 else 0
        audio_perc = (show_audio / num_eps * 100) if num_eps > 0 else 0
        
        # Simple gap priority
        authority = p.get("authorityScore") or p.get("authority_score") or 5.0
        is_popular = p.get("isPopular") or p.get("is_popular") or False
        pop_mult = 1.5 if is_popular else 1.0
        missing_eps = num_eps - show_transcripts
        priority = (missing_eps * authority * pop_mult) / 10.0
        
        shows_list.append({
            "title": title,
            "episodes": num_eps,
            "enriched_perc": enriched_perc,
            "has_rss": True, # ABC podcast pages are live RSS integrations
            "audio_perc": audio_perc,
            "priority": priority
        })
        
    shows_list.sort(key=lambda x: x["priority"], reverse=True)
    
    ai_saturation = (episodes_with_transcript / total_episodes * 100) if total_episodes > 0 else 0
    audio_saturation = (episodes_with_audio / total_episodes * 100) if total_episodes > 0 else 0
    
    return {
        "total_shows": total_shows,
        "total_episodes": total_episodes,
        "ai_saturation": ai_saturation,
        "audio_saturation": audio_saturation,
        "shows": shows_list
    }

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Serves the GoldMine Command Centre dashboard page."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "../dashboard.html")
    if not os.path.exists(dashboard_path):
        # Fallback to local working directory path if not relative to file
        dashboard_path = "dashboard.html"
    try:
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dashboard: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
