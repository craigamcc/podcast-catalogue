/**
 * @prism/types — Canonical TypeScript interfaces for the PRISM Podcast Catalogue.
 *
 * Derived from: podcast_catalogue/models.py (Pydantic BaseModels)
 * Canonical source: podcast-catalogue/types/index.ts
 *
 * ALL consumer apps (SoTA, Daisy Web Demo, Reel, Sentinel) MUST import
 * from this package instead of defining their own Episode/Podcast types.
 *
 * Tone convention: string[] (array). PRISM's Python models store tone as a
 * single string; the Daisy adapter normalizes it to an array. Consumer apps
 * should always expect string[].
 */

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

export interface Location {
  country?: string;
  state?: string;
  city?: string;
}

export interface TargetAudience {
  interests: string[];
  ageGroups: string[];
  location?: Location;
}

export interface Vibe {
  /** Normalized to array. Legacy single-string values are wrapped in []. */
  tone: string[];
  /** 0.0 (trivial) to 1.0 (PhD-level). */
  complexity: number;
  /** "Fast" | "Medium" | "Slow" */
  pace: string;
}

// ---------------------------------------------------------------------------
// Transcript & Structural Intelligence
// ---------------------------------------------------------------------------

export interface TranscriptSegment {
  text: string;
  /** Start time in seconds. */
  start: number;
  /** End time in seconds. */
  end: number;
  /** Speaker label (from SpeechBrain diarization). */
  speaker?: string;
}

export interface Chapter {
  title: string;
  summary: string;
  /** Start time in seconds. */
  startTime: number;
  /** End time in seconds. */
  endTime: number;
}

export interface Highlight {
  title: string;
  reason: string;
  /** Start time in seconds. */
  startTime: number;
  /** End time in seconds. */
  endTime: number;
}

// ---------------------------------------------------------------------------
// Review
// ---------------------------------------------------------------------------

export interface Review {
  author: string;
  rating: number;
  content: string;
  date?: string;
}

// ---------------------------------------------------------------------------
// Episode
// ---------------------------------------------------------------------------

export interface Episode {
  title: string;
  description?: string;
  publishedAt?: string;
  /** Duration in seconds (stored as string in PRISM for legacy reasons). */
  duration?: string;
  /** Direct audio URL (MP3). Required for playback and clipping. */
  audioUrl?: string;
  /** Page URL for deep-crawling. */
  url?: string;
  /** Full transcript text (concatenated segments). */
  transcript?: string;

  // --- Timestamped Intelligence ---
  /** Whisper + SpeechBrain segments with speaker labels. */
  segments: TranscriptSegment[];
  /** AI-generated chapter boundaries. */
  chapters: Chapter[];
  /** AI-detected highlight moments (most engaging). */
  highlights: Highlight[];

  /** Content hash for incremental skipping. */
  contentHash?: string;
  /** AI-generated narrative hook (1-2 sentence teaser). */
  narrativeHook?: string;
  /** Episode-level vibe analysis. */
  vibe?: Vibe;
  /** Extracted entities (people, places, topics). */
  entities: string[];
}

// ---------------------------------------------------------------------------
// Podcast (Show-level)
// ---------------------------------------------------------------------------

export interface Podcast {
  title: string;
  hostInformation?: string;
  description?: string;
  language?: string;

  // --- Distribution Links ---
  abcPodcastPage?: string;
  imageUrl?: string;
  applePodcastPage?: string;
  spotifyPodcastPage?: string;
  youtubePage?: string;
  otherReviewLinks?: string[];

  // --- Discovery Metadata ---
  targetAudience?: TargetAudience;
  recommendationScenarios?: string[];
  recommendationReasons?: string[];
  isPopular: boolean;
  isAwardWinning: boolean;

  // --- iTunes Enrichment ---
  averageRating?: number;
  ratingCount?: number;
  itunesId?: number;
  primaryGenre?: string;
  appleGenres?: string[];
  reviews?: Review[];

  // --- AI Enrichment ---
  narrativeHook?: string;
  vibe?: Vibe;

  // --- Content ---
  episodes: Episode[];
}

// ---------------------------------------------------------------------------
// Consumer-side convenience types
// ---------------------------------------------------------------------------

/** A flattened episode with its parent show context attached. */
export interface NormalizedEpisode extends Episode {
  podcastTitle: string;
  podcastImageUrl?: string;
  podcastGenre?: string;
  applePodcastPage?: string;
}

/** Search result from semantic or keyword search. */
export interface SearchResult {
  podcastTitle: string;
  episodeTitle: string;
  audioUrl?: string;
  textSnippet: string;
  relevanceScore: number;
  entities: string[];
}

/** Guest profile (derived from entity + diarization cross-referencing). */
export interface GuestProfile {
  id: string;
  name: string;
  avatar?: string;
  bio?: string;
  snipCount: number;
  roles: string[];
  episodeIds: string[];
}

// ---------------------------------------------------------------------------
// Utility: Vibe normalization
// ---------------------------------------------------------------------------

/**
 * Coerce a raw vibe object (from PRISM's Python output where tone may be
 * a single string) into the canonical form with tone as string[].
 */
export function normalizeVibe(raw: any): Vibe {
  if (!raw) return { tone: ['General'], complexity: 0.5, pace: 'Medium' };

  let tone: string[];
  if (typeof raw.tone === 'string') {
    tone = [raw.tone];
  } else if (Array.isArray(raw.tone)) {
    tone = raw.tone;
  } else {
    tone = ['General'];
  }

  const pace = ['Fast', 'Medium', 'Slow'].includes(raw.pace) ? raw.pace : 'Medium';

  return {
    tone,
    complexity: typeof raw.complexity === 'number' ? raw.complexity : 0.5,
    pace,
  };
}
