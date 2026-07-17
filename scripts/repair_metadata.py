import json
import time
import requests
import os
from typing import List, Dict, Any

METADATA_PATH = "data/podcasts_450_metadata.jsonl"
OUTPUT_PATH = "data/podcasts_450_metadata_enriched.jsonl"

def search_itunes(term: str) -> str:
    """Searches iTunes API for a podcast and returns the feedUrl."""
    try:
        # Rate limiting: wait 2 seconds between calls to stay well within ToS
        time.sleep(2)
        
        url = "https://itunes.apple.com/search"
        params = {
            "term": term,
            "entity": "podcast",
            "limit": 1
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("resultCount", 0) > 0:
                return data["results"][0].get("feedUrl")
    except Exception as e:
        print(f"Error searching iTunes for '{term}': {e}")
    return None

def repair_podcasts(limit: int = 50):
    """Repairs the top N podcasts with missing feed URLs."""
    if not os.path.exists(METADATA_PATH):
        print(f"Metadata file not found: {METADATA_PATH}")
        return

    updated_podcasts = []
    
    with open(METADATA_PATH, "r") as f:
        podcasts = [json.loads(line) for line in f]

    print(f"Starting Metadata Repair for top {limit} shows...")
    
    repaired_count = 0
    for i, p in enumerate(podcasts):
        if i >= limit:
            updated_podcasts.append(p)
            continue
            
        title = p.get("title")
        current_feed = p.get("feed_url") or p.get("rss_url")
        
        if not current_feed and title:
            print(f"[{i+1}/{limit}] Repairing: {title}...")
            # Use show title + 'ABC' to improve accuracy
            feed_url = search_itunes(f"{title} ABC")
            if feed_url:
                print(f"  > Found Feed: {feed_url}")
                p["feed_url"] = feed_url
                repaired_count += 1
            else:
                print(f"  > No feed found on iTunes.")
        
        updated_podcasts.append(p)

    # Save enriched metadata
    with open(OUTPUT_PATH, "w") as f:
        for p in updated_podcasts:
            f.write(json.dumps(p) + "\n")
            
    print(f"\nRepair Complete! {repaired_count} shows enriched.")
    print(f"Saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    repair_podcasts(limit=1000)
