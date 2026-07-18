import json
import os
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

# Absolute imports for running as module
from podcast_catalogue.models import RegionalPulse, CanonicalEvent, StorylineUpdate
from podcast_catalogue.ai_enricher import get_engine

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
UNIVERSE_FILE = os.path.join(DATA_DIR, "universe.jsonl")
REGIONAL_PULSE_FILE = os.path.join(DATA_DIR, "regional_pulses.jsonl")

# Australian Mega-Region Mapping
MEGA_REGIONS = {
    "seqld": {
        "name": "Southeast Queensland",
        "keywords": ["brisbane", "queensland", "qld", "gold coast", "sunshine coast", "ipswich", "brookwater", "logan", "moreton bay"]
    },
    "sydney": {
        "name": "Greater Sydney Basin",
        "keywords": ["sydney", "nsw", "new south wales", "parramatta", "western sydney", "wollongong", "newcastle", "penrith", "liverpool"]
    },
    "melbourne": {
        "name": "Greater Melbourne",
        "keywords": ["melbourne", "victoria", "vic", "geelong", "bendigo", "ballarat", "mornington", "dandenong", "frankston"]
    },
    "perth": {
        "name": "Perth & Peel",
        "keywords": ["perth", "wa", "western australia", "fremantle", "joondalup", "mandurah"]
    }
}

