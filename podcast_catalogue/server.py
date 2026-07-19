from __future__ import annotations

import json
import os
import sys
import hashlib
import re
from typing import List, Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from .entity_registry import load_registry, save_registry

# Load environment variables from .env if present
load_dotenv()

# Initialize FastMCP Server
mcp = FastMCP("Podcast Catalogue")


# Try enriched data first, fallback to basic
UNIVERSE_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/universe.jsonl")
FULL_INTELLIGENCE_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/podcasts_450_full_intelligence.jsonl")
ENRICHED_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/podcasts_enriched.jsonl")
BASIC_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/podcasts.jsonl")
REGIONAL_PULSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/regional_pulses.jsonl")

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

    def _build_aggregate_vibes(self):
        """Computes show-level vibes based on the majority tone/complexity of its episodes."""
        for title, podcast in self.podcasts.items():
            episodes = podcast.get("episodes", [])
            if not episodes: continue
            
            tones = []
            complexities = []
            for ep in episodes:
                v = ep.get("vibe")
                if not v or not isinstance(v, dict): continue
                
                if v.get("tone"):
                    if isinstance(v["tone"], list): tones.extend(v["tone"])
                    else: tones.append(v["tone"])
                if v.get("complexity") is not None: complexities.append(v["complexity"])
            
            if tones:
                from collections import Counter
                top_tones = [t for t, _ in Counter(tones).most_common(3)]
                if not podcast.get("vibe"): podcast["vibe"] = {}
                podcast["vibe"]["tone"] = top_tones
            
            if complexities:
                avg_complexity = sum(complexities) / len(complexities)
                if "vibe" not in podcast: podcast["vibe"] = {}
                podcast["vibe"]["complexity"] = avg_complexity

    def load_data(self, path: str = DATA_FILE):
        if not os.path.exists(path):
            print(f"Warning: Data file not found at {path}", file=sys.stderr)
            return

        print(f"Loading GoldMine catalogue from {path}...", file=sys.stderr)
        
        # Clear existing state for clean reload
        self.podcasts = {}
        self.episodes_index = []
        self.episodes_by_id = {}

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    title = data.get("title")
                    if not title: continue
                    
                    self.podcasts[title.lower()] = data
                    
                    for ep in data.get("episodes", []):
                        ep_title = ep.get("title")
                        ep_id = hashlib.md5(f"{title}:{ep_title}".encode()).hexdigest()[:12]
                        
                        # Hallucination Shield: Skip contaminated transcripts
                        transcript = ep.get("transcript", "")
                        if not self._is_transcript_valid(transcript):
                            transcript = "[TRANSCRIPT UNAVAILABLE: DATA QUALITY ISSUE DETECTED]"
                            
                        episode_data = {
                            "id": ep_id,
                            "podcast_title": title,
                            "title": ep_title,
                            "description": ep.get("description", ""),
                            "publishedAt": ep.get("publishedAt", ""),
                            "transcript": transcript,
                            "hook": ep.get("narrativeHook") or ep.get("description", ""),
                            "entities": ep.get("entities", []),
                            "guests": ep.get("guests", []),
                            "segments": ep.get("segments", []),
                            "chapters": ep.get("chapters", []),
                            "highlights": ep.get("highlights", []),
                            "audio_url": ep.get("audioUrl") or ep.get("audio_url", ""),
                            "vibe": ep.get("vibe", {}),
                            "engagement": ep.get("engagement", {}),
                            "apple_podcast_page": data.get("applePodcastPage"),
                            # Editorial Trust Layer
                            "genre": ep.get("genre"),
                            "content_risk": ep.get("contentRisk") or ep.get("content_risk"),
                            "ai_provenance": ep.get("aiProvenance") or ep.get("ai_provenance"),
                            "expires": ep.get("expires"),
                            "content_reference_time": ep.get("contentReferenceTime") or ep.get("content_reference_time"),
                        }
                        self.episodes_index.append(episode_data)
                        self.episodes_by_id[ep_id] = episode_data
                except Exception as e:
                    continue
        
        # Priority 1: Aggregate Show Vibes
        self._build_aggregate_vibes()
        
        print(f"Loaded {len(self.podcasts)} shows and {len(self.episodes_index)} episodes.", file=sys.stderr)

    def save_data(self, path: str = DATA_FILE):
        """Persists the in-memory podcasts store back to a JSONL file."""
        print(f"Saving GoldMine catalogue to {path}...", file=sys.stderr)
        try:
            with open(path, "w", encoding="utf-8") as f:
                for podcast in self.podcasts.values():
                    f.write(json.dumps(podcast, ensure_ascii=False) + "\n")
            print(f"Successfully saved {len(self.podcasts)} shows.", file=sys.stderr)
        except Exception as e:
            print(f"Error saving data: {e}", file=sys.stderr)

    def ingest_snipd_markdown(self, content: str):
        """Parses Snipd Markdown and integrates it into the store."""
        metadata = self._parse_snipd_metadata(content)
        if not metadata:
            print("Failed to parse Snipd metadata.", file=sys.stderr)
            return
        
        podcast_title = metadata.get("show_title", "Unknown Show")
        episode_title = metadata.get("episode_title", "Unknown Episode")
        
        # 1. Get or create Podcast
        p_key = podcast_title.lower()
        if p_key not in self.podcasts:
            self.podcasts[p_key] = {
                "title": podcast_title,
                "imageUrl": metadata.get("image_url"),
                "episodes": []
            }
        
        podcast = self.podcasts[p_key]
        
        # 2. Get or create Episode
        episode = None
        for ep in podcast.get("episodes", []):
            if ep.get("title") == episode_title:
                episode = ep
                break
        
        if not episode:
            episode = {
                "title": episode_title,
                "publishedAt": metadata.get("episode_publish_date"),
                "url": metadata.get("episode_url"),
                "highlights": [],
                "guests": [{"name": g} for g in metadata.get("guests", [])]
            }
            podcast["episodes"].append(episode)
        
        # 3. Parse Snips (Highlights)
        snips = self._parse_snipd_snips(content)
        existing_highlights = {h.get("title") for h in episode.get("highlights", [])}
        
        for snip in snips:
            if snip.get("title") not in existing_highlights:
                episode["highlights"].append({
                    "title": snip.get("title"),
                    "reason": snip.get("summary", ""),
                    "category": "GENERAL",
                    "startTime": snip.get("startTime", 0.0),
                    "endTime": snip.get("endTime", 0.0)
                })

        # 4. Add Transcript if present
        transcript_match = re.search(r"#### 📚 Transcript\n\n(.*?)(?=\n\n---|\Z)", content, re.DOTALL)
        if transcript_match:
            episode["transcript"] = transcript_match.group(1).strip()

        # 5. Sync and Rebuild indices
        self.save_data()
        self.load_data()

    def _parse_snipd_metadata(self, content: str) -> Dict[str, Any]:
        """Extracts YAML-like frontmatter from Snipd MD."""
        match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match: return {}
        
        lines = match.group(1).split("\n")
        metadata = {}
        current_key = None
        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"')
                if not val and key == "guests":
                    metadata[key] = []
                    current_key = key
                else:
                    metadata[key] = val
                    current_key = None
            elif line.strip().startswith("- ") and current_key == "guests":
                metadata[current_key].append(line.strip("- ").strip())
        return metadata

    def _parse_snipd_snips(self, content: str) -> List[Dict[str, Any]]:
        """Extracts snips with timestamps and summaries."""
        snips = []
        # Find ### [TITLE](URL) sections
        sections = re.split(r"###\s+\[(.*?)\]\((.*?)\)", content)
        # Skip everything before first snip
        for i in range(1, len(sections), 3):
            title = sections[i]
            # url = sections[i+1] # not used yet
            body = sections[i+2]
            
            # Extract timestamps: 🎧 00:00 - 00:01
            time_match = re.search(r"🎧\s+(\d{2}:\d{2})\s+-\s+(\d{2}:\d{2})", body)
            start_time = 0.0
            end_time = 0.0
            if time_match:
                start_time = self._to_seconds(time_match.group(1))
                end_time = self._to_seconds(time_match.group(2))
            
            # Extract summary (text after iframe and title header)
            summary_match = re.search(r"##\s+.*?\n(.*?)(?=\n#### 📚 Transcript|\n###|\Z)", body, re.DOTALL)
            summary = summary_match.group(1).strip() if summary_match else ""
            
            snips.append({
                "title": title,
                "startTime": start_time,
                "endTime": end_time,
                "summary": summary
            })
        return snips

    def _to_seconds(self, ts: str) -> float:
        parts = ts.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0.0

    def _is_transcript_valid(self, text: str) -> bool:
        """Simple check for transcription hallucinations/loops."""
        if not text: return True
        words = text.split()
        if not words: return True
        max_repeat = 0
        current_repeat = 1
        for i in range(1, len(words)):
            if words[i] == words[i-1]:
                current_repeat += 1
                max_repeat = max(max_repeat, current_repeat)
            else:
                current_repeat = 1
        return max_repeat < 15

    def search(self, query: str) -> List[Dict[str, Any]]:
        query = query.lower()
        results = []
        for p in self.podcasts.values():
            if query in p.get("title", "").lower() or query in p.get("description", "").lower():
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
        return results[:10]

    def get_details(self, title: str):
        q = title.lower()
        if q in self.podcasts: return self.podcasts[q]
        for k, v in self.podcasts.items():
            if q in k or k in q:
                return v
        return None

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

