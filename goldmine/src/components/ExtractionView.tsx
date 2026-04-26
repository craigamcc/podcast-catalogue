import { useState } from 'react';
import type { NormalizedEpisode, Segment } from '../types';
import { Icons } from './icons';

export const ExtractionView = ({ episodes }: { episodes: NormalizedEpisode[] }) => {
    const [selectedEp, setSelectedEp] = useState<NormalizedEpisode | null>(null);
    const [isExtracting, setIsExtracting] = useState(false);
    const [extractedSegment, setExtractedSegment] = useState<Segment | null>(null);

    const handleSelectEpisode = (ep: NormalizedEpisode) => {
        setSelectedEp(ep);
        setExtractedSegment(null);
    };

    const handleExtract = () => {
        if (!selectedEp || !selectedEp.segments || selectedEp.segments.length === 0) return;

        setIsExtracting(true);
        setExtractedSegment(null);

        setTimeout(() => {
            const midPoint = Math.floor(selectedEp.segments!.length / 2);
            setExtractedSegment(selectedEp.segments![midPoint]);
            setIsExtracting(false);
        }, 2000); // slightly longer for the "magic" feel
    };

    return (
        <div style={{ paddingBottom: '120px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>

            <div style={{ width: '100%', maxWidth: '1000px', margin: '40px 0' }}>
                <h2 className="text-display-large" style={{ marginBottom: '16px' }}>Extraction Studio.</h2>
                <p className="text-subheadline" style={{ maxWidth: '600px' }}>
                    Simulate the automated discovery pipeline. Find emotional peaks and orchestrate FFmpeg render graphs instantly.
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '32px', width: '100%', maxWidth: '1000px' }}>

                {/* Source Selection - Clean Native List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px', paddingLeft: '8px' }}>Source Audio</h3>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '600px', overflowY: 'auto', paddingRight: '8px' }}>
                        {episodes.map((ep, i) => (
                            <div
                                key={i}
                                onClick={() => handleSelectEpisode(ep)}
                                style={{
                                    padding: '16px 20px',
                                    borderRadius: '12px',
                                    cursor: 'pointer',
                                    background: selectedEp === ep ? 'rgba(255,255,255,0.1)' : 'transparent',
                                    border: `1px solid ${selectedEp === ep ? 'rgba(255,255,255,0.2)' : 'transparent'}`,
                                    transition: 'all 0.2s var(--ease-out-expo)'
                                }}
                                onMouseEnter={(e) => {
                                    if (selectedEp !== ep) e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                                }}
                                onMouseLeave={(e) => {
                                    if (selectedEp !== ep) e.currentTarget.style.background = 'transparent';
                                }}
                            >
                                <h4 style={{ fontWeight: 600, fontSize: '15px', color: 'var(--text-primary)', marginBottom: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ep.title}</h4>
                                <p style={{ fontSize: '13px', color: 'var(--text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ep.podcastTitle}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Extraction Engine - Massive Glass Canvas */}
                <div className="glass-card" style={{ height: '600px', display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>

                    {!selectedEp ? (
                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
                            <div style={{ fontSize: '32px', marginBottom: '16px', opacity: 0.5 }}><Icons.Film /></div>
                            <p style={{ fontSize: '16px' }}>Select an episode to begin.</p>
                        </div>
                    ) : (
                        <div className="fade-in-up" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>

                            {/* Active Header */}
                            <div style={{ padding: '24px 32px', borderBottom: '1px solid var(--border-subtle)', background: 'rgba(0,0,0,0.2)' }}>
                                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Target File</span>
                                <h4 style={{ fontSize: '18px', fontWeight: 600, marginTop: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{selectedEp.title}</h4>
                            </div>

                            <div style={{ flex: 1, padding: '32px', display: 'flex', flexDirection: 'column', position: 'relative' }}>
                                {!extractedSegment && !isExtracting ? (
                                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        <button className="btn-magic" onClick={handleExtract} style={{ fontSize: '18px', padding: '16px 40px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                                            <Icons.Sparkles /> Locate Perfect Cold Open
                                        </button>
                                    </div>
                                ) : isExtracting ? (
                                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                                        <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: 'linear-gradient(120deg, #0A84FF, #BF5AF2)', animation: 'spin 2s linear infinite', position: 'relative' }}>
                                            <div style={{ position: 'absolute', top: '2px', left: '2px', right: '2px', bottom: '2px', background: 'var(--bg-elevated)', borderRadius: '50%' }} />
                                        </div>
                                        <p className="text-gradient-magic" style={{ marginTop: '32px', fontSize: '18px', fontWeight: 500, letterSpacing: '0.02em' }}>Scanning Narrative Vectors...</p>
                                    </div>
                                ) : (
                                    <div className="fade-in-up" style={{ display: 'flex', flexDirection: 'column', gap: '24px', height: '100%', overflowY: 'auto' }}>

                                        {/* The Quote */}
                                        <div style={{ background: 'rgba(0,0,0,0.5)', padding: '32px', borderRadius: '16px', borderLeft: '4px solid var(--accent-purple)' }}>
                                            <p style={{ fontSize: '20px', lineHeight: 1.5, fontStyle: 'italic', fontWeight: 400 }}>
                                                "{extractedSegment?.text}"
                                            </p>
                                            {extractedSegment?.speaker && (
                                                <p style={{ marginTop: '16px', fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', textAlign: 'right' }}>
                                                    — {extractedSegment.speaker}
                                                </p>
                                            )}
                                        </div>

                                        {/* Technical Traces */}
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: 'auto' }}>
                                            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '20px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
                                                <h5 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '8px' }}>Generated Visual Context</h5>
                                                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--accent-blue)', lineHeight: 1.5 }}>
                                                    "Cinematic portrait of {extractedSegment?.speaker || 'Speaker'}, moody atmospheric lighting, {selectedEp.vibe?.tone || 'intense'} discussion, photorealistic, 8k"
                                                </p>
                                            </div>

                                            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '20px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
                                                <h5 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '8px' }}>FFMpeg Render Trace</h5>
                                                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                                    ffmpeg -i src.wav -loop 1 -i bg.jpg -filter_complex "[1:v]scale=2160x2160,zoompan=z='min(zoom+0.0005,1.2)':d=1500;[0:a]showwaves=s=1080x300:colors=0xBF5AF2" output.mp4
                                                </p>
                                            </div>
                                        </div>

                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
        </div>
    );
};
