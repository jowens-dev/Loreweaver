import React, { useState, useEffect, useRef } from 'react';
import { Search, Loader2 } from 'lucide-react';

const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
    return 'http://localhost:8000';
  }
  return 'https://api.lore-weaver.app';
};

const COLOR_DOTS = {
  W: '#fef3c7',
  U: '#38bdf8',
  B: '#a1a1aa',
  R: '#f87171',
  G: '#4ade80',
};

export default function CommanderAutocomplete({
  value,
  onChange,
  onSelect,
  placeholder = 'e.g. Belbe, Corrupted Observer (or leave blank)',
  commandersOnly = true,
  className = 'form-input'
}) {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  const containerRef = useRef(null);
  const debounceTimerRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch predictive suggestions as user types
  useEffect(() => {
    const query = (value || '').trim();
    if (query.length < 2) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const url = `${getApiBaseUrl()}/api/search?q=${encodeURIComponent(query)}&commanders_only=${commandersOnly}&limit=8`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          setSuggestions(Array.isArray(data) ? data : []);
          setIsOpen(Array.isArray(data) && data.length > 0);
          setHighlightedIndex(-1);
        }
      } catch (err) {
        console.error('Error fetching predictive search suggestions:', err);
      } finally {
        setLoading(false);
      }
    }, 150);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [value, commandersOnly]);

  const handleSelectCard = (card) => {
    if (onChange) onChange(card.name);
    if (onSelect) onSelect(card);
    setIsOpen(false);
    setSuggestions([]);
  };

  const handleKeyDown = (e) => {
    if (!isOpen || suggestions.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === 'Enter') {
      if (highlightedIndex >= 0 && highlightedIndex < suggestions.length) {
        e.preventDefault();
        handleSelectCard(suggestions[highlightedIndex]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        <input
          type="text"
          className={className}
          style={{ width: '100%', paddingRight: loading ? '36px' : '12px' }}
          placeholder={placeholder}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            if (!isOpen && e.target.value.trim().length >= 2) {
              setIsOpen(true);
            }
          }}
          onFocus={() => {
            if (suggestions.length > 0) setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          autoComplete="off"
          spellCheck="false"
        />

        {loading && (
          <div style={{ 
            position: 'absolute', 
            right: '12px', 
            display: 'flex', 
            alignItems: 'center', 
            pointerEvents: 'none',
            color: 'var(--text-accent)'
          }}>
            <Loader2 size={16} className="loader-spinner" />
          </div>
        )}
      </div>

      {/* Floating Autocomplete Dropdown */}
      {isOpen && suggestions.length > 0 && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          zIndex: 100,
          background: 'rgba(15, 23, 42, 0.98)',
          backdropFilter: 'blur(12px)',
          border: '1px solid var(--border-purple)',
          borderRadius: '8px',
          boxShadow: '0 12px 30px rgba(0, 0, 0, 0.75)',
          maxHeight: '340px',
          overflowY: 'auto',
          padding: '4px 0'
        }}>
          {suggestions.map((card, idx) => {
            const isHighlighted = idx === highlightedIndex;
            return (
              <div
                key={`${card.name}-${idx}`}
                onClick={() => handleSelectCard(card)}
                onMouseEnter={() => setHighlightedIndex(idx)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '8px 12px',
                  cursor: 'pointer',
                  background: isHighlighted ? 'rgba(147, 51, 234, 0.25)' : 'transparent',
                  borderLeft: isHighlighted ? '3px solid var(--text-accent)' : '3px solid transparent',
                  transition: 'background 0.1s ease'
                }}
              >
                {/* Thumbnail Art */}
                {card.image_url ? (
                  <img
                    src={card.image_url}
                    alt={card.name}
                    loading="lazy"
                    style={{
                      width: '32px',
                      height: '44px',
                      objectFit: 'cover',
                      borderRadius: '4px',
                      flexShrink: 0,
                      boxShadow: '0 2px 6px rgba(0,0,0,0.4)'
                    }}
                  />
                ) : (
                  <div style={{
                    width: '32px',
                    height: '44px',
                    borderRadius: '4px',
                    background: '#1e293b',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}>
                    <Search size={14} style={{ color: 'var(--text-muted)' }} />
                  </div>
                )}

                {/* Card Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
                    <span style={{ 
                      fontWeight: 'bold', 
                      fontSize: '0.86rem', 
                      color: isHighlighted ? '#ffffff' : 'var(--text-primary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {card.name}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-accent)', flexShrink: 0 }}>
                      {card.mana_cost}
                    </span>
                  </div>

                  <div style={{ 
                    fontSize: '0.72rem', 
                    color: 'var(--text-muted)', 
                    whiteSpace: 'nowrap', 
                    overflow: 'hidden', 
                    textOverflow: 'ellipsis',
                    marginTop: '2px'
                  }}>
                    {card.type_line}
                  </div>
                </div>

                {/* Color Identity Dots */}
                <div style={{ display: 'flex', gap: '3px', flexShrink: 0 }}>
                  {(card.color_identity || []).map((c) => (
                    <span
                      key={c}
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: COLOR_DOTS[c] || '#a1a1aa',
                        display: 'inline-block'
                      }}
                      title={c}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
