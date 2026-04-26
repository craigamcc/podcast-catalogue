import { useMemo } from 'react';
import type { NormalizedEpisode } from '../types';

interface PulseItem {
    type: 'QUOTE' | 'STAT' | 'TAKEAWAY' | 'HIGHLIGHT';
    content: string;
    reason?: string;
    episodeTitle: string;
    podcastTitle: string;
    timestamp?: number;
}

export const FeedPulseView = ({ episodes }: { episodes: NormalizedEpisode[] }) => {
    const pulseItems = useMemo(() => {
        const items: PulseItem[] = [];

        episodes.forEach(ep => {
            // Add Engagement Takeaway
            if (ep.engagement?.takeaway) {
                items.push({
                    type: 'TAKEAWAY',
                    content: ep.engagement.takeaway,
                    episodeTitle: ep.title,
                    podcastTitle: ep.podcastTitle
                });
            }

            // Add Best Quotes
            ep.engagement?.bestQuotes?.forEach(quote => {
                items.push({
                    type: 'QUOTE',
                    content: quote,
                    episodeTitle: ep.title,
                    podcastTitle: ep.podcastTitle
                });
            });

            // Add Key Statistics
            ep.engagement?.keyStatistics?.forEach(stat => {
                items.push({
                    type: 'STAT',
                    content: stat,
                    episodeTitle: ep.title,
                    podcastTitle: ep.podcastTitle
                });
            });

            // Add Highlights
            ep.highlights?.forEach(h => {
                items.push({
                    type: 'HIGHLIGHT',
                    content: h.title,
                    reason: h.reason,
                    episodeTitle: ep.title,
                    podcastTitle: ep.podcastTitle,
                    timestamp: h.startTime
                });
            });
        });

        // Shuffle items for a more "active" feel (since we don't have real dates for all items yet)
        return items.sort(() => Math.random() - 0.5);
    }, [episodes]);

    const TypeBadge = ({ type }: { type: string }) => {
        const colors = {
            QUOTE: 'var(--primary)',
            STAT: 'var(--secondary)',
            TAKEAWAY: 'var(--tertiary)',
            HIGHLIGHT: '#ff8f8f'
        };
        return (
            <span className="label-technical" style={{ 
                color: (colors as any)[type] || 'var(--text-tertiary)',
                background: `${(colors as any)[type]}10`,
                padding: '4px 8px',
                borderRadius: '4px',
                border: `1px solid ${(colors as any)[type]}20`
            }}>
                {type}
            </span>
        );
    };

    return (
        <div className="fade-in-up">
            <div style={{ marginBottom: '48px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                <div>
                    <span className="label-technical">Real-time narrative flow</span>
                    <h2 className="headline-large" style={{ marginTop: '8px' }}>Feed <span className="text-gradient">Pulse</span></h2>
                    <p style={{ color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '600px' }}>
                        The latest insights, provocations, and hard data across the GoldMine network.
                    </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div className="pulse-glow" style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--primary)' }} />
                    <span className="label-technical">Live Feed</span>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '800px', margin: '0 auto' }}>
                {pulseItems.map((item, i) => (
                    <div key={i} className="card-intelligence fade-in-up" style={{ 
                        animationDelay: `${i * 0.1}s`,
                        borderLeft: `4px solid ${item.type === 'QUOTE' ? 'var(--primary)' : item.type === 'STAT' ? 'var(--secondary)' : 'var(--tertiary)'}`
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                            <TypeBadge type={item.type} />
                            <div style={{ textAlign: 'right' }}>
                                <div className="label-technical" style={{ fontSize: '9px' }}>{item.podcastTitle}</div>
                                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.episodeTitle}</div>
                            </div>
                        </div>

                        <div style={{ 
                            fontSize: '18px', 
                            lineHeight: '1.6', 
                            color: 'var(--text-primary)',
                            fontStyle: item.type === 'QUOTE' ? 'italic' : 'normal',
                            fontWeight: 500
                        }}>
                            {item.type === 'QUOTE' ? `"${item.content}"` : item.content}
                        </div>

                        {item.reason && (
                            <div style={{ marginTop: '16px', padding: '12px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                                <span className="label-technical" style={{ fontSize: '9px', display: 'block', marginBottom: '4px' }}>AI Reasoning</span>
                                {item.reason}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};
