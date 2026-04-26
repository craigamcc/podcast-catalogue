import re
import json
import os
from podcast_catalogue.models import Podcast, TargetAudience, Location

def migrate():
    input_path = "data/podcasts_sitemap.ts"
    output_path = "data/universe.jsonl"
    
    if not os.path.exists(input_path):
        print(f"❌ Source {input_path} not found.")
        return

    with open(input_path, "r") as f:
        content = f.read()

    # Extract the MOCKED_PODCASTS array content
    array_match = re.search(r"export const MOCKED_PODCASTS: Podcast\[\] = (\[.*\]);", content, re.DOTALL)
    if not array_match:
        print("❌ Could not find MOCKED_PODCASTS array.")
        return

    array_str = array_match.group(1)
    
    # We need to turn this TS/JS object into valid JSON (handle trailing commas, unquoted keys if any)
    # Since the user provided valid-ish JSON in the file, we can try a simple clean
    cleaned_json = re.sub(r",\s*([\]}])", r"\1", array_str) # Trailing commas
    try:
        podcasts_data = json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to decode JSON: {e}")
        # Fallback to a more aggressive clean if needed
        return

    # Load existing 450+ shows if they exist
    existing_shows = []
    source_450 = "data/podcasts_450_full_intelligence.jsonl"
    if os.path.exists(source_450):
        with open(source_450, "r") as f:
            for line in f:
                if line.strip():
                    existing_shows.append(json.loads(line))

    # Merge and deduplicate by title/abcPodcastPage
    seen_urls = {p.get("abcPodcastPage") for p in podcasts_data if p.get("abcPodcastPage")}
    
    final_count = 0
    with open(output_path, "w") as f:
        # Write migrated shows first
        for p in podcasts_data:
            f.write(json.dumps(p) + "\n")
            final_count += 1
            
        # Write existing shows if not already in migrated list
        for p in existing_shows:
            if p.get("abcPodcastPage") not in seen_urls:
                f.write(json.dumps(p) + "\n")
                final_count += 1

    print(f"✅ Migration complete. {len(podcasts_data)} mocked shows merged with {len(existing_shows)} existing shows.")
    print(f"🚀 Integrated Universe: {final_count} shows written to {output_path}")

if __name__ == "__main__":
    migrate()
