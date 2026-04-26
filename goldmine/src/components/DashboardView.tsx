import { useState } from 'react';
import type { NormalizedEpisode } from '../types';
import { Icons } from './icons';

interface DashboardProps {
    episodes: NormalizedEpisode[];
}

export const DashboardView = ({ episodes }: DashboardProps) => {
    const [selectedPersona, setSelectedPersona] = useState<string>('all');
    const [isScouring, setIsScouring] = useState(false);

    const totalEntities = episodes.reduce((acc, ep) => acc + (ep.entities?.length || 0), 0);

    const getTopScouredEpisodes = () => {
        if (selectedPersona === 'all') return episodes.slice(0, 5);

        return episodes.filter(ep => {
            const tone = ep.vibe?.tone?.toLowerCase() || '';
            const entities = (ep.entities || []).join(' ').toLowerCase();

            switch (selectedPersona) {
                case 'tech':
                    return tone.includes('tech') || tone.includes('academic') || entities.includes('ai') || entities.includes('technology');
                case 'drama':
                    return tone.includes('tense') || tone.includes('heated') || tone.includes('argument');
                case 'finance':
                    return tone.includes('serious') || entities.includes('money') || entities.includes('tax') || entities.includes('economy');
                default:
                    return true;
            }
        }).slice(0, 5);
    };

    const handleScour = (persona: string) => {
        setSelectedPersona(persona);
        setIsScouring(true);
        setTimeout(() => setIsScouring(false), 1200);
    };

    const scouredResults = getTopScouredEpisodes();

    const FilterPill = ({ id, label }: { id: string, label: string }) => (
        <button
            onClick={() => handleScour(id)}
            style={{
                padding: '10px 24px',
                borderRadius: '999px',
                fontSize: '15px',
                fontWeight: 500,
                color: selectedPersona === id ? '#000' : 'var(--text-primary)',
                background: selectedPersona === id ? '#fff' : 'rgba(255,255,255,0.05)',
                border: `1px solid ${selectedPersona === id ? '#fff' : 'var(--border-subtle)'}`,
                transition: 'all 0.4s var(--ease-out-expo)'
            }}
        >
            {label}
        </button>
    );

    return (
        <div style={{ paddingBottom: '100px' }}>

            {/* Hero Section */}
            <div style={{ textAlign: 'center', marginBottom: '80px', marginTop: '40px' }}>
                <h1 className="text-display-hero" style={{ marginBottom: '16px' }}>The Scour Engine.</h1>
                <p className="text-subheadline" style={{ maxWidth: '600px', margin: '0 auto' }}>
                    Simulating how Prism vectors semantic dimensions to power hyper-personalized client agents.
                </p>
            </div>

            {/* Widget Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px', marginBottom: '80px' }}>
                <div className="glass-card" style={{ padding: '32px', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ color: 'var(--accent-blue)', marginBottom: '24px', opacity: 0.8 }}><Icons.ChartBar /></div>
                    <div style={{ fontSize: '48px', fontWeight: 600, letterSpacing: '-0.04em', lineHeight: 1, marginBottom: '8px' }}>{episodes.length}</div>
                    <div style={{ color: 'var(--text-tertiary)', fontWeight: 500, fontSize: '15px' }}>Semantic Episodes</div>
                </div>
                <div className="glass-card" style={{ padding: '32px', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ color: 'var(--accent-purple)', marginBottom: '24px', opacity: 0.8 }}><Icons.Sparkles /></div>
                    <div style={{ fontSize: '48px', fontWeight: 600, letterSpacing: '-0.04em', lineHeight: 1, marginBottom: '8px' }}>{totalEntities.toLocaleString()}</div>
                    <div style={{ color: 'var(--text-tertiary)', fontWeight: 500, fontSize: '15px' }}>Extracted Entities</div>
                </div>
                <div className="glass-card" style={{ padding: '32px', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ color: 'var(--accent-indigo)', marginBottom: '24px', opacity: 0.8 }}><Icons.MagnifyingGlass /></div>
                    <div style={{ fontSize: '48px', fontWeight: 600, letterSpacing: '-0.04em', lineHeight: 1, marginBottom: '8px' }}>{(totalEntities * 3.4).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                    <div style={{ color: 'var(--text-tertiary)', fontWeight: 500, fontSize: '15px' }}>Data Points Indexed</div>
                </div>
            </div>

            {/* The Scour Interface */}
            <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '32px' }}>
                    <h2 className="text-display-large">Curated Top 5</h2>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <FilterPill id="all" label="General" />
                        <FilterPill id="tech" label="Tech Focus" />
                        <FilterPill id="drama" label="High Drama" />
                    </div>
                </div>

                {isScouring ? (
                    <div style={{ height: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                        <div style={{ fontSize: '24px', color: 'var(--text-secondary)', animation: 'pulse 1.5s infinite' }}>Prism is mapping semantic vectors...</div>
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {scouredResults.map((ep, idx) => (
                            <div key={idx} className="glass-card fade-in-up" style={{ padding: '32px 40px', display: 'flex', alignItems: 'center', gap: '32px', animationDelay: `${idx * 0.1}s` }}>
                                <div style={{ fontSize: '48px', fontWeight: 700, opacity: 0.1, fontVariantNumeric: 'tabular-nums' }}>
                                    0{idx + 1}
                                </div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <h3 style={{ fontSize: '22px', fontWeight: 600, letterSpacing: '-0.01em', marginBottom: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ep.title}</h3>
                                    <p style={{ color: 'var(--text-secondary)', fontSize: '16px', marginBottom: '16px' }}>{ep.podcastTitle}</p>

                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                            {ep.vibe && (
                                                <span style={{ padding: '4px 12px', background: 'rgba(255,255,255,0.1)', borderRadius: '6px', fontSize: '13px', fontWeight: 500 }}>
                                                    {ep.vibe.tone}
                                                </span>
                                            )}
                                            {ep.entities && ep.entities.slice(0, 3).map((ent, i) => (
                                                <span key={i} style={{ padding: '4px 12px', background: 'transparent', border: '1px solid var(--border-subtle)', borderRadius: '6px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                                                    {ent}
                                                </span>
                                            ))}
                                        </div>

                                        {ep.applePodcastPage && (
                                            <a
                                                href={ep.applePodcastPage}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="btn-primary"
                                                style={{
                                                    fontSize: '13px',
                                                    padding: '8px 16px',
                                                    textDecoration: 'none',
                                                    background: 'rgba(255,255,255,0.1)',
                                                    border: '1px solid var(--border-subtle)',
                                                    color: 'var(--text-primary)',
                                                    borderRadius: '6px',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '6px'
                                                }}
                                            >
                                                Listen on Apple
                                                <Icons.ExternalLink />
                                            </a>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};
