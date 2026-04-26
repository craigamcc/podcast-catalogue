import asyncio
import aiohttp
import json
import os
from podcast_catalogue.vector_store import get_db_client, get_collection, semantic_search
from podcast_catalogue.recommender import recommend
from podcast_catalogue.models import Podcast

async def run_trial():
    # 1. Load the expanded data
    podcasts = {}
    with open("data/podcasts_enriched.jsonl", "r") as f:
        for line in f:
            p = Podcast.model_validate_json(line).model_dump(by_alias=True)
            podcasts[p['title']] = p
    
    print(f"--- Prism Intelligence Trial ---")
    print(f"Database size: {len(podcasts)} shows\n")

    # 2. Vibe-Based Recommendation Test
    # Scenario: High complexity, Serious tone, Science/History
    print("Test 1: Vibe-Based Discovery")
    print("Query: 'Serious, High-Complexity Science/History'")
    results = recommend(
        podcasts, 
        tone="Serious", 
        max_complexity=0.9, 
        genres=["Science", "History"],
        top_k=3
    )
    
    for r in results:
        print(f"  [SCORE {r['score']}] {r['title']}")
        print(f"  Vibe: {r['vibe']['tone']} | Complexity: {r['vibe']['complexity']}")
        print(f"  Hook: {r['hook']}\n")

    # 3. Semantic Search Test (LanceDB)
    # Query: Specific thematic interest
    print("Test 2: Semantic Vector Search (LanceDB)")
    query = "investigations into mysterious crimes or hidden history"
    print(f"Query: '{query}'")
    
    async with aiohttp.ClientSession() as session:
        db = get_db_client()
        table = get_collection(db)
        matches = await semantic_search(session, table, query, top_k=3)
        
        for m in matches:
            print(f"  [RELEVANCE {m['relevance_score']}] {m['podcast_title']}")
            print(f"  Episode: {m['episode_title']}")
            print(f"  Snippet: {m['text_snippet']}\n")

if __name__ == "__main__":
    asyncio.run(run_trial())
