import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  X, ArrowRightLeft, Dices, Search, Sparkles, RefreshCw, AlertCircle, Check
} from 'lucide-react';

const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
    return 'http://localhost:8000';
  }
  return 'https://api.lore-weaver.app';
};

const CATEGORY_META = {
  win_con: { label: 'Win Con', color: '#f43f5e', bg: 'rgba(244, 63, 94, 0.15)' },
  ramp: { label: 'Ramp', color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)' },
  draw: { label: 'Draw', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)' },
  removal: { label: 'Removal', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },
  synergy: { label: 'Synergy', color: '#a855f7', bg: 'rgba(168, 85, 247, 0.15)' },
  lands: { label: 'Lands', color: '#ca8a04', bg: 'rgba(202, 138, 4, 0.15)' }
};

export default function CardSwapModal({
  isOpen,
  onClose,
  card,
  role = 'synergy',
  commander = '',
  bracket = 3,
  exclude = [],
  onSwap
}) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Custom Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [swappingCardName, setSwappingCardName] = useState(null);

  const searchDebounceRef = useRef(null);

  // Fetch smart swap candidates
  const fetchCandidates = useCallback(async () => {
    if (!card) return;
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.append('card_name', card.name);
      if (commander) params.append('commander', commander);
      params.append('category', role);
      params.append('bracket', String(bracket));
      params.append('limit', '8');

      // Add exclusions (limit to 120 items to stay safely within URL limits)
      if (Array.isArray(exclude)) {
        const uniqueEx = Array.from(new Set(exclude)).slice(0, 100);
        for (const ex of uniqueEx) {
          if (ex) params.append('exclude', ex);
        }
      }

      const response = await fetch(`${getApiBaseUrl()}/api/swap-candidates?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Failed to load candidates: ${response.statusText}`);
      }

      const data = await response.json();
      setCandidates(data);
    } catch (err) {
      setError(err.message || 'Error fetching swap candidates.');
    } finally {
      setLoading(false);
    }
  }, [card, commander, role, bracket, exclude]);

  // Initial candidate fetch on modal open
  useEffect(() => {
    if (isOpen && card) {
      setSearchQuery('');
      setSearchResults([]);
      setSwappingCardName(null);
      fetchCandidates();
    }
  }, [isOpen, card, fetchCandidates]);

  // Handle Escape key to close modal
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Debounced search for custom card replacements
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setSearching(false);
      return;
    }

    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current);
    }

    setSearching(true);
    searchDebounceRef.current = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          q: searchQuery.trim(),
          commanders_only: 'false',
          limit: '8'
        });
        if (commander) params.append('commander', commander);

        const res = await fetch(`${getApiBaseUrl()}/api/search?${params.toString()}`);
        if (res.ok) {
          const results = await res.json();
          // Filter out card being replaced and cards in exclude list
          const excludeSet = new Set((exclude || []).map((e) => e.toLowerCase()));
          if (card?.name) excludeSet.add(card.name.toLowerCase());

          const filtered = results.filter((r) => !excludeSet.has(r.name.toLowerCase()));
          setSearchResults(filtered);
        }
      } catch (e) {
        console.error('Search error in swap modal:', e);
      } finally {
        setSearching(false);
      }
    }, 250);

    return () => {
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current);
      }
    };
  }, [searchQuery, commander, exclude, card]);

  if (!isOpen || !card) return null;

  const currentMeta = CATEGORY_META[role] || CATEGORY_META.synergy;

  const handleConfirmSwap = (replacementCard) => {
    if (!replacementCard) return;
    setSwappingCardName(replacementCard.name);
    setTimeout(() => {
      onSwap(card, replacementCard, role);
      onClose();
    }, 200);
  };

  const handleQuickReroll = () => {
    if (candidates.length > 0) {
      handleConfirmSwap(candidates[0]);
    } else {
      fetchCandidates();
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1050,
        backgroundColor: 'rgba(5, 2, 12, 0.82)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px'
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '820px',
          maxHeight: '92vh',
          backgroundColor: 'var(--bg-panel, #1c0f35)',
          border: '1px solid var(--border-purple, #3b2668)',
          borderRadius: '16px',
          boxShadow: '0 24px 60px rgba(0, 0, 0, 0.85), 0 0 40px rgba(168, 85, 247, 0.15)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid var(--border-purple, #3b2668)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            background: 'linear-gradient(135deg, rgba(37, 22, 66, 0.7), rgba(20, 10, 38, 0.9))'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: currentMeta.bg,
                border: `1px solid ${currentMeta.color}66`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: currentMeta.color
              }}
            >
              <ArrowRightLeft size={18} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0, fontSize: '1.25rem', color: 'var(--text-white, #ffffff)', fontWeight: '700' }}>
                  Swap Card: {card.name}
                </h3>
                <span
                  style={{
                    background: currentMeta.bg,
                    border: `1px solid ${currentMeta.color}88`,
                    color: currentMeta.color,
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontSize: '0.75rem',
                    fontWeight: 'bold'
                  }}
                >
                  [{currentMeta.label}]
                </span>
                <span
                  style={{
                    background: 'rgba(56, 189, 248, 0.12)',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    color: '#38bdf8',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontSize: '0.72rem'
                  }}
                >
                  {card.mana_cost || `${card.cmc || 0} CMC`}
                </span>
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted, #94a3b8)', marginTop: '2px' }}>
                Replaces this card without altering total 100-card count or deck structure.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* 1-Click Quick Re-roll button */}
            <button
              onClick={handleQuickReroll}
              disabled={loading || candidates.length === 0}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 12px',
                borderRadius: '8px',
                fontSize: '0.8rem',
                fontWeight: '600',
                cursor: loading || candidates.length === 0 ? 'not-allowed' : 'pointer',
                background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.25), rgba(56, 189, 248, 0.2))',
                border: '1px solid #c084fc',
                color: '#ffffff',
                opacity: loading || candidates.length === 0 ? 0.6 : 1,
                transition: 'all 0.15s ease'
              }}
              title="Instantly swap in the #1 recommended card"
            >
              <Dices size={15} style={{ color: '#c084fc' }} />
              <span>Quick Re-roll</span>
            </button>

            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-accent, #bb8fdf)',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'background 0.15s'
              }}
              title="Close (Esc)"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* Custom Search Box */}
          <div style={{ position: 'relative' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: 'var(--bg-input, #100522)',
                border: '1px solid var(--border-purple, #3b2668)',
                borderRadius: '8px',
                padding: '8px 12px'
              }}
            >
              <Search size={16} style={{ color: 'var(--text-muted, #94a3b8)' }} />
              <input
                type="text"
                placeholder="Or search any card to swap into this slot (e.g. Hero's Downfall, Cultivate)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: 'var(--text-white, #ffffff)',
                  fontSize: '0.85rem',
                  width: '100%'
                }}
              />
              {searching && <RefreshCw size={14} className="loader-spinner" style={{ color: 'var(--text-accent)' }} />}
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: 0
                  }}
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Custom Search Results Dropdown/Flyout */}
            {searchResults.length > 0 && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  marginTop: '4px',
                  background: 'var(--bg-panel, #1c0f35)',
                  border: '1px solid var(--border-purple, #3b2668)',
                  borderRadius: '8px',
                  boxShadow: '0 12px 30px rgba(0, 0, 0, 0.8)',
                  zIndex: 20,
                  maxHeight: '260px',
                  overflowY: 'auto'
                }}
              >
                <div style={{ padding: '6px 12px', fontSize: '0.72rem', color: 'var(--text-muted)', borderBottom: '1px solid rgba(59, 38, 104, 0.4)' }}>
                  Search Results ({searchResults.length})
                </div>
                {searchResults.map((res) => (
                  <div
                    key={res.name}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 12px',
                      borderBottom: '1px solid rgba(59, 38, 104, 0.25)',
                      gap: '8px'
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 'bold', fontSize: '0.84rem', color: 'var(--text-white)' }}>
                          {res.name}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {res.mana_cost}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {res.type_line}
                      </div>
                    </div>
                    <button
                      onClick={() => handleConfirmSwap(res)}
                      disabled={swappingCardName === res.name}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '5px 12px',
                        borderRadius: '6px',
                        fontSize: '0.76rem',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        background: 'linear-gradient(135deg, #10b981, #059669)',
                        border: '1px solid #34d399',
                        color: '#ffffff'
                      }}
                    >
                      {swappingCardName === res.name ? <Check size={13} /> : <ArrowRightLeft size={13} />}
                      <span>Swap In</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Error Banner */}
          {error && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid #ef4444',
                borderRadius: '8px',
                padding: '10px 14px',
                color: '#f87171',
                fontSize: '0.82rem',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Smart Candidates Section */}
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '12px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Sparkles size={16} style={{ color: currentMeta.color }} />
                <h4 style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-white)' }}>
                  Smart Candidates for {currentMeta.label}
                </h4>
              </div>
              <button
                onClick={fetchCandidates}
                disabled={loading}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-accent, #bb8fdf)',
                  fontSize: '0.75rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  cursor: 'pointer'
                }}
              >
                <RefreshCw size={12} className={loading ? 'loader-spinner' : ''} />
                <span>Refresh Suggestions</span>
              </button>
            </div>

            {loading ? (
              <div style={{ textAlign: 'center', padding: '40px 12px', color: 'var(--text-muted)' }}>
                <RefreshCw size={28} className="loader-spinner" style={{ marginBottom: '8px', opacity: 0.7 }} />
                <div style={{ fontSize: '0.85rem' }}>Evaluating candidate synergy & color legality...</div>
              </div>
            ) : candidates.length > 0 ? (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                  gap: '12px'
                }}
              >
                {candidates.map((cand) => {
                  const isSwapping = swappingCardName === cand.name;

                  return (
                    <div
                      key={cand.name}
                      style={{
                        padding: '10px',
                        background: 'var(--bg-primary, #0c0414)',
                        border: isSwapping ? '1px solid #10b981' : '1px solid var(--border-purple, #3b2668)',
                        borderRadius: '8px',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        gap: '8px',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {/* Image Thumbnail */}
                      {cand.image_url ? (
                        <img
                          src={cand.image_url}
                          alt={cand.name}
                          loading="lazy"
                          style={{
                            width: '100%',
                            borderRadius: '4px',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.5)'
                          }}
                        />
                      ) : (
                        <div
                          style={{
                            width: '100%',
                            height: '110px',
                            background: '#1e293b',
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '0.72rem',
                            color: 'var(--text-muted)'
                          }}
                        >
                          No Image
                        </div>
                      )}

                      {/* Card Details */}
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '4px' }}>
                          <span style={{ fontWeight: 'bold', fontSize: '0.82rem', lineHeight: '1.2', color: 'var(--text-white)' }}>
                            {cand.name}
                          </span>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                            {cand.mana_cost}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                          {cand.type_line}
                        </div>

                        {/* Reason Badge */}
                        {cand.reason && (
                          <div
                            style={{
                              marginTop: '6px',
                              fontSize: '0.68rem',
                              lineHeight: '1.3',
                              color: 'var(--text-accent, #bb8fdf)',
                              background: 'rgba(168, 85, 247, 0.1)',
                              border: '1px solid rgba(168, 85, 247, 0.25)',
                              borderRadius: '4px',
                              padding: '4px 6px'
                            }}
                          >
                            {cand.reason}
                          </div>
                        )}
                      </div>

                      {/* Swap In CTA */}
                      <button
                        onClick={() => handleConfirmSwap(cand)}
                        disabled={isSwapping}
                        style={{
                          width: '100%',
                          padding: '6px',
                          borderRadius: '6px',
                          fontSize: '0.78rem',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '6px',
                          background: isSwapping 
                            ? 'linear-gradient(135deg, #15803d, #22c55e)' 
                            : 'linear-gradient(135deg, #9333ea, #7b2cbf)',
                          border: isSwapping ? '1px solid #22c55e' : '1px solid #c084fc',
                          color: '#ffffff',
                          boxShadow: isSwapping 
                            ? '0 0 12px rgba(34, 197, 94, 0.5)' 
                            : '0 0 10px rgba(147, 51, 234, 0.25)',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {isSwapping ? <Check size={14} /> : <ArrowRightLeft size={14} />}
                        <span>{isSwapping ? 'Swapping...' : 'Swap In'}</span>
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '30px 12px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                No candidate replacements found. Try searching for a specific card above.
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: '14px 24px',
            borderTop: '1px solid var(--border-purple, #3b2668)',
            backgroundColor: 'var(--bg-input, #100522)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            fontSize: '0.78rem',
            color: 'var(--text-muted)'
          }}
        >
          <div>
            Swapping ensures zero non-basic duplicates and preserves tournament color legality.
          </div>
          <button
            onClick={onClose}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: '1px solid var(--border-purple, #3b2668)',
              background: 'transparent',
              color: 'var(--text-white)',
              cursor: 'pointer',
              fontSize: '0.8rem'
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