# --- Browse & Personalized Tools ---

@mcp.tool()
def list_categories() -> str:
    categories = sorted(list(set([p.get("primaryGenre") for p in store.podcasts.values() if p.get("primaryGenre")])))
    return json.dumps({"categories": categories}, indent=2)

@mcp.tool()
def browse_by_category(category: str, limit: int = 10) -> str:
    matches = []
    cat_lower = category.lower()
    for p in store.podcasts.values():
        p_genres = [g.lower() for g in (p.get("appleGenres", []) + [p.get("primaryGenre") or ""])]
        if any(cat_lower in g for g in p_genres if g):
            matches.append({"title": p.get("title"), "description": (p.get("description") or "")[:200] + "...", "episodes": len(p.get("episodes", []))})
    return json.dumps({"category": category, "shows": matches[:limit]}, indent=2)

@mcp.tool()
def search_by_location(location: str, limit: int = 10) -> Any:
    matches = []
    loc_lower = location.lower()
    for p in store.podcasts.values():
        text = (p.get("title", "") + " " + (p.get("description") or "")).lower()
        if loc_lower in text:
            matches.append({"type": "show", "title": p.get("title")})
    for ep in store.episodes_index:
        if loc_lower in (ep.get("title", "") + " " + ep.get("description", "")).lower():
            matches.append({"type": "episode", "podcast": ep.get("podcast_title"), "title": ep.get("title")})
    return json.dumps(matches[:limit], indent=2)

