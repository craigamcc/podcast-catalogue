import json
import os

INTELLIGENCE_FILE = "data/podcasts_450_full_intelligence.jsonl"
ENRICHED_METADATA_FILE = "data/podcasts_450_metadata_enriched.jsonl"
TEMP_FILE = "data/podcasts_450_full_intelligence_merged.jsonl"

def merge_metadata():
    if not os.path.exists(ENRICHED_METADATA_FILE):
        print("Enriched metadata not found.")
        return

    # Load the repaired feeds
    repaired_feeds = {}
    with open(ENRICHED_METADATA_FILE, "r") as f:
        for line in f:
            data = json.loads(line)
            title = data.get("title")
            feed_url = data.get("feed_url")
            if title and feed_url:
                repaired_feeds[title.lower()] = feed_url

    print(f"Loaded {len(repaired_feeds)} repaired feeds.")

    # Merge into the intelligence file
    count = 0
    with open(INTELLIGENCE_FILE, "r") as f_in, open(TEMP_FILE, "w") as f_out:
        for line in f_in:
            data = json.loads(line)
            title = data.get("title")
            if title and title.lower() in repaired_feeds:
                # Update the feed URL
                data["rss_url"] = repaired_feeds[title.lower()]
                count += 1
            f_out.write(json.dumps(data) + "\n")

    # Swap files
    os.replace(TEMP_FILE, INTELLIGENCE_FILE)
    print(f"Successfully merged {count} feed URLs into {INTELLIGENCE_FILE}.")

if __name__ == "__main__":
    merge_metadata()
