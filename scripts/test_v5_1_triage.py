import asyncio
from podcast_catalogue.dj_triage import triage_service

async def test_triage():
    print(f"📡 Testing DJ Triage Service...")
    print(f"   Universe Path: {triage_service.universe_path}")
    print(f"   Loaded Podcasts: {len(triage_service.podcasts)}")
    
    if len(triage_service.podcasts) == 0:
        print("❌ Error: No podcasts loaded!")
        return
        
    session = await triage_service.curate_session(prompt="AI and Music")
    print("\n✅ Session Curated:")
    print(f"   Title: {session['title']}")
    print(f"   Snips: {len(session['snips'])}")
    for snip in session['snips']:
        print(f"   - [{snip['podcastTitle']}] {snip['episodeTitle']} ({snip['startTime']}s - {snip['endTime']}s)")

if __name__ == "__main__":
    asyncio.run(test_triage())
