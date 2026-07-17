"""
Composable Pipeline for Podcast Catalogue.

Each stage reads a list of Podcasts, transforms them, and returns the modified list.
Stages can be run independently via the --stage CLI flag.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import aiohttp

from .models import Podcast, Review, Vibe, TargetAudience, TranscriptSegment, Chapter, Highlight, EngagementIntelligence, GuestProfile, ContentRisk, AIProvenance, SourceAnchor
from .parser import parse_podcast_detail, parse_episode_page
from .authority import get_authority_for_podcast
from .entity_registry import apply_corrections
from .transcriber import process_episode_transcription
from .enricher import enrich_podcast_data, search_itunes_podcast
from .ai_enricher import (
    analyze_podcast_description,
    analyze_episode_description,
    analyze_episode_transcript,
    generate_chapters,
    identify_speakers,
    extract_highlights,
)
from .vector_store import get_db_client, get_collection, index_episode
from .spotify_resolver import resolver as spotify_resolver
from .youtube_enricher import youtube_enricher


# ---------------------------------------------------------------------------
# Context: shared resources available to all stages
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """Shared resources passed through the pipeline."""
    session: aiohttp.ClientSession
    config: Any  # CatalogueConfig (avoid circular import)
    existing_podcasts: Dict[str, Podcast] = field(default_factory=dict)
    popular_urls: set = field(default_factory=set)

    # Helpers shared across stages (injected by CatalogueBuilder)
    fetch_text: Any = None   # async (url, delay, cache_dir) -> Optional[str]
    fetch_bytes: Any = None  # async (url) -> bytes


# ---------------------------------------------------------------------------
# Stage base class
# ---------------------------------------------------------------------------

class Stage:
    """Base class for a pipeline stage."""
    name: str = "base"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Stage 1: Discover — fetch sitemap, filter, and sort URLs
# ---------------------------------------------------------------------------

class DiscoverStage(Stage):
    name = "discover"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        """If podcasts are already loaded (from --input), skip discovery."""
        if podcasts:
            print(f"▶ discover: Skipping (already have {len(podcasts)} podcasts from input)")
            return podcasts

        from xml.etree import ElementTree
        import gzip

        config = ctx.config

        # Fetch popular list
        try:
            from bs4 import BeautifulSoup
            POPULAR_URL = "https://www.abc.net.au/listen/listenapp/most-listened-podcasts/103470928"
            print(f"  Fetching popular list from {POPULAR_URL}...")
            text = await ctx.fetch_text(ctx.session, POPULAR_URL)
            if text:
                soup = BeautifulSoup(text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/listen/programs/" in href:
                        if href.startswith("/"):
                            href = f"https://www.abc.net.au{href}"
                        ctx.popular_urls.add(href.rstrip("/"))
                print(f"  Found {len(ctx.popular_urls)} popular shows.")
        except Exception as e:
            print(f"  Warning: Failed to fetch popular list: {e}")

        # Fetch sitemap
        print(f"  Fetching sitemap: {config.sitemap_url}")
        content = await ctx.fetch_bytes(ctx.session, config.sitemap_url)
        if not content:
            return []

        if config.sitemap_url.endswith(".gz"):
            try:
                content = gzip.decompress(content)
            except gzip.BadGzipFile:
                pass

        try:
            root = ElementTree.fromstring(content)
            ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            all_urls = [
                loc.text for url_tag in root.findall("ns:url", ns)
                if (loc := url_tag.find("ns:loc", ns)) is not None and loc.text
            ]
        except ElementTree.ParseError:
            return []

        # Deduplicate to unique show base URLs
        unique_shows = set()
        for link in all_urls:
            if "/listen/programs/" in link and "/episodes/" not in link:
                parts = link.split("/")
                if len(parts) >= 6:
                    unique_shows.add("/".join(parts[:6]))

        # Sort: popular first, then by existing rating, then alphabetical
        def sort_key(url: str):
            p_url = url.rstrip("/")
            is_popular = 0 if p_url in ctx.popular_urls else 1
            rating = 0.0
            for p_obj in ctx.existing_podcasts.values():
                if p_obj.abc_podcast_page and p_obj.abc_podcast_page.rstrip("/") == p_url:
                    rating = p_obj.average_rating or 0.0
                    break
            return (is_popular, -rating, url)

        targets = sorted(list(unique_shows), key=sort_key)
        print(f"  Found {len(targets)} unique shows.")

        # Filter
        if config.filter_pattern:
            pattern = re.compile(config.filter_pattern, re.IGNORECASE)
            targets = [t for t in targets if pattern.search(t)]
            print(f"  Filtered to {len(targets)} shows.")

        if config.limit > 0:
            targets = targets[:config.limit]

        # We store URLs as stub Podcasts (only abc_podcast_page set)
        # ParseStage will fill in the rest
        result = []
        for url in targets:
            p = Podcast(title=url, abc_podcast_page=url)
            result.append(p)

        print(f"  Discovered {len(result)} shows to process.")
        return result


# ---------------------------------------------------------------------------
# Stage 2: Parse — fetch HTML and extract podcast metadata
# ---------------------------------------------------------------------------

class ParseStage(Stage):
    name = "parse"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        on_podcast_processed = kwargs.get("on_podcast_processed")
        config = ctx.config
        semaphore = asyncio.Semaphore(10)
        parsed = []

        async def parse_one(podcast: Podcast) -> Optional[Podcast]:
            async with semaphore:
                url = podcast.abc_podcast_page
                if not url:
                    return podcast  # Already parsed (from --input)

                # If podcast already has real data, skip parsing (unless forced)
                force_parse = config.force or config.stage == self.name
                if podcast.description and not force_parse:
                    return podcast

                html = await ctx.fetch_text(ctx.session, url, delay=config.delay, cache_dir=config.cache_dir)
                if not html:
                    return None

                parsed_podcast = await asyncio.to_thread(parse_podcast_detail, html, url, [])
                if parsed_podcast:
                    # Merge with existing data
                    existing = ctx.existing_podcasts.get(parsed_podcast.title)
                    if existing:
                        # 1. Merge Show-Level Metadata
                        parsed_podcast.itunes_id = existing.itunes_id or parsed_podcast.itunes_id
                        parsed_podcast.average_rating = existing.average_rating or parsed_podcast.average_rating
                        parsed_podcast.rating_count = existing.rating_count or parsed_podcast.rating_count
                        parsed_podcast.primary_genre = existing.primary_genre or parsed_podcast.primary_genre
                        parsed_podcast.apple_genres = existing.apple_genres or parsed_podcast.apple_genres
                        parsed_podcast.reviews = existing.reviews or parsed_podcast.reviews
                        parsed_podcast.narrative_hook = existing.narrative_hook or parsed_podcast.narrative_hook
                        parsed_podcast.vibe = existing.vibe or parsed_podcast.vibe
                        parsed_podcast.origin_location = existing.origin_location or parsed_podcast.origin_location
                        parsed_podcast.geographic_coverage = existing.geographic_coverage or parsed_podcast.geographic_coverage
                        parsed_podcast.scouting_priority = existing.scouting_priority or parsed_podcast.scouting_priority
                        parsed_podcast.is_award_winning = existing.is_award_winning or parsed_podcast.is_award_winning
                        parsed_podcast.recommendation_scenarios = existing.recommendation_scenarios or parsed_podcast.recommendation_scenarios
                        parsed_podcast.target_audience = existing.target_audience or parsed_podcast.target_audience
                        parsed_podcast.source_organization = existing.source_organization or parsed_podcast.source_organization
                        parsed_podcast.authority_score = existing.authority_score or parsed_podcast.authority_score

                        # 2. Merge Episode-Level Intelligence
                        # Keep existing episodes if they have transcripts/engagement
                        # and match the title of the newly parsed ones.
                        new_eps_map = {e.title: e for e in parsed_podcast.episodes}
                        for old_ep in existing.episodes:
                            if old_ep.title in new_eps_map:
                                new_ep = new_eps_map[old_ep.title]
                                # Copy over intelligence
                                new_ep.transcript = old_ep.transcript or new_ep.transcript
                                new_ep.segments = old_ep.segments or new_ep.segments
                                new_ep.chapters = old_ep.chapters or new_ep.chapters
                                new_ep.engagement = old_ep.engagement or new_ep.engagement
                                new_ep.guests = old_ep.guests or new_ep.guests
                                new_ep.vibe = old_ep.vibe or new_ep.vibe
                                new_ep.narrative_hook = old_ep.narrative_hook or new_ep.narrative_hook
                                new_ep.entities = old_ep.entities or new_ep.entities
                                new_ep.content_locations = old_ep.content_locations or new_ep.content_locations
                                new_ep.timeline = old_ep.timeline or new_ep.timeline
                                new_ep.highlights = old_ep.highlights or new_ep.highlights
                                # Note: published_at is kept from newly parsed (since it's now fixed)
                        
                    # Initialize authority if missing
                    if not parsed_podcast.source_organization:
                        org, score = get_authority_for_podcast(parsed_podcast.title)
                        parsed_podcast.source_organization = org
                        parsed_podcast.authority_score = score

                    # Cascade to episodes
                    for ep in parsed_podcast.episodes:
                        ep.source_organization = parsed_podcast.source_organization
                        ep.authority_score = parsed_podcast.authority_score

                    # Apply popularity tag
                    clean_link = url.rstrip("/")
                    if clean_link in ctx.popular_urls:
                        parsed_podcast.is_popular = True
                        if "Featured in ABC Most Listened" not in parsed_podcast.recommendation_reasons:
                            parsed_podcast.recommendation_reasons.append("Featured in ABC Most Listened")
                    return parsed_podcast
                return None

        tasks = [parse_one(p) for p in podcasts]
        results = await asyncio.gather(*tasks)

        for p in results:
            if p:
                parsed.append(p)
                print(f"  Parsed: {p.title} ({len(p.episodes)} eps)")
                if on_podcast_processed:
                    on_podcast_processed(p)

        return parsed


# ---------------------------------------------------------------------------
# Stage 3: Enrich — iTunes API ratings, genres, reviews
# ---------------------------------------------------------------------------

class EnrichStage(Stage):
    name = "enrich"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        on_podcast_processed = kwargs.get("on_podcast_processed")
        for podcast in podcasts:
            # Skip if already enriched (unless forced)
            force_enrich = ctx.config.force or ctx.config.stage == self.name
            if podcast.itunes_id and not force_enrich:
                continue

            itunes_id, rating, count, p_genre, genres, reviews = None, None, None, None, None, []

            if podcast.apple_podcast_page:
                itunes_id, rating, count, p_genre, genres, reviews = await enrich_podcast_data(
                    ctx.session, apple_url=podcast.apple_podcast_page
                )

            if not itunes_id:
                result = await search_itunes_podcast(ctx.session, podcast.title)
                if result:
                    search_id, _, _ = result
                    if search_id:
                        itunes_id, rating, count, p_genre, genres, reviews = await enrich_podcast_data(
                            ctx.session, itunes_id=search_id
                        )

            podcast.itunes_id = itunes_id
            podcast.average_rating = rating
            podcast.rating_count = count
            podcast.primary_genre = p_genre
            podcast.apple_genres = genres
            if reviews:
                podcast.reviews = [Review(**r) for r in reviews]

            if itunes_id:
                print(f"  ★ {podcast.title[:30]}: ID={itunes_id}, Genre='{p_genre}', Reviews={len(reviews)}")

            if on_podcast_processed:
                on_podcast_processed(podcast)

        return podcasts


# ---------------------------------------------------------------------------
# Stage 4: DeepCrawl — fetch episode pages for audio URLs
# ---------------------------------------------------------------------------

class DeepCrawlStage(Stage):
    name = "deep-crawl"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        on_podcast_processed = kwargs.get("on_podcast_processed")
        config = ctx.config

        for podcast in podcasts:
            if not podcast.episodes:
                continue

            existing_p = ctx.existing_podcasts.get(podcast.title)
            existing_eps_map = {}
            if existing_p:
                for ep in existing_p.episodes:
                    if ep.url:
                        existing_eps_map[ep.url] = ep

            for ep in podcast.episodes:
                if not ep.url:
                    continue

                if ep.url in existing_eps_map:
                    existing_ep = existing_eps_map[ep.url]
                    if existing_ep.audio_url: ep.audio_url = existing_ep.audio_url
                    if existing_ep.published_at: ep.published_at = existing_ep.published_at
                    if existing_ep.transcript: ep.transcript = existing_ep.transcript
                    if existing_ep.segments: ep.segments = existing_ep.segments
                    if existing_ep.chapters: ep.chapters = existing_ep.chapters
                    if existing_ep.content_hash: ep.content_hash = existing_ep.content_hash
                    if existing_ep.narrative_hook: ep.narrative_hook = existing_ep.narrative_hook
                    if existing_ep.vibe: ep.vibe = existing_ep.vibe
                    if existing_ep.entities: ep.entities = existing_ep.entities
                    if existing_ep.engagement: ep.engagement = existing_ep.engagement

                # If after merging we still lack data, fetch it
                if not ep.audio_url or not ep.published_at:
                    html = await ctx.fetch_text(ctx.session, ep.url, delay=config.delay, cache_dir=config.cache_dir)
                    if html:
                        extracted_data = parse_episode_page(html)
                        if extracted_data:
                            if not ep.audio_url and extracted_data.get("audio_url"):
                                ep.audio_url = extracted_data["audio_url"]
                            if not ep.published_at and extracted_data.get("published_at"):
                                ep.published_at = extracted_data["published_at"]

            if on_podcast_processed:
                on_podcast_processed(podcast)

        return podcasts


# ---------------------------------------------------------------------------
# Stage 5: Transcribe — Whisper + SpeechBrain diarization
# ---------------------------------------------------------------------------

class TranscribeStage(Stage):
    name = "transcribe"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        on_podcast_processed = kwargs.get("on_podcast_processed")
        config = ctx.config

        # 1. Flatten the queue and calculate priority
        pending_tasks = []
        for podcast in podcasts:
            for ep in podcast.episodes:
                force_transcribe = config.force or config.stage == self.name
                if not ep.audio_url or (ep.transcript and not force_transcribe):
                    continue  # Skip if no audio or already transcribed (unless forced)

                # Calculate Priority Score
                score = 0
                
                # A. Authority Weight
                auth_score = getattr(podcast, 'authority_score', 0) or 0
                score += (auth_score * 50)
                
                # B. Entity & Guest Triggers
                desc_lower = (ep.description or "").lower()
                title_lower = (ep.title or "").lower()
                if any(kw in desc_lower for kw in ["interview", "speaks with", "guest", "exclusive", "opinion"]):
                    score += 15
                
                if "with " in title_lower or "on " in title_lower:
                    score += 15
                
                # C. Timeliness Decay
                if ep.published_at:
                    try:
                        from datetime import datetime, timezone
                        dt_str = ep.published_at.replace("Z", "+00:00")
                        pub_date = datetime.fromisoformat(dt_str)
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)
                        delta = now - pub_date
                        if delta.days <= 1:
                            score += 20
                        elif delta.days <= 7:
                            score += 10
                    except Exception:
                        pass
                
                pending_tasks.append((score, podcast, ep))
                
        # 2. Sort by priority descending
        pending_tasks.sort(key=lambda x: x[0], reverse=True)
        
        print(f"  📝 Transcribe: Queued {len(pending_tasks)} episodes by priority...")

        # 3. Process the sorted queue
        for score, podcast, ep in pending_tasks:
            print(f"  Transcribing [Priority: {score:.1f}]: {ep.title[:50]}...")
            try:
                transcript_text, segments = await process_episode_transcription(
                    ep.audio_url, duration_limit=config.duration_limit
                )
                ep.transcript = transcript_text

                # Speaker identification
                if segments and any(s.get("speaker") for s in segments if isinstance(s, dict)):
                    print(f"    🗣 Identifying speakers...")
                    speaker_map = await identify_speakers(
                        ctx.session, segments, ep.title,
                        ep.description or podcast.description or ""
                    )
                    if speaker_map:
                        print(f"       Map: {speaker_map}")
                        for seg in segments:
                            if isinstance(seg, dict) and seg.get("speaker"):
                                s_label = seg["speaker"]
                                if s_label in speaker_map:
                                    seg["speaker"] = speaker_map[s_label]

                ep.segments = [TranscriptSegment(**s) for s in segments]
                print(f"    ✓ {len(transcript_text)} chars, {len(segments)} segments")

            except Exception as e:
                print(f"    ✗ Failed: {e}")

            # Intermediate save per episode processed
            if on_podcast_processed:
                on_podcast_processed(podcast)

        return podcasts


# ---------------------------------------------------------------------------
# Stage 6A: ContentEnrich — Vibes, Hooks, Entities (Breadth Pass)
# ---------------------------------------------------------------------------

class ContentEnrichStage(Stage):
    name = "content-enrich"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        on_podcast_processed = kwargs.get("on_podcast_processed")
        for podcast in podcasts:
            try:
                # Instant Metadata Pass
                print(f"  🤖 6A-Content: {podcast.title[:40]}...")
                p_data = await analyze_podcast_description(ctx.session, podcast.description, podcast.title, ctx=ctx)
                if p_data:
                    # Vibes, Hooks, Audience
                    podcast.narrative_hook = p_data.get("narrative_hook")
                    v_data = p_data.get("vibe")
                    if isinstance(v_data, dict):
                        # Normalise tone: Gemini sometimes returns a string
                        if isinstance(v_data.get("tone"), str):
                            v_data["tone"] = [v_data["tone"]]
                        podcast.vibe = Vibe(**v_data)
                    
                    # Priority Trigger: If tone is intense, boost priority
                    if podcast.vibe and any(t in ["High-Stakes", "Intense", "Deep"] for t in podcast.vibe.tone):
                        podcast.scouting_priority = 1.0
                        print(f"    ⭐ Priority Boost: {podcast.title[:30]} (Intensity detected)")

                if on_podcast_processed:
                    on_podcast_processed(podcast)
            except Exception as e:
                print(f"    ❌ 6A Failure: {e}")
        return podcasts

# ---------------------------------------------------------------------------
# Stage 6B: ScoutEnrich — Deep Intelligence & Engagement (Depth Pass)
# ---------------------------------------------------------------------------

class ScoutEnrichStage(Stage):
    name = "scout-enrich"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        # Sort by scouting priority
        sorted_podcasts = sorted(podcasts, key=lambda x: x.scouting_priority, reverse=True)
        on_podcast_processed = kwargs.get("on_podcast_processed")

        for podcast in sorted_podcasts:
            try:
                if not podcast.episodes:
                    continue
                
                # Deep Pass: Requires transcription (segments)
                for ep in podcast.episodes:
                    if (ep.segments or ep.transcript) and not ep.engagement:
                        print(f"  🔍 6B-Scout: Deep Analysis for {ep.title[:40]}...")
                        # Map HighlightSchema/EngagementSchema to Pydantic models
                        e_data = await analyze_episode_transcript(ctx.session, ep.segments, ep.title, transcript=ep.transcript, ctx=ctx)
                        if isinstance(e_data, dict):
                            if e_data.get("highlights"):
                                ep.highlights = [Highlight(**h) for h in e_data["highlights"]]
                            if e_data.get("engagement"):
                                ep.engagement = EngagementIntelligence(**e_data["engagement"])
                            
                            # --- Spotify Deep-linking ---
                            print(f"    🎵 Resolving Spotify URI: {ep.title[:30]}...")
                            s_uri = await spotify_resolver.resolve_episode(ctx.session, podcast.title, ep.title)
                            
                            # --- Trust Layer Mapping ---
                            if e_data.get("trust"):
                                t = e_data["trust"]
                                ep.genre = t.get("genre")
                                ep.expires = t.get("expires")
                                ep.content_reference_time = t.get("contentReferenceTime")
                                if t.get("contentRisk"):
                                    try:
                                        ep.content_risk = ContentRisk(**t["contentRisk"])
                                    except Exception as re:
                                        print(f"    ⚠️ Risk parsing error: {re}")
                            
                            if e_data.get("ai_provenance"):
                                try:
                                    ep.ai_provenance = AIProvenance(**e_data["ai_provenance"])
                                except Exception as pe:
                                    print(f"    ⚠️ Provenance parsing error: {pe}")

                            # Cascade Spotify URI to highlight anchors
                            if s_uri:
                                for hl in ep.highlights:
                                    if hl.source_anchor:
                                        hl.source_anchor.spotify_uri = s_uri
                                        hl.source_anchor.spotify_deep_link = hl.source_anchor.get_deep_link()

                            if e_data.get("guests"):
                                # Avoid duplicating guests if they already exist from description
                                existing_guest_names = {g.name.lower() for g in ep.guests}
                                for g_data in e_data["guests"]:
                                    if g_data.get("name") and g_data["name"].lower() not in existing_guest_names:
                                        ep.guests.append(GuestProfile(**g_data))
                            
                            if not ep.chapters:
                                from .ai_enricher import generate_chapters
                                print(f"    📖 Generating chapters: {ep.title[:30]}...")
                                raw_chapters = await generate_chapters(ctx.session, ep.segments, ep.title, ctx=ctx)
                                if raw_chapters:
                                    ep.chapters = [Chapter(**c) for c in raw_chapters]

                if on_podcast_processed:
                    on_podcast_processed(podcast)

            except Exception as e:
                print(f"    ❌ Scouting failure for {podcast.title[:30]}: {e}")

        return podcasts



# ---------------------------------------------------------------------------
# Stage 6C: YouTubeEnrich — Cross-platform Telemetry & Human Benchmarks
# ---------------------------------------------------------------------------

class YouTubeEnrichStage(Stage):
    name = "youtube-enrich"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        """Enriches episodes with YouTube telemetry and social signals."""
        print(f"  📺 YouTubeEnrich: Syncing cross-platform telemetry...")
        for podcast in podcasts:
            count = 0
            for ep in podcast.episodes:
                # Resolve video and telemetry
                yt_data = await youtube_enricher.resolve_video(ctx.session, podcast.title, ep.title)
                if yt_data:
                    if not ep.engagement:
                        ep.engagement = EngagementIntelligence()
                    
                    # Apply telemetry
                    ep.engagement.youtube_views = yt_data.get("views")
                    ep.engagement.youtube_likes = yt_data.get("likes")
                    ep.engagement.youtube_url = yt_data.get("youtube_url")
                    ep.engagement.youtube_comments_paused = yt_data.get("comments_paused", False)
                    
                    # Map Chapters as functional benchmarks (if not already chaptered)
                    if not ep.chapters and yt_data.get("chapters"):
                        print(f"    📖 Using YouTube AI Chapters for {ep.title[:30]}")
                        for ch in yt_data["chapters"]:
                            ep.chapters.append(Chapter(
                                title=ch["title"],
                                summary="YouTube AI Benchmark",
                                startTime=float(ch["start"]),
                                endTime=float(ch["end"])
                            ))
                    
                    # Also map to rich timeline
                    if yt_data.get("chapters"):
                        ep.timeline.extend(youtube_enricher.map_chapters_to_timeline(yt_data["chapters"]))
                    
                    count += 1
            if count > 0:
                print(f"    ✓ {podcast.title[:30]}: enriched {count} episodes from YouTube.")
        return podcasts


# ---------------------------------------------------------------------------
# Stage 6C: EpisodeEnrich — Guests, Entities, Vibe from Descriptions
# ---------------------------------------------------------------------------

class EpisodeEnrichStage(Stage):
    name = "episode-enrich"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        on_podcast_processed = kwargs.get("on_podcast_processed")
        for podcast in podcasts:
            try:
                for ep in podcast.episodes:
                    # Skip if already enriched with entities/guests
                    if ep.entities or ep.guests:
                        continue
                    desc = ep.description or ""
                    if len(desc) < 20:
                        continue
                    print(f"  🎯 Episode Enrich: {ep.title[:50]}...")
                    data = await analyze_episode_description(
                        ctx.session, desc, ep.title, ctx=ctx
                    )
                    if data:
                        if data.get("narrative_hook") and not ep.narrative_hook:
                            ep.narrative_hook = data["narrative_hook"]
                        if data.get("vibe") and not ep.vibe:
                            v_data = data["vibe"]
                            if isinstance(v_data, dict):
                                # Normalise tone: Gemini sometimes returns a string
                                if isinstance(v_data.get("tone"), str):
                                    v_data["tone"] = [v_data["tone"]]
                                ep.vibe = Vibe(**v_data)
                        if data.get("entities"):
                            ep.entities = data["entities"]
                        if data.get("guests"):
                            try:
                                ep.guests = [GuestProfile(**g) if isinstance(g, dict) else g for g in data["guests"]]
                            except Exception:
                                ep.guests = []  # Graceful fallback

                if on_podcast_processed:
                    on_podcast_processed(podcast)
            except Exception as e:
                print(f"    ❌ Episode Enrich failure for {podcast.title[:30]}: {e}")
        return podcasts
    


# ---------------------------------------------------------------------------
# Stage 7: Correction — Editorial Safety Net (Named Entity Verification)
# ---------------------------------------------------------------------------

class CorrectionStage(Stage):
    name = "correction"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        """Apply global entity corrections to all extracted intelligence."""
        print(f"  🪄 Correction: Applying Named Entity Verification Registry...")
        count = 0
        for p in podcasts:
            # 1. Show Level
            p.title = apply_corrections(p.title)
            p.description = apply_corrections(p.description)
            
            # 2. Episode Level
            for ep in p.episodes:
                ep.title = apply_corrections(ep.title)
                ep.description = apply_corrections(ep.description)
                ep.narrative_hook = apply_corrections(ep.narrative_hook)
                
                if ep.engagement:
                    ep.engagement.takeaway = apply_corrections(ep.engagement.takeaway)
                    ep.engagement.why_listen = apply_corrections(ep.engagement.why_listen)
                    ep.engagement.social_post = apply_corrections(ep.engagement.social_post)
                    ep.engagement.best_quotes = [apply_corrections(q) for q in ep.engagement.best_quotes]
                    ep.engagement.key_statistics = [apply_corrections(s) for s in ep.engagement.key_statistics]
                
                for hl in ep.highlights:
                    hl.title = apply_corrections(hl.title)
                    hl.reason = apply_corrections(hl.reason)
                    if hl.source_anchor:
                        hl.source_anchor.transcript_text = apply_corrections(hl.source_anchor.transcript_text)
                
                for chapter in ep.chapters:
                    chapter.title = apply_corrections(chapter.title)
                
                for item in ep.timeline:
                    item.title = apply_corrections(item.title)
                
                for guest in ep.guests:
                    guest.name = apply_corrections(guest.name)
                    guest.expertise = apply_corrections(guest.expertise)
                    guest.bio = apply_corrections(guest.bio)
                
                count += 1
                
        print(f"    ✓ Applied corrections to {len(podcasts)} shows and {count} episodes.")
        return podcasts



# ---------------------------------------------------------------------------
# Stage 7: Index — ChromaDB vector indexing
# ---------------------------------------------------------------------------

class IndexStage(Stage):
    name = "index"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        try:
            db_client = get_db_client()
            collection = get_collection(db_client)
        except Exception as e:
            print(f"  ⚠ LanceDB unavailable: {e}")
            return podcasts

        for podcast in podcasts:
            total_indexed = 0
            for ep in podcast.episodes:
                ep_dict = ep.model_dump(by_alias=True)
                n = await index_episode(ctx.session, collection, podcast.title, ep_dict)
                total_indexed += n
            if total_indexed > 0:
                print(f"  🔍 {podcast.title[:30]}: indexed {total_indexed} chunks")

        return podcasts


# ---------------------------------------------------------------------------
# Stage 8: RegionalSynthesis — Master Pulse Synthesis (The Substrate Layer)
# ---------------------------------------------------------------------------

class RegionalSynthesisStage(Stage):
    name = "regional-synthesis"

    async def process(self, podcasts: List[Podcast], ctx: PipelineContext, **kwargs) -> List[Podcast]:
        """Clusters enriched episodes by region and synthesizes master pulses."""
        from .regional_pipeline import synthesize_regional_pulses
        print(f"  🤖 Regional Synthesis: Aggregating master pulses...")
        try:
            # We run the synthesis logic which pulls from the universe.jsonl (persisted by previous stages)
            await synthesize_regional_pulses()
        except Exception as e:
            print(f"    ❌ Regional synthesis failed: {e}")
        return podcasts


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

# Registry of all available stages
ALL_STAGES = {
    "discover": DiscoverStage,
    "parse": ParseStage,
    "enrich": EnrichStage,
    "deep-crawl": DeepCrawlStage,
    "transcribe": TranscribeStage,
    "content-enrich": ContentEnrichStage,
    "episode-enrich": EpisodeEnrichStage,
    "scout-enrich": ScoutEnrichStage,
    "youtube-enrich": YouTubeEnrichStage,
    "correction": CorrectionStage,
    "index": IndexStage,
    "regional-synthesis": RegionalSynthesisStage,
}

# Default execution order
DEFAULT_STAGE_ORDER = ["discover", "parse", "enrich", "deep-crawl", "transcribe", "content-enrich", "episode-enrich", "scout-enrich", "index", "regional-synthesis"]


class Pipeline:
    """Runs a sequence of stages."""

    def __init__(self, stages: List[Stage]):
        self.stages = stages

    async def run(self, podcastsList: List[Podcast], ctx: PipelineContext, on_podcast_processed=None) -> List[Podcast]:
        # If we are running multiple stages, we want to process podcasts one by one 
        # or in small batches to preserve memory and enable incremental callbacks.
        
        # NOTE: To simplify current architecture, we process the WHOLE list through each stage.
        # But we will call on_podcast_processed after the FINAL stage is finished for the entire list.
        # To get truly real-time trends, we'd need to invert the loops.
        # For now, let's at least call it after each stage.
        
        for stage in self.stages:
            print(f"\n▶ Stage: {stage.name}")
            # Only pass callback if stage supports it or via **kwargs
            podcastsList = await stage.process(podcastsList, ctx, on_podcast_processed=on_podcast_processed)
            print(f"  ✓ {stage.name} complete ({len(podcastsList)} podcasts)")
                    
        return podcastsList


def build_pipeline(config, stage_name: str = "all") -> Pipeline:
    """Constructs a pipeline based on config flags and optional --stage selection."""
    if stage_name != "all":
        # Single-stage mode
        if stage_name not in ALL_STAGES:
            raise ValueError(f"Unknown stage: {stage_name}. Available: {list(ALL_STAGES.keys())}")
        return Pipeline([ALL_STAGES[stage_name]()])

    # Full pipeline — include stages based on config flags
    stages = []
    stages.append(DiscoverStage())
    stages.append(ParseStage())

    if config.enrich:
        stages.append(EnrichStage())

    if config.fetch_audio:
        stages.append(DeepCrawlStage())

    if config.transcribe:
        stages.append(TranscribeStage())

    if config.content_enrich:
        stages.append(ContentEnrichStage())

    if config.episode_enrich:
        stages.append(EpisodeEnrichStage())

    if config.scout_enrich:
        stages.append(ScoutEnrichStage())
        stages.append(IndexStage())

    if config.ai_enrich and not config.content_enrich:
        stages.append(ContentEnrichStage())

    if config.regional_synthesis:
        stages.append(RegionalSynthesisStage())

    return Pipeline(stages)
