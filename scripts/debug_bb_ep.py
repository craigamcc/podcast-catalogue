import sys
import asyncio
import json
import aiohttp
from bs4 import BeautifulSoup

# Add project root to sys.path
sys.path.append("/Users/craigmccosker/Developer/podcast-catalogue")

from podcast_catalogue.parser import parse_episode_page

async def debug_bb_ep():
    url = "https://www.abc.net.au/listen/programs/backgroundbriefing/02-in-search-of-the-missing-artist-the-plastic/106577676"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()
            data = parse_episode_page(html)
            print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(debug_bb_ep())
