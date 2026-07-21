from __future__ import annotations

from enum import Enum
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field, field_validator


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
    same_as: Optional[str] = Field(None, alias="sameAs")  # schema.org sameAs (e.g. Wikidata URL)

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
    
    # Phase 4: Audio-Native Emotional Analysis (Placeholders for Qwen-Audio / Gemini Audio)
    emotional_arousal: Optional[float] = Field(None, alias="emotionalArousal")
    vocal_tension: Optional[float] = Field(None, alias="vocalTension")


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


class TimelineItem(BaseModel):
    title: str
    type: str  # CHAPTER, EXPERT, SHOW_LINK, IMAGE, POLL, AD
    start_time: float = Field(alias="startTime")
    end_time: float = Field(alias="endTime")
    link: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


# --- Editorial Trust Layer (schema.org-aligned) ---

class ClaimStatus(str, Enum):
    """Epistemic classification for extracted claims.
    Sources: GPT-5.5 §4/§9, News Atom knowledge_frame, schema.org Claim."""
    CONFIRMED = "confirmed"       # Stated as fact by authority
    ALLEGED = "alleged"           # Attributed claim ("Police believe...")
    FORECAST = "forecast"         # Forward-looking ("Rates are expected to rise")
    ATTRIBUTED = "attributed"     # Sourced opinion ("The Mayor said...")
    UNVERIFIED = "unverified"     # No clear source or attribution


class SourceAnchor(BaseModel):
    """Provenance link from enriched insight back to source audio.
    Models schema.org/Clip semantics: startOffset, endOffset, partOfEpisode.
    Sources: News Atom media_anchor, schema.org Clip, Spotify Timeline analysis."""
    audio_url: Optional[str] = Field(None, alias="audioUrl")  # Source episode audio
    transcript_text: Optional[str] = Field(None, alias="transcriptText")  # Verbatim text
    timestamp_start: Optional[float] = Field(0.0, alias="timestampStart")  # Seconds
    timestamp_end: Optional[float] = Field(0.0, alias="timestampEnd")  # Seconds
    # Phase 4: Spotify Deep-linking
    spotify_uri: Optional[str] = Field(None, alias="spotifyUri")
    spotify_deep_link: Optional[str] = Field(None, alias="spotifyDeepLink")

    def get_deep_link(self) -> Optional[str]:
        """Generates a timestamped Spotify web URL."""
        if not self.spotify_uri:
            return None
        
        # Convert spotify:episode:ID to web URL
        if self.spotify_uri.startswith("spotify:episode:"):
            ep_id = self.spotify_uri.split(":")[-1]
            base_url = f"https://open.spotify.com/episode/{ep_id}"
        elif "open.spotify.com/episode/" in self.spotify_uri:
            base_url = self.spotify_uri.split("?")[0]
        else:
            return self.spotify_uri
            
        # Add timestamp (integer seconds)
        t = int(self.timestamp_start or 0)
        return f"{base_url}?t={t}"

    class Config:
        populate_by_name = True


class ContentRisk(BaseModel):
    """Risk assessment for downstream content handling.
    Schema.org alignment: projected as contentRating for external consumers.
    Sources: GPT-5.5 §5/§15."""
    level: str = "low"  # "low", "medium", "high"
    categories: List[str] = Field(default_factory=list)  # ["court", "crime", "health", ...]
    requires_human_review: bool = Field(False, alias="requiresHumanReview")

    class Config:
        populate_by_name = True


class AIProvenance(BaseModel):
    """Audit trail for AI-generated enrichment.
    Schema.org alignment: claimInterpreter on Claim objects.
    Sources: News Atom review_process, GPT-5.5 §3."""
    model_name: str = Field(alias="modelName")  # e.g. "gemini-2.5-flash"
    model_version: Optional[str] = Field(None, alias="modelVersion")
    generated_at: Optional[str] = Field(None, alias="generatedAt")  # ISO datetime
    human_reviewed: bool = Field(False, alias="humanReviewed")

    class Config:
        populate_by_name = True


class HighlightCategory(str, Enum):
    """Functional taxonomy of extracted clips/highlights."""
    QUOTE = "QUOTE"        # Verbatim speaker statement
    STAT = "STAT"          # Data point, percentage, or number
    PEAK = "PEAK"          # Emotional or narrative climax
    INSIGHT = "INSIGHT"    # Conceptual takeaway or lesson
    ADVICE = "ADVICE"      # Practical recommendation or guidance
    ANECDOTE = "ANECDOTE"  # Illustrative story or personal incident
    GENERAL = "GENERAL"    # Default fallback

class Highlight(BaseModel):
    title: str
    reason: str
    category: HighlightCategory = HighlightCategory.GENERAL
    start_time: float = Field(alias="startTime")
    end_time: float = Field(alias="endTime")

    # Editorial Trust Fields
    claim_status: Optional[ClaimStatus] = Field(None, alias="claimStatus")
    claim_interpreter: Optional[str] = Field(None, alias="claimInterpreter")  # schema.org claimInterpreter
    source_anchor: Optional[SourceAnchor] = Field(None, alias="sourceAnchor")

    class Config:
        populate_by_name = True