async def synthesize_regional_pulses():
    """Main orchestration for regional master synthesis across all Mega-Regions."""
    if not os.path.exists(UNIVERSE_FILE):
        print(f"Data file not found: {UNIVERSE_FILE}")
        return

    print(f"▶ Loading signals from {UNIVERSE_FILE}...")
    
    # 1. Load Data
    podcasts = []
    with open(UNIVERSE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    podcasts.append(json.loads(line))
                except:
                    continue

    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 2. Process Each Mega-Region
    for region_id, config in MEGA_REGIONS.items():
        print(f"\n--- Processing Region: {config['name']} ({region_id}) ---")
        
        region_keywords = config["keywords"]
        region_episodes = []

        for p in podcasts:
            p_title = p.get("title", "").lower()
            # Check show-level coverage
            is_region_show = any(kw in p_title for kw in region_keywords)
            
            for ep in p.get("episodes", []):
                ep_title = ep.get("title", "").lower()
                is_region_ep = is_region_show or any(kw in ep_title for kw in region_keywords)
                
        region_keywords = config["keywords"]
        region_episodes = []

        for p in podcasts:
            p_title = p.get("title", "").lower()
            # Check show-level coverage
            is_region_show = any(kw in p_title for kw in region_keywords)
            
            for ep in p.get("episodes", []):
                ep_title = ep.get("title", "").lower()
                is_region_ep = is_region_show or any(kw in ep_title for kw in region_keywords)
                
                if is_region_ep and ep.get("publishedAt"):
                    # Only take episodes that have at least some basic AI enrichment
                    if ep.get("narrativeHook") or ep.get("engagement") or ep.get("highlights"):
                        # Extract Experts from timeline or guests
                        experts = [g.get("name") for g in ep.get("guests", []) if g.get("name")]
                        for item in ep.get("timeline", []):
                            if item.get("type") == "EXPERT" and item.get("title"):
                                experts.append(item.get("title").replace("Expert Mention: ", ""))

                        ep_data = {
                            "podcast_title": p.get("title"),
                            "title": ep.get("title"),
                            "narrative_hook": ep.get("narrativeHook") or ep.get("description", "")[:100],
                            "engagement": ep.get("engagement") or {},
                            "publishedAt": ep.get("publishedAt"),
                            "experts": list(set(experts)),
                            "source_organization": ep.get("sourceOrganization") or ep.get("source_organization") or "Unknown",
                            "authority_score": ep.get("authorityScore") or ep.get("authority_score") or 0.5
                        }
                        region_episodes.append(ep_data)

        if not region_episodes:
            print(f"  ⚠ No regional signals found for {region_id}.")
            continue

        print(f"  ✓ Found {len(region_episodes)} relevant signals.")

        # 3. Load Previous Context for Narrative Continuity
        previous_pulse = None
        if os.path.exists(REGIONAL_PULSE_FILE):
            try:
                with open(REGIONAL_PULSE_FILE, "r") as f:
                    pulses = [json.loads(line) for line in f if line.strip()]
                    region_pulses = [p for p in pulses if p.get("regionId") == region_id]
                    if region_pulses:
                        previous_pulse = region_pulses[-1]
            except Exception as e:
                print(f"  ⚠ Could not load previous pulse context: {e}")

        # 4. Trigger Synthesis
        provider = "gemini" if os.environ.get("GEMINI_API_KEY") else "ollama"
        engine = get_engine(provider=provider)
        
        region_episodes.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)
        latest_signals = region_episodes[:15] # Increased for more depth

        print(f"  🤖 Synthesizing Master Regional Pulse for '{region_id}' using {provider.upper()}...")
        try:
            pulse_data = await engine.generate_regional_master_pulse(
                region_id, 
                latest_signals, 
                previous_pulse=previous_pulse
            )
            
            if not pulse_data and provider == "gemini":
                print("  ⚠ Gemini failed. Falling back to OLLAMA...")
                engine = get_engine(provider="ollama")
                pulse_data = await engine.generate_regional_master_pulse(
                    region_id, 
                    latest_signals, 
                    previous_pulse=previous_pulse
                )

            if pulse_data and isinstance(pulse_data, dict):
                # 4. Create and Persist RegionalPulse
                regional_pulse = RegionalPulse(
                    regionId=region_id,
                    date=today_str,
                    masterSummary=pulse_data.get("masterSummary", pulse_data.get("master_summary", "No summary generated.")),
                    narrativeShifts=pulse_data.get("narrativeShifts", pulse_data.get("narrative_shifts", [])),
                    featuredEpisodes=pulse_data.get("featuredEpisodes", pulse_data.get("featured_episodes", [])),
                    canonicalEvents=[]
                )

                # Safely map canonical events, skipping malformed entries
                for ev in pulse_data.get("canonicalEvents", pulse_data.get("canonical_events", [])):
                    if not isinstance(ev, dict):
                        continue
                    eid = ev.get("eventId") or ev.get("event_id") or ev.get("id")
                    etitle = ev.get("title")
                    edesc = ev.get("description") or ev.get("summary") or ""
                    if not eid or not etitle:
                        print(f"    ⚠ Skipping malformed event: {ev}")
                        continue
                    
                    updates = []
                    raw_updates = ev.get("storylineUpdates", ev.get("storyline_updates", []))
                    for upd in raw_updates:
                        if not isinstance(upd, dict):
                            continue
                        try:
                            updates.append(StorylineUpdate(
                                updateId=upd.get("updateId") or upd.get("update_id") or f"{eid}-update",
                                episodeTitle=upd.get("episodeTitle") or upd.get("episode_title") or "Unknown",
                                date=upd.get("date") or today_str,
                                summary=upd.get("summary") or ""
                            ))
                        except Exception:
                            continue
                    
                    regional_pulse.canonical_events.append(CanonicalEvent(
                        eventId=eid,
                        title=etitle,
                        description=edesc,
                        date=today_str,
                        tags=ev.get("tags", []),
                        storylineUpdates=updates
                    ))


                
                # Save to JSONL (append mode)
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(REGIONAL_PULSE_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(regional_pulse.model_dump(by_alias=True), ensure_ascii=False) + "\n")
                
                print(f"  ✓ Successfully persisted Regional Pulse to {REGIONAL_PULSE_FILE}")
                print(f"  📝 Summary: {regional_pulse.master_summary[:100]}...")
            else:
                print(f"  ❌ Failed to generate valid pulse data for {region_id}.")
        except Exception as e:
            print(f"  ❌ Error during regional synthesis for {region_id}: {e}")

if __name__ == "__main__":
    asyncio.run(synthesize_regional_pulses())
