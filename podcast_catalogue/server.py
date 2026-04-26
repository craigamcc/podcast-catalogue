from __future__ import annotations

import json
import os
import sys
import hashlib
from typing import List, Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Initialize FastMCP Server
mcp = FastMCP("Podcast Catalogue")


# Try enriched data first, fallback to basic
UNIVERSE_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/universe.jsonl")
FULL_INTELLIGENCE_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/podcasts_450_full_intelligence.jsonl")
ENRICHED_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/podcasts_enriched.jsonl")
BASIC_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/podcasts.jsonl")

if os.path.exists(UNIVERSE_DATA_FILE):
    DATA_FILE = UNIVERSE_DATA_FILE
elif os.path.exists(FULL_INTELLIGENCE_DATA_FILE):
    DATA_FILE = FULL_INTELLIGENCE_DATA_FILE
else:
    DATA_FILE = ENRICHED_DATA_FILE if os.path.exists(ENRICHED_DATA_FILE) else BASIC_DATA_FILE

# --- In-Memory Data Store ---
class DataStore:
    def __init__(self):
        self.podcasts: Dict[str, Dict[str, Any]] = {}
        self.episodes_index: List[Dict[str, Any]] = [] # For semantic/text search
        self.episodes_by_id: Dict[str, Dict[str, Any]] = {} # Unique ID mapping

    def load_data(self, path: str = DATA_FILE):
        if not os.path.exists(path):
            print(f"Warning: Data file not found at {path}", file=sys.stderr)
            return

        print(f"Loading GoldMine catalogue from {path}...", file=sys.stderr)
        count = 0
        
        # Single-pass diagnostic counters
        stats = {"dated": 0, "transcript": 0, "engagement": 0, "entities": 0, "guests": 0, "vibe": 0, "show_vibe": 0}
        
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    title = data.get("title")
                    if not title: continue
                    
                    self.podcasts[title.lower()] = data
                    count += 1
                    
                    if data.get("vibe") and any(data["vibe"].values()):
                        stats["show_vibe"] += 1
                        
                    for ep in data.get("episodes", []):
                        ep_title = ep.get("title")
                        ep_id = hashlib.md5(f"{title}:{ep_title}".encode()).hexdigest()[:12]
                        
                        # Pre-extract common search fields
                        transcript = ep.get("transcript", "")
                        engagement = ep.get("engagement") or {}
                        entities = ep.get("entities", [])
                        guests = ep.get("guests", [])
                        vibe = ep.get("vibe", {})
                        
                        # Update stats
                        if ep.get("publishedAt"): stats["dated"] += 1
                        if len(transcript) > 50: stats["transcript"] += 1
                        if engagement: stats["engagement"] += 1
                        if entities: stats["entities"] += 1
                        if guests: stats["guests"] += 1
                        if vibe and any(vibe.values()): stats["vibe"] += 1
                        
                        episode_data = {
                            "id": ep_id,
                            "podcast_title": title,
                            "title": ep_title,
                            "description": ep.get("description", ""),
                            "publishedAt": ep.get("publishedAt", ""),
                            "transcript": transcript,
                            "hook": ep.get("narrativeHook") or ep.get("description", ""),
                            "entities": entities,
                            "guests": guests,
                            "segments": ep.get("segments", []),
                            "chapters": ep.get("chapters", []),
                            "highlights": ep.get("highlights", []),
                            "audio_url": ep.get("audioUrl") or ep.get("audio_url", ""),
                            "vibe": vibe,
                            "engagement": engagement,
                            "apple_podcast_page": data.get("applePodcastPage")
                        }
                        self.episodes_index.append(episode_data)
                        self.episodes_by_id[ep_id] = episode_data
                except Exception as e:
                    continue
        
        print(f"Loaded {count} shows and {len(self.episodes_index)} episodes.", file=sys.stderr)
        print(f"  Dates: {stats['dated']} | Transcripts: {stats['transcript']} | Vibe: {stats['vibe']} | Show Vibe: {stats['show_vibe']}", file=sys.stderr)


    def search(self, query: str) -> List[Dict[str, Any]]:
        """Simple keyword search."""
        query = query.lower()
        results = []
        for p in self.podcasts.values():
            if query in p.get("title", "").lower() or query in p.get("description", "").lower():
                # Return summary only
                results.append({
                    "title": p.get("title"),
                    "host": p.get("hostInformation"),
                    "episodes_count": len(p.get("episodes", [])),
                    "targetAudience": p.get("targetAudience"),
                    "recommendationScenarios": p.get("recommendationScenarios"),
                    "vibe": p.get("vibe"),
                    "apple_podcast_page": p.get("applePodcastPage"),
                    "description": p.get("description", "")[:200] + "..."
                })
        return results[:10] # Limit to 10

    def get_details(self, title: str) -> Optional[Dict[str, Any]]:
        return self.podcasts.get(title.lower())

# Global Store
store = DataStore()
store.load_data()

# --- Resources ---

@mcp.resource("ui://podcast-app")
def get_podcast_app_ui() -> str:
    """Returns the Industrial-Noir Podcast Player UI."""
    ui_path = os.path.join(os.path.dirname(__file__), "resources/podcast_app.html")
    if os.path.exists(ui_path):
        with open(ui_path, "r", encoding="utf-8") as f:
            return f.read()
    return "UI Resource Not Found"

def parse_duration_to_minutes(dur_str: str) -> Optional[float]:
    """Helper to convert 'HH:MM:SS' or 'MM:SS' to minutes."""
    if not dur_str or not isinstance(dur_str, str):
        return None
    try:
        parts = dur_str.split(':')
        if len(parts) == 3: # HH:MM:SS
            return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60
        elif len(parts) == 2: # MM:SS
            return int(parts[0]) + int(parts[1]) / 60
        return float(dur_str) / 60 # Assume seconds if just a number string
    except:
        return None

def wrap_with_ui(results: Any) -> Any:
    """Wraps tool results with MCP App UI metadata."""
    return {
        "content": [{"type": "text", "text": json.dumps(results, indent=2, default=str)}],
        "_meta": {
            "ui": {
                "resourceUri": "ui://podcast-app"
            }
        }
    }

async def async_resolve_audio(ep: Dict[str, Any]):
    """Live-resolves audio URL for an episode if missing."""
    audio_url = ep.get("audio_url") or ep.get("audioUrl")
    if not audio_url and ep.get("url"):
        try:
            from .parser import parse_episode_page
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(ep["url"], timeout=2) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        ep_data = parse_episode_page(html)
                        if ep_data:
                            new_url = ep_data.get("audio_url")
                            ep["audio_url"] = new_url
        except:
            pass

_search_cache = {}

