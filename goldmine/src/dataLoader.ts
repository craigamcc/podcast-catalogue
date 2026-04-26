import type { Podcast, NormalizedEpisode } from './types';

export const loadPodcastData = async (): Promise<{ podcasts: Podcast[], allEpisodes: NormalizedEpisode[] }> => {
    try {
        const response = await fetch('/data.jsonl');
        const text = await response.text();

        const lines = text.split('\n').filter(line => line.trim().length > 0);
        const podcasts: Podcast[] = lines.map(line => JSON.parse(line));

        // Normalize episodes into a flat array for easy searching/filtering
        const allEpisodes: NormalizedEpisode[] = [];
        podcasts.forEach(podcast => {
            podcast.episodes.forEach(episode => {
                allEpisodes.push({
                    ...episode,
                    podcastTitle: podcast.title,
                    podcastUrl: podcast.url,
                    applePodcastPage: podcast.applePodcastPage
                });
            });
        });

        // Filter down to only episodes with semantic data (segments/entities) for the demo
        const enrichedEpisodes = allEpisodes.filter(ep => ep.segments && ep.segments.length > 0);

        return { podcasts, allEpisodes: enrichedEpisodes };
    } catch (error) {
        console.error("Failed to load podcast data:", error);
        return { podcasts: [], allEpisodes: [] };
    }
};
