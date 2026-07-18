import os
import aiohttp
import asyncio
import base64
from typing import Optional, Dict

class SpotifyResolver:
    """
    Resolves ABC podcast episodes to Spotify Episode URIs using the Spotify Search API.
    Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env.
    """
    def __init__(self):
        self.client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        self.client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        self.token = None
        self._cache: Dict[str, str] = {}

    async def _get_token(self, session: aiohttp.ClientSession) -> Optional[str]:
        if self.token:
            return self.token
        
        if not self.client_id or not self.client_secret:
            return None

        auth_str = f"{self.client_id}:{self.client_secret}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        
        url = "https://accounts.spotify.com/api/token"
        headers = {"Authorization": f"Basic {auth_b64}"}
        data = {"grant_type": "client_credentials"}
        
        async with session.post(url, headers=headers, data=data) as resp:
            if resp.status == 200:
                res = await resp.json()
                self.token = res.get("access_token")
                return self.token
            else:
                print(f"  ⚠️ Spotify Auth Failed: {resp.status}")
                return None

    async def resolve_episode(self, session: aiohttp.ClientSession, podcast_title: str, episode_title: str) -> Optional[str]:
        """Finds the Spotify URI for an episode."""
        cache_key = f"{podcast_title}:{episode_title}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        token = await self._get_token(session)
        if not token:
            # Fallback to a deterministic mock ID for development if keys missing
            # In production, this would return None or use a scraper
            return f"spotify:episode:MOCK_{base64.b64encode(cache_key.encode()).decode()[:10]}"

        # Construct search query
        # We search for "episode_title" and include the podcast name in the query for precision
        query = f"episode:\"{episode_title}\" show:\"{podcast_title}\""
        url = "https://api.spotify.com/v1/search"
        params = {
            "q": query,
            "type": "episode",
            "market": "AU",
            "limit": 1
        }
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("episodes", {}).get("items", [])
                    if items:
                        uri = items[0].get("uri")
                        self._cache[cache_key] = uri
                        return uri
        except Exception as e:
            print(f"  ⚠️ Spotify Search Error: {e}")
            
        return None

# Global instance for shared cache
resolver = SpotifyResolver()