@mcp.tool()
async def search_catalogue(query: str, limit: int = 10) -> Any:
    """
    Search the entire ABC podcast catalogue by topic, guest, keyword, or show name.
    Returns relevant results with explanations and playable links.
    """
    global _search_cache
    if query in _search_cache:
        return _search_cache[query]

    query_lower = query.lower()
    
    # TOPIC EXPANSION: Broaden keywords to catch more content
    synonyms = {
        "ai": ["artificial intelligence", "machine learning", "automation", "tech", "algorithm"],
        "innovation": ["technology", "strategy", "future", "digital", "research"],
        "journalism": ["media", "news", "reporting", "investigation", "press"],
        "politics": ["government", "election", "policy", "parliament"],
        "climate": ["environment", "warming", "sustainability", "energy"]
    }
    
    expanded_queries = [query_lower]
    if query_lower in synonyms:
        expanded_queries.extend(synonyms[query_lower])

    scored_results = []
    import re
    
    for ep in store.episodes_index:
        score = 0
        reasons = []
        
        # Check all expanded queries
        for q in expanded_queries:
            q_regex = re.compile(rf'\b{re.escape(q)}\b')
            is_short = len(q) <= 3
            
            # Title match
            title = (ep.get("title") or "").lower()
            if q == title:
                score += 20
                reasons.append(f"exact title match for '{q}'")
            elif q in title:
                if not is_short or q_regex.search(title):
                    score += 10
                    reasons.append(f"title match for '{q}'")
            
            # Show/Genre match
            show = (ep.get("podcast_title") or "").lower()
            genre = (ep.get("genre") or "").lower()
            if q in show or q in genre:
                score += 6
                reasons.append(f"from related show/genre: {show or genre}")
                
            # Description/Takeaway
            desc = (ep.get("description") or "").lower()
            eng = ep.get("engagement") or {}
            takeaway = (eng.get("takeaway") or "").lower()
            if q in desc or q in takeaway:
                if not is_short or q_regex.search(desc) or q_regex.search(takeaway):
                    score += 8
                    reasons.append(f"topic '{q}' mentioned in description")

            # Transcript (Broadest)
            transcript = (ep.get("transcript") or "").lower()
            if q in transcript:
                if not is_short or q_regex.search(transcript):
                    score += 4
                    reasons.append(f"discussed in transcript")
            
            if score > 0: break # Found a match for this episode, move to next

        if score > 0:
            scored_results.append((score, reasons, ep))
    
    scored_results.sort(key=lambda x: (-x[0], x[2].get("publishedAt", "") or ""))
    
    # Live Media Bridge: Resolve audio for top matches
    import asyncio
    top_picks = [x[2] for x in scored_results[:5]]
    await asyncio.gather(*(async_resolve_audio(ep) for ep in top_picks))

    results = []
    for score, reasons, ep in scored_results[:limit]:
        audio_url = ep.get("audio_url") or ep.get("audioUrl")
        results.append({
            "relevance_score": score,
            "reason": "; ".join(reasons),
            "podcast_title": ep.get("podcast_title"),
            "episode_title": ep.get("title"),
            "publishedAt": ep.get("publishedAt"),
            "hook": ep.get("hook") or "No narrative hook available.",
            "audio_url": audio_url,
            "listen_link": f"[Play Episode]({audio_url})" if audio_url else f"[Open on ABC Listen]({ep.get('url')})",
            "engagement": ep.get("engagement")
        })
    
    if not results:
        # Suggested shows if no episodes found
        show_suggestions = {
            "ai": ["Future Tense", "Download This Show", "Big Ideas"],
            "journalism": ["Media Watch", "Background Briefing", "Late Night Live"],
            "innovation": ["The Money", "Future Tense", "Science Friction"]
        }
        suggestion = show_suggestions.get(query_lower, ["Future Tense", "Background Briefing"])
        return json.dumps({
            "results": [], 
            "suggestion": f"No direct episode matches for '{query}'. However, these shows often cover this topic: {', '.join(suggestion)}. Try searching for the show name directly."
        }, indent=2)

    output = json.dumps(results, indent=2, default=str)
    _search_cache[query] = output
    return output


@mcp.tool()
def get_catalogue_context() -> Any:
    """
    Returns the scope and data coverage of the ABC podcast catalogue.
    Includes count of episodes with transcripts, dates, vibes, and engagement takeaways.
    """
    total_eps = len(store.episodes_index)
    if total_eps == 0:
        return json.dumps({"error": "Catalogue is empty."}, indent=2)

    eps_dated = sum(1 for e in store.episodes_index if e.get("publishedAt"))
    eps_transcript = sum(1 for e in store.episodes_index if e.get("transcript"))
    eps_engagement = sum(1 for e in store.episodes_index if e.get("engagement"))
    eps_entities = sum(1 for e in store.episodes_index if e.get("entities"))
    eps_guests = sum(1 for e in store.episodes_index if e.get("guests"))
    eps_vibe = sum(1 for e in store.episodes_index if e.get("vibe") and any(e["vibe"].values()))
    eps_audio = sum(1 for e in store.episodes_index if e.get("audio_url"))
    shows_vibe = sum(1 for p in store.podcasts.values() if p.get("vibe") and any(p["vibe"].values()))
    
    dates = sorted([e["publishedAt"] for e in store.episodes_index if e.get("publishedAt")])
    date_range = f"{dates[0][:10]} to {dates[-1][:10]}" if dates else "unknown"
    
    # Popular shows
    popular = [p["title"] for p in store.podcasts.values() if p.get("isPopular")]
    
    return json.dumps({
        "catalogue_scope": {
            "total_shows": len(store.podcasts),
            "total_episodes": total_eps,
            "date_range": date_range,
            "network": "ABC (Australian Broadcasting Corporation)"
        },
        "data_coverage": {
            "episodes_with_dates": f"{eps_dated}/{total_eps}",
            "episodes_with_transcripts": f"{eps_transcript}/{total_eps}",
            "episodes_with_engagement": f"{eps_engagement}/{total_eps}",
            "episodes_with_entities": f"{eps_entities}/{total_eps}",
            "episodes_with_guests": f"{eps_guests}/{total_eps}",
            "episodes_with_vibe": f"{eps_vibe}/{total_eps}",
            "episodes_with_audio": f"{eps_audio}/{total_eps}",
            "shows_with_vibe": f"{shows_vibe}/{len(store.podcasts)}"
        },
        "best_tools_for": {
            "topic_search": "search_catalogue",
            "whats_new": "get_recent_episodes",
            "guest_lookup": "search_catalogue",
            "mood_discovery": "find_podcast_by_vibe or recommend_episodes(mood=...)",
            "show_details": "get_podcast_details"
        },
        "popular_shows": popular[:10],
        "limitations": [
            f"Only {eps_transcript} of {total_eps} episodes have transcripts — transcript search coverage is partial",
            "Semantic/vector search is not available (requires LanceDB)" if not eps_entities else None,
            f"Guest profiles exist for {eps_guests} episodes" if eps_guests > 0 else "Guest profiles are still being populated"
        ]
    }, indent=2)