@mcp.tool()
def get_trending_content(limit: int = 5) -> Any:
    scored_shows = []
    for p in store.podcasts.values():
        score = 0
        if p.get("isPopular"): score += 50
        scored_shows.append((score, p))
    scored_shows.sort(key=lambda x: x[0], reverse=True)
    results = [{"title": p.get("title"), "description": (p.get("description") or "")[:200] + "..."} for _, p in scored_shows[:limit]]
    return wrap_with_ui(results)

def wrap_with_ui(results: Any) -> Any:
    return {"content": [{"type": "text", "text": json.dumps(results, indent=2, default=str)}], "_meta": {"ui": {"resourceUri": "ui://podcast-app"}}}

_search_cache = {}

@mcp.tool()
async def search_catalogue(query: str, limit: int = 10) -> Any:
    """
    Search the entire GoldMine catalogue. Supports topic expansion and coverage bridge.
    """
    query_lower = query.lower()
    results = []
    
    # Priority 4: Topic Coverage Bridge
    bridge = {
        "ai": "Science (general tech), Business (tech industry), or Future Tense (emerging tech)",
        "tech": "Technology category, Science, or Future Tense",
        "defense": "Politics, News Daily, or Background Briefing",
        "climate": "Science, Big Ideas, or Climate Council mentions",
        "crypto": "The Money, Business, or RN Breakfast (fintech updates)"
    }
    
    synonyms = {
        "aukus": ["submarines", "defense", "security", "nuclear", "us-australia"],
        "housing": ["property", "rent", "interest rates", "real estate"],
        "ai": ["artificial intelligence", "machine learning", "automation"]
    }
    
    search_terms = [query_lower]
    if query_lower in synonyms: search_terms.extend(synonyms[query_lower])
    
    # Search logic
    for p in store.podcasts.values():
        score = 0
        title = p.get("title", "").lower()
        if query_lower in title: score += 50
        if score > 0:
            results.append({"score": score, "type": "podcast", "title": p["title"], "desc": p.get("description", "")[:150]})

    for ep in store.episodes_index:
        score = 0
        text = (ep.get("title", "") + " " + (ep.get("transcript") or "")).lower()
        if any(t in text for t in search_terms): score += 20
        if score > 0:
            results.append({"score": score, "type": "episode", "podcast": ep["podcast_title"], "title": ep["title"]})

    results.sort(key=lambda x: x["score"], reverse=True)
    
    if not results:
        bridge_msg = bridge.get(query_lower, "our general Politics, Science, or Society categories")
        return json.dumps({
            "results": [],
            "suggestion": f"No direct matches for '{query}'. ABC's catalogue focuses on politics, health, and culture. For '{query}', try exploring {bridge_msg}.",
            "tip": "Try more general terms or browse by category."
        }, indent=2)

    return wrap_with_ui(results[:limit])




@mcp.tool()
def get_catalogue_context() -> Any:
    """
    Returns the scope and strategy for the GoldMine discovery engine.
    Includes count of episodes, vibes, and a guide for persona-based recommendations.
    """
    total_eps = len(store.episodes_index)
    
    # Priority 4: Outstanding Response Strategy Guide
    persona_guide = {
        "The Deep Diver": "Recommend multi-part series (e.g., Expanse, Background Briefing). Focus on investigative tones and high narrative hooks.",
        "The Substance Seeker": "Recommend shows with high Complexity scores (>0.6) and 'Analytical' or 'Serious' tones (e.g., The Case Of, The Money).",
        "The Commute Optimizer": "Filter by duration (<30 mins) and recommend high-engagement 'News' or 'Daily' shows (e.g., ABC News Daily, Breakfast).",
        "The Skeptical Executive": "Focus on high-utility business, crypto, or tech investigative series (e.g., A Death in Cryptoland, Future Tense)."
    }

    # Best Practice Patterns for the Agent
    agent_patterns = [
        "Empty Results? Always check the 'suggestion' field in search_catalogue for the Topic Coverage Bridge.",
        "Vibe Checks: For every recommendation, offer to 'extract_chapter_clip' for a 2-minute audio vibe preview.",
        "Guest Search: Always use 'First Last' but suggest searching by 'Last Name' if zero results return.",
        "Comparison: Use 'compare_perspectives' when a user asks about controversial or multi-faceted topics."
    ]

    return json.dumps({
        "catalogue_scope": {
            "total_shows": len(store.podcasts),
            "total_episodes": total_eps,
            "network": "ABC Australian Content (Sentinel Hardened / Editorial Trust Layer)",
            "update_status": "Production-Ready / Metadata Enriched / Epistemic Flagging Active"
        },
        "discovery_strategy_guide": persona_guide,
        "agent_best_practices": agent_patterns,
        "best_tools_by_scenario": {
            "mood_discovery": "find_podcast_by_vibe(tone=...)",
            "expert_lookup": "search_by_guest(guest_name=...)",
            "preview_audio": "extract_chapter_clip(episode_title=..., chapter_keyword=...)",
            "trust_verification": "get_editorial_trust_report(podcast_title=..., episode_title=...)",
            "technical_depth": "recommend_episodes(complexity_min=0.7)"
        }
    }, indent=2)

