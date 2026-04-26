import json
import os

input_file = "/Users/craigmccosker/Developer/podcast-catalogue/data/podcasts_enriched.jsonl"
output_file = "/Users/craigmccosker/Developer/podcast-catalogue/data/podcasts_enriched_referral.jsonl"

mock_links = {
    "Conversations": "https://podcasts.apple.com/au/podcast/conversations/id80934561",
    "The Money": "https://podcasts.apple.com/au/podcast/the-money/id108819543",
    "Big Ideas": "https://podcasts.apple.com/au/podcast/big-ideas/id111100342",
    "Future Tense": "https://podcasts.apple.com/au/podcast/future-tense/id214210603",
    "All In The Mind": "https://podcasts.apple.com/au/podcast/all-in-the-mind/id73330925"
}

with open(input_file, "r") as f, open(output_file, "w") as out:
    for line in f:
        data = json.loads(line)
        title = data.get("title")
        if title in mock_links:
            data["applePodcastPage"] = mock_links[title]
        else:
            # Add a generic one for others if empty
            data["applePodcastPage"] = f"https://podcasts.apple.com/au/search?term={title.replace(' ', '+')}"
        
        out.write(json.dumps(data) + "\n")

# Replace the original for the demo
os.replace(output_file, input_file)
print("Updated podcasts_enriched.jsonl with discovery links.")
