from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
import datetime

from bs4 import BeautifulSoup

from .models import Location, Podcast, TargetAudience, Episode

WHITESPACE_RE = re.compile(r"\s+")


class ReviewLinks:
    def __init__(self, apple: Optional[str] = None, spotify: Optional[str] = None, youtube: Optional[str] = None):
        self.apple = apple
        self.spotify = spotify
        self.youtube = youtube
        self.others: List[str] = []

def clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


def extract_nextjs_data(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """Extracts the __NEXT_DATA__ JSON blob."""
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    try:
        return json.loads(script.string)
    except json.JSONDecodeError:
        return None


def get_program_data_from_nextjs(data: Dict[str, Any], base_url: str) -> Optional[Dict[str, Any]]:
    """Traverses the Next.js props to find the main program entity and episodes."""
    props = data.get("props", {}).get("pageProps", {})
    
    analytics = props.get("pageAnalytics", {}).get("document", {})
    program_info = analytics.get("program", {})
    hero = props.get("heroImageWithCTAPrepared", {})
    head_tags = props.get("headTagsPagePrepared", {})
    
    episodes_data = []

    # Helper to construct absolute URL
    def make_absolute(link):
        if not link: return None
        if link.startswith("http"): return link
        # Handle Next.js paths which might be relative or absolute path only
        if link.startswith("/"):
             return f"https://www.abc.net.au{link}"
        return urljoin("https://www.abc.net.au", link)

    # Strategy 1: Check programCollectionPrepared (Common for program pages)
    collection = props.get("programCollectionPrepared")
    if collection and "items" in collection:
        for item in collection["items"]:
            # Valid episode check: usually has cardMediaIndicator or duration implies audio
            media = item.get("cardMediaIndicatorPrepared") or {}
            
            title = item.get("cardTitle")
            if title:
                ep_url = make_absolute(item.get("articleLink") or item.get("link") or item.get("to"))
                published_at = item.get("contentLabelPrepared")
                if not published_at and item.get("cardAttributionPrepared"):
                    published_at = item["cardAttributionPrepared"].get("publishedDate")
                
                ep = {
                    "title": title,
                    "description": item.get("description"),
                    "publishedAt": published_at,
                    "duration": str(media.get("duration")) if media.get("duration") else None,
                    "url": ep_url
                }
                episodes_data.append(ep)

    # Strategy 2: Check standard componentsContent (for generic pages or different layouts)
    if not episodes_data:
        components = props.get("data", {}).get("componentsContent", [])
        for comp in components:
            if "items" in comp.get("componentProps", {}):
                 items = comp["componentProps"]["items"]
                 for item in items:
                     if "title" in item and "url" in item:
                         ep = {
                             "title": item.get("title"),
                             "description": item.get("teaserText") or item.get("synopsis"),
                             "publishedAt": item.get("published"),
                             "duration": item.get("duration"),
                             "url": make_absolute(item.get("url") or item.get("link"))
                         }
                         episodes_data.append(ep)

    return {
        "analytics": analytics,
        "program_info": program_info,
        "hero": hero,
        "head_tags": head_tags,
        "episodes": episodes_data
    }


def parse_podcast_detail(html: str, url: str, flags: Optional[List[str]] = None) -> Podcast:
    soup = BeautifulSoup(html, "html.parser")
    next_data = extract_nextjs_data(soup)
    
    title = None
    description = None
    image_url = None
    episodes: List[Episode] = []
    
    if next_data:
        extracted = get_program_data_from_nextjs(next_data, url)
        if extracted:
            hero = extracted["hero"]
            head = extracted["head_tags"]
            
            # Title
            if hero.get("title"):
                title = clean_text(hero.get("title"))
            elif head.get("title"):
                title = clean_text(head.get("title"))
            
            # Description
            if head.get("description"):
                description = clean_text(head.get("description"))
                
            # Image
            hero_image = hero.get("heroImagePrepared", {})
            if hero_image.get("imgSrc"):
                image_url = hero_image.get("imgSrc")
            elif head.get("fullTouchIconPath"):
                image_url = head.get("fullTouchIconPath")
            
            # Episodes
            raw_eps = extracted.get("episodes", [])
            for ep in raw_eps:
                if ep.get("title"):
                    episodes.append(Episode(
                        title=clean_text(ep["title"]),
                        description=clean_text(ep.get("description")),
                        publishedAt=ep.get("publishedAt"), 
                        duration=str(ep.get("duration")) if ep.get("duration") else None,
                        url=ep.get("url")
                    ))

    def get_meta(prop: str) -> Optional[str]:
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return tag["content"] if tag and tag.has_attr("content") else None

    if not title:
        title = clean_text(get_meta("og:title")) or clean_text(get_meta("twitter:title")) or url
        
    if not description:
        description = clean_text(get_meta("og:description")) or clean_text(get_meta("twitter:description"))
        
    if not image_url:
        image_url = get_meta("og:image") or get_meta("twitter:image")

    host = None
    if title and "Conversations with" in title:
         parts = title.split("Conversations with")
         if len(parts) > 1:
             host = parts[1].split("-")[0].strip()

    genres = []
    review_links = parse_review_links(soup, url)
    
    if image_url and image_url.startswith("//"):
        image_url = "https:" + image_url

    is_popular = any(flag.lower() == "popular" for flag in (flags or []))
    is_award_winning = any("award" in flag.lower() for flag in (flags or []))

    podcast = Podcast(
        title=title or url,
        host_information=host,
        description=description,
        genres=genres,
        abc_podcast_page=url,
        image_url=image_url,
        apple_podcast_page=review_links.apple,
        spotify_podcast_page=review_links.spotify,
        youtube_page=review_links.youtube,
        other_review_links=review_links.others,
        episodes=episodes,
        is_popular=is_popular,
        is_award_winning=is_award_winning,
    )
    return podcast


def parse_review_links(soup: BeautifulSoup, base_url: str) -> ReviewLinks:
    review_links = ReviewLinks()
    seen: set[str] = set()
    
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        try:
            absolute = urljoin(base_url, href)
        except Exception:
            continue
        
        if absolute in seen:
            continue
        seen.add(absolute)
        
        lower_href = absolute.lower()
        if "podcasts.apple.com" in lower_href:
            review_links.apple = review_links.apple or absolute
        elif "spotify.com" in lower_href:
            review_links.spotify = review_links.spotify or absolute
        elif "youtube.com" in lower_href or "youtu.be" in lower_href:
            review_links.youtube = review_links.youtube or absolute
        elif any(domain in lower_href for domain in ["podchaser.com", "listennotes.com", "podcastaddict.com"]):
            review_links.others.append(absolute)
            
    return review_links


def parse_episode_page(html: str) -> Dict[str, Optional[str]]:
    """Extracts MP3 URL and Published Date from an episode page."""
    soup = BeautifulSoup(html, "html.parser")
    next_data = extract_nextjs_data(soup)
    if not next_data:
        return None
        
    found_audio = None
    
    # Recursive search for mp3/m4a in the props
    def find_stream(obj):
        nonlocal found_audio
        if found_audio: return
        
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    if (v.endswith(".mp3") or v.endswith(".m4a")) and "mediacore" in v:
                        found_audio = v
                        return
                elif isinstance(v, (dict, list)):
                    find_stream(v)
        elif isinstance(obj, list):
            for item in obj:
                find_stream(item)

    # Optimization: Look in documentProps first as seen in debug
    props = next_data.get("props", {}).get("pageProps", {})
    doc_props = props.get("data", {}).get("documentProps", {})
    
    published_at = doc_props.get("publishedAt") or doc_props.get("firstPublishedAt") or doc_props.get("updatedAt")
    if not published_at:
        # Fallback to recursively searching for ISO date strings nearby
        pass 
        
    if "renditions" in doc_props:
        for r in doc_props["renditions"]:
            if r.get("url") and r["url"].endswith(".mp3"):
                return {"audio_url": r["url"], "published_at": published_at}
    
    # Fallback to deep search
    find_stream(props)
    return {"audio_url": found_audio, "published_at": published_at}
