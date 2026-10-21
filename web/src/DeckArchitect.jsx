import React, { useState } from 'react';
import { 
  Sparkles,
  Copy, Download, ExternalLink, RefreshCw, Check, AlertCircle, Layers
} from 'lucide-react';

const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
    return 'http://localhost:8000';
  }
  return 'https://api.lore-weaver.app';
};

const BRACKET_DEFINITIONS = [
  {
    tier: 1,
    name: 'Exhibition / Narrative',
    badge: 'Jank & Art Tribal',
    color: '#8b5cf6',
    desc: 'Narrative or tribal focus. Low power, zero fast mana, zero tutors, and zero infinite combos.'
  },
  {
    tier: 2,
    name: 'Core Casual',
    badge: 'Upgraded Precon',
    color: '#3b82f6',
    desc: 'Fair, board-centric Magic. Standard ramp (Sol Ring, Signets, Cultivate). No 2-card infinites or cheap tutors.'
  },
  {
    tier: 3,
    name: 'Optimized Casual',
    badge: 'Focused FNM',
    color: '#10b981',
    desc: 'High synergy, focused win conditions, resilient mana base, responsive interaction, and multi-card combos.'
  },
  {
    tier: 4,
    name: 'High-Power Unrestricted',
    badge: 'Fringe cEDH / Max Power',
    color: '#f59e0b',
    desc: 'Maximum power casual / fringe cEDH. Explosive fast mana, unrestricted combos, and top tutors without being locked into tournament cEDH meta staples.'
  },
  {
    tier: 5,
    name: 'Competitive EDH (cEDH Meta)',
    badge: 'Tournament cEDH',
    color: '#ef4444',
    desc: 'The tournament cEDH metagame. Razor-thin curve, full fast mana suite, free counterspells, and compact tournament-winning combo lines.'
  }
];

const WIN_CONS = [
  { id: 'combat', label: 'Combat / Overrun', icon: '⚔️' },
  { id: 'combo', label: 'Infinite Combo', icon: '♾️' },
  { id: 'drain', label: 'Aristocrats / Drain', icon: '🩸' },
  { id: 'burn', label: 'Burn / Group Slug', icon: '🔥' },
  { id: 'stax', label: 'Stax / Resource Denial', icon: '⛓️' },
  { id: 'voltron', label: 'Voltron / Cmdr Damage', icon: '🗡️' },
  { id: 'mill', label: 'Mill / Alternate Win', icon: '🌀' }
];

const COLOR_PIPS = [
  { key: 'W', label: 'White', bg: '#fef3c7', text: '#78350f', border: '#f59e0b' },
  { key: 'U', label: 'Blue', bg: '#e0f2fe', text: '#0369a1', border: '#0284c7' },
  { key: 'B', label: 'Black', bg: '#27272a', text: '#f4f4f5', border: '#52525b' },
  { key: 'R', label: 'Red', bg: '#fee2e2', text: '#b91c1c', border: '#ef4444' },
  { key: 'G', label: 'Green', bg: '#dcfce7', text: '#15803d', border: '#22c55e' },
  { key: 'C', label: 'Colorless', bg: '#3f3f46', text: '#e4e4e7', border: '#71717a' },
];

const SUGGESTIONS = [
  'Belbe, Corrupted Observer',
  'Teysa Karlov',
  'Talion, the Kindly Lord',
  'Veyran, Voice of Duality',
  'Atraxa, Grand Unifier',
  'Kozilek, the Broken Reality'
];

