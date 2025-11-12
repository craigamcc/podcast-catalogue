from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


def _ts_literal(value: Optional[str]) -> str:
    return json.dumps(value) if value is not None else "null"


@dataclass
class Location:
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None

    def to_typescript(self, indent: str = "        ") -> str:
        parts = [
            f"country: {_ts_literal(self.country)}",
            f"state: {_ts_literal(self.state)}",
            f"city: {_ts_literal(self.city)}",
        ]
        formatted = ", ".join(parts)
        return "{ " + formatted + " }"


@dataclass
class TargetAudience:
    interests: List[str] = field(default_factory=list)
    age_groups: List[str] = field(default_factory=list)
    location: Location = field(default_factory=Location)

    def to_typescript(self, indent: str = "      ") -> str:
        interests_ts = (
            "[" + ", ".join(json.dumps(item) for item in self.interests) + "]"
            if self.interests
            else "[]"
        )
        age_groups_ts = (
            "[" + ", ".join(json.dumps(item) for item in self.age_groups) + "]"
            if self.age_groups
            else "[]"
        )
        location_ts = self.location.to_typescript(indent=indent + "  ")
        inner_indent = indent + "  "
        return (
            "{\n"
            f"{inner_indent}interests: {interests_ts},\n"
            f"{inner_indent}ageGroups: {age_groups_ts},\n"
            f"{inner_indent}location: {location_ts}\n"
            f"{indent}" + "}"
        )


@dataclass
class Podcast:
    title: str
    host_information: Optional[str]
    description: Optional[str]
    genres: List[str] = field(default_factory=list)
    language: Optional[str] = None
    target_audience: TargetAudience = field(default_factory=TargetAudience)
    recommendation_scenarios: List[str] = field(default_factory=list)
    recommendation_reasons: List[str] = field(default_factory=list)
    abc_podcast_page: Optional[str] = None
    apple_podcast_page: Optional[str] = None
    spotify_podcast_page: Optional[str] = None
    youtube_page: Optional[str] = None
    other_review_links: List[str] = field(default_factory=list)
    is_popular: bool = False
    is_award_winning: bool = False

    def to_typescript(self, indent: str = "  ") -> str:
        inner_indent = indent + "  "
        target_ts = self.target_audience.to_typescript(indent=inner_indent)
        genre_value = ", ".join(self.genres) if self.genres else ""
        scenarios_ts = (
            "[" + ", ".join(json.dumps(s) for s in self.recommendation_scenarios) + "]"
            if self.recommendation_scenarios
            else "[]"
        )
        reasons_ts = (
            "[" + ", ".join(json.dumps(r) for r in self.recommendation_reasons) + "]"
            if self.recommendation_reasons
            else "[]"
        )
        other_links_ts = (
            "[" + ", ".join(json.dumps(link) for link in self.other_review_links) + "]"
            if self.other_review_links
            else "[]"
        )

        fields = [
            f"{inner_indent}title: {json.dumps(self.title)}",
            f"{inner_indent}hostInformation: {_ts_literal(self.host_information)}",
            f"{inner_indent}description: {_ts_literal(self.description)}",
            f"{inner_indent}genre: {json.dumps(genre_value)}",
            f"{inner_indent}language: {_ts_literal(self.language)}",
            f"{inner_indent}targetAudience: {target_ts}",
            f"{inner_indent}recommendationScenarios: {scenarios_ts}",
            f"{inner_indent}recommendationReasons: {reasons_ts}",
            f"{inner_indent}abcPodcastPage: {_ts_literal(self.abc_podcast_page)}",
            f"{inner_indent}applePodcastPage: {_ts_literal(self.apple_podcast_page)}",
        ]

        if self.spotify_podcast_page:
            fields.append(f"{inner_indent}spotifyPodcastPage: {_ts_literal(self.spotify_podcast_page)}")
        if self.youtube_page:
            fields.append(f"{inner_indent}youtubePage: {_ts_literal(self.youtube_page)}")
        if self.other_review_links:
            fields.append(f"{inner_indent}otherReviewLinks: {other_links_ts}")

        fields.extend(
            [
                f"{inner_indent}isPopular: {str(self.is_popular).lower()}",
                f"{inner_indent}isAwardWinning: {str(self.is_award_winning).lower()}",
            ]
        )

        lines = []
        for index, field in enumerate(fields):
            suffix = "," if index < len(fields) - 1 else ""
            lines.append(f"{field}{suffix}")

        return "{\n" + "\n".join(lines) + f"\n{indent}" + "}"