@mcp.tool()
def get_episode_details(podcast_title: str, episode_title: str) -> Any:
    """
    Get full structured metadata for a specific episode.
    Returns transcript, chapters, guests, entities, vibe, and engagement data.
    """
    p = store.get_details(podcast_title)
    if not p:
        return json.dumps({"error": f"Podcast '{podcast_title}' not found."}, indent=2)
    
    episode = None
    ep_lower = episode_title.lower()
    for ep in p.get("episodes", []):
        if ep_lower == ep.get("title", "").lower() or ep_lower in ep.get("title", "").lower():
            episode = ep
            break
            
    if not episode:
        return json.dumps({"error": f"Episode '{episode_title}' not found in '{podcast_title}'."}, indent=2)
        
    return json.dumps(episode, indent=2, default=str)

@mcp.tool()
async def play_episode(podcast_title: str, episode_title: str) -> Any:
    """
    Get the playable audio URL for an episode.
    Use this when the user wants to listen to a specific episode.
    """
    p = store.get_details(podcast_title)
    if not p:
        return f"Podcast '{podcast_title}' not found."
    
    episode = None
    ep_lower = episode_title.lower()
    for ep in p.get("episodes", []):
        if ep_lower == ep.get("title", "").lower() or ep_lower in ep.get("title", "").lower():
            episode = ep
            break
            
    if not episode:
        return f"Episode '{episode_title}' not found in '{podcast_title}'."
        
    audio_url = episode.get("audioUrl") or episode.get("audio_url")
    
    # DYNAMIC MEDIA BRIDGE: If URL is null, try to fetch it live from the episode page
    if not audio_url and episode.get("url"):
        try:
            from .parser import parse_episode_page
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(episode["url"]) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        ep_data = parse_episode_page(html)
                        if ep_data:
                            audio_url = ep_data.get("audio_url")
                            # Update index for this session
                            episode["audio_url"] = audio_url
        except Exception as e:
            print(f"Media Bridge failed: {e}")

    if not audio_url:
        return f"No audio URL available for '{episode_title}'. The ABC Listen page doesn't have a direct stream link yet."
        
    return wrap_with_ui({"audio_url": audio_url, "title": episode.get("title"), "podcast": podcast_title})



@mcp.tool()
def get_podcast_details(title: str) -> Any:
    """
    Get full details for a specific podcast, including episode list, vibe, and narrative hook.
    Use the exact title from search results.
    """
    p = store.get_details(title)
    if not p:
        return f"Podcast '{title}' not found."
    return wrap_with_ui(p)

@mcp.tool()
def find_podcast_by_vibe(tone: Optional[str] = None, complexity: Optional[str] = None) -> Any:
    """
    Find podcasts matching a specific Vibe.
    Args:
        tone: e.g. "Inspirational", "Humorous", "Dark"
        complexity: "Simple" (<0.3), "Medium" (0.3-0.7), "Deep" (>0.7)
    """
    matches = []
    for p in store.podcasts.values():
        vibe = p.get("vibe", {})
        
        # Heuristic fallback if AI vibe is missing
        if not vibe:
            desc = p.get("description", "").lower()
            if tone and tone.lower() in desc:
                vibe = {"tone": [tone], "complexity": 0.5, "heuristic": True}
        
        if not vibe: continue
        
        match_tone = True
        tone_val = vibe.get("tone", "")
        if tone:
            tone_lower = tone.lower()
            if isinstance(tone_val, list):
                if not any(tone_lower in str(t).lower() for t in tone_val): match_tone = False
            elif tone_lower not in str(tone_val).lower():
                match_tone = False
            
        match_complex = True
        if complexity:
            c = vibe.get("complexity", 0.5)
            if complexity == "Simple" and c > 0.3: match_complex = False
            if complexity == "Medium" and (c <= 0.3 or c >= 0.7): match_complex = False
            if complexity == "Deep" and c < 0.7: match_complex = False
        
        if match_tone and match_complex:
             matches.append({
            "title": p["title"],
                 "hook": p.get("narrativeHook") or p.get("description", "")[:100],
                 "vibe": vibe
             })
             
    return json.dumps(matches[:10], indent=2)

@mcp.tool()
async def get_recent_episodes(show: Optional[str] = None, limit: int = 5) -> Any:
    """
    Get the most recently published episodes across the entire catalogue, or filtered to a specific show.
    Returns episode title, podcast title, publish date, narrative hook, and playable audio URL.
    Args:
        limit: Number of episodes to return (default 5)
        show: Optional show name to filter by (partial match supported)
    """
    episodes = store.episodes_index
    
    # Filter by show if specified
    if show:
        show_lower = show.lower()
        episodes = [ep for ep in episodes if show_lower in (ep.get("podcast_title") or "").lower()]
        if not episodes:
            return json.dumps({
                "results": [],
                "suggestion": f"No show matching '{show}' found. Use search_catalogue to find show names."
            }, indent=2)
    
    # Sort by publishedAt descending
    sorted_eps = sorted(
        episodes,
        key=lambda x: x.get("publishedAt", "") or "",
        reverse=True
    )
    
    # Live Media Bridge: Resolve audio for top picks
    import asyncio
    top_picks = sorted_eps[:limit]
    await asyncio.gather(*(async_resolve_audio(ep) for ep in top_picks))

    results = []
    for ep in sorted_eps[:limit]:
        audio_url = ep.get("audio_url") or ep.get("audioUrl")
        results.append({
            "podcast_title": ep.get("podcast_title"),
            "episode_title": ep.get("title"),
            "publishedAt": ep.get("publishedAt"),
            "hook": ep.get("hook") or "No narrative hook available.",
            "audio_url": audio_url,
            "listen_link": f"[Play Episode]({audio_url})" if audio_url else f"[Open on ABC Listen]({ep.get('url')})",
            "vibe": ep.get("vibe"),
            "engagement": ep.get("engagement")
        })
    return json.dumps(results, indent=2, default=str)

