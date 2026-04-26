import sys
import asyncio
import json
import aiohttp
import re
from bs4 import BeautifulSoup

# Add project root to sys.path
sys.path.append("/Users/craigmccosker/Developer/podcast-catalogue")

from podcast_catalogue.parser import extract_nextjs_data

async def find_dates():
    url = "https://www.abc.net.au/listen/programs/conversations"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            next_data = extract_nextjs_data(soup)
            
            s = json.dumps(next_data)
            matches = re.findall(r'"[0-9]{4}-[0-9]{2}-[0-9]{2}[^"]*"', s)
            print("Found dates:", set(matches))

if __name__ == "__main__":
    asyncio.run(find_dates())
