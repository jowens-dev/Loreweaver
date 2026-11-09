import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { 
  Sparkles,
  Copy, Download, ExternalLink, RefreshCw, Check, AlertCircle, Layers, ArrowRightLeft,
  Shield, ChevronDown, ChevronUp, X, Plus, ShoppingCart, Share2
} from 'lucide-react';
import CommanderAutocomplete from './components/CommanderAutocomplete';
import DeckExportModal from './components/DeckExportModal';
import CardSwapModal from './components/CardSwapModal';
import CardTooltip from './components/CardTooltip';
import { 
  exportToMoxfield, 
  exportToManaPool,
  exportToArchidekt, 
  exportToMtgo, 
  exportToText, 
  exportToCsv,
  getManaPoolMassEntryUrl
} from './utils/deckExport';
import { safeCopyToClipboard } from './utils/clipboard';

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

export default function DeckArchitect({ onAnalyzeDeck, initialParams, onClearInitialParams }) {
  // Form State
  const [commander, setCommander] = useState('');
  const [deckIdea, setDeckIdea] = useState('');
  const [bracket, setBracket] = useState(3);
  const [budget, setBudget] = useState('moderate');
  const [selectedColors, setSelectedColors] = useState([]);
  const [winCon, setWinCon] = useState('combat');
  const [houseRules, setHouseRules] = useState([]);
  const [customBans, setCustomBans] = useState([]);
  const [customBanInput, setCustomBanInput] = useState('');
  const [isHouseRulesOpen, setIsHouseRulesOpen] = useState(false);

  // Loading & Result State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deckResult, setDeckResult] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [exportModalFormat, setExportModalFormat] = useState('moxfield');
  const [copiedMoxfield, setCopiedMoxfield] = useState(false);
  const [copiedArchidekt, setCopiedArchidekt] = useState(false);
  const [buyingManaPool, setBuyingManaPool] = useState(false);

  // Card Swap State
  const [isSwapModalOpen, setIsSwapModalOpen] = useState(false);
  const [activeSwapCard, setActiveSwapCard] = useState(null);
  const [activeSwapRole, setActiveSwapRole] = useState('synergy');
  const [toastMessage, setToastMessage] = useState(null);
  const toastTimeoutRef = useRef(null);

  // Aggregated card names currently in the deck to prevent non-basic duplicates
  const allDeckCardNames = useMemo(() => {
    if (!deckResult?.categories) return [];
    const names = [];
    for (const group of Object.values(deckResult.categories)) {
      if (Array.isArray(group)) {
        for (const c of group) {
          if (c?.name) names.push(c.name);
        }
      }
    }
    return names;
  }, [deckResult]);

  const handleOpenSwapModal = (card, role) => {
    setActiveSwapCard(card);
    setActiveSwapRole(role);
    setIsSwapModalOpen(true);
  };

  const handleConfirmCardSwap = (oldCard, newCard, role) => {
    if (!deckResult || !oldCard || !newCard) return;

    const updatedCategories = { ...deckResult.categories };
    const roleKey = role || 'synergy';
    const roleCards = [...(updatedCategories[roleKey] || [])];

    // Find first occurrence of oldCard
    const replaceIdx = roleCards.findIndex(
      (c) => c.name.toLowerCase() === oldCard.name.toLowerCase()
    );

    if (replaceIdx !== -1) {
      roleCards[replaceIdx] = newCard;
    } else {
      roleCards.push(newCard);
    }
    updatedCategories[roleKey] = roleCards;

    // Recalculate curve and avg_cmc across non-land mainboard cards
    const nonlandCards = [];
    for (const [catName, cards] of Object.entries(updatedCategories)) {
      if (catName === 'commander' || catName === 'lands') continue;
      for (const c of cards) {
        const typeLine = (c.type_line || '').toLowerCase();
        if (!typeLine.includes('land')) {
          nonlandCards.push(c);
        }
      }
    }

    const avgCmc = nonlandCards.length > 0
      ? Number((nonlandCards.reduce((sum, c) => sum + (Number(c.cmc) || 0), 0) / nonlandCards.length).toFixed(2))
      : 0;

    const manaCurve = { "0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6+": 0 };
    for (const c of nonlandCards) {
      const cmcVal = Math.floor(Number(c.cmc) || 0);
      if (cmcVal >= 6) manaCurve["6+"] += 1;
      else if (cmcVal >= 0) manaCurve[String(cmcVal)] += 1;
    }

    const updatedStats = {
      ...deckResult.stats,
      avg_cmc: avgCmc,
      mana_curve: manaCurve,
      roles: {
        ...deckResult.stats?.roles,
        lands: (updatedCategories.lands || []).length,
        ramp: (updatedCategories.ramp || []).length,
        draw: (updatedCategories.draw || []).length,
        removal: (updatedCategories.removal || []).length,
        win_con: (updatedCategories.win_con || []).length,
        synergy: (updatedCategories.synergy || []).length
      }
    };

    const updatedDeck = {
      ...deckResult,
      categories: updatedCategories,
      stats: updatedStats
    };

    // Re-generate all platform export strings
    const updatedExports = {
      moxfield: exportToMoxfield(updatedDeck),
      archidekt: exportToArchidekt(updatedDeck),
      mtgo: exportToMtgo(updatedDeck),
      text: exportToText(updatedDeck),
      csv: exportToCsv(updatedDeck)
    };
    updatedDeck.exports = updatedExports;
    updatedDeck.decklist_text = updatedExports.text;

    setDeckResult(updatedDeck);

    // Toast notification
    setToastMessage(`Swapped ${oldCard.name} for ${newCard.name}`);
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current);
    }
    toastTimeoutRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  };

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

  const toggleHouseRule = (ruleId) => {
    setHouseRules((prev) =>
      prev.includes(ruleId) ? prev.filter((r) => r !== ruleId) : [...prev, ruleId]
    );
  };

  const handleAddCustomBan = (cardName) => {
    const trimmed = (cardName || customBanInput).trim();
    if (!trimmed) return;
    if (!customBans.some((b) => b.toLowerCase() === trimmed.toLowerCase())) {
      setCustomBans((prev) => [...prev, trimmed]);
    }
    setCustomBanInput('');
  };

  const handleRemoveCustomBan = (cardToRemove) => {
    setCustomBans((prev) => prev.filter((b) => b.toLowerCase() !== cardToRemove.toLowerCase()));
  };

  const showToast = useCallback((msg) => {
    setToastMessage(msg);
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current);
    }
    toastTimeoutRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  }, []);

  const executeBuild = useCallback(async (overrideParams = {}) => {
    setLoading(true);
    setError(null);

    const cmdVal = (overrideParams.commander !== undefined ? overrideParams.commander : commander).trim();
    if (!cmdVal) {
      setLoading(false);
      return;
    }

    const rawBracket = overrideParams.bracket !== undefined ? overrideParams.bracket : bracket;
    const safeBracket = Math.min(5, Math.max(1, parseInt(rawBracket, 10) || 3));

    const payload = {
      commander: cmdVal,
      deck_idea: (overrideParams.deck_idea !== undefined ? overrideParams.deck_idea : deckIdea).trim(),
      bracket: safeBracket,
      budget: overrideParams.budget !== undefined ? overrideParams.budget : budget,
      color_preference: (overrideParams.selectedColors || selectedColors).filter((c) => c !== 'C').join(','),
      preferred_win_con: overrideParams.win_con !== undefined ? overrideParams.win_con : winCon,
      house_rules: overrideParams.house_rules || houseRules,
      custom_bans: overrideParams.custom_bans || customBans
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
        let errMsg = `Server returned error status ${response.status}`;
        if (errData?.detail) {
          if (Array.isArray(errData.detail)) {
            errMsg = errData.detail.map((d) => (d.msg ? `${d.loc ? d.loc.join('.') + ': ' : ''}${d.msg}` : JSON.stringify(d))).join(', ');
          } else if (typeof errData.detail === 'string') {
            errMsg = errData.detail;
          }
        }
        throw new Error(errMsg);
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
  }, [commander, deckIdea, bracket, budget, selectedColors, winCon, houseRules, customBans]);

  const handleBuildDeck = (e) => {
    if (e) e.preventDefault();
    executeBuild();
  };

  // Keep a stable ref to executeBuild so reactive state changes in the builder
  // don't re-trigger URL parameter parsing or initialParams ingestion.
  const executeBuildRef = useRef(executeBuild);
  useEffect(() => {
    executeBuildRef.current = executeBuild;
  });

  const hasProcessedInitialRef = useRef(false);

  // URL Deep-linking and initialParams handling on mount only
  useEffect(() => {
    if (hasProcessedInitialRef.current) return;

    let paramsToBuild = null;

    if (initialParams && initialParams.commander) {
      hasProcessedInitialRef.current = true;
      setCommander(initialParams.commander);
      if (initialParams.bracket) {
        const safeB = Math.min(5, Math.max(1, parseInt(initialParams.bracket, 10) || 3));
        setBracket(safeB);
      }
      if (initialParams.budget) setBudget(initialParams.budget);
      if (initialParams.win_con) setWinCon(initialParams.win_con);
      paramsToBuild = initialParams;
      onClearInitialParams?.();
    } else if (typeof window !== 'undefined' && window.location.search) {
      const searchParams = new URLSearchParams(window.location.search);
      const cmd = searchParams.get('commander') || searchParams.get('c');
      const b = searchParams.get('bracket') || searchParams.get('b');
      const bg = searchParams.get('budget');
      const wc = searchParams.get('win_con') || searchParams.get('w');
      const auto = searchParams.get('auto') === 'true' || searchParams.get('build') === 'true';

      if (cmd) {
        hasProcessedInitialRef.current = true;
        setCommander(cmd);
        const p = { commander: cmd };
        if (b) {
          const safeB = Math.min(5, Math.max(1, parseInt(b, 10) || 3));
          setBracket(safeB);
          p.bracket = safeB;
        }
        if (bg) {
          setBudget(bg);
          p.budget = bg;
        }
        if (wc) {
          setWinCon(wc);
          p.win_con = wc;
        }
        if (auto) {
          paramsToBuild = p;
        }
      }
    }

    if (paramsToBuild && paramsToBuild.commander) {
      executeBuildRef.current(paramsToBuild);
    }
  }, [initialParams, onClearInitialParams]);

  const handleCopyShareLink = async () => {
    if (!commander) return;
    const origin = typeof window !== 'undefined' ? window.location.origin : 'https://lore-weaver.app';
    const params = new URLSearchParams();
    params.set('c', commander);
    params.set('b', String(bracket));
    if (budget !== 'moderate') params.set('budget', budget);
    if (winCon !== 'combat') params.set('w', winCon);
    params.set('auto', 'true');
    const shareUrl = `${origin}/?${params.toString()}`;

    const ok = await safeCopyToClipboard(shareUrl);
    if (ok) {
      showToast('📋 Share link copied! Ready to paste into video description or bio.');
    } else {
      showToast('⚠️ Could not copy link automatically. Please copy the URL from your browser bar.');
    }
  };

  const handleFastCopyMoxfield = async () => {
    if (!deckResult) return;
    const text = deckResult.exports?.moxfield || exportToMoxfield(deckResult);
    if (!text) return;
    const ok = await safeCopyToClipboard(text);
    if (ok) {
      setCopiedMoxfield(true);
      setTimeout(() => setCopiedMoxfield(false), 2400);
      showToast('📋 Copied Moxfield list to clipboard!');
    } else {
      showToast('⚠️ Could not copy decklist automatically.');
    }
  };

  const handleFastCopyArchidekt = async () => {
    if (!deckResult) return;
    const text = deckResult.exports?.archidekt || exportToArchidekt(deckResult);
    if (!text) return;
    const ok = await safeCopyToClipboard(text);
    if (ok) {
      setCopiedArchidekt(true);
      setTimeout(() => setCopiedArchidekt(false), 2400);
      showToast('📋 Copied Archidekt list to clipboard!');
    } else {
      showToast('⚠️ Could not copy decklist automatically.');
    }
  };

  const handleBuyManaPool = async () => {
    if (!deckResult) return;
    const text = deckResult.exports?.tcgplayer || exportToManaPool(deckResult);
    if (text) {
      await safeCopyToClipboard(text);
    }
    setBuyingManaPool(true);
    const url = getManaPoolMassEntryUrl(deckResult);
    window.open(url, '_blank', 'noopener,noreferrer');
    showToast('⚡ Loading 100 cards directly into Mana Pool...');
    setTimeout(() => setBuyingManaPool(false), 3000);
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

  const currentBracketDef = BRACKET_DEFINITIONS[(bracket >= 1 && bracket <= 5 ? bracket : 3) - 1] || BRACKET_DEFINITIONS[2];

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
            {/* Commander Input with Predictive Search */}
            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Commander (Optional)</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Auto-discovers if empty</span>
              </label>
              <CommanderAutocomplete
                value={commander}
                onChange={setCommander}
                onSelect={(card) => {
                  setCommander(card.name);
                  if (card.color_identity) {
                    setSelectedColors(card.color_identity.length > 0 ? card.color_identity : ['C']);
                  }
                }}
                placeholder="Type commander name (e.g. Belbe, Atraxa, Ur-Dragon...)"
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
                  color: currentBracketDef.color, 
                  fontWeight: 'bold', 
                  fontSize: '0.8rem' 
                }}>
                  {currentBracketDef.badge}
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
                borderLeft: `3px solid ${currentBracketDef.color}`,
                lineHeight: '1.4'
              }}>
                <div style={{ fontWeight: 'bold', color: currentBracketDef.color, marginBottom: '2px' }}>
                  {currentBracketDef.name}
                </div>
                {currentBracketDef.desc}
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
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px' }}>
                {[
                  { id: 'ultra_budget', label: 'Ultra-Budget (<$50)' },
                  { id: 'budget', label: 'Budget (<$100)' },
                  { id: 'moderate', label: 'Moderate (~$250)' },
                  { id: 'unlimited', label: 'Unlimited (No Cap)' }
                ].map((b) => (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => setBudget(b.id)}
                    style={{
                      padding: '8px 6px',
                      borderRadius: '6px',
                      border: budget === b.id ? '2px solid var(--color-green)' : '1px solid var(--border-color)',
                      background: budget === b.id ? 'rgba(34, 197, 94, 0.15)' : 'var(--bg-primary)',
                      color: budget === b.id ? 'var(--color-green)' : 'var(--text-secondary)',
                      fontSize: '0.75rem',
                      fontWeight: budget === b.id ? '600' : 'normal',
                      cursor: 'pointer',
                      textAlign: 'center',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Collapsible House Rules & Ban Filter Panel */}
            <div className="form-group" style={{ marginBottom: '16px' }}>
              <button
                type="button"
                onClick={() => setIsHouseRulesOpen(!isHouseRulesOpen)}
                style={{
                  width: '100%',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: isHouseRulesOpen ? 'rgba(30, 41, 59, 0.7)' : 'rgba(30, 41, 59, 0.4)',
                  border: '1px solid var(--border-color)',
                  borderRadius: isHouseRulesOpen ? '8px 8px 0 0' : '8px',
                  padding: '10px 12px',
                  cursor: 'pointer',
                  color: 'var(--text-primary)',
                  fontSize: '0.84rem',
                  fontWeight: '600',
                  transition: 'background 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Shield size={16} style={{ color: 'var(--text-accent)' }} />
                  <span>House Rules & Ban Filter</span>
                  {(houseRules.length > 0 || customBans.length > 0) && (
                    <span style={{
                      background: 'rgba(239, 68, 68, 0.25)',
                      color: '#f87171',
                      border: '1px solid rgba(239, 68, 68, 0.4)',
                      fontSize: '0.68rem',
                      padding: '1px 7px',
                      borderRadius: '10px',
                      fontWeight: '700'
                    }}>
                      {houseRules.length + customBans.length} active
                    </span>
                  )}
                </div>
                {isHouseRulesOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              {isHouseRulesOpen && (
                <div style={{
                  padding: '14px',
                  background: 'rgba(15, 23, 42, 0.65)',
                  border: '1px solid var(--border-color)',
                  borderTop: 'none',
                  borderRadius: '0 0 8px 8px'
                }}>
                  {/* House Rules Pill Toggles */}
                  <label className="form-label" style={{ fontSize: '0.76rem', marginBottom: '8px' }}>
                    Common Playgroup House Bans
                  </label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '14px' }}>
                    {[
                      { id: 'no_combos', label: '🚫 No Infinite Combos' },
                      { id: 'no_fast_mana', label: '⚡ No Fast Mana' },
                      { id: 'no_free_spells', label: '🛡️ No Free Spells' },
                      { id: 'no_stax', label: '⛓️ No Stax / MLD' },
                      { id: 'no_tutors', label: '🔍 No Cheap Tutors' }
                    ].map((rule) => {
                      const isActive = houseRules.includes(rule.id);
                      return (
                        <button
                          key={rule.id}
                          type="button"
                          onClick={() => toggleHouseRule(rule.id)}
                          style={{
                            padding: '6px 10px',
                            borderRadius: '16px',
                            fontSize: '0.74rem',
                            fontWeight: isActive ? '600' : 'normal',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            border: isActive ? '1px solid #ef4444' : '1px solid var(--border-color)',
                            background: isActive ? 'rgba(239, 68, 68, 0.2)' : 'rgba(30, 41, 59, 0.5)',
                            color: isActive ? '#fca5a5' : 'var(--text-secondary)'
                          }}
                        >
                          {rule.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Custom Card Exclusions */}
                  <label className="form-label" style={{ fontSize: '0.76rem', marginBottom: '6px' }}>
                    Custom Card Exclusions
                  </label>
                  <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
                    <div style={{ flex: 1 }}>
                      <CommanderAutocomplete
                        value={customBanInput}
                        onChange={setCustomBanInput}
                        onSelect={(card) => handleAddCustomBan(card.name)}
                        placeholder="Search card to exclude..."
                        commandersOnly={false}
                        className="form-input"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => handleAddCustomBan()}
                      className="btn btn-secondary"
                      style={{
                        padding: '6px 12px',
                        fontSize: '0.78rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        cursor: 'pointer',
                        flexShrink: 0
                      }}
                      title="Add Card to Exclude"
                    >
                      <Plus size={14} />
                      <span>Exclude</span>
                    </button>
                  </div>

                  {/* Excluded Card Chips */}
                  {customBans.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                      {customBans.map((cardName) => (
                        <span
                          key={cardName}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            background: 'rgba(239, 68, 68, 0.15)',
                            border: '1px solid rgba(239, 68, 68, 0.35)',
                            borderRadius: '12px',
                            padding: '2px 8px',
                            fontSize: '0.72rem',
                            color: '#f87171'
                          }}
                        >
                          <span>{cardName}</span>
                          <button
                            type="button"
                            onClick={() => handleRemoveCustomBan(cardName)}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: '#f87171',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              padding: 0
                            }}
                            title={`Remove ${cardName} ban`}
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
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
                  <CardTooltip card={deckResult.commander} name={deckResult.commander.name}>
                    <img
                      src={deckResult.commander.image_url}
                      alt={deckResult.commander.name}
                      style={{ width: '120px', borderRadius: '8px', boxShadow: '0 4px 14px rgba(0,0,0,0.6)', cursor: 'pointer' }}
                    />
                  </CardTooltip>
                )}
                <div style={{ flex: 1, minWidth: '280px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <CardTooltip card={deckResult.commander} name={deckResult.commander?.name}>
                      <h3 style={{ margin: 0, fontSize: '1.45rem', color: 'var(--text-accent)', cursor: 'pointer' }}>
                        {deckResult.commander?.name}
                      </h3>
                    </CardTooltip>
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
                    <span style={{ 
                      background: 'rgba(34, 197, 94, 0.2)',
                      color: 'var(--color-green)',
                      border: '1px solid rgba(34, 197, 94, 0.4)',
                      fontSize: '0.75rem',
                      fontWeight: 'bold',
                      padding: '2px 8px',
                      borderRadius: '12px'
                    }}>
                      Budget: {deckResult.budget === 'ultra_budget' ? 'Ultra-Budget (<$50)' : deckResult.budget === 'budget' ? 'Budget (<$100)' : deckResult.budget === 'moderate' ? 'Moderate (~$250)' : 'Unlimited'}
                    </span>
                    {((deckResult.house_rules && deckResult.house_rules.length > 0) || (deckResult.custom_bans && deckResult.custom_bans.length > 0)) && (
                      <span style={{ 
                        background: 'rgba(239, 68, 68, 0.2)',
                        color: '#f87171',
                        border: '1px solid rgba(239, 68, 68, 0.4)',
                        fontSize: '0.75rem',
                        fontWeight: 'bold',
                        padding: '2px 8px',
                        borderRadius: '12px'
                      }}>
                        🚫 {(deckResult.house_rules || []).length + (deckResult.custom_bans || []).length} Restrictions Active
                      </span>
                    )}
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
                    lineHeight: '1.45',
                    whiteSpace: 'pre-line'
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
                {/* Prominent Mana Pool Affiliate Commerce Button */}
                <button
                  onClick={handleBuyManaPool}
                  className="btn"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    fontSize: '0.82rem',
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    cursor: 'pointer',
                    borderRadius: '8px',
                    border: buyingManaPool ? '1px solid #22c55e' : '1px solid #38bdf8',
                    background: buyingManaPool 
                      ? 'linear-gradient(135deg, rgba(34, 197, 94, 0.25), rgba(21, 128, 61, 0.35))'
                      : 'linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(14, 165, 233, 0.32))',
                    color: buyingManaPool ? '#4ade80' : '#38bdf8',
                    boxShadow: buyingManaPool
                      ? '0 0 14px rgba(34, 197, 94, 0.4)'
                      : '0 0 14px rgba(56, 189, 248, 0.25)',
                    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    transform: buyingManaPool ? 'scale(1.01)' : 'scale(1)'
                  }}
                  title="Copy 100-card decklist and open Mana Pool Mass Entry (5% affiliate support)"
                >
                  {buyingManaPool ? (
                    <>
                      <Check size={14} style={{ color: '#4ade80' }} />
                      <span>Deck copied! Opening Mana Pool...</span>
                    </>
                  ) : (
                    <>
                      <ShoppingCart size={14} />
                      <span>⚡ Buy on Mana Pool (5% Supports Us)</span>
                    </>
                  )}
                </button>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={handleFastCopyMoxfield}
                    className="btn btn-secondary"
                    style={{ 
                      flex: 1, 
                      padding: '7px 8px', 
                      fontSize: '0.78rem', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      gap: '4px', 
                      cursor: 'pointer',
                      border: copiedMoxfield ? '1px solid #22c55e' : '1px solid var(--border-purple)',
                      background: copiedMoxfield ? 'rgba(34, 197, 94, 0.2)' : 'var(--bg-card)',
                      transition: 'all 0.15s ease'
                    }}
                    title="Copy 100 cards formatted for Moxfield (*CMDR* tag)"
                  >
                    {copiedMoxfield ? <Check size={14} style={{ color: '#22c55e' }} /> : <Copy size={14} />}
                    <span>{copiedMoxfield ? 'Copied Moxfield!' : 'Copy Moxfield'}</span>
                  </button>

                  <button
                    onClick={handleFastCopyArchidekt}
                    className="btn btn-secondary"
                    style={{ 
                      flex: 1, 
                      padding: '7px 8px', 
                      fontSize: '0.78rem', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      gap: '4px', 
                      cursor: 'pointer',
                      border: copiedArchidekt ? '1px solid #22c55e' : '1px solid var(--border-purple)',
                      background: copiedArchidekt ? 'rgba(34, 197, 94, 0.2)' : 'var(--bg-card)',
                      transition: 'all 0.15s ease'
                    }}
                    title="Copy 100 cards formatted for Archidekt ([Ramp], [Removal] tags)"
                  >
                    {copiedArchidekt ? <Check size={14} style={{ color: '#22c55e' }} /> : <Copy size={14} />}
                    <span>{copiedArchidekt ? 'Copied Archidekt!' : 'Copy Archidekt'}</span>
                  </button>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={handleCopyShareLink}
                    className="btn btn-secondary"
                    style={{
                      flex: 1,
                      padding: '7px 8px',
                      fontSize: '0.78rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px',
                      cursor: 'pointer',
                      border: '1px solid rgba(56, 189, 248, 0.4)',
                      background: 'rgba(56, 189, 248, 0.12)',
                      color: '#38bdf8',
                      transition: 'all 0.15s ease'
                    }}
                    title="Copy 1-click shareable URL for video descriptions and bio links"
                  >
                    <Share2 size={13} />
                    <span>🔗 Share Link</span>
                  </button>

                  <button
                    onClick={() => {
                      setExportModalFormat('moxfield');
                      setIsExportModalOpen(true);
                    }}
                    className="btn"
                    style={{ 
                      flex: 1,
                      padding: '7px 8px', 
                      fontSize: '0.78rem', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      gap: '4px', 
                      cursor: 'pointer',
                      background: 'linear-gradient(135deg, rgba(147, 51, 234, 0.3), rgba(56, 189, 248, 0.25))',
                      border: '1px solid #c084fc',
                      color: 'var(--text-white)',
                      fontWeight: '600'
                    }}
                    title="Open export modal for MTGO .dec, CSV, TXT, and options"
                  >
                    <Download size={14} />
                    <span>Export Options...</span>
                  </button>

                  {onAnalyzeDeck && (
                    <button
                      onClick={handleSendToAnalyzer}
                      className="btn"
                      style={{ 
                        flex: 1,
                        background: 'rgba(56, 189, 248, 0.15)', 
                        border: '1px solid #38bdf8', 
                        color: '#38bdf8', 
                        padding: '7px 8px', 
                        fontSize: '0.78rem', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        gap: '4px',
                        cursor: 'pointer'
                      }}
                    >
                      <ExternalLink size={14} />
                      <span>Audit in Analyzer</span>
                    </button>
                  )}
                </div>
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
                          <CardTooltip card={card} name={card.name} style={{ width: '100%' }}>
                            <div style={{ width: '100%', cursor: 'pointer' }}>
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
                          </CardTooltip>

                          {/* Swap Card Button (excluded for Commander) */}
                          {sec.id !== 'commander' && (
                            <button
                              type="button"
                              onClick={() => handleOpenSwapModal(card, sec.id)}
                              style={{
                                marginTop: '8px',
                                width: '100%',
                                padding: '5px 8px',
                                borderRadius: '6px',
                                fontSize: '0.74rem',
                                fontWeight: '600',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: '5px',
                                background: 'rgba(168, 85, 247, 0.12)',
                                border: '1px solid rgba(168, 85, 247, 0.35)',
                                color: 'var(--text-accent, #bb8fdf)',
                                transition: 'all 0.15s ease'
                              }}
                              title={`Swap ${card.name} for another ${sec.title}`}
                            >
                              <ArrowRightLeft size={12} />
                              <span>Swap</span>
                            </button>
                          )}
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

      {/* 100-Card Deck Export & Integrations Modal */}
      <DeckExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        deck={deckResult}
        initialFormat={exportModalFormat}
      />

      {/* Interactive Card Swap Modal */}
      <CardSwapModal
        isOpen={isSwapModalOpen}
        onClose={() => setIsSwapModalOpen(false)}
        card={activeSwapCard}
        role={activeSwapRole}
        commander={deckResult?.commander?.name || (deckResult?.commanders || []).map((c) => c.name).join(' / ')}
        bracket={deckResult?.bracket?.tier || 3}
        exclude={allDeckCardNames}
        onSwap={handleConfirmCardSwap}
      />

      {/* Toast Notification */}
      {toastMessage && (
        <div
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            zIndex: 1100,
            backgroundColor: '#10b981',
            color: '#ffffff',
            padding: '12px 18px',
            borderRadius: '10px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.6), 0 0 16px rgba(16, 185, 129, 0.4)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontWeight: '600',
            fontSize: '0.86rem'
          }}
        >
          <Check size={18} />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
