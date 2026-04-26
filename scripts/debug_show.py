import sys
import asyncio
import json
import aiohttp
from bs4 import BeautifulSoup

# Add project root to sys.path
sys.path.append("/Users/craigmccosker/Developer/podcast-catalogue")

from podcast_catalogue.parser import extract_nextjs_data

async def debug_show():
    url = "https://www.abc.net.au/listen/programs/conversations"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            next_data = extract_nextjs_data(soup)
            if not next_data:
                print("No NEXT_DATA")
                return
            
            props = next_data.get("props", {}).get("pageProps", {})
            collection = props.get("programCollectionPrepared", {})
            items = collection.get("items", [])
            for item in items[:3]:
                print(f"Title: {item.get('cardTitle')}")
                print(f"Label: {item.get('contentLabelPrepared')}")
                print(f"Sublabel: {item.get('contentSublabelPrepared')}")
                print("---")

if __name__ == "__main__":
    asyncio.run(debug_show())
