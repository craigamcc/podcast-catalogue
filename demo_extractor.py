"""
demo_extractor.py - Actionable Demo Script

This script demonstrates the Semantic Audio Extraction Suite
by dynamically finding a compelling moment and generating shareable clips.
"""

import json
import time

# Use the direct MCP tools
from podcast_catalogue.server import (
    search_transcripts,
    extract_cold_open,
    create_audiogram
)

def print_header(title):
    print(f"\n{'='*70}")
    print(f"🎬 {title}")
    print(f"{'='*70}")

def main():
    print_header("Scenario: Creating a shareable social media clip from a podcast")
    
    # 1. We know 'Science Friction' has transcripts. Let's do a cold open.
    podcast_title = "Science Friction - ABC listen"
    episode_title = "05 | The Challenger"  # Partial match should work
    
    print("\n[Step 1] Extracting the 'Cold Open' hook...")
    print(f"Calling: extract_cold_open('{podcast_title}', '{episode_title}')")
    
    start_time = time.time()
    res = extract_cold_open(podcast_title, episode_title)
    try:
        data = json.loads(res)
        print(f"✅ Success! (Took {time.time() - start_time:.1f}s)")
        print(f"   Clip Path: {data['clip_path']}")
        print(f"   Duration:  {data.get('duration_seconds', '?')}s")
    except Exception as e:
        print(f"❌ Failed to parse JSON: {res} ({e})")

    print("\n[Step 2] Let's find a specific quote about 'science'...")
    print(f"Calling: search_transcripts('science')")
    start_time = time.time()
    res2 = search_transcripts("science")
    try:
        search_data = json.loads(res2)
        if isinstance(search_data, list) and len(search_data) > 0:
            best_episode = search_data[0]
            if best_episode.get("matching_segments"):
                best_match = best_episode["matching_segments"][0]
                print(f"✅ Found interesting quote in '{best_episode['title'][:50]}...' (Took {time.time() - start_time:.1f}s)")
                print(f"   \"{best_match['text']}\"")
                print(f"   (Speaker: {best_match.get('speaker', 'Unknown')}, Time: {best_match.get('start')}s)")
                
                # Use that exact quote for the next steps
                clip_start = max(0, float(best_match["start"]) - 2.0)
                clip_end = clip_start + 15.0 # Generate a 15-second audiogram
                
            print("\n[Step 3] Generating a standard Audiogram...")
            start_time = time.time()
            res3 = create_audiogram(
                best_episode["podcast_title"], 
                best_episode["title"], 
                clip_start, 
                clip_end
            )
            
            try:
                audio_data = json.loads(res3)
                print(f"✅ Success! (Took {time.time() - start_time:.1f}s)")
                print(f"   Audiogram Path: {audio_data.get('audiogram_path')}")
            except Exception as e:
                print(f"❌ Failed: {e}")
                print(f"   Raw output: {res3}")

            print("\n[Step 4] PREVIEW: Premium AI-Visual Audiogram")
            print("1. Analyzing clip for visual theme...")
            
            # Note: In a production scenario, we'd call an image generation API here.
            # For the demo, we show the prompt generation logic.
            from podcast_catalogue.ai_enricher import generate_image_prompt
            import asyncio
            import aiohttp
            import certifi
            import ssl

            async def get_prompt():
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                    segments = best_episode.get("matching_segments", [])[0:10]
                    return await generate_image_prompt(session, segments)

            img_prompt = asyncio.run(get_prompt())
            print(f"✨ AI Visual Prompt Generated:")
            print(f"   \"{img_prompt}\"")
            print("   (Next: Generate image with this prompt and pass to create_audiogram)")

        else:
            print("No matching quotes found.")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n✨ Demo Complete ✨")
    print("Standard clips are ready in data/clips/")

if __name__ == "__main__":
    main()