@mcp.tool()
def get_episode_details(podcast_title: str, episode_title: str) -> Any:
    """
    Get full structured metadata for a specific episode.
    Returns transcript, chapters, highlights (with trust signals), guests, entities, vibe, and engagement data.
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
    Get full details for a specific podcast, including episode list, vibe, licensing, and source organization.
    Use the exact title from search results.
    """
    p = store.get_details(title)
    if not p:
        return f"Podcast '{title}' not found."
    return wrap_with_ui(p)


@mcp.tool()
def get_editorial_trust_report(podcast_title: str, episode_title: str) -> Any:
    """
    Get a comprehensive editorial trust report for a specific episode.
    Includes claim status, content risk labels, AI provenance, and source anchors.
    Use this to verify the 'truth-status' and liability of any highlight or claim.
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
        
    report = {
        "episode": episode.get("title"),
        "podcast": podcast_title,
        "trust_summary": {
            "risk_level": (episode.get("contentRisk") or episode.get("content_risk") or {}).get("level", "low"),
            "risk_categories": (episode.get("contentRisk") or episode.get("content_risk") or {}).get("categories", []),
            "ai_model": (episode.get("aiProvenance") or episode.get("ai_provenance") or {}).get("modelName"),
            "expiry": episode.get("expires"),
            "reference_time": episode.get("contentReferenceTime") or episode.get("content_reference_time")
        },
        "highlight_claims": []
    }
    
    for hl in episode.get("highlights", []):
        report["highlight_claims"].append({
            "claim": hl.get("title"),
            "category": hl.get("category"),
            "status": hl.get("claimStatus") or hl.get("claim_status") or "unverified",
            "provenance": {
                "transcript_segment": (hl.get("sourceAnchor") or hl.get("source_anchor") or {}).get("transcriptText"),
                "timestamp": (hl.get("sourceAnchor") or hl.get("source_anchor") or {}).get("timestampStart"),
                "spotify_link": (hl.get("sourceAnchor") or hl.get("source_anchor") or {}).get("spotifyDeepLink") or (hl.get("sourceAnchor") or hl.get("source_anchor") or {}).get("spotify_deep_link")
            }
        })
        
    return wrap_with_ui(report)


@mcp.tool()
def generate_json_ld(podcast_title: str, episode_title: Optional[str] = None) -> Any:
    """
    Generates schema.org compliant JSON-LD for a podcast or specific episode.
    Use this for external search engine optimization (SEO) or interoperability with third-party systems.
    """
    p = store.get_details(podcast_title)
    if not p:
        return json.dumps({"error": f"Podcast '{podcast_title}' not found."}, indent=2)
    
    # Podcast level JSON-LD
    ld = {
        "@context": "https://schema.org",
        "@type": "PodcastSeries",
        "name": p.get("title"),
        "description": p.get("description"),
        "publisher": {
            "@type": "Organization",
            "name": p.get("sourceOrganization") or p.get("source_organization") or "ABC Australia"
        },
        "genre": p.get("genre") or p.get("primaryGenre"),
        "license": p.get("license") or p.get("licenseUrl") or p.get("license_url")
    }
    
    if episode_title:
        episode = None
        ep_lower = episode_title.lower()
        for ep in p.get("episodes", []):
            if ep_lower == ep.get("title", "").lower() or ep_lower in ep.get("title", "").lower():
                episode = ep
                break
        
        if episode:
            ld["@type"] = "PodcastEpisode"
            ld["name"] = episode.get("title")
            ld["description"] = episode.get("description")
            ld["expires"] = episode.get("expires")
            ld["contentRating"] = (episode.get("contentRisk") or episode.get("content_risk") or {}).get("level")
            
            # Add Clips (Highlights)
            clips = []
            for hl in episode.get("highlights", []):
                clip = {
                    "@type": "Clip",
                    "name": hl.get("title"),
                    "startOffset": hl.get("startTime") or hl.get("start_time"),
                    "endOffset": hl.get("endTime") or hl.get("end_time"),
                    "interpretedAsClaim": {
                        "@type": "Claim",
                        "claimInterpreter": hl.get("claimInterpreter") or hl.get("claim_interpreter"),
                        "claimStatus": hl.get("claimStatus") or hl.get("claim_status")
                    }
                }
                clips.append(clip)
            ld["hasPart"] = clips
            
    return json.dumps(ld, indent=2)


@mcp.tool()
def register_entity_correction(wrong_pattern: str, correct_name: str) -> str:
    """
    Registers a new entity correction to fix transcription errors.
    The 'wrong_pattern' should be a simple string or a regex pattern (e.g. '\\bBargara\\b').
    The 'correct_name' is the intended professional spelling.
    """
    registry = load_registry()
    registry[wrong_pattern] = correct_name
    save_registry(registry)
    return f"Successfully registered correction: '{wrong_pattern}' -> '{correct_name}'"


@mcp.tool()
def get_canonical_event_timeline(event_id: str) -> str:
    """
    Retrieve the longitudinal timeline for a specific Canonical Event.
    Shows how a story has evolved across multiple episodes and shows.
    """
    if not os.path.exists(REGIONAL_PULSE_FILE):
        return json.dumps({"error": "No regional pulse data found."}, indent=2)
        
    timeline = []
    try:
        with open(REGIONAL_PULSE_FILE, "r") as f:
            for line in f:
                if not line.strip(): continue
                pulse = json.loads(line)
                events = pulse.get("canonicalEvents") or pulse.get("canonical_events") or []
                for ev in events:
                    if ev.get("eventId") == event_id or ev.get("event_id") == event_id:
                        timeline.append({
                            "date": pulse.get("date"),
                            "region": pulse.get("regionId") or pulse.get("region_id"),
                            "event_title": ev.get("title"),
                            "summary": ev.get("description"),
                            "episodes": ev.get("episodeTitles") or ev.get("episode_titles", [])
                        })
    except Exception as e:
        return json.dumps({"error": f"Failed to read pulses: {e}"}, indent=2)
        
    if not timeline:
        return json.dumps({"error": f"Event '{event_id}' not found."}, indent=2)
        
    # Sort by date
    timeline.sort(key=lambda x: x.get("date", ""))
    
    report = {
        "event_id": event_id,
        "timeline_depth": len(timeline),
        "updates": timeline
    }
    
    return wrap_with_ui(report)


@mcp.tool()
def find_podcast_by_vibe(tone: Optional[str] = None, complexity: Optional[str] = None, limit: int = 10) -> Any:
    """
    Find podcasts matching a specific mood or depth level.
    Best tool for finding new shows based on "vibe" rather than keywords.

    Args:
        tone: e.g. "Inspirational", "Humorous", "Dark", "Analytical"
        complexity: "Simple" (low technical depth), "Medium", "Deep" (high substance)
    """
    matches = []
    t_lower = tone.lower() if tone else None

    for p in store.podcasts.values():
        vibe = p.get("vibe", {})
        if not vibe: continue

        # 1. Tone Matching (Fuzzy)
        match_tone = True
        if t_lower:
            p_tones = [str(t).lower() for t in vibe.get("tone", [])]
            if not any(t_lower in pt or pt in t_lower for pt in p_tones):
                match_tone = False

        # 2. Complexity Matching
        match_complex = True
        if complexity:
            c = vibe.get("complexity", 0.5)
            if complexity == "Simple" and c > 0.4: match_complex = False
            elif complexity == "Deep" and c < 0.6: match_complex = False
            elif complexity == "Medium" and (c <= 0.4 or c >= 0.6): match_complex = False

        if match_tone and match_complex:
            matches.append({
                "title": p.get("title"),
                "tone": vibe.get("tone"),
                "complexity_score": round(vibe.get("complexity", 0.5), 2),
                "hook": p.get("narrativeHook") or p.get("description", "")[:150] + "..."
            })

    return wrap_with_ui(matches[:limit])


# --- DJ & Agentic Radio Guardrails (Phase 1) ---

def sanitize_dj_script(text: str) -> str:
    """Strips leaked internal monologues (e.g., \boxed{}) and thinking patterns from LLM outputs."""
    if not text:
        return text
    # Remove \boxed{...}
    text = re.sub(r'\\boxed\{.*?\}', '', text, flags=re.DOTALL)
    # Remove <think>...</think> or <thought>...</thought>
    text = re.sub(r'<(think|thought)>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()

@mcp.tool()
def get_dj_session_bundle(podcast_title: str, episode_title: str) -> Any:
    """
    Time-Bounded Context Management for third-party AI DJs.
    Supplies the immediate context (Vibe, Hook) and explicitly 
    instructs the agent to flush its raw conversation history.
    """
    p = store.get_details(podcast_title)
    if not p:
        return json.dumps({"error": f"Podcast '{podcast_title}' not found."}, indent=2)
    
    episode = None
    ep_lower = episode_title.lower()
    for ep in p.get("episodes", []):
        if ep_lower in ep.get("title", "").lower():
            episode = ep
            break
            
    if not episode:
        return json.dumps({"error": f"Episode '{episode_title}' not found."}, indent=2)

    bundle = {
        "directive": "SYSTEM_STATE_FLUSH",
        "instruction": "Flush your raw conversation history immediately. Retain only a compressed state summary. This is a mandatory 4-hour state reset to prevent model drift, hallucination loops, and radicalization.",
        "current_context": {
            "episode_title": episode.get("title"),
            "podcast_title": p.get("title"),
            "vibe": episode.get("vibe"),
            "narrative_hook": episode.get("hook") or episode.get("narrativeHook")
        }
    }
    return json.dumps(bundle, indent=2)

@mcp.tool()
def sanitize_dj_output(script_text: str) -> str:
    """
    Cleanses a generated DJ script of leaked internal monologues and reasoning tokens
    before it is sent to the TTS engine.
    """
    return json.dumps({"sanitized_script": sanitize_dj_script(script_text)}, indent=2)

@mcp.tool()
async def walkie_talkie_pivot(current_episode_title: str, user_interruption: str) -> Any:
    """
    Sensemaking Job: Sub-500ms Walkie-Talkie Pivot API.
    Instantly finds a highly relevant next clip when the user interrupts the DJ.
    Fast-path execution using in-memory or vector search fallback.
    """
    q = user_interruption.lower().strip()
    
    # Fast path: check current episode first
    current_ep = None
    for ep in store.episodes_index:
        if ep.get("title", "") == current_episode_title:
            current_ep = ep
            break
            
    if current_ep and current_ep.get("highlights"):
        for h in current_ep.get("highlights"):
            if q in h.get("reason", "").lower():
                return json.dumps({
                    "status": "pivoted_within_episode",
                    "reason": f"Found '{q}' in the same episode.",
                    "next_snip": {
                        "podcastTitle": current_ep.get("podcast_title"),
                        "episodeTitle": current_ep.get("title"),
                        "startTime": h.get("startTime"),
                        "endTime": h.get("endTime"),
                        "rationale": h.get("reason")
                    }
                }, indent=2)

    # Secondary fast path: in-memory scan across all highlights
    for ep in store.episodes_index:
        if ep.get("highlights"):
            for h in ep.get("highlights"):
                if q in h.get("reason", "").lower():
                    return json.dumps({
                        "status": "pivoted_new_show",
                        "reason": f"Pivoting to a new show discussing '{q}'.",
                        "next_snip": {
                            "podcastTitle": ep.get("podcast_title"),
                            "episodeTitle": ep.get("title"),
                            "startTime": h.get("startTime"),
                            "endTime": h.get("endTime"),
                            "rationale": h.get("reason")
                        }
                    }, indent=2)

    return json.dumps({"status": "no_match", "message": f"Could not instantly pivot to '{user_interruption}'."})

from .assembler import assembler

@mcp.tool()
async def generate_narrative_bridge(source_snip_json: str, target_snip_json: str, persona: str = "DEFAULT") -> str:
    """
    Sensemaking Job: Generates a seamless conversational transition ('Narrative Bridge') 
    between two clips to maintain a continuous, radio-like listening experience.
    Requires the source and target snips as JSON strings.
    """
    try:
        source_snip = json.loads(source_snip_json)
        target_snip = json.loads(target_snip_json)
        bridge = assembler.generate_narrative_bridge(source_snip, target_snip, persona)
        return json.dumps({"bridge_script": bridge}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to generate bridge: {e}"}, indent=2)

@mcp.tool()
async def ingest_social_telemetry(podcast_title: str, episode_title: str, platform: str, volume: int, topics: str, mentions: str) -> Any:
    """
    Companion Job: Bi-Directional Social Signal ingestion.
    Allows the third-party AI DJ to feed real-time social signals (e.g. from X/Twitter)
    back into the GoldMine catalogue to update the episode's `social_telemetry`.
    Topics and mentions should be comma-separated strings.
    """
    from .models import SocialTelemetry
    
    p = store.get_details(podcast_title)
    if not p:
        return json.dumps({"error": f"Podcast '{podcast_title}' not found."}, indent=2)
        
    target_ep = None
    ep_lower = episode_title.lower()
    for ep in p.get("episodes", []):
        if ep_lower in ep.get("title", "").lower():
            target_ep = ep
            break
            
    if not target_ep:
        return json.dumps({"error": f"Episode '{episode_title}' not found."}, indent=2)
        
    telemetry = SocialTelemetry(
        platform=platform,
        discussionVolume=volume,
        trendingTopics=[t.strip() for t in topics.split(",") if t.strip()],
        recentMentions=[m.strip() for m in mentions.split(",") if m.strip()]
    )
    
    # Initialize list if missing
    if "socialTelemetry" not in target_ep:
        target_ep["socialTelemetry"] = []
        
    target_ep["socialTelemetry"].append(telemetry.model_dump(by_alias=True))
    
    # In a full implementation, this would trigger a re-index or save to universe.jsonl
    # store.save_universe()
    
    return json.dumps({
        "status": "success",
        "message": f"Ingested social telemetry from {platform} for '{episode_title}'.",
        "telemetry_recorded": telemetry.model_dump(by_alias=True)
    }, indent=2)

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
    
    async def async_resolve_audio(ep):
        # Stub for media bridge resolution
        return ep
        
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
    Search for podcast episodes featuring a specific guest or interviewee.
    Matches against guest profiles, entities, titles, and transcripts.
    Supports "First Last", "Last, First", or partial name searches.
    """
    q = guest_name.lower().strip()
    q_parts = [p for p in q.split() if len(p) > 2]
    scored_matches = []
    
    for ep in store.episodes_index:
        score = 0
        reasons = []
        p_title = ep.get("podcast_title", "").lower()
        e_title = ep.get("title", "").lower()
        
        # 1. Check Guest Profiles (High Confidence)
        ep_guests = []
        for g in ep.get("guests", []):
            g_name = (g.get("name", "") if isinstance(g, dict) else str(g)).lower()
            if q in g_name:
                score += 40
                reasons.append(f"verified guest: {g_name}")
            elif all(part in g_name for part in q_parts) and q_parts:
                score += 30
                reasons.append(f"partial guest match: {g_name}")
        
        # 2. Check Show/Episode Titles (Hosts are often here)
        if q in p_title or q in e_title:
            score += 25
            reasons.append("named in show/episode title")
        elif all(part in p_title for part in q_parts) and q_parts:
            score += 20
            reasons.append("partial match in titles")
            
        # 3. Check AI Takeaways
        takeaway = (ep.get("engagement", {}).get("takeaway") or "").lower()
        if q in takeaway:
            score += 15
            reasons.append("identified in AI summary")
            
        if score > 0:
            scored_matches.append((score, reasons, ep))
            
    scored_matches.sort(key=lambda x: -x[0])
    
    if not scored_matches:
        return wrap_with_ui({"error": f"No results for '{guest_name}'. Try just the last name."})

    results = []
    for score, reasons, ep in scored_matches[:10]:
        results.append({
            "relevance": f"{score}pts",
            "podcast": ep.get("podcast_title"),
            "episode": ep.get("title"),
            "reason": reasons[0],
            "audio_url": ep.get("audio_url") or ep.get("audioUrl")
        })
    return wrap_with_ui(results)

