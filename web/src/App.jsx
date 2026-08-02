import React, { useEffect, useState } from 'react';
import { fetchCardsMetadata } from './utils/scryfall';
import { parseDecklistText, calculateCohesionScore, calculateFlavorProfile, analyzeIntentionalExperience } from './utils/themeEngine';
import { analyzeStress } from './utils/stressTester';
import { detectBrokenChains, fetchSpiceRecommendations } from './utils/spiceInjector';
import LoreweaverDashboard from './LoreweaverDashboard';
const RECOMMENDATION_API_URL = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/recommendations`;
const CARD_BACK_FALLBACK = 'https://cards.scryfall.io/back.jpg';
const RECOMMENDATION_LANE_ORDER = ['lands', 'ramp', 'draw', 'removal', 'synergy', 'utility', 'other'];

const LANE_LABELS = {
  lands: 'Lands',
  ramp: 'Ramp',
  draw: 'Draw',
  removal: 'Removal',
  synergy: 'Synergy',
  utility: 'Utility',
  other: 'Other'
};

const normalizeLaneKey = (value) => {
  const normalized = String(value || 'other').toLowerCase();

  if (normalized.includes('land')) return 'lands';
  if (normalized.includes('ramp') || normalized.includes('mana')) return 'ramp';
  if (normalized.includes('draw') || normalized.includes('card advantage')) return 'draw';
  if (normalized.includes('removal') || normalized.includes('interaction') || normalized.includes('answer')) return 'removal';
  if (normalized.includes('utility') || normalized.includes('toolbox')) return 'utility';
  if (normalized.includes('synergy') || normalized.includes('engine') || normalized.includes('core')) return 'synergy';
  return normalized;
};

const normalizeRecommendationCard = (card) => ({
  name: card?.name || 'Unnamed Card',
  mana_cost: card?.mana_cost || '',
  type_line: card?.type_line || card?.type || '',
  oracle_text: card?.oracle_text || '',
  image_url: card?.image_url || card?.imageUrl || card?.image || '',
  edhrec_rank: card?.edhrec_rank ?? card?.rank ?? null
});

const laneTitle = (key) => LANE_LABELS[key] || String(key || 'Other').replace(/[_-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());

const mapRecommendationResponse = (payload) => {
  const lanes = new Map();

  const addCard = (laneName, card) => {
    const laneKey = normalizeLaneKey(laneName);
    const nextCard = normalizeRecommendationCard(card);
    if (!lanes.has(laneKey)) {
      lanes.set(laneKey, []);
    }
    lanes.get(laneKey).push(nextCard);
  };

  const addLaneObject = (laneName, cards) => {
    if (!Array.isArray(cards)) return;
    cards.forEach((card) => addCard(laneName, card));
  };

  if (Array.isArray(payload)) {
    payload.forEach((entry) => {
      if (!entry) return;

      if (Array.isArray(entry.cards)) {
        addLaneObject(entry.title || entry.name || entry.category || entry.lane || entry.section || 'other', entry.cards);
        return;
      }

      addCard(entry.lane || entry.category || entry.section || entry.bucket || entry.kind || entry.group || 'other', entry);
    });
  } else if (payload && typeof payload === 'object') {
    const lanePayload = payload.data || payload.swimlanes || payload.recommendations || payload.categories || payload.lanes || payload.sections || payload.groups;

    if (lanePayload && typeof lanePayload === 'object' && !Array.isArray(lanePayload)) {
      Object.entries(lanePayload).forEach(([laneName, cards]) => addLaneObject(laneName, cards));
    } else if (Array.isArray(lanePayload)) {
      lanePayload.forEach((entry) => {
        if (!entry) return;

        if (Array.isArray(entry.cards)) {
          addLaneObject(entry.title || entry.name || entry.category || entry.lane || entry.section || 'other', entry.cards);
          return;
        }

        addCard(entry.lane || entry.category || entry.section || entry.bucket || entry.kind || entry.group || 'other', entry);
      });
    } else {
      ['lands', 'ramp', 'draw', 'removal', 'synergy', 'utility', 'other'].forEach((laneName) => {
        if (Array.isArray(payload[laneName])) {
          addLaneObject(laneName, payload[laneName]);
        }
      });
    }
  }

  return RECOMMENDATION_LANE_ORDER
    .filter((laneKey) => lanes.has(laneKey))
    .map((laneKey) => ({ title: laneTitle(laneKey), cards: lanes.get(laneKey) }))
    .concat(
      [...lanes.entries()]
        .filter(([laneKey]) => !RECOMMENDATION_LANE_ORDER.includes(laneKey))
        .map(([laneKey, cards]) => ({ title: laneTitle(laneKey), cards }))
    );
};

function App() {
  const [activeTab, setActiveTab] = useState('input');
  const [commander, setCommander] = useState('Kozilek, the Great Distortion');
  const [bracket, setBracket] = useState(2);
  const [targetIX, setTargetIX] = useState('Aggro-Combat');
  const [decklist, setDecklist] = useState(
    `// Commander\n` +
    `1 Kozilek, the Great Distortion\n\n` +
    `// Lands\n` +
    `37 Wastes\n\n` +
    `// Spells\n` +
    `1 Sol Ring\n` +
    `1 Mana Vault\n` +
    `1 Thran Dynamo\n` +
    `1 Mind Stone\n` +
    `1 Worn Powerstone\n` +
    `1 Everflowing Chalice\n` +
    `1 Hedron Archive\n` +
    `1 Kozilek's Channeler\n` +
    `1 Palladium Myr\n` +
    `1 Gilded Lotus\n` +
    `1 Kozilek's Command\n` +
    `1 Endbringer\n` +
    `1 Solemn Simulacrum\n` +
    `1 All Is Dust\n` +
    `1 Titan's Presence\n` +
    `1 Not of This World\n` +
    `1 Introduction to Prophecy\n` +
    `1 Warping Wail\n` +
    `1 Spatial Contortion\n` +
    `1 Swiftfoot Boots\n` +
    `1 Lightning Greaves\n` +
    `1 Soul of New Phyrexia`
  );
  
  const [hasInteracted, setHasInteracted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analyzed, setAnalyzed] = useState(false);
  const [results, setResults] = useState(null);
  
  const [brokenChains, setBrokenChains] = useState([]);
  const [spiceRecommendations, setSpiceRecommendations] = useState([]);
  const [spiceLoading, setSpiceLoading] = useState(false);
  const [selectedChainIndex, setSelectedChainIndex] = useState(0);
  const [commanderQuery, setCommanderQuery] = useState(commander);
  const [requestedCommander, setRequestedCommander] = useState('');
  const [spiceLevel, setSpiceLevel] = useState(50);
  const [recommendationLanes, setRecommendationLanes] = useState([]);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [recommendationError, setRecommendationError] = useState('');
  const [hasRequestedRecommendations, setHasRequestedRecommendations] = useState(false);

  const handleAnalyze = async () => {
    if (!decklist.trim()) return;
    setLoading(true);
    
    try {
      // 1. Fetch Commander details dynamically from Scryfall
      let commanderCardInfo = null;
      try {
        let cleanCommander = commander.trim();
        const commMatch = cleanCommander.match(/^(\d+)\s+(.+)$/);
        if (commMatch) {
          cleanCommander = commMatch[2].trim();
        }
        const res = await fetch(`https://api.scryfall.com/cards/named?exact=${encodeURIComponent(cleanCommander)}`, {
          headers: {
            "Accept": "application/json;q=0.9,*/*;q=0.8"
          }
        });
        if (res.ok) {
          const data = await res.json();
          let types = [];
          let subtypes = [];
          const typeLine = data.type_line || "";
          if (typeLine) {
            const parts = typeLine.split("—");
            types = parts[0].trim().split(" ").map(t => t.toLowerCase());
            if (parts[1]) {
              subtypes = parts[1].trim().split(" ").filter(Boolean).map(s => s.toLowerCase());
            }
          }
          commanderCardInfo = {
            name: data.name,
            raw_type: typeLine,
            types,
            subtypes,
            oracle_text: data.oracle_text || "",
            colors: data.color_identity || []
          };
        }
      } catch (e) {
        console.error("Could not fetch commander info from Scryfall:", e);
      }

      // 2. Parse deck lists
      const parsedNames = parseDecklistText(decklist);
      
      // 3. Batch fetch card details from Scryfall API
      const db = await fetchCardsMetadata(parsedNames);
      
      // 4. Run theme calculations
      const cohesion = calculateCohesionScore(parsedNames, db);
      const flavor = calculateFlavorProfile(parsedNames, db);
      const ix = analyzeIntentionalExperience(parsedNames, db, targetIX, bracket);
      
      // 5. Run stress-tester engine calculations
      const stress = analyzeStress(parsedNames, db, commanderCardInfo, cohesion);
      
      // 6. Broken chain detection
      const chains = detectBrokenChains(parsedNames, db);
      setBrokenChains(chains);
      setSelectedChainIndex(0);
      setSpiceRecommendations([]);
      
      setResults({
        cohesion,
        flavor,
        ix,
        stress,
        totalCards: parsedNames.length,
        commanderInfo: commanderCardInfo
      });
      setAnalyzed(true);

      // Trigger spice fetch for first broken chain
      if (chains.length > 0) {
        setSpiceLoading(true);
        const firstChain = chains[0];
        const colorIdentity = commanderCardInfo ? commanderCardInfo.colors : [];
        const recs = await fetchSpiceRecommendations(firstChain.queryKeyword, colorIdentity);
        setSpiceRecommendations(recs);
        setSpiceLoading(false);
      }
      
      setActiveTab('cohesion');
    } catch (error) {
      alert(`Error analyzing deck list: ${error.message || error}`);
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectChain = async (index) => {
    setSelectedChainIndex(index);
    setSpiceLoading(true);
    setSpiceRecommendations([]);
    const chain = brokenChains[index];
    const colorIdentity = results?.commanderInfo ? results.commanderInfo.colors : [];
    const recs = await fetchSpiceRecommendations(chain.queryKeyword, colorIdentity);
    setSpiceRecommendations(recs);
    setSpiceLoading(false);
  };

  const handleCommanderSearch = () => {
    const nextCommander = commanderQuery.trim();

    if (!nextCommander) return;

    setRequestedCommander(nextCommander);
    setHasRequestedRecommendations(true);
  };

  useEffect(() => {
    if (!hasRequestedRecommendations || !requestedCommander.trim()) {
      return;
    }

    const controller = new AbortController();

    const loadRecommendations = async () => {
      setRecommendationLoading(true);
      setRecommendationError('');

      try {
        const url = new URL(RECOMMENDATION_API_URL);
        url.searchParams.set('commander', requestedCommander.trim());
        url.searchParams.set('spice', String(spiceLevel));

        const response = await fetch(url.toString(), { signal: controller.signal });

        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }

        const payload = await response.json();
        setRecommendationLanes(mapRecommendationResponse(payload));
      } catch (error) {
        if (error?.name !== 'AbortError') {
          setRecommendationLanes([]);
          setRecommendationError(error?.message || 'Could not load recommendations from the backend.');
        }
      } finally {
        if (!controller.signal.aborted) {
          setRecommendationLoading(false);
        }
      }
    };

    loadRecommendations();

    return () => controller.abort();
  }, [hasRequestedRecommendations, requestedCommander, spiceLevel]);

  const getCohesionStyleClass = (score) => {
    if (score >= 75) return 'cohesion-excellent';
    if (score >= 50) return 'cohesion-moderate';
    return 'cohesion-low';
  };

  const getCohesionText = (score) => {
    if (score >= 75) return 'Excellent';
    if (score >= 50) return 'Moderate';
    return 'Low Cohesion';
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <img src="/logo.png" alt="Loreweaver Logo" className="logo-img" />
        <h1 className="app-title">Loreweaver</h1>
      </header>

      {/* Main Tab Switcher */}
      <main className="tab-content">
        {activeTab === 'input' && (
          <div className="tab-panel">
            <h2>Deck Analysis Input</h2>
            
            <div className="card">
              <div className="form-group">
                <label className="form-label">Commander Name</label>
                <input 
                  type="text" 
                  className="text-input" 
                  value={commander}
                  onChange={(e) => setCommander(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Target Intentional Experience (IX)</label>
                <select 
                  className="text-input"
                  value={targetIX}
                  onChange={(e) => setTargetIX(e.target.value)}
                >
                  <option value="Aggro-Combat">Aggro-Combat (Combat focused, damage modifiers)</option>
                  <option value="Grindy Value Engine">Grindy Value Engine (Graveyard, draw, end-step triggers)</option>
                  <option value="Deterministic Combo">Deterministic Combo (Infinite loops, tutors, untapping)</option>
                  <option value="Political/Interactive">Political/Interactive (Voting, choices, group play)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Target Power Bracket (Tier: {bracket})</label>
                <input 
                  type="range" 
                  min="1" 
                  max="5" 
                  className="text-input" 
                  value={bracket}
                  onChange={(e) => setBracket(parseInt(e.target.value))}
                  style={{ height: '8px', padding: 0 }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', marginTop: '4px', color: 'var(--text-accent)' }}>
                  <span>1: Battlecruiser</span>
                  <span>2: Precon+</span>
                  <span>3: Focused</span>
                  <span>4: Optimized</span>
                  <span>5: cEDH</span>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Paste Decklist</label>
                <textarea 
                  className="textarea-input"
                  value={decklist}
                  onChange={(e) => {
                    setDecklist(e.target.value);
                    setHasInteracted(true);
                  }}
                  onFocus={() => {
                    if (!hasInteracted) {
                      setDecklist("");
                      setHasInteracted(true);
                    }
                  }}
                  placeholder="1 Sol Ring&#10;1 Mana Crypt..."
                />
              </div>

              <button 
                className="btn-action" 
                onClick={handleAnalyze}
                disabled={loading}
              >
                {loading ? 'Analyzing...' : 'Analyze Deck'}
              </button>
            </div>
          </div>
        )}

        {activeTab === 'cohesion' && (
          <div className="tab-panel">
            <h2>Thematic Cohesion Dashboard</h2>

            {!analyzed ? (
              <div className="empty-state">
                <div className="empty-icon">🔮</div>
                <p>No analysis loaded. Go to the Input tab and run "Analyze Deck" first.</p>
              </div>
            ) : loading ? (
              <div className="loader-container">
                <div className="loader-spinner"></div>
                <p>Ingesting data and calculating themes...</p>
              </div>
            ) : (
              <div>
                {/* CFP Matchmaking Dashboard */}
                <div className="card">
                  <div className="form-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>Commander Brackets Matchmaking</span>
                    <span style={{ fontSize: '0.8rem', backgroundColor: 'var(--bg-input)', padding: '2px 8px', borderRadius: '12px', color: 'var(--text-accent)' }}>
                      Target: Bracket {bracket}
                    </span>
                  </div>

                  <div className="theme-row" style={{ marginTop: '10px' }}>
                    <span>Game Changers List:</span>
                    <span style={{ 
                      fontWeight: 'bold', 
                      color: results.ix.gameChangersFound.length > (bracket === 3 ? 3 : (bracket >= 4 ? 40 : 0)) ? 'var(--color-red)' : 'var(--color-green)'
                    }}>
                      {results.ix.gameChangersFound.length} / {bracket === 3 ? '3' : (bracket >= 4 ? 'Unlimited' : '0')} allowed
                    </span>
                  </div>

                  {results.ix.gameChangersFound.length > 0 && (
                    <div style={{ marginTop: '8px', fontSize: '0.85rem' }}>
                      <span style={{ color: 'var(--text-accent)', fontWeight: 'bold' }}>Game Changers:</span>{' '}
                      <span style={{ color: 'var(--text-white)' }}>{results.ix.gameChangersFound.join(", ")}</span>
                    </div>
                  )}

                  {results.ix.landDenialFound.length > 0 && (
                    <div style={{ marginTop: '8px', fontSize: '0.85rem' }}>
                      <span style={{ color: 'var(--text-accent)', fontWeight: 'bold' }}>Mass Land Denial:</span>{' '}
                      <span style={{ color: 'var(--text-white)' }}>{results.ix.landDenialFound.join(", ")}</span>
                    </div>
                  )}

                  {results.ix.extraTurnsFound.length > 0 && (
                    <div style={{ marginTop: '8px', fontSize: '0.85rem' }}>
                      <span style={{ color: 'var(--text-accent)', fontWeight: 'bold' }}>Extra-Turn Spells:</span>{' '}
                      <span style={{ color: 'var(--text-white)' }}>{results.ix.extraTurnsFound.join(", ")}</span>
                    </div>
                  )}

                  {results.ix.tutorsFound.length > 0 && (
                    <div style={{ marginTop: '8px', fontSize: '0.85rem' }}>
                      <span style={{ color: 'var(--text-accent)', fontWeight: 'bold' }}>Non-Land Tutors:</span>{' '}
                      <span style={{ color: 'var(--text-white)' }}>{results.ix.tutorsFound.join(", ")} ({results.ix.tutorsFound.length})</span>
                    </div>
                  )}
                </div>

                {/* Intentional Experience Warning Alerts */}
                {results.ix.alerts.length > 0 && (
                  <div className="card" style={{ border: '1px solid var(--color-orange)', backgroundColor: 'rgba(230, 126, 34, 0.05)' }}>
                    <div className="form-label" style={{ color: 'var(--color-orange)' }}>⚠️ Experience Warnings</div>
                    {results.ix.alerts.map((alert, i) => (
                      <div key={i} style={{ marginBottom: '8px', fontSize: '0.85rem', lineHeight: '1.4' }}>
                        <span style={{ fontWeight: 'bold', color: alert.type === 'warning' ? 'var(--color-red)' : 'var(--color-orange)' }}>
                          [{alert.title}]
                        </span>{' '}
                        {alert.message}
                      </div>
                    ))}
                  </div>
                )}

                {/* Cohesion Score card */}
                <div className="card" style={{ textAlign: 'center' }}>
                  <div className="form-label">Theme Cohesion Score</div>
                  <div className={`score-badge ${getCohesionStyleClass(results.cohesion.cohesion_score)}`}>
                    {results.cohesion.cohesion_score}/100
                  </div>
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-accent)' }}>
                    Rating: {getCohesionText(results.cohesion.cohesion_score)}
                  </p>
                </div>

                {/* Flavor Profile card */}
                <div className="card">
                  <div className="form-label">Flavor Profile</div>
                  <div>
                    <p style={{ fontWeight: 'bold', color: results.flavor.flavorColor }}>
                      {results.flavor.flavorRating} ({results.flavor.spiceRatio}% Spice)
                    </p>
                    
                    {results.flavor.spicyCards.length > 0 && (
                      <div style={{ marginTop: '12px' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-accent)' }}>
                          Synergistic / Spicy Cards ({results.flavor.spicyCards.length}):
                        </span>
                        <div style={{ marginTop: '6px', maxHeight: '120px', overflowY: 'auto', paddingRight: '4px' }}>
                          {results.flavor.spicyCards.map((c, i) => (
                            <div key={i} className="clash-card-item" style={{ fontSize: '0.85rem', color: 'var(--text-white)', padding: '2px 0' }}>
                              ✦ {c}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Theme Breakdowns card */}
                <div className="card">
                  <div className="form-label">Thematic Clusters</div>
                  
                  <div className="list-header">Creature Subtypes</div>
                  {Object.keys(results.cohesion.subtype_counts).length > 0 ? (
                    Object.entries(results.cohesion.subtype_counts).map(([sub, count]) => (
                      <div key={sub} className="theme-row">
                        <span style={{ textTransform: 'capitalize' }}>{sub}</span>
                        <span className="theme-count">{count}</span>
                      </div>
                    ))
                  ) : (
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-accent)', padding: '6px 0' }}>None</p>
                  )}

                  <div className="list-header">Mechanical Themes</div>
                  {Object.keys(results.cohesion.theme_counts).length > 0 ? (
                    Object.entries(results.cohesion.theme_counts).map(([theme, count]) => (
                      <div key={theme} className="theme-row">
                        <span>{theme}</span>
                        <span className="theme-count">{count}</span>
                      </div>
                    ))
                  ) : (
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-accent)', padding: '6px 0' }}>None</p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'stress' && (
          <div className="tab-panel">
            <h2>Engine Stress-Tester Dashboard</h2>

            {!analyzed ? (
              <div className="empty-state">
                <div className="empty-icon">📊</div>
                <p>No analysis loaded. Go to the Input tab and run "Analyze Deck" first.</p>
              </div>
            ) : loading ? (
              <div className="loader-container">
                <div className="loader-spinner"></div>
                <p>Calculating engine statistics...</p>
              </div>
            ) : (
              <div>
                {/* CDI Dashboard card */}
                <div className="card">
                  <div className="metric-row">
                    <div className="metric-header">
                      <span className="metric-title" style={{ color: 'var(--text-accent)' }}>Commander Dependency (CDI)</span>
                      <span className="metric-value" style={{ color: results.stress.cdiRating === 'HIGH' ? 'var(--color-red)' : results.stress.cdiRating === 'MEDIUM' ? 'var(--color-orange)' : 'var(--color-green)' }}>
                        {results.stress.cdiRating} ({results.stress.cdiScore}/100)
                      </span>
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-main)', marginTop: '4px', lineHeight: '1.4' }}>
                      Maps how heavily the 99 payoffs rely on the commander generator to execute their strategy.
                    </p>

                    {results.stress.glassCannonAlert && (
                      <div style={{ marginTop: '12px', padding: '10px', backgroundColor: 'rgba(226, 74, 74, 0.1)', border: '1px solid var(--color-red)', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--color-red)', fontWeight: 'bold' }}>
                        [!] Glass Cannon Alert: High CDI, but deck has less than 8 protection spells ({results.stress.protectionCount} found). Add more protective cards!
                      </div>
                    )}
                  </div>
                </div>

                {/* 1. Fragility Index card */}
                <div className="card">
                  <div className="metric-row">
                    <div className="metric-header">
                      <span className="metric-title" style={{ color: 'var(--text-accent)' }}>1. Fragility Index</span>
                      <span className="metric-value" style={{ color: results.stress.fragilityColor }}>
                        {results.stress.fragilityRating}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.9rem', marginBottom: '8px', color: 'var(--text-main)' }}>
                      Adjusted Score: {results.stress.adjustedFragility.toFixed(2)} (Average: {results.stress.avgFragility.toFixed(2)})
                    </p>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-accent)', lineHeight: '1.4' }}>
                      Permanents: Creatures ({results.stress.creaturesCount}) | Artifacts ({results.stress.artifactsCount}) | Enchantments ({results.stress.enchantmentsCount}) | Planeswalkers ({results.stress.planeswalkersCount}) | Protection Spells ({results.stress.protectionCount})
                    </p>
                    
                    {results.stress.adjustedFragility >= 0.6 && (
                      <div style={{ marginTop: '12px', padding: '10px', backgroundColor: 'rgba(226, 74, 74, 0.1)', border: '1px solid var(--color-red)', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--color-red)', fontWeight: 'bold' }}>
                        [!] WARNING: High risk of board wipe disruption. Consider adding more protection.
                      </div>
                    )}
                  </div>
                </div>

                {/* 2. Multiplayer Table-Pressure card */}
                <div className="card">
                  <div className="metric-row">
                    <div className="metric-header">
                      <span className="metric-title" style={{ color: 'var(--text-accent)' }}>2. Multiplayer Table-Pressure</span>
                      <span className="metric-value">{results.stress.tablePressureScore}%</span>
                    </div>
                    
                    <div className="progress-container" style={{ margin: '8px 0 16px 0' }}>
                      <div 
                        className="progress-fill" 
                        style={{ 
                          width: `${results.stress.tablePressureScore}%`,
                          backgroundColor: results.stress.tablePressureScore >= 70 ? 'var(--color-red)' : results.stress.tablePressureScore >= 40 ? 'var(--color-orange)' : 'var(--color-green)'
                        }}
                      ></div>
                      <span className="progress-text">Pressure Rating: {results.stress.tablePressureScore}%</span>
                    </div>
                    
                    <div className="form-label" style={{ fontSize: '0.8rem', marginBottom: '6px' }}>Scaling Multiplayer Spells ({results.stress.scalingSpells.length})</div>
                    {results.stress.scalingSpells.length > 0 ? (
                      <div className="scrolling-list">
                        {results.stress.scalingSpells.map((spell, i) => (
                          <div key={i} className="list-item">{spell}</div>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-accent)' }}>None found.</p>
                    )}
                  </div>
                </div>

                {/* 3. Draw Consistency card */}
                <div className="card">
                  <div className="metric-row">
                    <div className="metric-header">
                      <span className="metric-title" style={{ color: 'var(--text-accent)' }}>3. Engine Consistency</span>
                      <span className="metric-value" style={{ color: results.stress.consistencyColor }}>
                        {results.stress.consistencyRating}
                      </span>
                    </div>
                    <p style={{ fontSize: '1.2rem', fontWeight: 'bold', color: 'var(--text-white)', margin: '4px 0' }}>
                      Draw Probability: {(results.stress.jointProb * 100).toFixed(1)}%
                    </p>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-accent)', lineHeight: '1.4' }}>
                      Probability of drawing &ge;3 lands, &ge;1 ramp spell, and &ge;1 draw spell by turn 6 (sample of 13 cards).
                    </p>

                    {(results.stress.commanderFulfillsRamp || results.stress.commanderFulfillsDraw) && (
                      <div style={{ margin: '10px 0', padding: '8px', backgroundColor: 'rgba(39, 174, 96, 0.08)', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--color-green)' }}>
                        {results.stress.commanderFulfillsRamp && "✓ Commander fulfills RAMP engine (Guaranteed Turn 0 draw: reduced 99 requirement by 25%)\n"}
                        {results.stress.commanderFulfillsDraw && "✓ Commander fulfills DRAW engine (Guaranteed Turn 0 draw: reduced 99 requirement by 25%)"}
                      </div>
                    )}

                    <p style={{ fontSize: '0.8rem', color: 'var(--text-accent)', marginTop: '8px' }}>
                      Core Ingestion: Lands ({results.stress.landsCount}/37 target) | Ramp ({results.stress.rampCount}/{results.stress.rampTarget} target) | Draw ({results.stress.drawCount}/{results.stress.drawTarget} target)
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'spice' && (
          <div className="tab-panel">
            <h2>Proactive Spice Injector</h2>

            {!analyzed ? (
              <div className="empty-state">
                <div className="empty-icon">🌶️</div>
                <p>No analysis loaded. Go to the Input tab and run "Analyze Deck" first.</p>
              </div>
            ) : loading ? (
              <div className="loader-container">
                <div className="loader-spinner"></div>
                <p>Searching for broken chains...</p>
              </div>
            ) : brokenChains.length === 0 ? (
              <div className="card" style={{ textAlign: 'center', padding: '30px 20px' }}>
                <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>✓</div>
                <h3>All Theme Chains Intact</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-accent)', marginTop: '8px' }}>
                  Your generators (cards placing counters/creating tokens) and payoffs (doubling season/aristocrat outlets) are perfectly balanced!
                </p>
              </div>
            ) : (
              <div>
                {/* Selector for broken chains */}
                <div className="form-group">
                  <label className="form-label">Select Broken Chain to Fix</label>
                  <select 
                    className="text-input"
                    value={selectedChainIndex}
                    onChange={(e) => handleSelectChain(parseInt(e.target.value))}
                  >
                    {brokenChains.map((chain, i) => (
                      <option key={i} value={i}>{chain.theme}: {chain.reason}</option>
                    ))}
                  </select>
                </div>

                <div className="card" style={{ border: '1px solid var(--color-orange)', backgroundColor: 'rgba(230, 126, 34, 0.03)' }}>
                  <div className="form-label" style={{ color: 'var(--color-orange)' }}>Broken Chain Analysis</div>
                  <p style={{ fontSize: '0.9rem', lineHeight: '1.4' }}>
                    Loreweaver identified that your deck supports the <strong>{brokenChains[selectedChainIndex].theme}</strong> theme, but lacks sufficient <strong>{brokenChains[selectedChainIndex].missingType}s</strong> to execute it reliably.
                  </p>
                </div>

                <div className="card">
                  <div className="form-label">Commander Recommendations</div>
                  <div className="form-group">
                    <label className="form-label">Commander Search</label>
                    <input
                      type="text"
                      className="text-input"
                      value={commanderQuery}
                      onChange={(e) => setCommanderQuery(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleCommanderSearch();
                        }
                      }}
                      placeholder="Type a commander name and press Enter"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Flavor Dial: {spiceLevel}</label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      className="text-input"
                      value={spiceLevel}
                      onChange={(e) => {
                        const nextSpiceLevel = parseInt(e.target.value, 10);
                        setSpiceLevel(nextSpiceLevel);

                        const nextCommander = commanderQuery.trim();
                        if (nextCommander) {
                          setRequestedCommander(nextCommander);
                          setHasRequestedRecommendations(true);
                        }
                      }}
                      style={{ height: '8px', padding: 0 }}
                    />
                  </div>

                  {!hasRequestedRecommendations ? (
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-accent)' }}>
                      Press Enter in the search bar to load backend recommendations.
                    </p>
                  ) : recommendationLoading ? (
                    <div className="loader-container">
                      <div className="loader-spinner"></div>
                      <p>Fetching commander recommendations from the backend...</p>
                    </div>
                  ) : recommendationError ? (
                    <p style={{ fontSize: '0.9rem', color: 'var(--color-red)' }}>{recommendationError}</p>
                  ) : recommendationLanes.length > 0 ? (
                    <div style={{ display: 'grid', gap: '16px' }}>
                      {recommendationLanes.map((lane) => (
                        <section key={lane.title} className="card" style={{ marginBottom: 0 }}>
                          <div className="form-label" style={{ marginBottom: '12px' }}>{lane.title}</div>
                          <div style={{ display: 'flex', gap: '16px', overflowX: 'auto', paddingBottom: '12px' }}>
                            {lane.cards.map((card, idx) => (
                              <div
                                key={`${lane.title}-${card.name}-${idx}`}
                                className="card"
                                style={{
                                  flex: '0 0 280px',
                                  marginBottom: 0,
                                  border: '1px solid var(--border-purple)',
                                  backgroundColor: 'var(--bg-panel)'
                                }}
                              >
                                <div
                                  style={{
                                    width: '100%',
                                    aspectRatio: '3 / 4',
                                    overflow: 'hidden',
                                    borderRadius: '12px',
                                    marginBottom: '12px',
                                    backgroundColor: 'rgba(255, 255, 255, 0.04)',
                                    border: '1px solid rgba(255, 255, 255, 0.08)'
                                  }}
                                >
                                  <img
                                    src={card.image_url || CARD_BACK_FALLBACK}
                                    alt={card.name}
                                    className="h-full w-full object-cover"
                                    style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                                    onError={(event) => {
                                      if (event.currentTarget.src !== CARD_BACK_FALLBACK) {
                                        event.currentTarget.src = CARD_BACK_FALLBACK;
                                      }
                                    }}
                                  />
                                </div>
                                <h3 style={{ fontSize: '1rem', color: 'var(--text-white)', display: 'flex', justifyContent: 'space-between' }}>
                                  <span>{card.name}</span>
                                  <span style={{ fontSize: '0.85rem', color: 'var(--text-accent)' }}>{card.mana_cost}</span>
                                </h3>
                                <p style={{ fontSize: '0.75rem', color: 'var(--text-accent)', marginBottom: '8px', fontStyle: 'italic' }}>
                                  {card.type_line}{card.edhrec_rank ? ` (Rank #${card.edhrec_rank})` : ''}
                                </p>
                                <p style={{ fontSize: '0.8rem', lineHeight: '1.4', color: 'var(--text-main)' }}>
                                  {card.oracle_text}
                                </p>
                              </div>
                            ))}
                          </div>
                        </section>
                      ))}
                    </div>
                  ) : (
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-accent)' }}>No recommendations returned for that commander and flavor level.</p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
        {activeTab === 'builder' && (
          <div className="tab-panel" style={{ padding: 0, height: '100vh', overflow: 'hidden' }}>
            <LoreweaverDashboard/>
          </div>
          )}
          {activeTab === 'legal' && (
          <div className="tab-panel">
            <div className="card" style={{ textAlign: 'center', opacity: 0.8, marginTop: '20px' }}>
              <h2>Legal & Privacy</h2>
              <p style={{ fontSize: '0.85rem', marginBottom: '16px', lineHeight: '1.5' }}>
                Unofficial Fan Content permitted under the <a href="https://company.wizards.com/fancontentpolicy" target="_blank" rel="noreferrer" style={{ color: 'var(--text-accent)', textDecoration: 'underline' }}>WotC Fan Content Policy</a>. © Wizards of the Coast LLC.
              </p>
              <p style={{ fontSize: '0.85rem', lineHeight: '1.5' }}>
                🔒 <strong>Privacy:</strong> Decklists are analyzed locally in your browser. No data is saved, tracked, or stored remotely on any server.
              </p>
            </div>
          </div>
        )}
      </main>

      {/* 1. Bottom Nav tabs bar MOVED UP */}
      <nav className="bottom-nav">
        <button 
          className={`nav-tab ${activeTab === 'input' ? 'active' : ''}`}
          onClick={() => setActiveTab('input')}
        >
          <span className="nav-icon">📥</span>
          <span>Input</span>
        </button>
        <button 
          className={`nav-tab ${activeTab === 'cohesion' ? 'active' : ''}`}
          onClick={() => setActiveTab('cohesion')}
        >
          <span className="nav-icon">🔮</span>
          <span>Cohesion</span>
        </button>
        <button 
          className={`nav-tab ${activeTab === 'stress' ? 'active' : ''}`}
          onClick={() => setActiveTab('stress')}
        >
          <span className="nav-icon">📊</span>
          <span>Stress</span>
        </button>
        <button 
          className={`nav-tab ${activeTab === 'spice' ? 'active' : ''}`}
          onClick={() => setActiveTab('spice')}
        >
          <span className="nav-icon">🌶️</span>
          <span>Spice</span>
        </button>
        <button 
          className={`nav-tab ${activeTab === 'builder' ? 'active' : ''}`}
          onClick={() => setActiveTab('builder')}
        >
          <span className="nav-icon">🏗️</span>
          <span>Builder</span>
        </button>
        <button 
          className={`nav-tab ${activeTab === 'legal' ? 'active' : ''}`}
          onClick={() => setActiveTab('legal')}
        >
          <span className="nav-icon">📜</span>
          <span>Legal</span>
        </button>
      </nav>
    </div>
  );
}

export default App;


