import sys
import asyncio
import json
import aiohttp
from bs4 import BeautifulSoup

# Add project root to sys.path
sys.path.append("/Users/craigmccosker/Developer/podcast-catalogue")

from podcast_catalogue.parser import extract_nextjs_data

async def debug_props():
    url = "https://www.abc.net.au/listen/programs/conversations/surviving-white-island-stephanie-browitt/103648430"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            next_data = extract_nextjs_data(soup)
            if not next_data:
                print("No NEXT_DATA found")
                return
            
            props = next_data.get("props", {}).get("pageProps", {})
            print("PageProps keys:", props.keys())
            
            if "data" in props:
                print("Data keys:", props["data"].keys())
                if "documentProps" in props["data"]:
                    print("DocumentProps keys:", props["data"]["documentProps"].keys())
                else:
                    # Search for any key that looks like document data
                    for k in props["data"].keys():
                        if "content" in k.lower() or "document" in k.lower():
                            print(f"Potential data key: {k}")

if __name__ == "__main__":
    asyncio.run(debug_props())
