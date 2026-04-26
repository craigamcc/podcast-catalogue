import { useState, useEffect } from 'react';
import { loadPodcastData } from './dataLoader';
import type { NormalizedEpisode, Podcast } from './types';
import { Icons } from './components/icons';
import { DashboardView } from './components/DashboardView';
import { SearchView } from './components/SearchView';
import { ExtractionView } from './components/ExtractionView';
import { AtmosphereView } from './components/AtmosphereView';
import { GuestsView } from './components/GuestsView';
import { FeedPulseView } from './components/FeedPulseView';

type TabId = 'dashboard' | 'search' | 'atmosphere' | 'guests' | 'pulse' | 'extraction';

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('dashboard');
  const [data, setData] = useState<{ podcasts: Podcast[], allEpisodes: NormalizedEpisode[] }>({ podcasts: [], allEpisodes: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPodcastData().then((result) => {
      setData(result);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="app-shell" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div className="fade-in-up" style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--primary)', marginBottom: '24px' }}>
            <Icons.Sparkles />
          </div>
          <h2 className="headline-large text-gradient">GoldMine Prime</h2>
          <p className="label-technical" style={{ marginTop: '12px' }}>Initializing Intelligence Matrix</p>
        </div>
      </div>
    );
  }

  const NavItem = ({ id, label, icon: Icon }: { id: TabId, label: string, icon: any }) => (
    <button
      onClick={() => setActiveTab(id)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '8px',
        padding: '12px 16px',
        borderRadius: '12px',
        color: activeTab === id ? 'var(--primary)' : 'var(--text-tertiary)',
        background: activeTab === id ? 'rgba(138, 235, 255, 0.05)' : 'transparent',
        transition: 'all 0.3s var(--ease-out-expo)',
        border: 'none',
        flex: 1,
        minWidth: '80px'
      }}
    >
      <Icon />
      <span className="label-technical" style={{ fontSize: '9px', color: 'inherit' }}>{label}</span>
    </button>
  );

  return (
    <div className="app-shell">
      {/* Industrial-Noir Sidebar Navigation */}
      <div style={{ display: 'flex', minHeight: '100vh' }}>
        <aside style={{
          width: '100px',
          background: 'var(--bg-surface-dim)',
          borderRight: '1px solid var(--outline-variant)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '32px 0',
          position: 'sticky',
          top: 0,
          height: '100vh',
          zIndex: 100
        }}>
          <div style={{ color: 'var(--primary)', marginBottom: '48px' }}>
            <Icons.Sparkles />
          </div>
          
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '100%', padding: '0 12px' }}>
            <NavItem id="dashboard" label="Dashboard" icon={Icons.ChartBar} />
            <NavItem id="pulse" label="Pulse" icon={Icons.Pulse} />
            <NavItem id="search" label="Semantic" icon={Icons.MagnifyingGlass} />
            <NavItem id="atmosphere" label="Vibe" icon={Icons.Cloud} />
            <NavItem id="guests" label="Guests" icon={Icons.Users} />
            <NavItem id="extraction" label="Studio" icon={Icons.Film} />
          </nav>

          <div style={{ marginTop: 'auto', textAlign: 'center' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#34C759', margin: '0 auto 8px' }} className="pulse-glow" />
            <span className="label-technical" style={{ fontSize: '8px' }}>{data.allEpisodes.length} Enriched</span>
          </div>
        </aside>

        <main style={{ flex: 1, padding: '48px 64px', maxWidth: '1400px', margin: '0 auto' }}>
          {/* Top Bar */}
          <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '64px' }}>
            <div>
              <h1 className="display-hero">GoldMine</h1>
              <div className="label-technical" style={{ color: 'var(--text-tertiary)' }}>Situational Intelligence Hub</div>
            </div>
            <div className="glass-panel" style={{ padding: '8px 24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className="label-technical">Active Session</span>
              <span style={{ fontSize: '12px', fontWeight: 600 }}>v6.15 HARDENED</span>
            </div>
          </header>

          <div key={activeTab}>
            {activeTab === 'dashboard' && <DashboardView episodes={data.allEpisodes} />}
            {activeTab === 'pulse' && <FeedPulseView episodes={data.allEpisodes} />}
            {activeTab === 'search' && <SearchView episodes={data.allEpisodes} />}
            {activeTab === 'atmosphere' && <AtmosphereView episodes={data.allEpisodes} />}
            {activeTab === 'guests' && <GuestsView episodes={data.allEpisodes} />}
            {activeTab === 'extraction' && <ExtractionView episodes={data.allEpisodes} />}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
