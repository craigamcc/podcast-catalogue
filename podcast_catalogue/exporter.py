from __future__ import annotations

import json
from typing import Iterable, List, Dict, Any, Optional

from .models import Podcast

def export_jsonl(podcasts: Iterable[Podcast]) -> str:
    """Exports as standard JSON Lines where each line is a valid JSON object."""
    lines = []
    for p in podcasts:
        lines.append(p.model_dump_json(by_alias=True, exclude_none=True))
    return "\n".join(lines) + "\n"

def export_universal_json(podcasts: Iterable[Podcast]) -> str:
    """Exports as a Universal Generic JSON array mapping directly from Pydantic schemas."""
    data = [p.model_dump(by_alias=True, exclude_none=True) for p in podcasts]
    return json.dumps(data, indent=2)

def export_tiered_json(podcasts: Iterable[Podcast], tier: int = 1) -> str:
    """
    Exports podcasts in structured tiers to optimize consumer app performance.
    
    Tier 0: Catalogue (Metadata only, for list views)
    Tier 1: Intelligence (Summary, hooks, chapters)
    Tier 2: Full Semantic (Includes full segments and transcripts)
    """
    data = []
    for p in podcasts:
        p_dict = p.model_dump(by_alias=True, exclude_none=True)
        
        if tier == 0:
            # Strip everything but summary/discovery info
            p_dict.pop("episodes", None)
            p_dict.pop("reviews", None)
            p_dict.pop("recommendationReasons", None)
            
        elif tier == 1:
            # Strip heavy audio segments and transcripts
            for ep in p_dict.get("episodes", []):
                ep.pop("segments", None)
                ep.pop("transcript", None)
        
        # Tier 2 is the full dump (default)
        data.append(p_dict)
        
    return json.dumps(data, indent=2)

def export_jsonld(podcasts: Iterable[Podcast]) -> str:
    """Exports as a Linked Data (JSON-LD) graph for generalized Agent and Search Engine traversal."""
    graph = []
    for p in podcasts:
        p_dict = p.model_dump(by_alias=True, exclude_none=True)
        # Transform generic dict into a JSON-LD compliant entity
        entity = {
            "@context": "https://schema.org",
            "@type": "PodcastSeries",
            "name": p_dict.get("title"),
            "description": p_dict.get("description"),
            "url": p_dict.get("abcPodcastPage"),
            "publisher": {
                "@type": "Organization",
                "name": "ABC"
            },
            # Map intelligence
            "abstract": p_dict.get("narrativeHook"),
            "keywords": p_dict.get("vibe", {}).get("tone", [])
        }
        graph.append(entity)
    return json.dumps({"@graph": graph}, indent=2)