class EngagementIntelligence(BaseModel):
    takeaway: Optional[str] = None
    key_statistics: List[str] = Field(default_factory=list, alias="keyStatistics")
    best_quotes: List[str] = Field(default_factory=list, alias="bestQuotes")
    why_listen: Optional[str] = Field(None, alias="whyListen")
    social_post: Optional[str] = Field(None, alias="socialPost")
    audiogram_captions: List[Dict[str, Any]] = Field(default_factory=list, alias="audiogramCaptions")

    # YouTube Telemetry
    youtube_views: Optional[int] = Field(None, alias="youtubeViews")
    youtube_likes: Optional[int] = Field(None, alias="youtubeLikes")
    youtube_url: Optional[str] = Field(None, alias="youtubeUrl")
    youtube_comments_paused: bool = Field(False, alias="youtubeCommentsPaused")

    class Config:
        populate_by_name = True

class SocialTelemetry(BaseModel):
    """
    Phase 4: Social Synthesis
    Tracks real-time conversation signals from external networks (e.g. X/Twitter)
    that correlate with this episode or highlight.
    """
    platform: str
    discussion_volume: int = Field(0, alias="discussionVolume")
    trending_topics: List[str] = Field(default_factory=list, alias="trendingTopics")
    recent_mentions: List[str] = Field(default_factory=list, alias="recentMentions")
    
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
    
    # Deep Context Timeline (Rich Markers)
    timeline: List[TimelineItem] = Field(default_factory=list)

    # --- Editorial Trust Layer (schema.org-aligned) ---
    genre: Optional[str] = None  # schema.org genre (news_bulletin, interview, etc.)
    content_risk: Optional[ContentRisk] = Field(None, alias="contentRisk")
    ai_provenance: Optional[AIProvenance] = Field(None, alias="aiProvenance")
    expires: Optional[str] = None  # schema.org expires (ISO datetime)
    content_reference_time: Optional[str] = Field(None, alias="contentReferenceTime")  # schema.org
    source_organization: Optional[str] = Field(None, alias="sourceOrganization")
    authority_score: float = Field(0.5, alias="authorityScore")

    # Phase 4: Social Syntheis
    social_telemetry: List[SocialTelemetry] = Field(default_factory=list, alias="socialTelemetry")

    @field_validator("guests", mode="before")
    @classmethod
    def _coerce_string_guests(cls, v):
        """Accept bare-string guests (["Jane Doe"]) as GuestProfile(name=...).

        Some enriched records store guests as a plain list of names rather than
        objects. Coerce here so a name-only guest never quarantines an entire
        show at the normalization boundary.
        """
        if isinstance(v, list):
            return [{"name": g} if isinstance(g, str) else g for g in v]
        return v

    class Config:
        populate_by_name = True


class Review(BaseModel):
    author: str
    rating: float
    content: str
    date: Optional[str] = None

class StorylineUpdate(BaseModel):
    update_id: str = Field(..., alias="updateId")
    episode_title: str = Field(..., alias="episodeTitle")
    date: str
    summary: str
    clip_reference: Optional[str] = Field(None, alias="clipReference")

    class Config:
        populate_by_name = True

class CanonicalEvent(BaseModel):
    event_id: str = Field(..., alias="eventId")
    title: str
    description: str
    date: str
    tags: List[str] = Field(default_factory=list)
    storyline_updates: List[StorylineUpdate] = Field(default_factory=list, alias="storylineUpdates")

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
    authority_score: float = Field(0.5, alias="authorityScore")

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

    # --- Editorial Trust Layer (schema.org-aligned) ---
    genre: Optional[str] = None  # schema.org genre (news_bulletin, interview, etc.)
    license: Optional[str] = None  # schema.org license (all_rights_reserved, cc_by, etc.)
    license_url: Optional[str] = Field(None, alias="licenseUrl")  # schema.org license URL
    source_organization: Optional[str] = Field(None, alias="sourceOrganization")  # schema.org
    origin: Optional[str] = None # Broad origin tracker (e.g. ABC Radio National)

    class Config:
        populate_by_name = True

# Rebuild all models for Python 3.14 + Pydantic v2 forward reference resolution
Location.model_rebuild()
GuestProfile.model_rebuild()
EntityProfile.model_rebuild()
TargetAudience.model_rebuild()
Vibe.model_rebuild()
TranscriptSegment.model_rebuild()
Chapter.model_rebuild()
TimelineItem.model_rebuild()
SourceAnchor.model_rebuild()
ContentRisk.model_rebuild()
AIProvenance.model_rebuild()
Highlight.model_rebuild()
EngagementIntelligence.model_rebuild()
Episode.model_rebuild()
Review.model_rebuild()
Podcast.model_rebuild()
CanonicalEvent.model_rebuild()

class RegionalPulse(BaseModel):
    region_id: str = Field(..., alias="regionId")
    date: str
    master_summary: str = Field(..., alias="masterSummary")
    narrative_shifts: List[Dict[str, Any]] = Field(default_factory=list, alias="narrativeShifts")
    featured_episodes: List[str] = Field(default_factory=list, alias="featuredEpisodes")
    canonical_events: List[CanonicalEvent] = Field(default_factory=list, alias="canonicalEvents")

    class Config:
        populate_by_name = True

RegionalPulse.model_rebuild()
