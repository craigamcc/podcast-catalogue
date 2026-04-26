"""
Content-Based and Contextual Recommendation Engine for Podcast Catalogue.
Works with existing enriched data (no vector store required).
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional


def _score_interest_overlap(podcast: Dict[str, Any], interests: List[str]) -> float:
    """Score based on overlap between user interests and podcast target audience."""
    ta = podcast.get("targetAudience", {})
    podcast_interests = [i.lower() for i in ta.get("interests", [])]
    if not podcast_interests or not interests:
        return 0.0
    
    query_interests = [i.lower() for i in interests]
    overlap = len(set(query_interests) & set(podcast_interests))
    return overlap / max(len(query_interests), 1)


def _score_scenario_match(podcast: Dict[str, Any], scenario: str) -> float:
    """Score based on recommendation scenario match."""
    scenarios = [s.lower() for s in podcast.get("recommendationScenarios", [])]
    if not scenarios or not scenario:
        return 0.0
    return 1.0 if scenario.lower() in scenarios else 0.0


def _score_vibe_match(podcast: Dict[str, Any], tone: Optional[str] = None, max_complexity: Optional[float] = None, pace: Optional[str] = None) -> float:
    """Score based on vibe alignment."""
    vibe = podcast.get("vibe", {})
    if not vibe:
        return 0.0
    
    score = 0.0
    checks = 0
    
    if tone:
        checks += 1
        if tone.lower() in str(vibe.get("tone", "")).lower():
            score += 1.0
    
    if max_complexity is not None:
        checks += 1
        complexity = vibe.get("complexity", 0.5)
        if complexity <= max_complexity:
            score += 1.0
    
    if pace:
        checks += 1
        if pace.lower() == str(vibe.get("pace", "")).lower():
            score += 1.0
    
    return score / max(checks, 1)


def _score_genre_match(podcast: Dict[str, Any], genres: List[str]) -> float:
    """Score based on genre overlap."""
    apple_genres = [g.lower() for g in (podcast.get("appleGenres") or [])]
    if not apple_genres or not genres:
        return 0.0
    
    query_genres = [g.lower() for g in genres]
    overlap = len(set(query_genres) & set(apple_genres))
    return overlap / max(len(query_genres), 1)


def _score_popularity(podcast: Dict[str, Any]) -> float:
    """Boost score for popular or highly-rated shows."""
    score = 0.0
    if podcast.get("isPopular"):
        score += 0.3
    rating = podcast.get("averageRating", 0)
    if rating and rating >= 4.0:
        score += 0.2
    return min(score, 0.5)


def calculate_jtbd_affinities(vibe: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate Jobs To Be Done (JTBD) affinities based on podcast vibe.
    Used to align content with user situational contexts.
    """
    if not vibe:
        return {
            "Mastery": 0.5, "Commute": 0.5, "Unwind": 0.5, 
            "Company": 0.5, "Sensemaking": 0.5
        }
        
    c = vibe.get("complexity", 0.5)
    p = str(vibe.get("pace", "Medium")).lower()
    
    return {
        "Mastery": 0.9 if c > 0.7 else 0.4,
        "Commute": 0.8 if p == "energetic" else 0.5,
        "Unwind": 0.9 if (p == "slow" and c < 0.4) else 0.2,
        "Company": 0.7 if p in ["medium", "moderate"] else 0.4,
        "Sensemaking": 0.9 if c > 0.6 else 0.3
    }


def recommend(
    podcasts: Dict[str, Dict[str, Any]],
    interests: Optional[List[str]] = None,
    scenario: Optional[str] = None,
    tone: Optional[str] = None,
    pace: Optional[str] = None,
    max_complexity: Optional[float] = None,
    genres: Optional[List[str]] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Content-based + contextual recommendation.
    Returns top_k podcasts ranked by composite score.
    """
    scored = []
    
    for p in podcasts.values():
        score = 0.0
        
        # Content-based signals
        if interests:
            score += _score_interest_overlap(p, interests) * 0.3
        if genres:
            score += _score_genre_match(p, genres) * 0.2
        
        # Contextual signals
        if scenario:
            score += _score_scenario_match(p, scenario) * 0.25
        if tone or pace or max_complexity is not None:
            score += _score_vibe_match(p, tone=tone, max_complexity=max_complexity, pace=pace) * 0.15
        
        # Popularity boost
        score += _score_popularity(p) * 0.1
        
        if score > 0.0:
            vibe = p.get("vibe", {})
            affinities = calculate_jtbd_affinities(vibe)
            
            scored.append({
                "title": p.get("title", ""),
                "hook": p.get("narrativeHook", ""),
                "vibe": vibe,
                "jtbd_affinities": affinities,
                "targetAudience": p.get("targetAudience", {}),
                "recommendationScenarios": p.get("recommendationScenarios", []),
                "score": round(score, 4),
                "image_url": p.get("imageUrl", "")
            })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
