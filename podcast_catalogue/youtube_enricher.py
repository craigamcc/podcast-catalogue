import aiohttp
import re
from typing import Optional, Dict, List, Tuple
from .models import TimelineItem, Highlight

class YouTubeEnricher:
    """
    Enriches podcast episodes with YouTube telemetry and metadata.
    Mapping: ABC Podcast Title -> YouTube Channel/Playlist
    """
    
    CHANNEL_MAPPINGS = {
        "That's Business with Alan Kohler": "PLn2RjxYNpcayVI9QrMs_DlvoCHEb1rBFG",
        "ABC Business Daily": "PLn2RjxYNpcayVI9QrMs_DlvoCHEb1rBFG",
        "If You're Listening": "@ABCNewsIndepth",
        "Conversations": "@abcaustralia"
    }

    def __init__(self):
        self._cache: Dict[str, Dict] = {}

    async def resolve_video(self, session: aiohttp.ClientSession, podcast_title: str, episode_title: str) -> Optional[Dict]:
        """
        Finds the corresponding YouTube video for an episode.
        Currently uses title matching heuristics.
        """
        playlist_id = self.CHANNEL_MAPPINGS.get(podcast_title)
        if not playlist_id:
            # Try fuzzy match or default channel
            if "Business" in podcast_title:
                playlist_id = "PLn2RjxYNpcayVI9QrMs_DlvoCHEb1rBFG"
            else:
                return None

        # In a real implementation, we would call the YouTube Data API search:
        # GET https://www.googleapis.com/youtube/v3/search?part=snippet&q={episode_title}&type=video
        
        # For this implementation, we will simulate a high-fidelity lookup
        # that returns the telemetry we audited.
        
        # MOCK DATA based on audit findings
        if "Hugh Marks" in episode_title:
            return {
                "youtube_url": "https://www.youtube.com/watch?v=MOCK_HUGH",
                "views": 1822,
                "likes": 38,
                "comments_paused": False,
                "chapters": [
                    {"title": "Introduction", "start": 0, "end": 120},
                    {"title": "The ABC Budget", "start": 120, "end": 600},
                    {"title": "Bluey and Commercial Success", "start": 600, "end": 1200}
                ]
            }
        
        if "Housing" in episode_title:
            return {
                "youtube_url": "https://www.youtube.com/watch?v=MOCK_HOUSING",
                "views": 37300,
                "likes": 594,
                "comments_paused": True,
                "chapters": [
                    {"title": "The Crisis", "start": 0, "end": 300},
                    {"title": "Superannuation Policy", "start": 300, "end": 900}
                ]
            }

        return None

    def map_chapters_to_timeline(self, chapters: List[Dict]) -> List[TimelineItem]:
        """Converts YouTube chapters to GoldMine TimelineItems."""
        timeline = []
        for ch in chapters:
            timeline.append(TimelineItem(
                title=ch["title"],
                type="CHAPTER",
                startTime=float(ch["start"]),
                endTime=float(ch["end"]),
                metadata={"source": "YouTube AI Chapters"}
            ))
        return timeline

youtube_enricher = YouTubeEnricher()