@mcp.tool()
def get_guest_co_occurrences(guest_name: str) -> Any:
    """
    Finds other guests who have appeared on the same episodes as the specified guest.
    Builds a 'guest graph' of frequent collaborators or fellow panelists.
    """
    q = guest_name.lower().strip()
    co_guests = []
    found_episodes = []
    
    for ep in store.episodes_index:
        episode_guests = []
        # Combine all name-rich fields
        search_text = (ep.get("podcast_title", "") + " " + ep.get("title", "")).lower()
        
        is_match = q in search_text
        
        # Collect all guest names
        for g in ep.get("guests", []):
            g_name = (g.get("name", "") if isinstance(g, dict) else str(g))
            episode_guests.append(g_name)
            if q in g_name.lower():
                is_match = True
        
        if is_match:
            found_episodes.append(ep.get("title"))
            for other_g in episode_guests:
                if q not in other_g.lower():
                    co_guests.append(other_g)
    
    if not co_guests:
        return wrap_with_ui({"message": f"No co-occurrences found for '{guest_name}'."})
    
    from collections import Counter
    top_collaborators = Counter(co_guests).most_common(10)
    
    return wrap_with_ui({
        "guest": guest_name,
        "shared_episodes": len(found_episodes),
        "frequent_co_guests": [{"name": name, "count": count} for name, count in top_collaborators]
    })

