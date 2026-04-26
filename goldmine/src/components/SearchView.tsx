import { useState } from 'react';
import type { NormalizedEpisode } from '../types';
import { Icons } from './icons';

export const SearchView = ({ episodes }: { episodes: NormalizedEpisode[] }) => {
    const [query, setQuery] = useState('');

    const getResults = () => {
        if (!query) return [];

        const q = query.toLowerCase();
        const results: any[] = [];

        episodes.forEach(ep => {
            // 1. Search semantic entities
            const matchEntity = ep.entities?.find(e => e.toLowerCase().includes(q));
            if (matchEntity) {
                results.push({ type: 'Entity Match', ep, text: `Matched AI-extracted entity: "${matchEntity}"` });
                return;
            }

            // 2. Deep search the exact segments if it exists
            if (ep.segments) {
                ep.segments.forEach(seg => {
                    if (seg.text.toLowerCase().includes(q)) {
                        const parts = seg.text.split(new RegExp(`(${query})`, 'gi'));
                        results.push({ type: 'Transcript Segment', ep, segment: seg, textParts: parts });
                    }
                });
            }
        });

        return results.slice(0, 50);
    };

    const results = getResults();

    const formatTime = (seconds: number) => {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    };

    return (
        <div style={{ paddingBottom: '120px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>

            {/* Massive Centered Search Area like Spotlight */}
            <div style={{ width: '100%', maxWidth: '800px', margin: '60px 0 40px 0', position: 'relative' }}>
                <h1 className="text-display-large" style={{ textAlign: 'center', marginBottom: '40px' }}>Semantic Search.</h1>

                <div style={{ position: 'relative' }}>
                    <div style={{ position: 'absolute', top: '50%', left: '24px', transform: 'translateY(-50%)', color: 'var(--accent-blue)' }}>
                        <Icons.MagnifyingGlass />
                    </div>
                    <input
                        type="text"
                        placeholder="Search entities, quotes, or themes..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="search-bar"
                    />
                    {query && (
                        <div style={{ position: 'absolute', right: '24px', top: '50%', transform: 'translateY(-50%)', fontSize: '13px', fontWeight: 600, color: 'var(--text-tertiary)' }}>
                            {results.length} results
                        </div>
                    )}
                </div>
            </div>

            {/* Results Container */}
            <div style={{ width: '100%', maxWidth: '800px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {!query ? (
                    <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', padding: '60px 0', fontSize: '18px' }}>
                        <p>Scan through {episodes.length} episodes instantly.</p>
                    </div>
                ) : (
                    results.length === 0 ? (
                        <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '40px 0' }}>
                            No semantic matches found.
                        </div>
                    ) : (
                        results.map((res, i) => (
                            <div key={i} className="glass-card fade-in-up" style={{ padding: '32px', animationDelay: `${Math.min(i * 0.05, 0.5)}s` }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                                    <div>
                                        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-indigo)', textTransform: 'uppercase', letterSpacing: '0.05em', background: 'rgba(94, 92, 230, 0.1)', padding: '4px 8px', borderRadius: '4px' }}>
                                            {res.type}
                                        </span>
                                        <h4 style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: '18px', marginTop: '12px', letterSpacing: '-0.01em' }}>{res.ep.title}</h4>
                                        <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '2px' }}>{res.ep.podcastTitle}</p>
                                    </div>
                                    {res.segment && (
                                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.05)', padding: '4px 8px', borderRadius: '6px' }}>
                                            {formatTime(res.segment.start)}
                                        </div>
                                    )}
                                </div>

                                <div style={{ marginTop: '24px', padding: '24px', background: 'rgba(0,0,0,0.4)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.03)' }}>
                                    {res.textParts ? (
                                        <p style={{ fontSize: '16px', lineHeight: 1.6, color: 'var(--text-primary)' }}>
                                            {res.textParts.map((part: string, idx: number) =>
                                                part.toLowerCase() === query.toLowerCase()
                                                    ? <span key={idx} style={{ color: 'var(--bg-base)', background: 'var(--text-primary)', fontWeight: 600, padding: '0 4px', borderRadius: '2px' }}>{part}</span>
                                                    : <span key={idx} style={{ opacity: 0.9 }}>{part}</span>
                                            )}
                                        </p>
                                    ) : (
                                        <p style={{ fontSize: '16px', color: 'var(--text-secondary)', fontStyle: 'italic' }}>{res.text}</p>
                                    )}

                                    {res.segment?.speaker && (
                                        <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: 'var(--border-highlight)' }} />
                                                <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-secondary)' }}>{res.segment.speaker}</span>
                                            </div>

                                            {res.ep.applePodcastPage && (
                                                <a
                                                    href={res.ep.applePodcastPage}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    style={{
                                                        fontSize: '12px',
                                                        color: 'var(--accent-blue)',
                                                        textDecoration: 'none',
                                                        fontWeight: 600,
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '4px'
                                                    }}
                                                >
                                                    Full Episode <Icons.ExternalLink />
                                                </a>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))
                    )
                )}
            </div>
        </div>
    );
};
