import sys
import asyncio
import json
import aiohttp
from bs4 import BeautifulSoup

# Add project root to sys.path
sys.path.append("/Users/craigmccosker/Developer/podcast-catalogue")

from podcast_catalogue.parser import extract_nextjs_data

def find_path(obj, target, path=""):
    if obj == target:
        return path
    if isinstance(obj, dict):
        for k, v in obj.items():
            res = find_path(v, target, f"{path}.{k}" if path else k)
            if res: return res
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            res = find_path(item, target, f"{path}[{i}]")
            if res: return res
    return None

async def debug_path():
    url = "https://www.abc.net.au/listen/programs/conversations"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            next_data = extract_nextjs_data(soup)
            
            target = "2026-04-24T01:00:00+00:00"
            path = find_path(next_data, target)
            print(f"Path to {target}: {path}")

if __name__ == "__main__":
    asyncio.run(debug_path())