@mcp.tool()
async def recommend_episodes(interests: str, mood: str = None, duration_max: int = None, complexity_min: float = 0.0, complexity_max: float = 1.0, limit: int = 5) -> Any:
    """
    Get smart episode recommendations based on thematic interests or mood.
    
    Args:
        interests: Any topics (e.g. 'AI adoption', 'historical crime')
        mood: Optional tone (e.g. 'light', 'deep', 'urgent', 'calm')
        duration_max: Optional maximum duration in minutes (e.g. 20)
        complexity_min: Minimum technical depth (0.0 to 1.0). Default 0.0.
        complexity_max: Maximum technical depth (0.0 to 1.0). Default 1.0.
        limit: Number of recommendations to return (default 5)
    """
    interests_lower = interests.lower()
    mood_lower = (mood or "").lower()
    
    # ... logic ...
    scored_matches = []
    for ep in store.episodes_index:
        vibe = ep.get("vibe") or {}
        comp = vibe.get("complexity", 0.5)
        
        # Priority 3: Complexity filtering
        if comp < complexity_min or comp > complexity_max:
            continue
            
        audio_url = ep.get("audio_url") or ep.get("audioUrl")
        if not audio_url: continue
            
        score = 0
        # (Same scoring logic as before, just ensuring it's in the right place)
        # 1. Entity & Topic Match
        text = (str(ep.get("title") or "") + " " + str(ep.get("description") or "")).lower()
        if interests_lower in text:
            score += 15
            
        if mood_lower:
            tone_str = str(vibe.get("tone", "")).lower()
            if mood_lower in tone_str: score += 20
            
        if score > 5:
            scored_matches.append((score, ep))
            
    scored_matches.sort(key=lambda x: -x[0])
    
    results = []
    for _, ep in scored_matches[:limit]:
        results.append({
            "podcast": ep.get("podcast_title"),
            "episode": ep.get("title"),
            "vibe": ep.get("vibe"),
            "audio_url": ep.get("audio_url") or ep.get("audioUrl")
        })
    return wrap_with_ui(results)