@mcp.tool()
async def search_by_guest(guest_name: str) -> Any:
    """
    Search for episodes featuring a specific guest or contributor.
    Matches against guest profiles, entities, titles, descriptions, and transcripts.
    """
    guest_lower = guest_name.lower()
    scored_matches = []
    for ep in store.episodes_index:
        score = 0
        reasons = []
        
        # 1. Structured Guest Profiles
        guests = ep.get("guests", [])
        for g in guests:
            g_name = (g.get("name", "") if isinstance(g, dict) else str(g)).lower()
            if guest_lower in g_name:
                score += 20
                reasons.append("verified guest profile")
                break
        
        # 2. Key Entities
        for e in ep.get("entities", []):
            e_str = (e.get("entity_name", "") if isinstance(e, dict) else str(e)).lower()
            if guest_lower in e_str:
                score += 15
                reasons.append("identified as key topic")
                break
        
        # 3. Transcript (Widest coverage for discovery)
        if guest_lower in (ep.get("transcript") or "").lower():
            score += 12
            reasons.append("mentioned in transcript (likely interviewee)")
        
        # 4. Title & Description
        if guest_lower in (ep.get("title") or "").lower():
            score += 8
            reasons.append("named in title")
        if guest_lower in (ep.get("description") or "").lower():
            score += 5
            reasons.append("mentioned in description")
        
        if score > 0:
            scored_matches.append((score, reasons, ep))
    
    scored_matches.sort(key=lambda x: (-x[0], x[2].get("publishedAt", "") or ""))
    
    # Live Media Bridge: Resolve audio for top matches
    import asyncio
    top_picks = [x[2] for x in scored_matches[:5]]
    await asyncio.gather(*(async_resolve_audio(ep) for ep in top_picks))

    results = []
    for score, reasons, ep in scored_matches[:10]:
        audio_url = ep.get("audio_url") or ep.get("audioUrl")
        results.append({
            "relevance_score": score,
            "reason": "; ".join(reasons),
            "podcast_title": ep.get("podcast_title"),
            "episode_title": ep.get("title"),
            "publishedAt": ep.get("publishedAt"),
            "audio_url": audio_url,
            "listen_link": f"[Play Episode]({audio_url})" if audio_url else f"[Open on ABC Listen]({ep.get('url')})"
        })
    
    if not results:
        return json.dumps({
            "results": [],
            "suggestion": f"No episodes found for '{guest_name}'. Try searching by first name or last name only.",
            "data_coverage": f"{sum(1 for e in store.episodes_index if e.get('guests'))} episodes have guest profiles"
        }, indent=2)
    return wrap_with_ui(results)

@mcp.tool()
def recommend_episodes(interests: str, mood: str = None, duration_max: int = None, limit: int = 5) -> Any:
    """
    Get personalized episode recommendations based on interests, mood, and available time.
    Scores episodes by topic relevance, vibe match, and recency.
    Each recommendation includes a rationale explaining why it was chosen.
    Args:
        interests: Topics or themes the user is interested in (e.g. "climate science", "true crime")
        mood: Optional mood preference (e.g. "light", "deep", "energetic", "calm")
        duration_max: Optional maximum episode duration in minutes
        limit: Number of recommendations to return (default 5)
    """
    interests_lower = interests.lower()
    mood_lower = (mood or "").lower()
    
    # Mood → vibe tone mapping
    mood_tones = {
        "light": ["light", "fun", "humorous", "casual", "entertaining"],
        "deep": ["deep", "analytical", "investigative", "complex", "intellectual"],
        "energetic": ["energetic", "fast", "passionate", "intense", "heated"],
        "calm": ["calm", "measured", "contemplative", "smooth", "relaxed", "flowing"],
        "informational": ["informational", "educational", "factual"],
    }
    target_tones = mood_tones.get(mood_lower, [mood_lower] if mood_lower else [])
    
    scored = []
    for ep in store.episodes_index:
        score = 0
        reasons = []
        
        # Topic relevance
        text = (str(ep.get("title") or "") + " " + str(ep.get("description") or "") + " " + str(ep.get("hook") or "")).lower()
        entities = [str(e).lower() for e in ep.get("entities", [])]
        
        if interests_lower in text:
            score += 10
            reasons.append(f"covers '{interests}'")
        if any(interests_lower in e for e in entities):
            score += 8
            reasons.append(f"tagged with '{interests}'")
        if interests_lower in (ep.get("transcript") or "").lower():
            score += 3
            reasons.append("discussed in transcript")
        
        if score == 0:
            continue  # Must have at least topic relevance
        
        # Vibe/mood match
        vibe = ep.get("vibe") or {}
        tone_str = str(vibe.get("tone", "")).lower()
        if target_tones and any(t in tone_str for t in target_tones):
            score += 5
            reasons.append(f"mood matches '{mood}'")
        elif mood_lower and not target_tones and mood_lower in tone_str:
            score += 5
            reasons.append(f"mood matches '{mood}'")
        
        # Duration filter
        if duration_max:
            dur_str = ep.get("duration") or ""
            dur_mins = parse_duration_to_minutes(dur_str)
            if dur_mins and dur_mins > duration_max:
                continue # Skip if too long
            if dur_mins:
                reasons.append(f"length: {int(dur_mins)} mins")
        
        # Engagement bonus
        eng = ep.get("engagement")
        if eng:
            score += 3
            why_listen = eng.get("whyListen", "")
            if why_listen:
                reasons.append(f"why listen: {why_listen[:80]}")
        
        # Recency bonus
        pub = ep.get("publishedAt", "") or ""
        if pub > "2025-01-01":
            score += 2
            reasons.append("recently published")
        
        scored.append((score, reasons, ep))
    
    scored.sort(key=lambda x: (-x[0], x[2].get("publishedAt", "") or ""))
    
    results = []
    for score, reasons, ep in scored[:limit]:
        results.append({
            "relevance_score": score,
            "reason": "; ".join(reasons),
            "podcast_title": ep.get("podcast_title"),
            "episode_title": ep.get("title"),
            "publishedAt": ep.get("publishedAt"),
            "hook": ep.get("hook") or "No hook available.",
            "audio_url": ep.get("audio_url") or ep.get("audioUrl"),
            "listen_link": f"[Play Episode]({ep.get('audio_url') or ep.get('audioUrl')})" if (ep.get("audio_url") or ep.get("audioUrl")) else None,
            "vibe": ep.get("vibe"),
            "engagement": ep.get("engagement"),
        })
    
    if not results:
        return json.dumps({
            "results": [],
            "suggestion": f"No episodes matching '{interests}' found. Try broader terms like 'science', 'politics', or 'health'."
        }, indent=2)
    return wrap_with_ui(results)

@mcp.tool()
def get_episode_chapters(podcast_title: str, episode_title: str) -> Any:
    """
    Get AI-generated chapters for a specific episode.
    Returns chapter list with titles, summaries, and timestamps for audio clipping.
    Use exact titles from search results.
    """
    p = store.get_details(podcast_title)
    if not p:
        return f"Podcast '{podcast_title}' not found."
    
    for ep in p.get("episodes", []):
        if ep.get("title", "").lower() == episode_title.lower():
            chapters = ep.get("chapters", [])
            if not chapters:
                return f"No chapters available for episode '{episode_title}'. Transcription with --ai-enrich may be required."
            return json.dumps({
                "episode_title": ep.get("title"),
                "audio_url": ep.get("audioUrl", ""),
                "chapters": chapters
            }, indent=2)
    
    return f"Episode '{episode_title}' not found in '{podcast_title}'."

