import sys
import asyncio
import json
import aiohttp
from bs4 import BeautifulSoup

# Add project root to sys.path
sys.path.append("/Users/craigmccosker/Developer/podcast-catalogue")

from podcast_catalogue.parser import parse_episode_page

async def debug_parse():
    url = "https://www.abc.net.au/listen/programs/conversations/surviving-white-island-stephanie-browitt/103648430"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            data = parse_episode_page(html)
            print(f"Extracted for {url}:")
            print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(debug_parse())
