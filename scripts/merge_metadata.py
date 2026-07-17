import json
import os

INTELLIGENCE_FILE = "data/podcasts_450_full_intelligence.jsonl"
ENRICHED_METADATA_FILE = "data/podcasts_450_metadata_enriched.jsonl"
TEMP_FILE = "data/podcasts_450_full_intelligence_merged.jsonl"

def merge_metadata():
    if not os.path.exists(ENRICHED_METADATA_FILE):
        print("Enriched metadata not found.")
        return

    # Load the repaired feeds and all metadata
    enriched_data = {}
    with open(ENRICHED_METADATA_FILE, "r") as f:
        for line in f:
            data = json.loads(line)
            title = data.get("title")
            if title:
                enriched_data[title.lower()] = data

    print(f"Loaded {len(enriched_data)} enriched shows from iTunes/ABC pulse.")

    # Merge into the intelligence file
    count = 0
    with open(INTELLIGENCE_FILE, "r") as f_in, open(TEMP_FILE, "w") as f_out:
        for line in f_in:
            data = json.loads(line)
            title = data.get("title", "")
            if title.lower() in enriched_data:
                # Merge ALL top-level fields (genres, ratings, feeds, etc.)
                extra = enriched_data[title.lower()]
                for k, v in extra.items():
                    if k != "episodes": # Don't overwrite existing rich episodes
                        data[k] = v
                count += 1
            f_out.write(json.dumps(data) + "\n")

    # Swap files
    os.replace(TEMP_FILE, INTELLIGENCE_FILE)
    print(f"Successfully performed deep merge for {count} shows into {INTELLIGENCE_FILE}.")

if __name__ == "__main__":
    merge_metadata()
