export interface Chapter {
    title: string;
    summary: string;
    startTime: number;
    endTime: number;
}

export interface Segment {
    start: number;
    end: number;
    text: string;
    speaker?: string;
}

export interface Highlight {
    title: string;
    reason: string;
    category: 'QUOTE' | 'STAT' | 'PEAK' | 'INSIGHT' | 'GENERAL';
    startTime: number;
    endTime: number;
}

export interface EngagementIntelligence {
    takeaway?: string;
    keyStatistics: string[];
    bestQuotes: string[];
    whyListen?: string;
    socialPost?: string;
}

export interface GuestProfile {
    name: string;
    expertise?: string;
    bio?: string;
    socialLinks: string[];
}

export interface Vibe {
    tone: string[];
    complexity: number;
    pace: string;
}

export interface Episode {
    title: string;
    url: string;
    audioUrl: string;
    description: string;
    duration?: string;
    contentHash?: string;
    publishedAt?: string;
    chapters?: Chapter[];
    segments?: Segment[];
    highlights?: Highlight[];
    transcript?: string;
    entities?: any[];
    vibe?: Vibe;
    narrativeHook?: string;
    guests?: GuestProfile[];
    engagement?: EngagementIntelligence;
}

export interface Podcast {
    title: string;
    url: string;
    description?: string;
    imageUrl?: string;
    episodes: Episode[];
    vibe?: Vibe;
    averageRating?: number;
    primaryGenre?: string;
}

// Normalized Data Structure for the UI
export interface NormalizedEpisode extends Episode {
    podcastTitle: string;
    podcastUrl?: string;
    applePodcastPage?: string;
    podcastId?: string;
}
