"""
Daisy Adapter — Transforms Prism's internal data model into the
Daisy-Podcasts end-user app's ideal consumption format.

This is a "Prism Client Lens": a projection of Prism's rich semantic
data into the specific shape a downstream AI agent needs.

Prism (internal)  →  Daisy Adapter  →  Daisy App
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional


def _slugify(text: str) -> str:
    """Generate a URL-safe slug from a title."""
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:60]


def _extract_keywords(podcast: Dict[str, Any]) -> List[str]:
    """
    Synthesize keywords from multiple Prism data sources:
    - Episode entities (Qwen-extracted)
    - Vibe tone
    - Genre tags
    - Target audience interests
    """
    keywords = set()

    # From vibe tone
    vibe = podcast.get("vibe") or {}
    tone = vibe.get("tone", "")
    if tone:
        keywords.add(tone.lower())

    # From genres
    for g in (podcast.get("appleGenres") or []):
        keywords.add(g.lower())
    if podcast.get("primaryGenre"):
        keywords.add(podcast["primaryGenre"].lower())

    # From target audience interests
    ta = podcast.get("targetAudience") or {}
    for interest in ta.get("interests", []):
        keywords.add(interest.lower())

    # From episode entities (top recurring ones across episodes)
    entity_counts: Dict[str, int] = {}
    for ep in podcast.get("episodes", []):
        for ent in ep.get("entities", []):
            normalized = ent.lower().strip()
            entity_counts[normalized] = entity_counts.get(normalized, 0) + 1

    # Take entities that appear in 2+ episodes (recurring themes)
    for ent, count in sorted(entity_counts.items(), key=lambda x: -x[1]):
        if count >= 2 or len(keywords) < 5:
            keywords.add(ent)
        if len(keywords) >= 12:
            break

    return sorted(keywords)


def _normalize_vibe(vibe: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize Prism's vibe format to Daisy's expected format.
    
    Prism:  { "tone": "Inspirational", "complexity": 0.5, "pace": "Fast" }
    Daisy:  { "tone": ["Inspirational"], "complexity": 0.5, "pace": "Fast" }
    
    Key difference: Daisy expects tone as an Array of strings.
    """
    if not vibe:
        return {"tone": ["General"], "complexity": 0.5, "pace": "Medium"}

    tone = vibe.get("tone", "General")
    # Prism stores tone as a single string; Daisy wants an array
    if isinstance(tone, str):
        tone_list = [tone]
    elif isinstance(tone, list):
        tone_list = tone
    else:
        tone_list = ["General"]

    # Normalize pace to one of the 3 allowed values
    pace = vibe.get("pace", "Medium")
    if pace not in ("Fast", "Medium", "Slow"):
        pace = "Medium"

    return {
        "tone": tone_list,
        "complexity": vibe.get("complexity", 0.5),
        "pace": pace
    }


def _infer_publisher(podcast: Dict[str, Any]) -> str:
    """Infer publisher from URL patterns or title."""
    if podcast.get("abcPodcastPage"):
        return "ABC (Australian Broadcasting Corporation)"
    title = podcast.get("title", "")
    if "ABC" in title:
        return "ABC"
    return "Independent"


def _estimate_frequency(episodes: List[Dict[str, Any]]) -> str:
    """Estimate publishing frequency from episode dates."""
    # Simple heuristic: if we have many episodes, assume regular
    count = len(episodes)
    if count >= 100:
        return "Daily"
    elif count >= 20:
        return "Weekly"
    elif count >= 5:
        return "Fortnightly"
    return "Irregular"


def _estimate_episode_length(episodes: List[Dict[str, Any]]) -> str:
    """Estimate typical episode length from durations."""
    durations = []
    for ep in episodes:
        d = ep.get("duration")
        if d:
            try:
                durations.append(int(d))
            except (ValueError, TypeError):
                pass

    if not durations:
        return "Unknown"

    avg_seconds = sum(durations) / len(durations)
    minutes = int(avg_seconds / 60)

    if minutes < 15:
        return f"{minutes} mins"
    elif minutes < 45:
        return f"{minutes} mins"
    else:
        return f"{minutes} mins"