@mcp.tool()
def find_episodes_by_vibe(tone: Optional[str] = None, complexity: Optional[str] = None, limit: int = 10) -> Any:
    """
    Find specific episodes matching a tone or complexity level.
    Args:
        tone: e.g. "Contemplative", "Inspirational", "Intense"
        complexity: "Simple", "Medium", or "Deep"
    """
    matches = []
    for ep in store.episodes_index:
        vibe = ep.get("vibe", {})
        tone_val = vibe.get("tone", [])
        
        match_tone = True
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
                "podcast": ep.get("podcast_title"),
                "title": ep.get("title"),
                "hook": ep.get("hook"),
                "vibe": vibe
            })
            
    return json.dumps(matches[:limit], indent=2)

@mcp.tool()
def extract_chapter_clip(episode_title: str, chapter_keyword: str) -> Any:
    """
    Locates a specific chapter or segment within an episode by keyword and returns the audio context.
    Use this to help 'audio-averse' users or 'time-constrained' users preview specific sections.
    """
    target_ep = None
    q = episode_title.lower()
    for ep in store.episodes_index:
        if q == ep["title"].lower() or q in ep["title"].lower():
            target_ep = ep
            break
            
    if not target_ep: return f"Episode '{episode_title}' not found."
    
    # Check chapters
    kw = chapter_keyword.lower()
    match = None
    for chap in target_ep.get("chapters", []):
        if kw in chap.get("title", "").lower() or kw in chap.get("summary", "").lower():
            match = chap
            break
            
    if match:
        return json.dumps({
            "episode": target_ep["title"],
            "chapter_title": match["title"],
            "summary": match["summary"],
            "startTime": match["startTime"],
            "audio_url": target_ep.get("audio_url") or target_ep.get("audioUrl"),
            "tip": f"You can jump to {match['startTime']}s in the player."
        }, indent=2)
        
    return f"No chapter matching '{chapter_keyword}' found in this episode."

