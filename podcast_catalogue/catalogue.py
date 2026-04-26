from __future__ import annotations

import asyncio
import aiohttp
import gzip
import io
import ssl
import certifi
import re
import random
import hashlib
import os
import json
from xml.etree import ElementTree
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .exporter import export_jsonl, export_universal_json, export_jsonld
from .models import Podcast, Review, Vibe, TargetAudience, TranscriptSegment, Chapter
from .pipeline import PipelineContext, build_pipeline


@dataclass
class CatalogueConfig:
    sitemap_url: str
    limit: int = 0
    filter_pattern: Optional[str] = None
    fetch_audio: bool = False
    delay: float = 0.0
    cache_dir: Optional[str] = None
    input_file: Optional[str] = None
    transcribe: bool = False
    enrich: bool = False
    ai_enrich: bool = False
    content_enrich: bool = False
    scout_enrich: bool = False
    episode_enrich: bool = False
    duration_limit: int = 0
    stage: str = "all"
    force: bool = False
    provider: str = "ollama"
    model: Optional[str] = None


class CatalogueBuilder:
    def __init__(self, limit_concurrency: int = 10):
        self.limit_concurrency = limit_concurrency

    def _get_cache_path(self, cache_dir: str, url: str) -> str:
        hash_md5 = hashlib.md5(url.encode("utf-8")).hexdigest()
        return os.path.join(cache_dir, f"{hash_md5}.html")

    async def _fetch_bytes(self, session: aiohttp.ClientSession, url: str) -> bytes:
        async with session.get(url) as response:
            try:
                response.raise_for_status()
                return await response.read()
            except aiohttp.ClientResponseError:
                return b""

    async def _fetch_text(self, session: aiohttp.ClientSession, url: str, delay: float = 0.0, cache_dir: Optional[str] = None) -> Optional[str]:
        # 1. Check Cache
        if cache_dir:
            cache_path = self._get_cache_path(cache_dir, url)
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    pass

        # 2. Network Fetch
        if delay > 0:
            sleep_time = delay + (random.random() * 0.2 * delay)
            await asyncio.sleep(sleep_time)

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                text = await response.text()
                
                # 3. Write Cache
                if cache_dir and text:
                    try:
                        os.makedirs(cache_dir, exist_ok=True)
                        cache_path = self._get_cache_path(cache_dir, url)
                        with open(cache_path, "w", encoding="utf-8") as f:
                            f.write(text)
                    except Exception as e:
                        print(f"Failed to cache {url}: {e}")
                        
                return text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _load_existing_data(self, input_file: str) -> Dict[str, Podcast]:
        existing = {}
        if not input_file or not os.path.exists(input_file):
            return existing
        
        print(f"Loading existing data from {input_file}...")
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        p = Podcast(**data)
                        existing[p.title] = p
                    except Exception:
                        continue
        except Exception as e:
            print(f"Error loading input file: {e}")
        
        print(f"Loaded {len(existing)} existing podcasts.")
        return existing

    async def build(self, config: CatalogueConfig, on_podcast_processed=None) -> List[Podcast]:
        # Load existing data for incremental update
        existing_podcasts = self._load_existing_data(config.input_file) if config.input_file else {}

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        timeout = aiohttp.ClientTimeout(total=0, sock_connect=10, sock_read=30)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers) as session:
            # Build pipeline context
            ctx = PipelineContext(
                session=session,
                config=config,
                existing_podcasts=existing_podcasts,
                fetch_text=self._fetch_text,
                fetch_bytes=self._fetch_bytes,
            )

            # Build and run the pipeline
            pipeline = build_pipeline(config, stage_name=config.stage)

            # If running a single stage with --input, start with loaded data
            if config.stage != "all" and existing_podcasts:
                initial_podcasts = list(existing_podcasts.values())
                # Apply filter and limit to loaded data if specified
                if config.filter_pattern:
                    pattern = re.compile(config.filter_pattern, re.IGNORECASE)
                    initial_podcasts = [p for p in initial_podcasts if (p.abc_podcast_page and pattern.search(p.abc_podcast_page)) or pattern.search(p.title)]
                if config.limit > 0:
                    initial_podcasts = initial_podcasts[:config.limit]
            else:
                initial_podcasts = []

            podcasts = await pipeline.run(initial_podcasts, ctx, on_podcast_processed=on_podcast_processed)

            return podcasts

    def export_universal_json(self, podcastsList: List[Podcast]) -> str:
        return export_universal_json(podcastsList)

    def export_jsonld(self, podcastsList: List[Podcast]) -> str:
        return export_jsonld(podcastsList)

    def export_jsonl(self, podcastsList: List[Podcast]) -> str:
        return export_jsonl(podcastsList)
