"""
Export PRISM data for the SoTA Podcast Intelligence demo.

Reads from the full intelligence JSONL and exports a consumer-ready JSON file
at the Tier 0+1 level (catalogue metadata + AI intelligence, no raw transcripts).

Usage:
    python scripts/export_sota.py [--limit 20] [--output ../AI\ Podcast/sota-app/public/catalogue.json]
"""
from __future__ import annotations

import json
import sys
import os
import argparse

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from podcast_catalogue.daisy_adapter import _normalize_vibe, _slugify


def load_enriched_data(path: str):
    """Load JSONL data from a file."""
    podcasts = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                podcasts.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return podcasts


def transform_for_sota(podcast: dict, include_segments: bool = False) -> dict:
    """
    Project a PRISM podcast record into the SoTA app's consumption format.
    
    Tier 0+1: Metadata + Intelligence (chapters, highlights, entities, vibes).
    Excludes raw transcript text and segments unless explicitly requested.
    """
    title = podcast.get("title", "Untitled")
    
    episodes = []
    for ep in podcast.get("episodes", []):
        episode_data = {
            "title": ep.get("title", "Untitled Episode"),
            "description": ep.get("description", ""),
            "publishedAt": ep.get("publishedAt"),
            "duration": str(ep.get("duration", "0")),
            "audioUrl": ep.get("audioUrl", ""),
            "url": ep.get("url", ""),
            "narrativeHook": ep.get("narrativeHook", ""),
            "vibe": _normalize_vibe(ep.get("vibe")),
            "entities": ep.get("entities", []),
            "chapters": ep.get("chapters", []),
            "highlights": ep.get("highlights", []),
            "contentHash": ep.get("contentHash"),
        }
        
        if include_segments:
            episode_data["segments"] = ep.get("segments", [])
            episode_data["transcript"] = ep.get("transcript", "")
        
        episodes.append(episode_data)
    
    return {
        "id": _slugify(title),
        "title": title,
        "description": podcast.get("description", ""),
        "hostInformation": podcast.get("hostInformation"),
        "imageUrl": podcast.get("imageUrl"),
        "language": podcast.get("language", "English"),
        
        # Distribution
        "abcPodcastPage": podcast.get("abcPodcastPage"),
        "applePodcastPage": podcast.get("applePodcastPage"),
        "spotifyPodcastPage": podcast.get("spotifyPodcastPage"),
        "youtubePage": podcast.get("youtubePage"),
        
        # Discovery
        "primaryGenre": podcast.get("primaryGenre"),
        "appleGenres": podcast.get("appleGenres"),
        "averageRating": podcast.get("averageRating"),
        "ratingCount": podcast.get("ratingCount"),
        "isPopular": podcast.get("isPopular", False),
        "isAwardWinning": podcast.get("isAwardWinning", False),
        
        # AI Intelligence
        "narrativeHook": podcast.get("narrativeHook", ""),
        "vibe": _normalize_vibe(podcast.get("vibe")),
        "targetAudience": podcast.get("targetAudience"),
        "recommendationScenarios": podcast.get("recommendationScenarios", []),
        
        # Content
        "episodes": episodes,
        "episodeCount": len(episodes),
    }


def main():
    parser = argparse.ArgumentParser(description="Export PRISM data for SoTA app")
    parser.add_argument("--input", default="data/podcasts_450_full_intelligence.jsonl",
                        help="Path to enriched JSONL input")
    parser.add_argument("--output", default="../AI Podcast/sota-app/public/catalogue.json",
                        help="Path to output JSON file")
    parser.add_argument("--limit", type=int, default=20,
                        help="Max number of shows to export (0 = all)")
    parser.add_argument("--enriched-only", action="store_true",
                        help="Only export shows that have AI-enriched episodes")
    parser.add_argument("--include-segments", action="store_true",
                        help="Include raw transcript segments (Tier 2)")
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"❌ Input file not found: {args.input}")
        sys.exit(1)
    
    print(f"📂 Loading from: {args.input}")
    raw_podcasts = load_enriched_data(args.input)
    print(f"   Loaded {len(raw_podcasts)} shows")
    
    # Filter to enriched-only if requested
    if args.enriched_only:
        raw_podcasts = [p for p in raw_podcasts if p.get("narrativeHook") or p.get("vibe")]
        print(f"   Filtered to {len(raw_podcasts)} enriched shows")
    
    # Sort: shows with enriched episodes first, then by rating
    def sort_key(p):
        has_chapters = any(ep.get("chapters") for ep in p.get("episodes", []))
        has_highlights = any(ep.get("highlights") for ep in p.get("episodes", []))
        rating = p.get("averageRating") or 0
        return (not has_chapters, not has_highlights, -rating)
    
    raw_podcasts.sort(key=sort_key)
    
    if args.limit > 0:
        raw_podcasts = raw_podcasts[:args.limit]
    
    # Transform
    exported = [transform_for_sota(p, include_segments=args.include_segments) for p in raw_podcasts]
    
    # Write output
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(exported, f, indent=2, ensure_ascii=False)
    
    size_kb = os.path.getsize(args.output) / 1024
    ep_count = sum(len(p["episodes"]) for p in exported)
    
    print(f"\n✅ Exported {len(exported)} shows ({ep_count} episodes) → {args.output}")
    print(f"   Size: {size_kb:.1f} KB")
    
    # Summary
    enriched = sum(1 for p in exported if p.get("narrativeHook"))
    with_chapters = sum(1 for p in exported for e in p["episodes"] if e.get("chapters"))
    print(f"   Enriched shows: {enriched}/{len(exported)}")
    print(f"   Episodes with chapters: {with_chapters}/{ep_count}")


if __name__ == "__main__":
    main()
