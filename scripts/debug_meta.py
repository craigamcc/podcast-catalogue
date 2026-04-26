import sys
import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def debug_meta():
    url = "https://www.abc.net.au/listen/programs/conversations/surviving-white-island-stephanie-browitt/103648430"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all("meta"):
                if tag.get("property") or tag.get("name"):
                    print(f"{tag.get('property') or tag.get('name')}: {tag.get('content')}")

if __name__ == "__main__":
    asyncio.run(debug_meta())