def _transform_chapter(ch: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a Prism chapter to Daisy's chapter format."""
    return {
        "title": ch.get("title", ""),
        "summary": ch.get("summary", ""),
        "startTime": ch.get("startTime", 0),
        "endTime": ch.get("endTime", 0),
    }


def _transform_timeline_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a Prism timeline item to Daisy's rich marker format."""
    return {
        "title": item.get("title", ""),
        "type": item.get("type", "CHAPTER"),
        "startTime": item.get("startTime") or item.get("start_time") or 0,
        "endTime": item.get("endTime") or item.get("end_time") or 0,
        "link": item.get("link"),
        "metadata": item.get("metadata", {})
    }


def _transform_review(review: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a Prism review to Daisy's review format."""
    return {
        "author": review.get("author", "Anonymous"),
        "rating": review.get("rating", 0),
        "content": review.get("content", ""),
    }


def _transform_highlight(hl: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a Prism highlight to Daisy's Clip/Claim format."""
    return {
        "title": hl.get("title", ""),
        "reason": hl.get("reason", ""),
        "category": hl.get("category", "GENERAL"),
        "startTime": hl.get("startTime") or hl.get("start_time") or 0,
        "endTime": hl.get("endTime") or hl.get("end_time") or 0,
        # Trust Layer
        "claimStatus": hl.get("claimStatus") or hl.get("claim_status"),
        "claimInterpreter": hl.get("claimInterpreter") or hl.get("claim_interpreter"),
        "sourceAnchor": hl.get("sourceAnchor") or hl.get("source_anchor"),
        "spotifyDeepLink": hl.get("sourceAnchor", {}).get("spotifyDeepLink") or hl.get("source_anchor", {}).get("spotify_deep_link"),
    }


def _build_entity_graph(podcast: Dict[str, Any]) -> List[str]:
    """
    Build a show-level entity graph from episode-level entities.
    Returns deduplicated, sorted list of all entities mentioned across episodes.
    Useful for cross-show linking ("Who else covered Trump this week?").
    """
    entities: Dict[str, int] = {}
    for ep in podcast.get("episodes", []):
        for ent in ep.get("entities", []):
            key = ent.strip()
            entities[key] = entities.get(key, 0) + 1
    # Sort by frequency (most mentioned first)
    return [k for k, _ in sorted(entities.items(), key=lambda x: -x[1])]


def transform_episode(ep: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a single Prism episode record into Daisy's consumption format.
    """
    result = {
        "title": ep.get("title", "Untitled"),
        "description": ep.get("description") or ep.get("narrativeHook") or "",
        "duration": str(ep.get("duration", "0")),
        "url": ep.get("audioUrl") or ep.get("url") or "",
        "audioUrl": ep.get("audioUrl") or "",
        "publishedAt": ep.get("publishedAt") or None,
        "narrativeHook": ep.get("narrativeHook") or "",
        "vibe": _normalize_vibe(ep.get("vibe")),
        "entities": ep.get("entities", []),
        "chapters": [_transform_chapter(ch) for ch in ep.get("chapters", [])],
        "timeline": [_transform_timeline_item(item) for item in ep.get("timeline", [])],
        "highlights": [_transform_highlight(hl) for hl in ep.get("highlights", [])],
        
        # Editorial Trust Layer (schema.org names)
        "genre": ep.get("genre"),
        "contentRating": ep.get("contentRisk") or ep.get("content_risk"),
        "claimInterpreter": ep.get("aiProvenance") or ep.get("ai_provenance"),
        "expires": ep.get("expires"),
        "contentReferenceTime": ep.get("contentReferenceTime") or ep.get("content_reference_time"),
    }
    return result


def transform_podcast(podcast: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a single Prism podcast record into Daisy's ideal format.
    
    This is the core projection — it maps Prism's rich, flat structure
    into Daisy's structured, agent-optimized shape.
    """
    title = podcast.get("title", "Untitled")
    episodes = podcast.get("episodes", [])

    # Build consolidated links object
    links = {}
    if podcast.get("abcPodcastPage"):
        links["web"] = podcast["abcPodcastPage"]
    if podcast.get("applePodcastPage"):
        links["apple"] = podcast["applePodcastPage"]
    if podcast.get("spotifyPodcastPage"):
        links["spotify"] = podcast["spotifyPodcastPage"]
    if podcast.get("youtubePage"):
        links["youtube"] = podcast["youtubePage"]

    return {
        "id": _slugify(title),
        "title": title,
        "publisher": podcast.get("sourceOrganization") or podcast.get("source_organization") or _infer_publisher(podcast),
        "hostInformation": podcast.get("hostInformation") or None,
        "description": podcast.get("description") or "",
        "genre": podcast.get("genre") or podcast.get("primaryGenre") or (podcast.get("appleGenres") or [None])[0],
        "language": podcast.get("language") or "English",

        "narrativeHook": podcast.get("narrativeHook") or "",
        "keywords": _extract_keywords(podcast),

        "vibe": _normalize_vibe(podcast.get("vibe")),

        "targetAudience": podcast.get("targetAudience") or {
            "interests": [],
            "ageGroups": ["Adults"],
            "location": {"country": "Australia", "state": None, "city": None}
        },

        "recommendationScenarios": podcast.get("recommendationScenarios") or [],
        "recommendationReasons": podcast.get("recommendationReasons") or [],

        "links": links,

        "rating": podcast.get("averageRating"),
        "ratingCount": podcast.get("ratingCount"),
        "frequency": _estimate_frequency(episodes),
        "episodeLength": _estimate_episode_length(episodes),
        "isPopular": podcast.get("isPopular", False),

        # Editorial Trust Layer
        "license": podcast.get("license"),
        "licenseUrl": podcast.get("licenseUrl") or podcast.get("license_url"),
        "sourceOrganization": podcast.get("sourceOrganization") or podcast.get("source_organization"),

        # Enhanced fields for discussion show & live chat
        "reviews": [_transform_review(r) for r in podcast.get("reviews", [])],
        "entityGraph": _build_entity_graph(podcast),

        "episodes": [transform_episode(ep) for ep in episodes],
    }


def export_daisy_json(podcasts_data: List[Dict[str, Any]], indent: int = 2) -> str:
    """
    Export the full catalogue as a JSON array in Daisy's format.
    
    Args:
        podcasts_data: List of raw Prism podcast dicts (from JSONL)
        indent: JSON indentation (2 for readable, None for compact)
    
    Returns:
        JSON string in Daisy's expected format
    """
    transformed = [transform_podcast(p) for p in podcasts_data]
    return json.dumps(transformed, indent=indent, ensure_ascii=False)


def export_daisy_jsonl(podcasts_data: List[Dict[str, Any]]) -> str:
    """Export as newline-delimited JSON (one Daisy record per line)."""
    lines = []
    for p in podcasts_data:
        lines.append(json.dumps(transform_podcast(p), ensure_ascii=False))
    return "\n".join(lines) + "\n"
