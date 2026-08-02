import React, { useEffect, useMemo, useState } from 'react';
import { Search, Flame, X, Check, Feather, ChevronLeft } from 'lucide-react';

const RECOMMENDATION_API_URL = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/recommendations`;
const FALLBACK_CARD_BACK = 'https://cards.scryfall.io/back.jpg';

const PIP_STYLES = {
  W: 'bg-amber-100 text-amber-900',
  U: 'bg-sky-500 text-white',
  B: 'bg-zinc-800 text-zinc-100 ring-1 ring-zinc-600',
  R: 'bg-red-500 text-white',
  G: 'bg-emerald-500 text-white',
  C: 'bg-slate-500 text-slate-100',
};

const CARD_ACCENT = {
  W: 'from-amber-200 to-amber-400',
  U: 'from-sky-400 to-sky-600',
  B: 'from-zinc-500 to-zinc-800',
  R: 'from-red-400 to-red-600',
  G: 'from-emerald-400 to-emerald-600',
  C: 'from-slate-400 to-slate-600',
};

const SUGGESTED_COMMANDERS = [
  { name: 'Atraxa, Grand Unifier', theme: 'Superfriends • Value • Counters' },
  { name: 'Muldrotha, the Gravetide', theme: 'Graveyard Recursion • Value Engine' },
  { name: 'Krenko, Mob Boss', theme: 'Goblins • Go-Wide • Combo' },
  { name: 'The Ur-Dragon', theme: 'Dragons • Tribal • Big Mana' },
];

function parsePips(manaCost) {
  const matches = manaCost.match(/\{([^}]+)\}/g) || [];
  return matches.map((m) => m.replace(/[{}]/g, ''));
}

function getSpiceZone(level) {
  if (level < 34) {
    return { label: 'Mainstream Staples', desc: 'Tournament-tested picks everyone runs. Consistent and powerful, if a little predictable.' };
  }
  if (level < 67) {
    return { label: 'Balanced Brew', desc: 'A mix of proven staples and a few cards that start making this deck feel like yours.' };
  }
  return { label: 'Spicy Deep Cuts', desc: 'Off-meta picks that still pull their weight mechanically. This is where the deck gets a personality.' };
}

export default function LoreweaverDashboard() {
  const [commander, setCommander] = useState(null);
  const [commanderTheme, setCommanderTheme] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [submittedCommander, setSubmittedCommander] = useState('');
  const [spiceLevel, setSpiceLevel] = useState(50);
  const [recommendations, setRecommendations] = useState([]);
  const [recommendationsLoading, setRecommendationsLoading] = useState(false);
  const [recommendationsError, setRecommendationsError] = useState('');
  const [decklist, setDecklist] = useState([]);
  const [justAddedId, setJustAddedId] = useState(null);

  const zone = getSpiceZone(spiceLevel);
  const inDeckIds = new Set(decklist.map((c) => c.id));
  const avgCmc = decklist.length ? (decklist.reduce((sum, c) => sum + (Number(c.cmc) || 0), 0) / decklist.length).toFixed(2) : '0.00';

  const swimlanes = useMemo(() => {
    return recommendations.reduce((acc, card) => {
      const category = card.category || card.lane || card.section || 'Recommendations';
      if (!acc[category]) {
        acc[category] = [];
      }
      acc[category].push(card);
      return acc;
    }, {});
  }, [recommendations]);

  const fetchRecommendations = async (commanderName, spiceValue) => {
    const controller = new AbortController();

    setRecommendationsLoading(true);
    setRecommendationsError('');

    try {
      const url = new URL(RECOMMENDATION_API_URL);
      url.searchParams.set('commander', commanderName);
      url.searchParams.set('spice', String(spiceValue));

      const response = await fetch(url.toString(), { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      setRecommendations(Array.isArray(data) ? data : []);
    } catch (error) {
      if (error?.name !== 'AbortError') {
        setRecommendations([]);
        setRecommendationsError(error?.message || 'Could not load recommendations.');
      }
    } finally {
      if (!controller.signal.aborted) {
        setRecommendationsLoading(false);
      }
    }

    return controller;
  };

  useEffect(() => {
    if (!submittedCommander.trim()) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void fetchRecommendations(submittedCommander.trim(), spiceLevel);
    }, 300);

    return () => window.clearTimeout(timeoutId);
  }, [submittedCommander, spiceLevel]);

  const chooseCommander = (name, theme) => {
    setCommander(name);
    setCommanderTheme(theme || 'Freeform build • Theme not yet identified');
    setSearchQuery(name);
    setSubmittedCommander(name);
  };

  const handleAddCard = (card) => {
    if (inDeckIds.has(card.id) || decklist.length >= 99) return;
    setDecklist((prev) => [...prev, card]);
    setJustAddedId(card.id);
    setTimeout(() => setJustAddedId((cur) => (cur === card.id ? null : cur)), 900);
  };

  const handleRemoveCard = (id) => {
    setDecklist((prev) => prev.filter((c) => c.id !== id));
  };

  return (
    <div
      className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden"
      style={{ fontFamily: "'Inter', ui-sans-serif, system-ui, sans-serif" }}
    >
      {/* Fonts + custom range-input thumb styling (native <select>-style pseudo-elements
          can't be reached with Tailwind utilities alone). If you already load fonts
          globally in your project, feel free to drop the @import line below. */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');

        @keyframes cardIn {
          from { opacity: 0; transform: translateY(-8px) scale(0.96); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .animate-card-in { animation: cardIn 0.35s ease-out; }

        .spice-slider {
          -webkit-appearance: none;
          appearance: none;
          background: transparent;
        }
        .spice-slider::-webkit-slider-runnable-track {
          height: 6px;
          border-radius: 9999px;
          background: linear-gradient(to right, #818cf8, #a78bfa, #f59e0b, #ef4444);
        }
        .spice-slider::-moz-range-track {
          height: 6px;
          border-radius: 9999px;
          background: linear-gradient(to right, #818cf8, #a78bfa, #f59e0b, #ef4444);
        }
        .spice-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 20px;
          height: 20px;
          margin-top: -7px;
          border-radius: 9999px;
          background: #0f172a;
          border: 2px solid #c7d2fe;
          box-shadow: 0 0 10px rgba(99,102,241,0.55);
          cursor: pointer;
          transition: box-shadow 0.2s ease;
        }
        .spice-slider::-moz-range-thumb {
          width: 20px;
          height: 20px;
          border-radius: 9999px;
          background: #0f172a;
          border: 2px solid #c7d2fe;
          box-shadow: 0 0 10px rgba(99,102,241,0.55);
          cursor: pointer;
        }
      `}</style>

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col p-8 overflow-y-auto relative">
        {!commander ? (
          /* ---------------------------- Hero Search ---------------------------- */
          <div className="flex flex-col items-center justify-center h-full relative">
            <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[32rem] h-[32rem] rounded-full bg-indigo-600/10 blur-3xl pointer-events-none" />
            <div className="absolute top-1/4 left-1/2 -translate-x-[70%] w-80 h-80 rounded-full bg-violet-600/10 blur-3xl pointer-events-none" />

            <div className="relative flex items-center gap-2 mb-3 text-indigo-400">
              <Feather className="w-6 h-6" />
              <span className="text-xs font-semibold tracking-[0.3em] uppercase text-slate-400">Commander Companion</span>
            </div>
            <h1
              className="relative text-6xl font-semibold mb-8 bg-gradient-to-r from-indigo-300 via-violet-300 to-indigo-200 bg-clip-text text-transparent"
              style={{ fontFamily: "'Fraunces', ui-serif, Georgia, serif" }}
            >
              Loreweaver
            </h1>

            <div className="relative w-full max-w-xl">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
              <input
                type="text"
                placeholder="Search for a commander..."
                className="w-full pl-12 pr-4 py-4 rounded-xl bg-slate-900/80 border border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-lg placeholder:text-slate-600 transition-colors"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && searchQuery.trim()) {
                    chooseCommander(searchQuery.trim(), 'Freeform build • Theme not yet identified');
                  }
                }}
              />
            </div>

            <div className="relative flex flex-wrap justify-center gap-2 mt-6 max-w-xl">
              {SUGGESTED_COMMANDERS.map((c) => (
                <button
                  key={c.name}
                  onClick={() => chooseCommander(c.name, c.theme)}
                  className="px-3 py-1.5 rounded-full text-sm bg-slate-900/60 border border-slate-800 text-slate-300 hover:border-indigo-500 hover:text-indigo-300 transition-colors"
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* ------------------------- Command Dashboard ------------------------- */
          <div className="flex flex-col lg:flex-row w-full min-h-[calc(100vh-4rem)] bg-slate-950 text-slate-100 pb-20 lg:pb-0">
            <div className="flex flex-wrap justify-between items-start gap-6 mb-8 pb-6 border-b border-slate-800">
              <div>
                <button
                  onClick={() => setCommander(null)}
                  className="flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-300 transition-colors mb-2"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  Change commander
                </button>
                <h2
                  className="text-3xl font-semibold text-slate-50"
                  style={{ fontFamily: "'Fraunces', ui-serif, Georgia, serif" }}
                >
                  {commander}
                </h2>
                <p className="text-slate-400 mt-1">{commanderTheme}</p>
              </div>

              {/* -------------------------- The Flavor Dial -------------------------- */}
              <div className="w-72 bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold tracking-wide uppercase text-slate-400">Spice Level</span>
                  <span className="flex items-center gap-1 text-xs font-semibold text-amber-400" style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace" }}>
                    <Flame className="w-3.5 h-3.5" />
                    {spiceLevel}
                  </span>
                </div>
                <p className="text-sm font-medium text-indigo-200 mb-2">{zone.label}</p>

                <input
                  type="range"
                  min="0"
                  max="100"
                  value={spiceLevel}
                  onChange={(e) => setSpiceLevel(Number(e.target.value))}
                  className="spice-slider w-full cursor-pointer"
                />
                <div className="flex justify-between text-[11px] text-slate-500 mt-1.5">
                  <span className={spiceLevel < 34 ? 'text-indigo-300 font-semibold' : ''}>Mainstream Staples</span>
                  <span className={spiceLevel >= 67 ? 'text-amber-400 font-semibold' : ''}>Spicy Deep Cuts</span>
                </div>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">{zone.desc}</p>
              </div>
            </div>

            {/* --------------------------- Swimlanes --------------------------- */}
            <div className="flex-1 space-y-9">
              {recommendationsLoading ? (
                <div className="flex items-center justify-center py-20 text-slate-400">
                  Loading recommendations from the backend...
                </div>
              ) : recommendationsError ? (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                  {recommendationsError}
                </div>
              ) : Object.keys(swimlanes).length > 0 ? (
                Object.entries(swimlanes).map(([category, cards]) => (
                  <section key={category}>
                    <h3
                      className="text-lg font-semibold mb-3 text-slate-200"
                      style={{ fontFamily: "'Fraunces', ui-serif, Georgia, serif" }}
                    >
                      {category}
                    </h3>
                    <div className="flex space-x-4 overflow-x-auto pb-3">
                      {cards.map((card, index) => {
                        const normalizedCard = {
                          ...card,
                          id: card.id ?? `${category}-${card.name}-${index}`,
                          manaCost: card.manaCost || card.mana_cost || '',
                          type: card.type || card.type_line || '',
                          color: card.color || (Array.isArray(card.colors) ? card.colors[0] : 'C'),
                          cmc: Number(card.cmc) || 0,
                        };
                        const spiceValue = Number(card.spice ?? card.spice_level ?? 50);
                        const inRange = Number.isFinite(spiceValue) ? Math.abs(spiceValue - spiceLevel) <= 40 : true;
                        const alreadyAdded = inDeckIds.has(normalizedCard.id);
                        const justAdded = justAddedId === normalizedCard.id;
                        const imageUrl = card.image_url || card.imageUrl || card.image || '';

                        return (
                          <div
                            key={normalizedCard.id}
                            className={`min-w-[168px] w-[168px] h-64 rounded-xl border overflow-hidden flex flex-col relative group transition-all duration-300 ${
                              inRange
                                ? 'bg-slate-800/70 border-slate-700 opacity-100'
                                : 'bg-slate-800/40 border-slate-800 opacity-40 grayscale-[0.4]'
                            }`}
                          >
                            <div className={`h-1.5 w-full bg-gradient-to-r ${CARD_ACCENT[normalizedCard.color] || CARD_ACCENT.C}`} />

                            <div className="h-16 overflow-hidden bg-slate-900/40">
                              {imageUrl ? (
                                <img
                                  src={imageUrl}
                                  alt={normalizedCard.name}
                                  className="h-full w-full object-cover"
                                  onError={(event) => {
                                    if (event.currentTarget.src !== FALLBACK_CARD_BACK) {
                                      event.currentTarget.src = FALLBACK_CARD_BACK;
                                    }
                                  }}
                                />
                              ) : (
                                <div className="flex h-full items-center justify-center">
                                  <Feather className="w-5 h-5 text-slate-700" />
                                </div>
                              )}
                            </div>

                            <div className="flex-1 flex flex-col p-3">
                              <p className="text-sm font-semibold text-slate-100 leading-snug">{normalizedCard.name}</p>
                              <div className="flex flex-wrap gap-1 mt-1.5">
                                {parsePips(normalizedCard.manaCost).map((pip, i) => (
                                  <span
                                    key={i}
                                    className={`w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center ${
                                      PIP_STYLES[pip] || 'bg-slate-700 text-slate-200'
                                    }`}
                                  >
                                    {pip}
                                  </span>
                                ))}
                              </div>
                              <p className="text-[11px] text-slate-500 mt-auto pt-2">{normalizedCard.type}</p>

                              <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/50">
                                <span
                                  className="text-[11px] text-slate-400"
                                  style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace" }}
                                >
                                  CMC {normalizedCard.cmc}
                                </span>
                                <span className="flex gap-0.5">
                                  {Array.from({ length: 5 }).map((_, i) => (
                                    <Flame
                                      key={i}
                                      className={`w-2.5 h-2.5 ${i < (card.spice ?? 0) ? 'text-amber-500' : 'text-slate-700'}`}
                                      fill={i < (card.spice ?? 0) ? 'currentColor' : 'none'}
                                    />
                                  ))}
                                </span>
                              </div>
                            </div>

                            <div className="absolute inset-0 bg-slate-950/85 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center rounded-xl">
                              <button
                                onClick={() => handleAddCard({
                                  ...card,
                                  ...normalizedCard,
                                  category: card.category || card.lane || card.section || 'Recommendations',
                                })}
                                disabled={alreadyAdded}
                                className={`px-4 py-2 rounded-lg font-semibold text-sm flex items-center gap-1.5 transition-all duration-200 ${
                                  alreadyAdded
                                    ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                                    : 'bg-gradient-to-r from-indigo-500 to-violet-500 text-white hover:scale-105 hover:shadow-lg hover:shadow-indigo-500/30'
                                }`}
                              >
                                {alreadyAdded || justAdded ? (
                                  <>
                                    <Check className="w-4 h-4" /> In Deck
                                  </>
                                ) : (
                                  'Add to Deck'
                                )}
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                ))
              ) : (
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm text-slate-400">
                  Press Enter in the search bar to load backend recommendations.
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ------------------------- Deckbuilder Drawer ------------------------- */}
      <div className="w-80 bg-slate-950 border-l border-slate-800 p-6 flex flex-col">
        <h3
          className="text-xl font-semibold mb-4 text-slate-50"
          style={{ fontFamily: "'Fraunces', ui-serif, Georgia, serif" }}
        >
          Active Deck
        </h3>
        <div
          className="flex justify-between text-sm text-slate-400 mb-6 pb-4 border-b border-slate-800"
          style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace" }}
        >
          <span>Cards: {decklist.length} / 100</span>
          <span>Avg CMC: {avgCmc}</span>
        </div>

        <ul className="flex-1 overflow-y-auto space-y-2">
          {decklist.map((card) => (
            <li
              key={card.id}
              className="animate-card-in flex items-center justify-between gap-2 px-3 py-2 bg-slate-900 rounded-lg border border-slate-800 text-sm text-slate-300"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className={`w-1.5 h-6 rounded-full bg-gradient-to-b ${CARD_ACCENT[card.color]} shrink-0`} />
                <span className="truncate">{card.name}</span>
              </div>
              <button
                onClick={() => handleRemoveCard(card.id)}
                className="text-slate-600 hover:text-red-400 transition-colors shrink-0"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
          {decklist.length === 0 && (
            <div className="text-center text-slate-600 mt-10 text-sm leading-relaxed">
              Your deck is empty.
              <br />
              Hover a card and add it to begin.
            </div>
          )}
        </ul>
      </div>
    </div>
  );
}
