import { useMemo } from 'react';
import type { NormalizedEpisode, GuestProfile } from '../types';

interface GuestWithEpisodes extends GuestProfile {
    episodes: { title: string, podcastTitle: string }[];
}

export const GuestsView = ({ episodes }: { episodes: NormalizedEpisode[] }) => {
    const guests = useMemo(() => {
        const guestMap = new Map<string, GuestWithEpisodes>();
        
        episodes.forEach(ep => {
            ep.guests?.forEach(g => {
                if (!guestMap.has(g.name)) {
                    guestMap.set(g.name, { ...g, episodes: [] });
                }
                const entry = guestMap.get(g.name)!;
                if (!entry.episodes.find(e => e.title === ep.title)) {
                    entry.episodes.push({ title: ep.title, podcastTitle: ep.podcastTitle });
                }
            });
        });

        return Array.from(guestMap.values()).sort((a, b) => b.episodes.length - a.episodes.length);
    }, [episodes]);

    return (
        <div className="fade-in-up">
            <div style={{ marginBottom: '48px' }}>
                <span className="label-technical">Human intelligence network</span>
                <h2 className="headline-large" style={{ marginTop: '8px' }}>Guests <span className="text-gradient">& Experts</span></h2>
                <p style={{ color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '600px' }}>
                    Discover the voices and expertise powering the GoldMine network.
                </p>
            </div>

            <div className="content-grid">
                {guests.map((guest, i) => (
                    <div key={i} className="card-intelligence fade-in-up" style={{ animationDelay: `${i * 0.05}s` }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '20px' }}>
                            <div style={{ 
                                width: '48px', 
                                height: '48px', 
                                borderRadius: '12px', 
                                background: 'linear-gradient(135deg, var(--tertiary) 0%, var(--tertiary-container) 100%)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                color: 'var(--on-tertiary)',
                                fontSize: '20px',
                                fontWeight: 700
                            }}>
                                {guest.name.charAt(0)}
                            </div>
                            <div>
                                <h3 style={{ fontSize: '18px', fontWeight: 600 }}>{guest.name}</h3>
                                {guest.expertise && (
                                    <span className="label-technical" style={{ color: 'var(--tertiary)', fontSize: '10px' }}>{guest.expertise}</span>
                                )}
                            </div>
                        </div>

                        {guest.bio && (
                            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '20px', lineHeight: '1.5' }}>
                                {guest.bio}
                            </p>
                        )}

                        <div>
                            <label className="label-technical" style={{ display: 'block', marginBottom: '12px', fontSize: '9px' }}>Featured In ({guest.episodes.length})</label>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {guest.episodes.slice(0, 3).map((ep, j) => (
                                    <div key={j} style={{ padding: '8px', background: 'rgba(255,255,255,0.03)', borderRadius: '4px' }}>
                                        <div className="label-technical" style={{ fontSize: '8px', opacity: 0.6 }}>{ep.podcastTitle}</div>
                                        <div style={{ fontSize: '12px', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ep.title}</div>
                                    </div>
                                ))}
                                {guest.episodes.length > 3 && (
                                    <span className="label-technical" style={{ fontSize: '9px', textAlign: 'center', marginTop: '4px' }}>+ {guest.episodes.length - 3} more</span>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
