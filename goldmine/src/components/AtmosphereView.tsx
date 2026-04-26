import { useState, useMemo } from 'react';
import type { NormalizedEpisode } from '../types';

export const AtmosphereView = ({ episodes }: { episodes: NormalizedEpisode[] }) => {
    const [selectedTone, setSelectedTone] = useState<string | null>(null);
    const [maxComplexity, setMaxComplexity] = useState(1);
    const [selectedPace, setSelectedPace] = useState<string | null>(null);

    const tones = useMemo(() => {
        const allTones = new Set<string>();
        episodes.forEach(ep => ep.vibe?.tone?.forEach(t => allTones.add(t)));
        return Array.from(allTones).sort();
    }, [episodes]);

    const paces = useMemo(() => {
        const allPaces = new Set<string>();
        episodes.forEach(ep => { if (ep.vibe?.pace) allPaces.add(ep.vibe.pace); });
        return Array.from(allPaces).sort();
    }, [episodes]);

    const filteredEpisodes = episodes.filter(ep => {
        if (selectedTone && !ep.vibe?.tone?.includes(selectedTone)) return false;
        if (ep.vibe?.complexity && ep.vibe.complexity > maxComplexity) return false;
        if (selectedPace && ep.vibe?.pace !== selectedPace) return false;
        return true;
    });

    return (
        <div className="fade-in-up">
            <div style={{ marginBottom: '48px' }}>
                <span className="label-technical">Situational discovery</span>
                <h2 className="headline-large" style={{ marginTop: '8px' }}>Atmosphere <span className="text-gradient">Scout</span></h2>
                <p style={{ color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '600px' }}>
                    Filter the network by narrative vibe, cognitive depth, and conversational tempo.
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '48px', alignItems: 'start' }}>
                {/* Filters Sidebar */}
                <div className="glass-panel" style={{ padding: '24px', position: 'sticky', top: '100px' }}>
                    <div style={{ marginBottom: '32px' }}>
                        <label className="label-technical" style={{ display: 'block', marginBottom: '16px' }}>Narrative Tone</label>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                            <button 
                                onClick={() => setSelectedTone(null)}
                                className={`label-technical`}
                                style={{ 
                                    padding: '6px 12px', 
                                    borderRadius: '4px', 
                                    background: selectedTone === null ? 'var(--primary)' : 'var(--bg-container-highest)',
                                    color: selectedTone === null ? 'var(--on-primary)' : 'var(--text-primary)',
                                    border: 'none',
                                    cursor: 'pointer'
                                }}
                            >
                                ALL
                            </button>
                            {tones.map(tone => (
                                <button 
                                    key={tone}
                                    onClick={() => setSelectedTone(tone)}
                                    className="label-technical"
                                    style={{ 
                                        padding: '6px 12px', 
                                        borderRadius: '4px', 
                                        background: selectedTone === tone ? 'var(--primary)' : 'rgba(255,255,255,0.05)',
                                        color: selectedTone === tone ? 'var(--on-primary)' : 'var(--text-secondary)',
                                        border: 'none',
                                        cursor: 'pointer'
                                    }}
                                >
                                    {tone}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div style={{ marginBottom: '32px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                            <label className="label-technical">Complexity Depth</label>
                            <span className="label-technical" style={{ color: 'var(--primary)' }}>{(maxComplexity * 100).toFixed(0)}%</span>
                        </div>
                        <input 
                            type="range" 
                            min="0" 
                            max="1" 
                            step="0.1" 
                            value={maxComplexity} 
                            onChange={(e) => setMaxComplexity(parseFloat(e.target.value))}
                            style={{ width: '100%', accentColor: 'var(--primary)' }}
                        />
                    </div>

                    <div>
                        <label className="label-technical" style={{ display: 'block', marginBottom: '16px' }}>Tempo (Pace)</label>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                            <button 
                                onClick={() => setSelectedPace(null)}
                                className="label-technical"
                                style={{ 
                                    padding: '6px 12px', 
                                    borderRadius: '4px', 
                                    background: selectedPace === null ? 'var(--secondary)' : 'var(--bg-container-highest)',
                                    color: selectedPace === null ? 'var(--on-secondary)' : 'var(--text-primary)',
                                    border: 'none',
                                    cursor: 'pointer'
                                }}
                            >
                                ALL
                            </button>
                            {paces.map(pace => (
                                <button 
                                    key={pace}
                                    onClick={() => setSelectedPace(pace)}
                                    className="label-technical"
                                    style={{ 
                                        padding: '6px 12px', 
                                        borderRadius: '4px', 
                                        background: selectedPace === pace ? 'var(--secondary)' : 'rgba(255,255,255,0.05)',
                                        color: selectedPace === pace ? 'var(--on-secondary)' : 'var(--text-secondary)',
                                        border: 'none',
                                        cursor: 'pointer'
                                    }}
                                >
                                    {pace}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Results Grid */}
                <div className="content-grid">
                    {filteredEpisodes.map((ep, i) => (
                        <div key={i} className="card-intelligence fade-in-up" style={{ animationDelay: `${i * 0.05}s` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
                                <span className="label-technical" style={{ color: 'var(--primary)' }}>{ep.podcastTitle}</span>
                                {ep.vibe?.pace && (
                                    <span className="label-technical" style={{ opacity: 0.6 }}>{ep.vibe.pace}</span>
                                )}
                            </div>
                            <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '12px' }}>{ep.title}</h3>
                            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '20px', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                {ep.description}
                            </p>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                {ep.vibe?.tone?.map(t => (
                                    <span key={t} style={{ fontSize: '10px', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px', color: 'var(--text-tertiary)' }}>
                                        {t}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};
