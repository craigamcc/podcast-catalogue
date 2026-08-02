import json
import os
import random
from typing import List, Dict, Any, Optional
from .models import Podcast, Episode, Highlight
from .ai_enricher import get_engine
from .config import data_path

class DJTriageService:
    def __init__(self, universe_path: str = None):
        self.universe_path = universe_path or data_path("universe.jsonl")
        self.podcasts: List[Podcast] = []
        self._load_universe()

    def _load_universe(self):
        if not os.path.exists(self.universe_path):
            print(f"⚠️ Universe not found at {self.universe_path}")
            return
        
        with open(self.universe_path, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        self.podcasts.append(Podcast.model_validate_json(line))
                    except Exception as e:
                        print(f"⚠️ Error loading podcast: {e}")

    async def curate_session(self, prompt: Optional[str] = None, mode: str = "DEFAULT", limit: int = 5) -> Dict[str, Any]:
        """
        The 'Brain' of the AI DJ.
        Assembles a sequence of snips based on user goals/prompts.
        """
        # Step 4: Relevance Scoring & Personalization
        # For now, we prioritize shows with high-quality highlights and specific vibe matches
        candidates = []
        
        for p in self.podcasts:
            for ep in p.episodes:
                # Prioritize enriched episodes
                if ep.highlights:
                    for h in ep.highlights:
                        if mode == "WATERCOOLER" and h.category not in ("STAT", "QUOTE"):
                            continue
                            
                        # Priority Weighting: PEAK = 1.0, QUOTE = 0.9, STAT = 0.8, GENERAL = 0.5
                        weight = 0.5
                        if h.category == "PEAK": weight = 1.0
                        elif h.category == "QUOTE": weight = 0.9
                        elif h.category == "STAT": weight = 0.8
                        
                        candidates.append({
                            "podcast": p,
                            "episode": ep,
                            "highlight": h,
                            "weight": weight
                        })

        # Logic: Sort by weight, then shuffle top pool for diversity
        candidates.sort(key=lambda x: x["weight"], reverse=True)
        top_pool = candidates[:limit*3]
        random.shuffle(top_pool)

        
        selected_snips = []
        seen_shows = set()
        total_duration = 0
        
        for cand in candidates:
            if len(selected_snips) >= limit:
                break
                
            p = cand["podcast"]
            # Diversity Rule: No more than 2 snips from the same show
            if list(seen_shows).count(p.title) >= 2:
                continue
                
            ep = cand["episode"]
            h = cand["highlight"]
            
            origin = p.origin or p.source_organization or "an unspecified source"
            
            snip = {
                "id": f"snip-{ep.title}-{h.start_time}",
                "episodeTitle": ep.title,
                "podcastTitle": p.title,
                "audioUrl": ep.audio_url or "",
                "startTime": h.start_time,
                "endTime": h.end_time,
                "rationale": h.reason,
                "provenanceWatermark": f"According to {origin}...",
                "confidenceByGoal": { "Relevance": 0.95 }
            }
            
            selected_snips.append(snip)
            seen_shows.add(p.title)
            total_duration += (h.end_time - h.start_time)

        return {
            "id": f"session-{random.randint(1000, 9999)}",
            "title": prompt if prompt else "Your Intelligence Triage",
            "totalDuration": total_duration,
            "snips": selected_snips,
            "generatedAt": "2024-04-21T00:00:00Z", # Mock date
            "userPrompt": prompt
        }

# Global singleton for the HTTP bridge
triage_service = DJTriageService()