export default function DeckArchitect({ onAnalyzeDeck }) {
  // Form State
  const [commander, setCommander] = useState('');
  const [deckIdea, setDeckIdea] = useState('');
  const [bracket, setBracket] = useState(3);
  const [budget, setBudget] = useState('moderate');
  const [selectedColors, setSelectedColors] = useState([]);
  const [winCon, setWinCon] = useState('combat');

  // Loading & Result State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deckResult, setDeckResult] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [copied, setCopied] = useState(false);

  const toggleColor = (pip) => {
    if (pip === 'C') {
      setSelectedColors((prev) => (prev.includes('C') ? [] : ['C']));
      return;
    }
    setSelectedColors((prev) => {
      const filtered = prev.filter((c) => c !== 'C');
      return filtered.includes(pip) ? filtered.filter((c) => c !== pip) : [...filtered, pip];
    });
  };

  const handleBuildDeck = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);

    const payload = {
      commander: commander.trim(),
      deck_idea: deckIdea.trim(),
      bracket: parseInt(bracket, 10),
      budget: budget,
      color_preference: selectedColors.filter((c) => c !== 'C').join(','),
      preferred_win_con: winCon
    };

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/build`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned error status ${response.status}`);
      }

      const data = await response.json();
      setDeckResult(data);
      setSelectedCategory('all');
    } catch (err) {
      console.error('Deck Architect build error:', err);
      setError(err.message || 'Failed to assemble deck.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyClipboard = () => {
    if (!deckResult?.decklist_text) return;
    navigator.clipboard.writeText(deckResult.decklist_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleDownload = () => {
    if (!deckResult?.decklist_text) return;
    const blob = new Blob([deckResult.decklist_text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const safeName = (deckResult.commander?.name || 'deck').replace(/[^a-zA-Z0-9_-]/g, '_');
    link.href = url;
    link.download = `${safeName}_bracket_${bracket}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleSendToAnalyzer = () => {
    if (onAnalyzeDeck && deckResult?.decklist_text) {
      onAnalyzeDeck(deckResult.commander?.name || '', deckResult.decklist_text);
    }
  };

  // Sections definitions for grouped display
  const sections = deckResult ? [
    {
      id: 'commander',
      title: 'Commander',
      icon: '🛡️',
      badgeColor: '#38bdf8',
      cards: deckResult.commander ? [deckResult.commander] : []
    },
    {
      id: 'win con',
      title: 'Win Condition Core',
      icon: '🏆',
      badgeColor: '#ef4444',
      cards: deckResult.categories?.win_con || []
    },
    {
      id: 'ramp',
      title: 'Fast Mana & Ramp',
      icon: '⚡',
      badgeColor: '#f59e0b',
      cards: deckResult.categories?.ramp || []
    },
    {
      id: 'draw',
      title: 'Card Advantage & Draw',
      icon: '📜',
      badgeColor: '#10b981',
      cards: deckResult.categories?.draw || []
    },
    {
      id: 'removal',
      title: 'Removal & Answers',
      icon: '⚔️',
      badgeColor: '#ec4899',
      cards: deckResult.categories?.removal || []
    },
    {
      id: 'synergy',
      title: 'Thematic Engine & Synergy',
      icon: '🔮',
      badgeColor: '#8b5cf6',
      cards: deckResult.categories?.synergy || []
    },
    {
      id: 'lands',
      title: 'Mana Base & Lands',
      icon: '⛰️',
      badgeColor: '#64748b',
      cards: deckResult.categories?.lands || []
    }
  ] : [];

  // Group duplicate cards (e.g. basic lands) for cleaner display
  const groupCards = (cardList) => {
    const map = new Map();
    for (const card of cardList) {
      const key = card.name;
      if (map.has(key)) {
        map.get(key).count += 1;
      } else {
        map.set(key, { ...card, count: 1 });
      }
    }
    return Array.from(map.values());
  };

  const visibleSections = selectedCategory === 'all'
    ? sections
    : sections.filter((s) => s.id.toLowerCase() === selectedCategory.toLowerCase());

  return (
    <div className="tab-panel" style={{ maxWidth: '1440px', margin: '0 auto', paddingBottom: '80px' }}>
      {/* Studio Header */}
      <div style={{ textAlign: 'center', marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.8rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
          <Sparkles style={{ color: 'var(--text-accent)' }} /> Loreweaver Deck Architect
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', maxWidth: '780px', margin: '6px auto 0' }}>
          Assemble tournament-legal 100-card Commander decks from scratch using objective synergy scores, Frank Karsten hypergeometric mana quotas, and Commander bracket rules.
        </p>
      </div>

      {/* Main Studio Grid: Form (Left) & Results (Right) */}
      <div style={{ display: 'grid', gridTemplateColumns: deckResult ? '380px 1fr' : '1fr', gap: '24px' }}>
        
        {/* Form Panel */}
        <div className="card" style={{ height: 'fit-content' }}>
          <form onSubmit={handleBuildDeck}>
            {/* Commander Input */}
            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Commander (Optional)</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Auto-discovers if empty</span>
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Belbe, Corrupted Observer (or leave blank)"
                value={commander}
                onChange={(e) => setCommander(e.target.value)}
              />
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setCommander(s)}
                    style={{
                      fontSize: '0.75rem',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      background: 'var(--bg-primary)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer'
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Deck Idea / Strategy Prompt */}
            <div className="form-group">
              <label className="form-label">Strategy / Deck Idea Prompt</label>
              <textarea
                className="form-input"
                style={{ height: '75px', resize: 'vertical' }}
                placeholder="e.g. Deal damage to all players on every turn to play huge colorless spells with flash or instant speed..."
                value={deckIdea}
                onChange={(e) => setDeckIdea(e.target.value)}
              />
            </div>

            {/* Bracket Selector (1 to 5) */}
            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Commander Bracket (Tier {bracket})</span>
                <span style={{ 
                  color: BRACKET_DEFINITIONS[bracket - 1].color, 
                  fontWeight: 'bold', 
                  fontSize: '0.8rem' 
                }}>
                  {BRACKET_DEFINITIONS[bracket - 1].badge}
                </span>
              </label>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '6px', marginBottom: '8px' }}>
                {BRACKET_DEFINITIONS.map((b) => (
                  <button
                    key={b.tier}
                    type="button"
                    onClick={() => setBracket(b.tier)}
                    style={{
                      padding: '8px 4px',
                      borderRadius: '8px',
                      border: bracket === b.tier ? `2px solid ${b.color}` : '1px solid var(--border-color)',
                      background: bracket === b.tier ? `${b.color}22` : 'var(--bg-primary)',
                      color: bracket === b.tier ? b.color : 'var(--text-secondary)',
                      fontWeight: bracket === b.tier ? 'bold' : 'normal',
                      cursor: 'pointer',
                      textAlign: 'center',
                      fontSize: '0.85rem'
                    }}
                  >
                    T{b.tier}
                  </button>
                ))}
              </div>

              <div style={{ 
                fontSize: '0.78rem', 
                background: 'var(--bg-primary)', 
                padding: '8px 10px', 
                borderRadius: '6px', 
                borderLeft: `3px solid ${BRACKET_DEFINITIONS[bracket - 1].color}`,
                lineHeight: '1.4'
              }}>
                <div style={{ fontWeight: 'bold', color: BRACKET_DEFINITIONS[bracket - 1].color, marginBottom: '2px' }}>
                  {BRACKET_DEFINITIONS[bracket - 1].name}
                </div>
                {BRACKET_DEFINITIONS[bracket - 1].desc}
              </div>
            </div>

            {/* Win Condition Preference */}
            <div className="form-group">
              <label className="form-label">Preferred Win Condition</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px' }}>
                {WIN_CONS.map((wc) => (
                  <button
                    key={wc.id}
                    type="button"
                    onClick={() => setWinCon(wc.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 8px',
                      borderRadius: '6px',
                      border: winCon === wc.id ? '2px solid var(--text-accent)' : '1px solid var(--border-color)',
                      background: winCon === wc.id ? 'rgba(56, 189, 248, 0.15)' : 'var(--bg-primary)',
                      color: winCon === wc.id ? 'var(--text-accent)' : 'var(--text-secondary)',
                      fontSize: '0.75rem',
                      cursor: 'pointer',
                      textAlign: 'left'
                    }}
                  >
                    <span>{wc.icon}</span>
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{wc.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Color Preference (Optional) */}
            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Color Preference</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Filters commander discovery</span>
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                {COLOR_PIPS.map((pip) => {
                  const active = selectedColors.includes(pip.key);
                  return (
                    <button
                      key={pip.key}
                      type="button"
                      onClick={() => toggleColor(pip.key)}
                      style={{
                        width: '34px',
                        height: '34px',
                        borderRadius: '50%',
                        border: active ? `3px solid ${pip.border}` : '1px solid var(--border-color)',
                        background: pip.bg,
                        color: pip.text,
                        fontWeight: 'bold',
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                        boxShadow: active ? `0 0 8px ${pip.border}88` : 'none',
                        transition: 'all 0.15s ease'
                      }}
                      title={pip.label}
                    >
                      {pip.key}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Budget Preference */}
            <div className="form-group">
              <label className="form-label">Budget Tier</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
                {[
                  { id: 'budget', label: 'Budget (<$100)' },
                  { id: 'moderate', label: 'Moderate' },
                  { id: 'unlimited', label: 'Optimized' }
                ].map((b) => (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => setBudget(b.id)}
                    style={{
                      padding: '6px 4px',
                      borderRadius: '6px',
                      border: budget === b.id ? '2px solid var(--color-green)' : '1px solid var(--border-color)',
                      background: budget === b.id ? 'rgba(34, 197, 94, 0.15)' : 'var(--bg-primary)',
                      color: budget === b.id ? 'var(--color-green)' : 'var(--text-secondary)',
                      fontSize: '0.75rem',
                      cursor: 'pointer',
                      textAlign: 'center'
                    }}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div style={{ 
                background: 'rgba(239, 68, 68, 0.15)', 
                border: '1px solid #ef4444', 
                borderRadius: '6px', 
                padding: '8px 12px', 
                color: '#f87171', 
                fontSize: '0.8rem', 
                display: 'flex', 
                gap: '8px',
                alignItems: 'center',
                marginBottom: '16px'
              }}>
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            {/* Weave CTA Button with Pulsing Purple Glow Box on Hover */}
            <button
              type="submit"
              className="btn btn-primary btn-weave"
              disabled={loading}
              style={{ 
                width: '100%', 
                padding: '13px', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center', 
                gap: '8px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '0.95rem'
              }}
            >
              {loading ? (
                <>
                  <RefreshCw className="loader-spinner" size={18} />
                  <span>Weaving 100-Card Deck...</span>
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  <span>Weave 100-Card Deck</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Results Panel */}
        {deckResult ? (
          <div>
            {/* 1. Commander Engine Dossier Banner */}
            <div className="card" style={{ 
              marginBottom: '16px', 
              background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.85), rgba(15, 23, 42, 0.95))',
              border: '1px solid rgba(56, 189, 248, 0.35)'
            }}>
              <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                {deckResult.commander?.image_url && (
                  <img
                    src={deckResult.commander.image_url}
                    alt={deckResult.commander.name}
                    style={{ width: '120px', borderRadius: '8px', boxShadow: '0 4px 14px rgba(0,0,0,0.6)' }}
                  />
                )}
                <div style={{ flex: 1, minWidth: '280px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <h3 style={{ margin: 0, fontSize: '1.45rem', color: 'var(--text-accent)' }}>
                      {deckResult.commander?.name}
                    </h3>
                    <span style={{ 
                      background: BRACKET_DEFINITIONS[deckResult.bracket?.tier - 1]?.color || '#3b82f6',
                      color: '#ffffff',
                      fontSize: '0.75rem',
                      fontWeight: 'bold',
                      padding: '2px 8px',
                      borderRadius: '12px'
                    }}>
                      Bracket {deckResult.bracket?.tier} ({deckResult.bracket?.name})
                    </span>
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: '4px 0 12px' }}>
                    {deckResult.commander?.type_line} • {deckResult.commander?.mana_cost}
                  </div>

                  {/* Engine Badges */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
                    <div style={{ background: 'rgba(0,0,0,0.35)', padding: '8px 10px', borderRadius: '6px', fontSize: '0.78rem' }}>
                      <div style={{ color: '#38bdf8', fontWeight: 'bold' }}>⚡ Catalyst</div>
                      <div>{deckResult.engine_dossier?.catalyst || 'Resource generator'}</div>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.35)', padding: '8px 10px', borderRadius: '6px', fontSize: '0.78rem' }}>
                      <div style={{ color: '#f59e0b', fontWeight: 'bold' }}>🪙 Yield</div>
                      <div>{deckResult.engine_dossier?.yield || 'Engine yield'}</div>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.35)', padding: '8px 10px', borderRadius: '6px', fontSize: '0.78rem' }}>
                      <div style={{ color: '#ef4444', fontWeight: 'bold' }}>🎯 Payoff</div>
                      <div>{deckResult.engine_dossier?.payoff || 'Payoff cards'}</div>
                    </div>
                  </div>

                  <div style={{ 
                    marginTop: '12px', 
                    fontSize: '0.84rem', 
                    background: 'rgba(16, 185, 129, 0.1)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    color: '#6ee7b7',
                    lineHeight: '1.45'
                  }}>
                    {deckResult.win_con_execution}
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Consistency & Role Stats Row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '16px' }}>
              {/* Mana Consistency */}
              <div className="card" style={{ padding: '12px 16px' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>📐 Karsten Consistency</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', margin: '4px 0' }}>
                  <span>P(≥3 Lands T3):</span>
                  <strong style={{ color: 'var(--color-green)' }}>{deckResult.stats?.hypergeometric_consistency?.p_3_lands_turn_3}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                  <span>P(Land + Ramp T2):</span>
                  <strong style={{ color: 'var(--text-accent)' }}>{deckResult.stats?.hypergeometric_consistency?.p_land_and_ramp_turn_2}</strong>
                </div>
              </div>

              {/* Curve & CMC */}
              <div className="card" style={{ padding: '12px 16px' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>📊 Curve & Average CMC</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', margin: '4px 0' }}>
                  <span>Average Nonland CMC:</span>
                  <strong style={{ color: '#f59e0b' }}>{deckResult.stats?.avg_cmc}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                  <span>Total Deck Size:</span>
                  <strong style={{ color: 'var(--color-green)' }}>100 / 100 Cards</strong>
                </div>
              </div>

              {/* Export Action Bar */}
              <div className="card" style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '8px' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={handleCopyClipboard}
                    className="btn btn-secondary"
                    style={{ flex: 1, padding: '6px 8px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', cursor: 'pointer' }}
                  >
                    {copied ? <Check size={14} style={{ color: '#22c55e' }} /> : <Copy size={14} />}
                    <span>{copied ? 'Copied!' : 'Copy 100 Cards'}</span>
                  </button>
                  <button
                    onClick={handleDownload}
                    className="btn btn-secondary"
                    style={{ flex: 1, padding: '6px 8px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', cursor: 'pointer' }}
                  >
                    <Download size={14} />
                    <span>Save .txt</span>
                  </button>
                </div>
                {onAnalyzeDeck && (
                  <button
                    onClick={handleSendToAnalyzer}
                    className="btn"
                    style={{ 
                      background: 'rgba(56, 189, 248, 0.2)', 
                      border: '1px solid #38bdf8', 
                      color: '#38bdf8', 
                      padding: '6px 8px', 
                      fontSize: '0.78rem', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      gap: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    <ExternalLink size={14} />
                    <span>Audit in Deck Analyzer</span>
                  </button>
                )}
              </div>
            </div>

            {/* 3. Category Filter Tabs */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
              {[
                { id: 'all', label: 'All Sections (100)' },
                { id: 'commander', label: 'Commander (1)' },
                { id: 'win con', label: `Win Cons (${deckResult.stats?.roles?.win_con})` },
                { id: 'ramp', label: `Ramp (${deckResult.stats?.roles?.ramp})` },
                { id: 'draw', label: `Draw (${deckResult.stats?.roles?.draw})` },
                { id: 'removal', label: `Removal (${deckResult.stats?.roles?.removal})` },
                { id: 'synergy', label: `Synergy (${deckResult.stats?.roles?.synergy})` },
                { id: 'lands', label: `Lands (${deckResult.stats?.roles?.lands})` },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setSelectedCategory(tab.id)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '16px',
                    border: selectedCategory === tab.id ? '1px solid var(--text-accent)' : '1px solid var(--border-color)',
                    background: selectedCategory === tab.id ? 'var(--text-accent)' : 'var(--bg-secondary)',
                    color: selectedCategory === tab.id ? '#0f172a' : 'var(--text-secondary)',
                    fontWeight: selectedCategory === tab.id ? 'bold' : 'normal',
                    fontSize: '0.78rem',
                    cursor: 'pointer'
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* 4. Organized 100-Card Sectioned Display */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {visibleSections.map((sec) => {
                const grouped = groupCards(sec.cards);
                if (grouped.length === 0) return null;

                return (
                  <div key={sec.id} className="card" style={{ padding: '16px' }}>
                    {/* Section Header */}
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between', 
                      marginBottom: '14px',
                      borderBottom: '1px solid var(--border-color)',
                      paddingBottom: '8px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '1.2rem' }}>{sec.icon}</span>
                        <h4 style={{ margin: 0, fontSize: '1.05rem', color: sec.badgeColor }}>
                          {sec.title}
                        </h4>
                      </div>
                      <span style={{ 
                        background: 'var(--bg-primary)', 
                        border: `1px solid ${sec.badgeColor}66`,
                        color: sec.badgeColor,
                        padding: '2px 8px',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        fontWeight: 'bold'
                      }}>
                        {sec.cards.length} cards
                      </span>
                    </div>

                    {/* Section Card Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px' }}>
                      {grouped.map((card, idx) => (
                        <div
                          key={`${card.name}-${idx}`}
                          className="card"
                          style={{
                            padding: '8px',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                            background: 'var(--bg-primary)',
                            border: `1px solid ${sec.badgeColor}44`,
                            borderRadius: '6px'
                          }}
                        >
                          {card.image_url ? (
                            <img
                              src={card.image_url}
                              alt={card.name}
                              loading="lazy"
                              style={{ width: '100%', borderRadius: '4px', marginBottom: '8px' }}
                            />
                          ) : (
                            <div style={{ 
                              width: '100%', 
                              height: '120px', 
                              background: '#1e293b', 
                              borderRadius: '4px', 
                              marginBottom: '8px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: '0.75rem',
                              color: 'var(--text-muted)'
                            }}>
                              No Image
                            </div>
                          )}
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '4px' }}>
                              <span style={{ fontWeight: 'bold', fontSize: '0.82rem', lineHeight: '1.2' }}>
                                {card.count > 1 ? `${card.count}x ` : ''}{card.name}
                              </span>
                              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                                {card.mana_cost}
                              </span>
                            </div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                              {card.type_line}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <Layers size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <h3 style={{ color: 'var(--text-secondary)', marginBottom: '8px' }}>Configure Your Parameters & Weave</h3>
            <p style={{ maxWidth: '450px', margin: '0 auto', fontSize: '0.88rem' }}>
              Choose a commander or describe your deck concept, select your bracket (1–5), budget, and preferred win condition. The objective engine will assemble the full 100 cards.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
