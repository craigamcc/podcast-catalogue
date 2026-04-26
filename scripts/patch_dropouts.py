import os
import json
import asyncio
from podcast_catalogue.ai_enricher import get_engine
from podcast_catalogue.models import Podcast, Vibe, TargetAudience

async def patch_dropouts():
    input_file = "data/podcasts_450_full_intelligence.jsonl"
    output_file = "data/podcasts_450_full_intelligence.jsonl.patched"
    
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return

    # Use Gemini for patching
    engine = get_engine(provider="gemini")
    
    patched_count = 0
    total_count = 0
    
    with open(input_file, "r") as f_in, open(output_file, "w") as f_out:
        for line in f_in:
            total_count += 1
            data = json.loads(line)
            p = Podcast(**data)
            
            # Check for 'Signal Dropout' (vibe is null)
            if not p.vibe or not p.narrative_hook:
                print(f"🔍 Rescuing signal for: {p.title}")
                try:
                    p_data = await engine.analyze_podcast(p.description, p.title)
                    if p_data:
                        if p_data.get("narrative_hook"):
                            p.narrative_hook = p_data["narrative_hook"]
                        if p_data.get("vibe"):
                            p.vibe = Vibe(**p_data["vibe"])
                        ta = p_data.get("targetAudience") or p_data.get("target_audience")
                        if ta:
                            p.target_audience = TargetAudience(**ta)
                        rs = p_data.get("recommendationScenarios") or p_data.get("recommendation_scenarios")
                        if rs:
                            p.recommendation_scenarios = rs
                        
                        patched_count += 1
                        print(f"  ✨ Signal Captured: {p.vibe.tone if p.vibe else 'Success'}")
                except Exception as e:
                    print(f"  ❌ Retry failed for {p.title}: {e}")
            
            f_out.write(json.dumps(p.model_dump(by_alias=True)) + "\n")

    # Swap files
    os.rename(output_file, input_file)
    print(f"✅ Patching complete. {patched_count} signals rescued out of {total_count} records.")

if __name__ == "__main__":
    asyncio.run(patch_dropouts())
