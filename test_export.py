import json
from podcast_catalogue.daisy_adapter import export_daisy_json
from podcast_catalogue.models import Podcast

podcasts = []
with open("data/podcasts_enriched.jsonl", "r") as f:
    for line in f:
        podcasts.append(Podcast.model_validate_json(line).model_dump(by_alias=True))

daisy_json = export_daisy_json(podcasts)
data = json.loads(daisy_json)
print(f"Exported {len(data)} podcasts to Daisy format.")

with open("data/daisy_abcPodcasts.ts", "w") as f:
    f.write(f"export const abcPodcasts = {json.dumps(data, indent=2)};")

print("Saved back to data/daisy_abcPodcasts.ts")

for p in data:
    if "conversations-with-richard-fidler" in p['id']:
        print(f"Title: {p['title']}")
        for ep in p['episodes'][:3]:
            print(f"  Episode: {ep['title']}")
            print(f"    Published At: {ep.get('publishedAt')}")
