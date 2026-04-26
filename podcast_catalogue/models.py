from __future__ import annotations

from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field


class Location(BaseModel):
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None

class GuestProfile(BaseModel):
    name: str
    expertise: Optional[str] = None
    bio: Optional[str] = None
    social_links: List[str] = Field(default_factory=list, alias="socialLinks")

    class Config:
        populate_by_name = True

class EntityProfile(BaseModel):
    name: str = Field(alias="entity_name")
    description: Optional[str] = None
    category: Optional[str] = None

    class Config:
        populate_by_name = True


class TargetAudience(BaseModel):
    interests: List[str] = Field(default_factory=list)
    age_groups: List[str] = Field(default_factory=list, alias="ageGroups")
    location: Location = Field(default_factory=Location)

    class Config:
        populate_by_name = True


class Vibe(BaseModel):
    tone: List[str] = Field(default_factory=list)
    complexity: Optional[float] = None
    pace: Optional[str] = None


class TranscriptSegment(BaseModel):
    text: str
    start: float
    end: float
    speaker: Optional[str] = None


class Chapter(BaseModel):
    title: str
    summary: str
    start_time: float = Field(alias="startTime")
    end_time: float = Field(alias="endTime")

    class Config:
        populate_by_name = True


class Highlight(BaseModel):
    title: str
    reason: str
    category: str = "GENERAL"  # QUOTE, STAT, PEAK, INSIGHT, GENERAL
    start_time: float = Field(alias="startTime")
    end_time: float = Field(alias="endTime")

    class Config:
        populate_by_name = True

class EngagementIntelligence(BaseModel):
    takeaway: Optional[str] = None
    key_statistics: List[str] = Field(default_factory=list, alias="keyStatistics")
    best_quotes: List[str] = Field(default_factory=list, alias="bestQuotes")
    why_listen: Optional[str] = Field(None, alias="whyListen")
    social_post: Optional[str] = Field(None, alias="socialPost")
    audiogram_captions: List[Dict[str, Any]] = Field(default_factory=list, alias="audiogramCaptions")

    class Config:
        populate_by_name = True


class Episode(BaseModel):
    title: str
    description: Optional[str] = None
    published_at: Optional[str] = Field(None, alias="publishedAt")
    duration: Optional[str] = None
    audio_url: Optional[str] = Field(None, alias="audioUrl")
    url: Optional[str] = None # The page URL, needed for deep crawling
    transcript: Optional[str] = None
    
    # Timestamped Segments (from Whisper)
    segments: List[TranscriptSegment] = Field(default_factory=list)
    
    # AI-generated Chapters
    chapters: List[Chapter] = Field(default_factory=list)
    
    # AI-detected Highlights (most exciting moments)
    highlights: List[Highlight] = Field(default_factory=list)
    
    # Content hash for incremental skipping
    content_hash: Optional[str] = Field(None, alias="contentHash")
    
    # AI Enrichment
    narrative_hook: Optional[str] = Field(None, alias="narrativeHook")
    vibe: Optional[Vibe] = Field(None, alias="vibe")
    entities: List[Union[str, EntityProfile]] = Field(default_factory=list)
    content_locations: List[Location] = Field(default_factory=list, alias="contentLocations")
    guests: List[GuestProfile] = Field(default_factory=list)
    engagement: Optional[EngagementIntelligence] = None

    class Config:
        populate_by_name = True


class Review(BaseModel):
    author: str
    rating: float
    content: str
    date: Optional[str] = None

class Podcast(BaseModel):
    title: str
    host_information: Optional[str] = Field(None, alias="hostInformation")
    description: Optional[str] = None
    language: Optional[str] = None
    target_audience: TargetAudience = Field(default_factory=TargetAudience, alias="targetAudience")
    recommendation_scenarios: List[str] = Field(default_factory=list, alias="recommendationScenarios")
    recommendation_reasons: List[str] = Field(default_factory=list, alias="recommendationReasons")
    abc_podcast_page: Optional[str] = Field(None, alias="abcPodcastPage")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    apple_podcast_page: Optional[str] = Field(None, alias="applePodcastPage")
    spotify_podcast_page: Optional[str] = Field(None, alias="spotifyPodcastPage")
    youtube_page: Optional[str] = Field(None, alias="youtubePage")
    other_review_links: List[str] = Field(default_factory=list, alias="otherReviewLinks")
    episodes: List[Episode] = Field(default_factory=list)
    is_popular: bool = Field(False, alias="isPopular")
    is_award_winning: bool = Field(False, alias="isAwardWinning")

    # Enrichment Data
    average_rating: Optional[float] = Field(None, alias="averageRating")
    rating_count: Optional[int] = Field(None, alias="ratingCount")
    itunes_id: Optional[int] = Field(None, alias="itunesId")
    primary_genre: Optional[str] = Field(None, alias="primaryGenre")
    apple_genres: Optional[List[str]] = Field(None, alias="appleGenres")
    reviews: List[Review] = Field(default_factory=list)
    
    # AI Enrichment
    narrative_hook: Optional[str] = Field(None, alias="narrativeHook")
    vibe: Optional[Vibe] = Field(None, alias="vibe")
    origin_location: Location = Field(default_factory=Location, alias="originLocation")
    geographic_coverage: List[Location] = Field(default_factory=list, alias="geographicCoverage")
    scouting_priority: float = Field(0.0, alias="scoutingPriority")

    class Config:
        populate_by_name = True

# Rebuild models for Union/Forward references
Episode.model_rebuild()
Podcast.model_rebuild()
