import json
import os
from typing import Dict, List, Any
from podcast_catalogue.models import Podcast, Episode, EntityProfile

INPUT_FILE = "data/podcasts_450_full_intelligence.jsonl"
OUTPUT_FILE = "data/universe.jsonl"

def repair():
    print(f"🛠 Starting Foundation Repair Pass...")
    print(f"   Input: {INPUT_FILE}")
    
    unique_podcasts: Dict[str, Any] = {}
    total_processed = 0
    errors_fixed = 0
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found!")
        return

    with open(INPUT_FILE, "r") as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                # Load as raw dict first to repair anomalies
                data = json.loads(line)
                title = data.get("title")
                if not title:
                    continue
                
                # Normalization Layer: entities
                for ep in data.get("episodes", []):
                    entities = ep.get("entities")
                    if entities:
                        # Case 1: Single dictionary instead of List[dict]
                        if isinstance(entities, dict):
                            # If it's a 'hallucinated' field like main_topic, we convert it
                            # to a generic entity name if possible, or just wrap it.
                            name = entities.get("entity_name") or entities.get("name") or str(entities)
                            ep["entities"] = [{"entity_name": name, "description": str(entities)}]
                            errors_fixed += 1
                        
                        # Case 2: List containing non-dict items (str) is fine because of Union
                        # Case 3: List containing dictionaries (standard)
                
                # Logic: Keep the version with the most episodes or narrative hook
                if title not in unique_podcasts:
                    unique_podcasts[title] = data
                else:
                    existing = unique_podcasts[title]
                    # Preference: Most enriched version
                    if len(data.get("episodes", [])) > len(existing.get("episodes", [])):
                        unique_podcasts[title] = data
                    elif data.get("narrativeHook") and not existing.get("narrativeHook"):
                        unique_podcasts[title] = data

                total_processed += 1
            except Exception as e:
                print(f"   ⚠️ Skipping corrupt line: {e}")

    print(f"   Processed {total_processed} lines.")
    print(f"   Deduplicated to {len(unique_podcasts)} unique shows.")
    print(f"   Fixed {errors_fixed} entity anomalies.")

    # Validation Pass & Write
    valid_count = 0
    with open(OUTPUT_FILE, "w") as f:
        for p_data in unique_podcasts.values():
            try:
                # Round-trip through Pydantic to ensure 100% validity
                p = Podcast.model_validate(p_data)
                f.write(p.model_dump_json(by_alias=True, exclude_none=True) + "\n")
                valid_count += 1
            except Exception as e:
                print(f"   ❌ Validation failed for '{p_data.get('title')}': {e}")

    print(f"\n✅ REPAIR COMPLETE")
    print(f"   Golden Record: {OUTPUT_FILE}")
    print(f"   Rock Solid Count: {valid_count}/{len(unique_podcasts)}")

if __name__ == "__main__":
    repair()