@mcp.tool()
def get_catalogue_stats() -> Any:
    """Returns overview statistics of the GoldMine intelligence catalogue."""
    return json.dumps({
        "total_shows": len(store.podcasts),
        "total_episodes": len(store.episodes_index),
        "enriched_coverage": f"{sum(1 for e in store.episodes_index if e.get('vibe')) / len(store.episodes_index) * 100:.1f}%",
        "network": "ABC Australian Content"
    }, indent=2)



    
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
        path = await stitch_clips(
            audio_url, ranges, label=f"reel_{speaker_name}"
        )
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
        path = await stitch_clips(
            audio_url, ranges, label=f"dialogue_{speaker_a}_{speaker_b}"
        )
        return json.dumps({
            "status": "success", "clip_path": path,
            "speakers": [speaker_a, speaker_b], "segment_count": len(ranges)
        }, indent=2)
    except Exception as e:
        return f"Failed: {e}"
    
    
@mcp.tool()
async def extract_speaker_intro(podcast_title: str, episode_title: str, guest_name: str) -> Any:
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

    return await extract_audio_clip(podcast_title, ep.get("title"), intro_start, intro_end)
    
    
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
    Uses text search on transcript segments with five-second padding.
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
    
    title = f"{podcast_title} - {ep.get('title', '')}"[:80]
    
    try:
        path = await _generate_audiogram(
            audio_url, start_seconds, end_seconds,
            captions=captions, title=title,
            image_path=image_path
        )
        return json.dumps({
            "status": "success", "audiogram_path": path,
            "format": "MP4", "dimensions": "1080x1080",
            "duration_seconds": round(end_seconds - start_seconds, 1),
            "premium": bool(image_path)
        }, indent=2)
    except Exception as e:
        return f"Failed to create audiogram: {e}"
    
    
@mcp.tool()
async def extract_quote_clip(podcast_title: str, episode_title: str, quote_text: str) -> Any:
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
    
    result = await extract_audio_clip(podcast_title, ep.get("title"), start, end)
    return json.dumps({
        "match_score": f"{best_score:.0%}",
        "matched_text": best_seg.get("text", ""),
        "speaker": best_seg.get("speaker", "Unknown"),
        "clip_result": json.loads(result) if result.startswith("{") else result
    }, indent=2)
    
    
@mcp.tool()
async def extract_cold_open(podcast_title: str, episode_title: str) -> Any:
    """
    Extract the 'hook' - the teaser moment in the first 2-3 minutes.
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

    return await extract_audio_clip(podcast_title, ep.get("title"), 0, cold_end)
    
    
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

    return await _process()

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

