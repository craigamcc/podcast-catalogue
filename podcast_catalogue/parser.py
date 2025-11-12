from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin

from .models import Location, Podcast, TargetAudience

JSON_LD_RE = re.compile(r"<script[^>]+type=\"application/ld\+json\"[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class _Link:
    href: str
    text: str


@dataclass
class ReviewLinks:
    apple: Optional[str] = None
    spotify: Optional[str] = None
    youtube: Optional[str] = None
    others: List[str] = field(default_factory=list)


class _LinkCollector(HTMLParser):
    def __init__(self, predicate):
        super().__init__()
        self.predicate = predicate
        self.links: List[_Link] = []
        self._current_href: Optional[str] = None
        self._text_parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attr_dict = dict(attrs)
        href = attr_dict.get("href")
        if href and self.predicate(href):
            self._current_href = href
            self._text_parts = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._current_href is not None:
            text = clean_text("".join(self._text_parts))
            self.links.append(_Link(self._current_href, text))
            self._current_href = None
            self._text_parts = []


def clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


def extract_json_ld_objects(html: str) -> List[dict]:
    objects: List[dict] = []
    for match in JSON_LD_RE.finditer(html):
        try:
            raw = match.group(1)
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            objects.extend(obj for obj in data if isinstance(obj, dict))
        elif isinstance(data, dict):
            objects.append(data)
    return objects


def _find_podcast_schema(objects: Iterable[dict]) -> Optional[dict]:
    for obj in objects:
        type_field = obj.get("@type")
        if isinstance(type_field, list):
            types = [str(t).lower() for t in type_field]
        else:
            types = [str(type_field).lower()] if type_field else []
        if any("podcast" in t for t in types):
            return obj
    return None


def parse_podcast_links(index_html: str, base_url: str) -> List[str]:
    def predicate(href: str) -> bool:
        return "/listen/programs/" in href

    collector = _LinkCollector(predicate)
    collector.feed(index_html)
    unique: Dict[str, str] = {}
    for link in collector.links:
        absolute = urljoin(base_url, link.href)
        unique[absolute] = link.text or absolute
    return sorted(unique.keys())


def parse_flag_sections(flags_html: str, base_url: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current_heading: Optional[str] = None

    class FlagParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            nonlocal current_heading
            if tag in {"h2", "h3"}:
                current_heading = ""
            elif tag == "a" and current_heading is not None:
                attr_dict = dict(attrs)
                href = attr_dict.get("href")
                if href and "/listen/programs/" in href:
                    absolute = urljoin(base_url, href)
                    heading_key = clean_text(current_heading)
                    if heading_key:
                        sections.setdefault(heading_key, []).append(absolute)

        def handle_data(self, data):
            nonlocal current_heading
            if current_heading is not None:
                current_heading += data

        def handle_endtag(self, tag):
            nonlocal current_heading
            if tag in {"h2", "h3"} and current_heading is not None:
                current_heading = clean_text(current_heading)

    parser = FlagParser()
    parser.feed(flags_html)

    flag_map: Dict[str, List[str]] = {}
    for heading, links in sections.items():
        flag_label = None
        lower_heading = heading.lower()
        if "popular" in lower_heading:
            flag_label = "Popular"
        elif "award" in lower_heading:
            flag_label = "Award Winning"
        if not flag_label:
            continue
        for link in links:
            flag_map.setdefault(link, []).append(flag_label)
    return flag_map


def _normalise_list(value) -> List[str]:
    if isinstance(value, list):
        return [clean_text(str(item)) for item in value if clean_text(str(item))]
    if value:
        return [clean_text(str(value))]
    return []


def _extract_host(schema: dict) -> Optional[str]:
    creator = schema.get("creator") or schema.get("author") or schema.get("host")
    if isinstance(creator, list):
        names = []
        for item in creator:
            if isinstance(item, dict) and item.get("name"):
                names.append(clean_text(str(item["name"])))
            elif item:
                names.append(clean_text(str(item)))
        return ", ".join(name for name in names if name)
    if isinstance(creator, dict) and creator.get("name"):
        return clean_text(str(creator["name"]))
    if isinstance(creator, str):
        return clean_text(creator)
    return None


def _derive_target_audience(schema: dict, description: str) -> TargetAudience:
    interests = []
    genres = _normalise_list(schema.get("genre"))
    if genres:
        interests.extend(genres)
    keywords = _normalise_list(schema.get("keywords"))
    for keyword in keywords:
        if keyword not in interests:
            interests.append(keyword)
    if description:
        lowered = description.lower()
        if "children" in lowered or "kids" in lowered:
            age_groups = ["Children"]
        elif "teen" in lowered:
            age_groups = ["Teens"]
        else:
            age_groups = ["Adults"]
    else:
        age_groups = ["Adults"]
    language = clean_text(str(schema.get("inLanguage"))) if schema.get("inLanguage") else None
    location = Location(country="Australia" if language and "english" in language.lower() else None)
    target = TargetAudience(interests=interests, age_groups=age_groups, location=location)
    return target


def _derive_recommendations(genres: List[str], description: str) -> (List[str], List[str]):
    scenarios: List[str] = []
    reasons: List[str] = []
    lower_genres = [g.lower() for g in genres]
    lowered_description = description.lower() if description else ""

    if any(g in lower_genres for g in ["news", "current affairs"]):
        scenarios.append("Staying informed")
        reasons.append("Covers current events with timely analysis.")
    if any(g in lower_genres for g in ["comedy", "entertainment"]):
        scenarios.append("Relaxing")
        reasons.append("Light-hearted content ideal for winding down.")
    if any(g in lower_genres for g in ["education", "history", "science"]):
        if "Learning" not in scenarios:
            scenarios.append("Learning")
        reasons.append("Informative episodes that deepen subject knowledge.")
    if any(g in lower_genres for g in ["sport", "sports"]):
        scenarios.append("Commute")
        reasons.append("Quick updates perfect for listening on the go.")
    if not scenarios and lowered_description:
        scenarios.append("General listening")
        reasons.append("Engaging storytelling suitable for most situations.")

    # Deduplicate while preserving order
    def dedupe(values: List[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    return dedupe(scenarios), dedupe(reasons)


def parse_review_links(html: str, base_url: str) -> ReviewLinks:
    collector = _LinkCollector(lambda href: True)
    collector.feed(html)
    review_links = ReviewLinks()
    seen: set[str] = set()
    for link in collector.links:
        href = link.href
        if href.startswith("/"):
            href = urljoin(base_url, href)
        lower_href = href.lower()
        if href in seen:
            continue
        seen.add(href)
        if "podcasts.apple.com" in lower_href:
            review_links.apple = review_links.apple or href
        elif "spotify.com" in lower_href:
            review_links.spotify = review_links.spotify or href
        elif "youtube.com" in lower_href or "youtu.be" in lower_href:
            review_links.youtube = review_links.youtube or href
        elif any(domain in lower_href for domain in ["podchaser.com", "listennotes.com", "podcastaddict.com"]):
            review_links.others.append(href)
    return review_links


def parse_podcast_detail(html: str, url: str, flags: Optional[List[str]] = None) -> Podcast:
    objects = extract_json_ld_objects(html)
    schema = _find_podcast_schema(objects) or {}

    title = clean_text(schema.get("name")) or clean_text(_extract_meta(html, "og:title")) or url
    description = clean_text(schema.get("description")) or clean_text(_extract_meta(html, "og:description"))
    language = clean_text(schema.get("inLanguage")) or clean_text(_extract_meta(html, "og:locale"))
    genres = _normalise_list(schema.get("genre"))
    host = _extract_host(schema)
    target = _derive_target_audience(schema, description)
    scenarios, reasons = _derive_recommendations(genres, description)
    review_links = parse_review_links(html, url)
    is_popular = any(flag.lower() == "popular" for flag in (flags or []))
    is_award_winning = any("award" in flag.lower() for flag in (flags or []))

    podcast = Podcast(
        title=title or url,
        host_information=host,
        description=description,
        genres=genres,
        language=language,
        target_audience=target,
        recommendation_scenarios=scenarios,
        recommendation_reasons=reasons,
        abc_podcast_page=url,
        apple_podcast_page=review_links.apple,
        spotify_podcast_page=review_links.spotify,
        youtube_page=review_links.youtube,
        other_review_links=review_links.others,
        is_popular=is_popular,
        is_award_winning=is_award_winning,
    )
    return podcast


def _extract_meta(html: str, property_name: str) -> Optional[str]:
    pattern = re.compile(
        rf"<meta[^>]+property=\"{re.escape(property_name)}\"[^>]+content=\"(.*?)\"", re.IGNORECASE
    )
    match = pattern.search(html)
    if match:
        return match.group(1)
    name_pattern = re.compile(
        rf"<meta[^>]+name=\"{re.escape(property_name)}\"[^>]+content=\"(.*?)\"", re.IGNORECASE
    )
    match = name_pattern.search(html)
    if match:
        return match.group(1)
    return None
