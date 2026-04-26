import sys
import asyncio
import json

# Add project root to sys.path
sys.path.append("/Users/craigmccosker/Developer/podcast-catalogue")

from podcast_catalogue.server import get_recent_episodes, find_episodes_by_topic

async def test_tools():
    print("--- Testing find_episodes_by_topic for 'White Island' ---")
    results = await find_episodes_by_topic("White Island")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(test_tools())
