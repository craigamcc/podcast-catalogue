import argparse
import asyncio
import os
import sys
import shutil
import aiohttp
import json
import re

from .catalogue import CatalogueBuilder, CatalogueConfig
from .exporter import export_universal_json, export_jsonl, export_jsonld, export_tiered_json
from .reporter_adapter import generate_editorial_report

# Default URLs
ABC_SITEMAP_URL = "https://www.abc.net.au/sitemaps/sitemap-listen-0.xml.gz"

def run_env_check():
    """Runs diagnostics on the development environment."""
    print("📋 GoldMine Environmental Diagnostic Check\n" + "="*40)
    
    # Check FFmpeg
    ffmpeg_ready = shutil.which("ffmpeg") is not None
    print(f"{'✅' if ffmpeg_ready else '❌'} FFmpeg: {'Installed' if ffmpeg_ready else 'NOT FOUND'}")
    if not ffmpeg_ready:
        print("   TIP: Install via 'brew install ffmpeg'")

    # Check Ollama
    ollama_ready = False
    try:
        import socket
        with socket.create_connection(("localhost", 11434), timeout=1):
            ollama_ready = True
    except: pass
    print(f"{'✅' if ollama_ready else '❌'} Ollama: {'Running' if ollama_ready else 'NOT RESPONDING'}")
    if not ollama_ready:
        print("   TIP: Ensure Ollama is running and Qwen3:14b is pulled.")

    # Check HF Token for Diarization
    hf_token = os.environ.get("HF_TOKEN")
    print(f"{'✅' if hf_token else '⚠️'} Hugging Face Token: {'Found' if hf_token else 'MISSING'}")
    if not hf_token:
        print("   TIP: Set export HF_TOKEN=... to enable diarization.")
    
    print("="*40)

async def main_async(args):
    if not args.output:
        print("❌ Error: --output is required")
        return

    # Extract arguments for clarity and potential modification
    sitemap_url = args.sitemap_url
    limit = args.limit
    filter_pattern = args.filter
    fetch_audio = args.deep_crawl
    delay = args.delay
    cache_dir = args.cache_dir
    input_file = args.input
    transcribe = args.transcribe
    enrich = args.enrich
    ai_enrich = args.ai_enrich
    content_enrich = args.content_enrich
    scout_enrich = args.scout_enrich
    episode_enrich = args.episode_enrich
    duration_limit = args.duration_limit
    stage = args.stage
    force = args.force
    provider = args.provider
    model = args.model

    # Initialize configuration
    config = CatalogueConfig(
        sitemap_url=sitemap_url,
        limit=limit,
        filter_pattern=filter_pattern,
        fetch_audio=fetch_audio,
        delay=delay,
        cache_dir=cache_dir,
        input_file=input_file,
        transcribe=transcribe,
        enrich=enrich,
        ai_enrich=ai_enrich,
        content_enrich=content_enrich,
        scout_enrich=scout_enrich,
        episode_enrich=episode_enrich,
        duration_limit=duration_limit,
        stage=stage,
        force=force,
        provider=provider,
        model=model
    )

    if stage != "all":
        print(f"Running single stage: {stage}")
    else:
        print(f"Starting full pipeline from sitemap: {config.sitemap_url}")

    builder = CatalogueBuilder(limit_concurrency=args.concurrency)
    
    def on_podcast_processed(p):
        if args.output and args.format == "jsonl":
            with open(args.output, "a", encoding="utf-8") as f:
                f.write(json.dumps(p.model_dump(by_alias=True)) + "\n")

    try:
        podcasts = await builder.build(config, on_podcast_processed=on_podcast_processed)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during build: {e}", file=sys.stderr)
        sys.exit(1)

    # Merge results back into the full catalogue if we loaded existing data and used a filter
    final_podcasts = podcasts
    if config.input_file and config.filter_pattern and os.path.exists(config.input_file):
        existing_full = builder._load_existing_data(config.input_file)
        # Update existing records with the new/modified ones from this run
        for p in podcasts:
            existing_full[p.title] = p
        final_podcasts = list(existing_full.values())

    if args.format == "jsonl":
        output_content = builder.export_jsonl(final_podcasts)
    elif args.format == "json":
        output_content = export_tiered_json(final_podcasts, tier=args.tier)
    elif args.format == "jsonld":
        output_content = export_jsonld(final_podcasts)
    elif args.format == "reporter":
        print("📡 Generating Editorial Meta-Summary...")
        output_content = generate_editorial_report(final_podcasts)
    else:
        output_content = export_jsonl(final_podcasts)

    # Ensure output directory exists
    if os.path.dirname(args.output):
        os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(output_content)

    print(f"Wrote data to {args.output}")


def main():
    parser = argparse.ArgumentParser(description="Generate podcast catalogue from ABC Listen.")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--sitemap-url", default=ABC_SITEMAP_URL, help="URL for the ABC Listen Sitemap")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of podcasts to fetch (0 for all)")
    parser.add_argument("--filter", type=str, default=None, help="Regex pattern to filter podcast URLs (case insensitive)")
    parser.add_argument("--format", choices=["json", "jsonl", "jsonld", "reporter"], default="jsonl", help="Output format (Universal JSON, JSONL, JSON-LD, or reporter)")
    parser.add_argument("--check-env", action="store_true", help="Run environmental diagnostic check")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrent requests")
    parser.add_argument("--deep-crawl", action="store_true", help="Fetch audio URLs for each episode (slow)")
    parser.add_argument("--delay", type=float, default=0.0, help="Minimum delay in seconds between requests (randomized +20%%)")
    parser.add_argument("--cache-dir", default=None, help="Directory to cache HTML responses")
    parser.add_argument("--input", default="data/universe.jsonl", help="Path to existing JSONL file for incremental update")
    parser.add_argument("--transcribe", action="store_true", help="Enable audio transcription on Deep Crawls (requires whisper)")
    parser.add_argument("--enrich", action="store_true", help="Enable metadata enrichment from Apple Podcasts API")
    parser.add_argument("--ai-enrich", action="store_true", help="Enable legacy AI analysis")
    parser.add_argument("--content-enrich", action="store_true", help="Enable 6A Content Enrichment (Vibes/Hooks)")
    parser.add_argument("--scout-enrich", action="store_true", help="Enable 6B Scout Enrichment (Deep intelligence)")
    parser.add_argument("--episode-enrich", action="store_true", help="Enable 6C Episode Enrichment (Guests, entities, vibe from descriptions)")
    parser.add_argument("--duration-limit", type=int, default=0, help="Limit transcription to N seconds of audio (0 = full episode)")
    parser.add_argument("--stage", default="all",
        choices=["all", "discover", "parse", "enrich", "deep-crawl", "transcribe", "content-enrich", "episode-enrich", "scout-enrich", "index"],
        help="Run only a specific pipeline stage (requires --input for most stages)")
    parser.add_argument("--force", action="store_true", help="Force re-running of stages even if data already exists")
    parser.add_argument("--provider", default="ollama", choices=["ollama", "gemini"], help="AI Provider (ollama or gemini)")
    parser.add_argument("--model", default=None, help="Explicit model name (e.g. qwen3.5:latest, gemini-1.5-flash)")
    parser.add_argument("--tier", type=int, default=2, choices=[0, 1, 2], help="Data Tier for JSON export (0=Slim, 1=Intelligence, 2=Full)")
    
    args = parser.parse_args()

    if args.check_env:
        run_env_check()
        return

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