# --- LEGACY GATING START ---
if os.environ.get("GOLDMINE_LEGACY_TOOLS", "0") == "1":



    
    @mcp.resource("podcasts://stats")
    def get_stats() -> Any:
        """Returns statistics about the podcast catalogue."""
        return f"Total Podcasts: {len(store.podcasts)}"
    
    
    # --- Phase 10: Conversational Service Tools ---
    
    import aiohttp
    import asyncio
    import ssl
    import certifi
    from .recommender import recommend
    from .router import classify_intent, format_conversational_response
    from .models import Podcast, Episode
    from .vector_store import get_db_client, get_collection, semantic_search, embed_text
    from .catalogue import CatalogueBuilder, CatalogueConfig
    from .exporter import export_jsonl
    from .reporter_adapter import generate_editorial_report
    
    # Conversation memory (lightweight, per session)
    _conversations: Dict[str, List[Dict[str, str]]] = {}
    
    # --- Search Configuration ---
    # Lazy-load LanceDB to avoid overhead if only listing shows
    _lancedb_client = None
    _lancedb_table = None
    
    def _get_vector_collection():
        global _lancedb_client, _lancedb_table
        if _lancedb_table is None:
            try:
                _lancedb_client = get_db_client()
                _lancedb_table = get_collection(_lancedb_client)
            except Exception as e:
                print(f"Warning: LanceDB not available: {e}", file=sys.stderr)
        return _lancedb_table
    
    
    @mcp.tool()
    async def chat(message: str, session_id: str = "default") -> Any:
        """
        Conversational entry point. Send a natural language message and get back
        podcast recommendations, search results, or answers to queries.
        Supports multi-turn context via session_id.
        """
        # Get or create conversation history
        if session_id not in _conversations:
            _conversations[session_id] = []
        history = _conversations[session_id]
    
        async def _process():
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                # 1. Classify intent
                intent_data = await classify_intent(session, message, history)
                intent = intent_data.get("intent", "search")
                params = intent_data.get("params", {})
                hint = intent_data.get("response_hint", "")
    
                # 2. Dispatch to engine
                results = []
                
                if intent == "recommend":
                    results = recommend(
                        store.podcasts,
                        interests=params.get("interests"),
                        scenario=params.get("scenario"),
                        tone=params.get("tone"),
                        pace=params.get("pace"),
                        max_complexity=params.get("max_complexity"),
                        genres=params.get("genres"),
                        top_k=5
                    )
                
                elif intent == "search":
                    keyword = params.get("keyword", message)
                    # Try semantic search first
                    collection = _get_vector_collection()
                    if collection and collection.count() > 0:
                        results = await semantic_search(session, collection, keyword, top_k=5)
                    else:
                        # Fallback to keyword search
                        results = store.search(keyword)
                
                elif intent == "query":
                    title = params.get("podcast_title", "")
                    if title:
                        p = store.get_details(title)
                        if p:
                            results = {
                                "title": p.get("title"),
                                "episodes": len(p.get("episodes", [])),
                                "rating": p.get("averageRating"),
                                "vibe": p.get("vibe"),
                                "genres": p.get("appleGenres"),
                                "hook": p.get("narrativeHook")
                            }
                        else:
                            results = {"error": f"Show '{title}' not found."}
                    else:
                        results = store.search(message)
                
                elif intent == "clip":
                    keyword = params.get("keyword", message)
                    results = []
                    kw = keyword.lower()
                    for item in store.episodes_index:
                        segs = [s for s in item.get("segments", []) if kw in s.get("text", "").lower()]
                        if segs:
                            results.append({
                                "podcast_title": item["podcast_title"],
                                "episode_title": item["title"],
                                "audio_url": item.get("audio_url", ""),
                                "clips": segs[:3]
                            })
                        if len(results) >= 3:
                            break
                
                elif intent == "similar":
                    collection = _get_vector_collection()
                    if collection and collection.count() > 0:
                        # Use the last recommendation or search result as seed
                        seed_text = params.get("keyword", message)
                        results = await semantic_search(session, collection, seed_text, top_k=5)
                    else:
                        results = store.search(message)
                
                # 3. Format response
                response_text = await format_conversational_response(session, intent, results, hint)
                
                # 4. Store in conversation history
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": response_text})
                
                # Keep history manageable
                if len(history) > 20:
                    _conversations[session_id] = history[-10:]
                
                return json.dumps({
                    "response": response_text,
                    "intent": intent,
                    "results": results if isinstance(results, list) else [results],
                    "session_id": session_id
                }, indent=2, default=str)
    
        return await _process()
    
    
    @mcp.tool()
    def list_shows(genre: Optional[str] = None, min_rating: Optional[float] = None, popular_only: bool = False) -> Any:
        """
        List shows with optional filters.
        Args:
            genre: Filter by Apple genre (e.g. "Science", "Society & Culture")
            min_rating: Minimum average rating (e.g. 4.0)
            popular_only: Only return shows marked as popular
        """
        results = []
        for p in store.podcasts.values():
            if popular_only and not p.get("isPopular"):
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
                "episodes": len(p.get("episodes", []))
            })
        
        results.sort(key=lambda x: x.get("rating") or 0, reverse=True)
        return json.dumps(results[:20], indent=2)
    
    
    @mcp.tool()
    def show_stats(title: str) -> Any:
        """
        Get detailed statistics for a specific show.
        Returns episode count, average duration, vibe summary, and audience info.
        """
        p = store.get_details(title)
        if not p:
            return f"Show '{title}' not found."
        
        episodes = p.get("episodes", [])
        durations = [int(ep.get("duration", 0)) for ep in episodes if ep.get("duration")]
        avg_duration = sum(durations) / max(len(durations), 1)
        
        return json.dumps({
            "title": p.get("title"),
            "episode_count": len(episodes),
            "average_duration_minutes": round(avg_duration / 60, 1),
            "rating": p.get("averageRating"),
            "rating_count": p.get("ratingCount"),
            "vibe": p.get("vibe"),
            "target_audience": p.get("targetAudience"),
            "recommendation_scenarios": p.get("recommendationScenarios"),
            "is_popular": p.get("isPopular"),
            "genres": p.get("appleGenres"),
            "hook": p.get("narrativeHook")
        }, indent=2)
    
    
    @mcp.tool()
    
    async def semantic_search_episodes(query: str, top_k: int = 5) -> Any:
        """
        Semantic search across all indexed episode transcripts and descriptions.
        Uses vector embeddings for meaning-based matching, not just keywords.
        Requires the vector store to be indexed first.
        """
        collection = _get_vector_collection()
        if not collection or collection.count() == 0:
            return "Vector store is empty. Run the pipeline with --ai-enrich to index episodes."
        
        async def _search():
            try:
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                async with aiohttp.ClientSession(connector=connector) as session:
                    results = await semantic_search(session, collection, query, top_k=top_k)
                    if not results:
                        return f"No semantic matches found for '{query}'. Try a simpler keyword search."
                    return results
            except Exception as e:
                return f"Semantic search failed: {e}. Ensure Ollama is running with 'nomic-embed-text'."
        
        return await _search()
    
    
    
    
    
    
    # --- Phase 17: Audio Clip Extraction Tools ---
    
    from .clipper import extract_clip
    
    
    @mcp.tool()
    
    async def extract_audio_clip(podcast_title: str, episode_title: str, start_seconds: float, end_seconds: float) -> Any:
        """
        Extract an audio clip from a podcast episode between the given timestamps.
        Returns the path to the generated MP3 file.
        Use get_episode_chapters, get_episode_highlights, or search_transcripts to find timestamps first.
        """
        p = store.get_details(podcast_title)
        if not p:
            return f"Podcast '{podcast_title}' not found."
    
        episode = None
        for ep in p.get("episodes", []):
            if ep.get("title", "").lower() == episode_title.lower():
                episode = ep
                break
    
        if not episode:
            # Try partial match
            for ep in p.get("episodes", []):
                if episode_title.lower() in ep.get("title", "").lower():
                    episode = ep
                    break
    
        if not episode:
            return f"Episode '{episode_title}' not found in '{podcast_title}'."
    
        audio_url = episode.get("audioUrl")
        if not audio_url:
            return f"No audio URL available for '{episode_title}'. Run with --deep-crawl first."
    
        async def _extract():
            return await extract_clip(
                audio_url=audio_url,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                podcast_title=podcast_title,
                episode_title=episode.get("title", episode_title),
            )
    
        try:
            path = await _extract()
            duration = end_seconds - start_seconds
            return json.dumps({
                "status": "success",
                "clip_path": path,
                "duration_seconds": round(duration, 1),
                "source_episode": episode.get("title"),
                "source_podcast": podcast_title,
                "time_range": f"{start_seconds:.1f}s - {end_seconds:.1f}s"
            }, indent=2)
        except Exception as e:
            return f"Failed to extract clip: {e}"
    
    
    @mcp.tool()
    def extract_chapter_clip(podcast_title: str, episode_title: str, chapter_title: str) -> Any:
        """
        Extract an audio clip for a specific AI-generated chapter.
        Automatically looks up the chapter's start and end timestamps.
        """
        p = store.get_details(podcast_title)
        if not p:
            return f"Podcast '{podcast_title}' not found."
    
        episode = None
        for ep in p.get("episodes", []):
            if episode_title.lower() in ep.get("title", "").lower():
                episode = ep
                break
    
        if not episode:
            return f"Episode '{episode_title}' not found."
    
        chapters = episode.get("chapters", [])
        if not chapters:
            return f"No chapters found for '{episode_title}'. Run with --ai-enrich first."
    
        chapter = None
        for ch in chapters:
            if chapter_title.lower() in ch.get("title", "").lower():
                chapter = ch
                break
    
        if not chapter:
            available = [c.get("title") for c in chapters]
            return f"Chapter '{chapter_title}' not found. Available: {available}"
    
        start = chapter.get("startTime", 0)
        end = chapter.get("endTime", 0)
    
        return extract_audio_clip(podcast_title, episode.get("title"), start, end)
    
    
    @mcp.tool()
    def get_episode_highlights(podcast_title: str, episode_title: str) -> Any:
        """
        Get AI-detected highlights (most exciting/engaging moments) for an episode.
        Returns highlights with timestamps that can be used with extract_audio_clip.
        """
        p = store.get_details(podcast_title)
        if not p:
            return f"Podcast '{podcast_title}' not found."
    
        episode = None
        for ep in p.get("episodes", []):
            if episode_title.lower() in ep.get("title", "").lower():
                episode = ep
                break
    
        if not episode:
            return f"Episode '{episode_title}' not found."
    
        highlights = episode.get("highlights", [])
        if not highlights:
            return f"No highlights found for '{episode_title}'. Run with --ai-enrich and --transcribe first."
    
        return json.dumps({
            "episode": episode.get("title"),
            "podcast": podcast_title,
            "highlights": highlights,
            "tip": "Use extract_audio_clip with the startTime and endTime to get an audio clip."
        }, indent=2)
    
    
    # --- Phase 18: Semantic Audio Extraction Suite ---
    
    from .clipper import stitch_clips, generate_audiogram as _generate_audiogram
    from .ai_enricher import (
        find_topic_segments, detect_emotional_peaks, detect_disagreements,
        detect_data_claims, generate_summary_points, identify_qa_pairs,
    )
    
    
    def _find_episode(podcast_title: str, episode_title: str):
        """Helper: find podcast dict and episode dict by title (partial match)."""
        p = store.get_details(podcast_title)
        if not p:
            return None, None, f"Podcast '{podcast_title}' not found."
        for ep in p.get("episodes", []):
            if episode_title.lower() in ep.get("title", "").lower():
                return p, ep, None
        return p, None, f"Episode '{episode_title}' not found in '{podcast_title}'."
    
    
    def _get_segments(episode):
        """Get segments list from episode dict."""
        return episode.get("segments", [])
    
    
    def _require_audio(episode):
        """Check episode has an audio URL."""
        url = episode.get("audioUrl")
        if not url:
            return None, "No audio URL. Run with --deep-crawl first."
        return url, None
    
    
    # --- A: Speaker-Centric ---
    
    @mcp.tool()
    
    async def extract_speaker_reel(podcast_title: str, episode_title: str, speaker_name: str) -> Any:
        """
        Extract all segments where a specific speaker talks, stitched into one clip.
        Great for creating a 'soundbite reel' of a guest or host.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
        audio_url, err = _require_audio(ep)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments. Run with --transcribe first."
    
        # Find all segments for this speaker
        ranges = []
        for seg in segments:
            s_name = seg.get("speaker", "")
            if s_name and speaker_name.lower() in s_name.lower():
                ranges.append((seg.get("start", 0), seg.get("end", 0)))
    
        if not ranges:
            speakers = list(set(s.get("speaker", "?") for s in segments if s.get("speaker")))
            return f"Speaker '{speaker_name}' not found. Available: {speakers}"
    
        try:
            path = asyncio.run(stitch_clips(
                audio_url, ranges, label=f"reel_{speaker_name}"
            ))
            return json.dumps({
                "status": "success", "clip_path": path,
                "speaker": speaker_name, "segment_count": len(ranges),
                "total_seconds": round(sum(e - s for s, e in ranges), 1)
            }, indent=2)
        except Exception as e:
            return f"Failed: {e}"
    
    
    @mcp.tool()
    
    async def extract_dialogue(podcast_title: str, episode_title: str, speaker_a: str, speaker_b: str) -> Any:
        """
        Extract the back-and-forth between two speakers, removing all other speakers.
        Perfect for isolating a debate or interview exchange.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
        audio_url, err = _require_audio(ep)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        ranges = []
        for seg in segments:
            s_name = (seg.get("speaker") or "").lower()
            if speaker_a.lower() in s_name or speaker_b.lower() in s_name:
                ranges.append((seg.get("start", 0), seg.get("end", 0)))
    
        if not ranges:
            return f"No dialogue found between '{speaker_a}' and '{speaker_b}'."
    
        try:
            path = asyncio.run(stitch_clips(
                audio_url, ranges, label=f"dialogue_{speaker_a}_{speaker_b}"
            ))
            return json.dumps({
                "status": "success", "clip_path": path,
                "speakers": [speaker_a, speaker_b], "segment_count": len(ranges)
            }, indent=2)
        except Exception as e:
            return f"Failed: {e}"
    
    
    @mcp.tool()
    def extract_speaker_intro(podcast_title: str, episode_title: str, guest_name: str) -> Any:
        """
        Find and clip the moment a guest is introduced (typically first appearance + context).
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
        audio_url, err = _require_audio(ep)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        # Find first mention of guest name in segment text
        intro_start = None
        for seg in segments:
            text = (seg.get("text") or "").lower()
            if guest_name.lower() in text:
                intro_start = max(0, seg.get("start", 0) - 10)
                intro_end = min(seg.get("end", 0) + 60, segments[-1].get("end", 300))
                break
    
        if intro_start is None:
            return f"'{guest_name}' not mentioned in transcript segments."
    
        return extract_audio_clip(podcast_title, ep.get("title"), intro_start, intro_end)
    
    
    # --- B: Topic & Entity ---
    
    @mcp.tool()
    
    async def extract_topic_segment(podcast_title: str, episode_title: str, topic: str) -> Any:
        """
        Find and extract all segments discussing a specific topic (semantic, not keyword).
        Args: topic e.g. "climate policy", "housing affordability"
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
        audio_url, err = _require_audio(ep)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        async def _process():
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                results = await find_topic_segments(session, segments, topic)
                if not results:
                    return json.dumps({"status": "not_found", "message": f"Topic '{topic}' not discussed."})
    
                ranges = [(r["startTime"], r["endTime"]) for r in results]
                path = await stitch_clips(audio_url, ranges, label=f"topic_{topic}")
                return json.dumps({
                    "status": "success", "clip_path": path, "topic": topic,
                    "segments": results, "segment_count": len(results)
                }, indent=2, default=str)
    
        return await _process()
    
    
    @mcp.tool()
    
    async def extract_entity_mentions(podcast_title: str, episode_title: str, entity: str) -> Any:
        """
        Extract every mention of a person, place, or organization.
        Uses text search on transcript segments with 5s padding.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
        audio_url, err = _require_audio(ep)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        # Text search with padding
        ranges = []
        mentions = []
        for seg in segments:
            text = seg.get("text", "")
            if entity.lower() in text.lower():
                start = max(0, seg.get("start", 0) - 3)
                end = seg.get("end", 0) + 3
                ranges.append((start, end))
                mentions.append({"text": text, "start": seg.get("start"), "end": seg.get("end")})
    
        if not ranges:
            return f"'{entity}' not mentioned in this episode."
    
        try:
            path = await stitch_clips(audio_url, ranges, label=f"mentions_{entity}")
            return json.dumps({
                "status": "success", "clip_path": path, "entity": entity,
                "mention_count": len(mentions), "mentions": mentions
            }, indent=2, default=str)
        except Exception as e:
            return f"Failed: {e}"
    
    
    @mcp.tool()
    
    async def extract_question_answers(podcast_title: str, episode_title: str) -> Any:
        """
        Identify Q&A pairs in interviews, each extractable as a standalone clip.
        Returns list of questions with answers and option to extract clips.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        async def _process():
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                qa_pairs = await identify_qa_pairs(session, segments)
                if not qa_pairs:
                    return json.dumps({"status": "not_interview", "message": "No Q&A pairs detected."})
                return json.dumps({
                    "status": "success", "qa_count": len(qa_pairs), "pairs": qa_pairs,
                    "tip": "Use extract_audio_clip with startTime/endTime to clip any Q&A pair."
                }, indent=2, default=str)
    
        return await _process()
    
    
    # --- C: Social & Sharing ---
    
    @mcp.tool()
    
    async def create_audiogram(
        podcast_title: str,
        episode_title: str,
        start_seconds: float,
        end_seconds: float,
        image_path: str = None
    ) -> Any:
        """
        Create a shareable audiogram video (MP4) with waveform visualization and captions.
        Optional image_path for a premium background with Ken Burns effect.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
        audio_url, err = _require_audio(ep)
        if err:
            return err
    
        # Get captions from segments in the time range
        segments = _get_segments(ep)
        captions = [s for s in segments
                    if s.get("start", 0) >= start_seconds and s.get("end", 0) <= end_seconds]
    
        title = f"{podcast_title} — {ep.get('title', '')}"[:80]
    
        try:
            path = asyncio.run(_generate_audiogram(
                audio_url, start_seconds, end_seconds,
                captions=captions, title=title,
                image_path=image_path
            ))
            return json.dumps({
                "status": "success", "audiogram_path": path,
                "format": "MP4", "dimensions": "1080x1080",
                "duration_seconds": round(end_seconds - start_seconds, 1),
                "premium": bool(image_path)
            }, indent=2)
        except Exception as e:
            return f"Failed to create audiogram: {e}"
    
    
    @mcp.tool()
    def extract_quote_clip(podcast_title: str, episode_title: str, quote_text: str) -> Any:
        """
        Find an exact or approximate text quote in the transcript and extract the audio.
        Useful when you read a quote and want to hear how it was actually said.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
        audio_url, err = _require_audio(ep)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        # Fuzzy search: find segment with best overlap
        query_words = set(quote_text.lower().split())
        best_seg = None
        best_score = 0
    
        for seg in segments:
            text_words = set(seg.get("text", "").lower().split())
            overlap = len(query_words & text_words) / max(len(query_words), 1)
            if overlap > best_score:
                best_score = overlap
                best_seg = seg
    
        if not best_seg or best_score < 0.3:
            return f"Quote not found in transcript. Best match score: {best_score:.0%}"
    
        start = max(0, best_seg.get("start", 0) - 2)
        end = best_seg.get("end", 0) + 2
    
        result = extract_audio_clip(podcast_title, ep.get("title"), start, end)
        return json.dumps({
            "match_score": f"{best_score:.0%}",
            "matched_text": best_seg.get("text", ""),
            "speaker": best_seg.get("speaker", "Unknown"),
            "clip_result": json.loads(result) if result.startswith("{") else result
        }, indent=2)
    
    
    @mcp.tool()
    def extract_cold_open(podcast_title: str, episode_title: str) -> Any:
        """
        Extract the 'hook' — the teaser moment in the first 2-3 minutes.
        Great for marketing clips that make people want to subscribe.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
        audio_url, err = _require_audio(ep)
        if err:
            return err
    
        segments = _get_segments(ep)
        # The cold open is typically the first 60-120 seconds
        cold_end = min(120.0, segments[-1].get("end", 120) if segments else 120)
    
        return extract_audio_clip(podcast_title, ep.get("title"), 0, cold_end)
    
    
    # --- D: Research & Analysis ---
    
    @mcp.tool()
    
    async def extract_emotional_peaks(podcast_title: str, episode_title: str, emotion: Optional[str] = None) -> Any:
        """
        Detect emotionally charged moments in the conversation.
        Optional emotion filter: 'anger', 'joy', 'surprise', 'sadness', 'passion'.
        Returns highlights with timestamps for clipping.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        async def _process():
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                peaks = await detect_emotional_peaks(session, segments, emotion)
                if not peaks:
                    return json.dumps({"status": "none_found", "message": "No emotional peaks detected."})
                return json.dumps({
                    "status": "success", "peaks": peaks,
                    "tip": "Use extract_audio_clip with startTime/endTime to clip any peak."
                }, indent=2, default=str)
    
        return await _process()
    
    
    @mcp.tool()
    
    async def extract_disagreements(podcast_title: str, episode_title: str) -> Any:
        """
        Find moments where speakers contradict or challenge each other.
        Useful for fact-checking, debate analysis, and research.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        async def _process():
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                disagreements = await detect_disagreements(session, segments)
                if not disagreements:
                    return json.dumps({"status": "none_found", "message": "No disagreements detected."})
                return json.dumps({
                    "status": "success", "disagreements": disagreements,
                    "tip": "Use extract_audio_clip to clip any disagreement."
                }, indent=2, default=str)
    
        return await _process()
    
    
    @mcp.tool()
    def compare_perspectives(topic: str, top_k: int = 5) -> Any:
        """
        Cross-episode: find different speakers' takes on the same topic.
        Searches across all episodes in the catalogue.
        """
        results = []
        for title, podcast in store.podcasts.items():
            for ep in podcast.get("episodes", []):
                segments = ep.get("segments", [])
                if not segments:
                    continue
                # Quick text scan for topic mention
                for seg in segments:
                    if topic.lower() in (seg.get("text", "")).lower():
                        results.append({
                            "podcast": title,
                            "episode": ep.get("title"),
                            "speaker": seg.get("speaker", "Unknown"),
                            "text": seg.get("text", ""),
                            "startTime": seg.get("start"),
                            "endTime": seg.get("end"),
                        })
                        break  # One per episode
    
        if not results:
            return f"Topic '{topic}' not mentioned in any transcribed episode."
    
        return json.dumps({
            "status": "success", "topic": topic,
            "perspectives": results[:top_k],
            "tip": "Use extract_audio_clip on any perspective to hear the original audio."
        }, indent=2, default=str)
    
    
    @mcp.tool()
    
    async def extract_data_claims(podcast_title: str, episode_title: str) -> Any:
        """
        Find moments where speakers cite statistics, studies, or specific numbers.
        Useful for fact-checking and research verification.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        async def _process():
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                claims = await detect_data_claims(session, segments)
                if not claims:
                    return json.dumps({"status": "none_found", "message": "No data claims detected."})
                return json.dumps({
                    "status": "success", "claims": claims,
                    "tip": "Use extract_audio_clip to clip any claim for verification."
                }, indent=2, default=str)
    
        return await _process()
    
    
    @mcp.tool()
    
    async def extract_summary_clip(podcast_title: str, episode_title: str, max_duration: int = 120) -> Any:
        """
        Create a 2-minute executive summary by stitching together key points.
        Perfect for busy people who want the gist of a long episode.
        """
        _, ep, err = _find_episode(podcast_title, episode_title)
        if err:
            return err
        audio_url, err = _require_audio(ep)
        if err:
            return err
    
        segments = _get_segments(ep)
        if not segments:
            return "No transcript segments."
    
        async def _process():
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                points = await generate_summary_points(session, segments)
                if not points:
                    return json.dumps({"status": "failed", "message": "Could not generate summary points."})
    
                # Trim to max_duration
                ranges = []
                total = 0
                for pt in points:
                    dur = pt["endTime"] - pt["startTime"]
                    if total + dur > max_duration:
                        break
                    ranges.append((pt["startTime"], pt["endTime"]))
                    total += dur
    
                if not ranges:
                    return json.dumps({"status": "failed", "message": "Summary points too short."})
    
                path = await stitch_clips(audio_url, ranges, label=f"summary_{episode_title}")
                return json.dumps({
                    "status": "success", "clip_path": path,
                    "key_points": points[:len(ranges)],
                    "duration_seconds": round(total, 1)
                }, indent=2, default=str)
    
        re
    # --- Legacy / Specialist Tools ---
    # These tools are subsumed by the core tools above but kept for specialized workflows.
    # They are only registered when GOLDMINE_LEGACY_TOOLS=1 is set.
    
    if os.environ.get("GOLDMINE_LEGACY_TOOLS", "0") == "1":
        
        @mcp.tool()
        def export_universal_catalogue() -> Any:
            """
            Export the full podcast catalogue in a standardized, universal format (JSON-LD).
            This graph format is optimized for generic Agent traversal and cross-platform indexing.
            """
            all_podcasts = list(store.podcasts.values())
            return json.dumps(all_podcasts, indent=2, ensure_ascii=False)
        
        @mcp.tool()
        def get_podcast(title: str) -> Any:
            """Get a single podcast entity uniformly by title."""
            p = store.get_details(title)
            if not p:
                return f"Podcast '{title}' not found."
            return json.dumps(p, indent=2, ensure_ascii=False)
        
        @mcp.tool()
        async def generate_daily_briefing(limit: int = 5) -> Any:
            """
            Generates a daily editorial meta-summary synthesizing the latest narrative trends.
            """
            from .reporter_adapter import generate_editorial_report
            all_podcasts = list(store.podcasts.values())
            async with aiohttp.ClientSession() as session:
                report = await generate_editorial_report(session, all_podcasts[:limit])
                return report

        @mcp.tool()
        async def find_narrative_shifts_legacy(topic: str) -> str:
            """Tracks how a specific topic's rhetoric or tone has evolved recently."""
            # Fallback to consolidated search
            results = store.search(topic)
            if not results:
                return f"No narrative data found for topic: {topic}"
            
            summary = f"Analysis of narrative shifts for '{topic}':\n\n"
            for r in results[:5]:
                vibe = r.get("vibe", {})
                tone = vibe.get("tone", "Standard")
                summary += f"- {r.get('podcast_title')}: {r.get('title')} | Tone: {tone}\n"
                summary += f"  Hook: {r.get('hook', 'N/A')}\n"
            return summary

if __name__ == "__main__":
    mcp.run()

