/**
 * @prism/types - Single Source of Truth
 * Canonical types for the Prism Intelligence Ecosystem.
 * Derived from pydantic models in podcast-catalogue/podcast_catalogue/models.py
 */

export interface Location {
  country?: string;
  state?: string;
  city?: string;
}

export interface GuestProfile {
  name: string;
  expertise?: string;
  bio?: string;
  socialLinks: string[];
}

export interface Vibe {
  tone: string[]; // PRISM v5.0 Canonical: Tone is now a list
  complexity: number; // 0.0 - 1.0
  pace: string; // "Fast" | "Medium" | "Slow"
}

export interface TranscriptSegment {
  text: string;
  start: number;
  end: number;
  speaker?: string;
}

export interface Chapter {
  title: string;
  summary: string;
  startTime: number;
  endTime: number;
}

export interface Highlight {
  title: string;
  reason: string;
  startTime: number;
  endTime: number;
}

export interface Episode {
  title: string;
  description?: string;
  publishedAt?: string;
  duration?: string;
  audioUrl?: string;
  url?: string;
  transcript?: string;
  segments: TranscriptSegment[];
  chapters: Chapter[];
  highlights: Highlight[];
  contentHash?: string;
  narrativeHook?: string;
  vibe?: Vibe;
  entities: string[];
  contentLocations: Location[];
  guests: GuestProfile[];
}

export interface TargetAudience {
  interests: string[];
  ageGroups: string[];
  location: Location;
}

export interface Review {
  author: string;
  rating: number;
  content: string;
  date?: string;
}

export interface Podcast {
  title: string;
  hostInformation?: string;
  description?: string;
  language?: string;
  imageUrl?: string;
  abcPodcastPage?: string;
  applePodcastPage?: string;
  spotifyPodcastPage?: string;
  primaryGenre?: string;
  appleGenres?: string[];
  averageRating?: number;
  ratingCount?: number;
  isPopular: boolean;
  isAwardWinning: boolean;
  narrativeHook?: string;
  vibe?: Vibe;
  targetAudience: TargetAudience;
  recommendationScenarios: string[];
  recommendationReasons: string[];
  originLocation: Location;
  geographicCoverage: Location[];
  episodes: Episode[];
  reviews: Review[];
  itunesId?: number;
}
