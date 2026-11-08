import React, { useState } from 'react';
import { 
  Sparkles, 
  ShoppingCart, 
  ExternalLink, 
  Layers, 
  Coffee, 
  Check, 
  Star, 
  Video, 
  Share2, 
  Flame, 
  ChevronRight,
  ArrowRight,
  Play
} from 'lucide-react';
import { getManaPoolMassEntryUrl } from '../utils/deckExport';
import { safeCopyToClipboard } from '../utils/clipboard';
import { VIDEO_DECKS } from '../data/videoDecksData';

export default function CreatorLinkHub({ onOpenDeck, onGoToBuilder }) {
  const [copiedId, setCopiedId] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);
  const [selectedFilter, setSelectedFilter] = useState('all');

  const featuredDeck = VIDEO_DECKS[0]; // Belbe $45 Big Mana

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleBuyDeck = async (deckItem, e) => {
    if (e) e.stopPropagation();
    setCopiedId(deckItem.id);

    // Copy exact 100-card text export to clipboard for instant pasting on Mana Pool mass entry
    if (deckItem.manapoolExport) {
      await safeCopyToClipboard(deckItem.manapoolExport);
    }

    const url = getManaPoolMassEntryUrl();
    window.open(url, '_blank', 'noopener,noreferrer');
    showToast(`📋 100-card decklist copied! Opening Mana Pool for ${deckItem.commander}...`);
    setTimeout(() => setCopiedId(null), 2500);
  };

  const handleShareLink = async () => {
    const origin = typeof window !== 'undefined' ? window.location.origin : 'https://lore-weaver.app';
    const ok = await safeCopyToClipboard(`${origin}/links`);
    if (ok) {
      showToast('📋 Link Hub URL copied to clipboard!');
    } else {
      showToast('⚠️ Could not copy link automatically.');
    }
  };

  const filteredDecks = VIDEO_DECKS.filter((d) => {
    if (selectedFilter === 'all') return true;
    if (selectedFilter === 'budget') return d.budgetLabel.includes('$');
    if (selectedFilter === 'bracket3') return d.bracket === 3;
    if (selectedFilter === 'bracket2') return d.bracket === 2;
    return true;
  });

  return (
    <div style={{
      maxWidth: '620px',
      margin: '0 auto',
      padding: '24px 16px 64px 16px',
      color: 'var(--text-white, #ffffff)',
      fontFamily: 'inherit'
    }}>
      {/* Toast Notification */}
      {toastMessage && (
        <div style={{
          position: 'fixed',
          top: '20px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 9999,
          background: 'linear-gradient(135deg, #10b981, #059669)',
          color: '#ffffff',
          padding: '10px 20px',
          borderRadius: '30px',
          fontSize: '0.85rem',
          fontWeight: 'bold',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5), 0 0 12px rgba(16, 185, 129, 0.4)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Check size={16} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Creator Profile Header */}
      <div style={{
        textAlign: 'center',
        marginBottom: '28px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center'
      }}>
        {/* Profile Avatar with Purple Glowing Ring */}
        <div style={{
          position: 'relative',
          marginBottom: '14px'
        }}>
          <img
            src="/logo.png"
            alt="Loreweaver & Strategic Synergy"
            style={{
              width: '92px',
              height: '92px',
              borderRadius: '50%',
              objectFit: 'cover',
              border: '3px solid #c084fc',
              boxShadow: '0 0 25px rgba(192, 132, 252, 0.5), 0 0 50px rgba(56, 189, 248, 0.25)',
              backgroundColor: '#1c0f35'
            }}
          />
          <span style={{
            position: 'absolute',
            bottom: '2px',
            right: '2px',
            background: 'linear-gradient(135deg, #38bdf8, #0284c7)',
            borderRadius: '50%',
            width: '24px',
            height: '24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '2px solid #0f0721',
            boxShadow: '0 0 8px rgba(56, 189, 248, 0.6)'
          }} title="Verified Creator">
            <Check size={13} color="#ffffff" strokeWidth={3} />
          </span>
        </div>

        <h1 style={{
          fontSize: '1.5rem',
          fontWeight: '800',
          margin: '0 0 6px 0',
          background: 'linear-gradient(135deg, #ffffff 40%, #c084fc 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}>
          Strategic Synergy • Loreweaver MTG
        </h1>

        <p style={{
          fontSize: '0.88rem',
          color: 'var(--text-accent, #bb8fdf)',
          margin: '0 0 14px 0',
          maxWidth: '440px',
          lineHeight: '1.45'
        }}>
          🧙‍♂️ High-Synergy Commander Deck Techs, Budget Brews & Algorithmic Theory
        </p>

        {/* Social Chips Row */}
        <div style={{
          display: 'flex',
          gap: '8px',
          flexWrap: 'wrap',
          justifyContent: 'center',
          fontSize: '0.78rem'
        }}>
          <a
            href="https://www.tiktok.com/@strategicsynergy0"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              padding: '5px 12px',
              borderRadius: '20px',
              background: 'rgba(28, 15, 53, 0.8)',
              border: '1px solid rgba(192, 132, 252, 0.4)',
              color: '#ffffff',
              textDecoration: 'none',
              fontWeight: '600'
            }}
          >
            <Play size={12} fill="#ef4444" color="#ef4444" />
            <span>@strategicsynergy0</span>
          </a>

          <a
            href="https://www.youtube.com/@LoreweaverMTG"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              padding: '5px 12px',
              borderRadius: '20px',
              background: 'rgba(28, 15, 53, 0.8)',
              border: '1px solid rgba(192, 132, 252, 0.4)',
              color: '#ffffff',
              textDecoration: 'none',
              fontWeight: '600'
            }}
          >
            <Video size={13} color="#ef4444" />
            <span>@LoreweaverMTG</span>
          </a>

          <button
            onClick={handleShareLink}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              padding: '5px 12px',
              borderRadius: '20px',
              background: 'rgba(56, 189, 248, 0.15)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              color: '#38bdf8',
              cursor: 'pointer',
              fontWeight: '600'
            }}
          >
            <Share2 size={12} />
            <span>Share Hub</span>
          </button>
        </div>
      </div>

      {/* Featured Video Deck Spotlight Box */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(37, 22, 66, 0.85), rgba(28, 15, 53, 0.95))',
        border: '1px solid #c084fc',
        borderRadius: '16px',
        padding: '18px 20px',
        marginBottom: '26px',
        boxShadow: '0 12px 35px rgba(0, 0, 0, 0.45), 0 0 20px rgba(192, 132, 252, 0.25)',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* Top Highlight Banner */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '12px',
          gap: '8px',
          flexWrap: 'wrap'
        }}>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            fontSize: '0.74rem',
            fontWeight: 'bold',
            padding: '3px 10px',
            borderRadius: '20px',
            background: 'linear-gradient(135deg, #f59e0b, #ef4444)',
            color: '#ffffff',
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}>
            <Flame size={12} />
            <span>Today's Video Deck</span>
          </span>

          <span style={{
            fontSize: '0.78rem',
            color: '#38bdf8',
            fontWeight: '600',
            background: 'rgba(56, 189, 248, 0.15)',
            padding: '3px 9px',
            borderRadius: '12px',
            border: '1px solid rgba(56, 189, 248, 0.3)'
          }}>
            {featuredDeck.budgetLabel}
          </span>
        </div>

        <h3 style={{
          margin: '0 0 4px 0',
          fontSize: '1.25rem',
          fontWeight: 'bold',
          color: '#ffffff'
        }}>
          {featuredDeck.commander}
        </h3>

        <div style={{
          fontSize: '0.9rem',
          color: '#c084fc',
          fontWeight: '600',
          marginBottom: '8px'
        }}>
          {featuredDeck.title}
        </div>

        <p style={{
          fontSize: '0.82rem',
          color: 'var(--text-accent, #bb8fdf)',
          lineHeight: '1.45',
          margin: '0 0 16px 0'
        }}>
          {featuredDeck.desc}
        </p>

        {/* Action Buttons for Featured Deck */}
        <div style={{ display: 'flex', gap: '10px', flexDirection: 'column' }}>
          {/* Primary Buy on Mana Pool */}
          <button
            onClick={(e) => handleBuyDeck(featuredDeck, e)}
            className="btn"
            style={{
              width: '100%',
              padding: '11px 16px',
              fontSize: '0.9rem',
              fontWeight: 'bold',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              cursor: 'pointer',
              borderRadius: '10px',
              border: '1px solid #38bdf8',
              background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.28), rgba(14, 165, 233, 0.38))',
              color: '#38bdf8',
              boxShadow: '0 0 16px rgba(56, 189, 248, 0.35)',
              transition: 'all 0.18s ease'
            }}
          >
            {copiedId === featuredDeck.id ? (
              <>
                <Check size={16} style={{ color: '#4ade80' }} />
                <span style={{ color: '#4ade80' }}>Opening Mana Pool Cart Optimizer...</span>
              </>
            ) : (
              <>
                <ShoppingCart size={16} />
                <span>⚡ Buy on Mana Pool ({featuredDeck.budgetLabel})</span>
              </>
            )}
          </button>

          {/* Secondary View on Loreweaver */}
          {onOpenDeck && (
            <button
              onClick={() => onOpenDeck(featuredDeck.params)}
              className="btn btn-secondary"
              style={{
                width: '100%',
                padding: '9px 14px',
                fontSize: '0.84rem',
                fontWeight: '600',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                cursor: 'pointer',
                borderRadius: '10px',
                border: '1px solid rgba(192, 132, 252, 0.4)',
                background: 'rgba(28, 15, 53, 0.8)',
                color: '#ffffff'
              }}
            >
              <Layers size={15} color="#c084fc" />
              <span>View & Goldfish 100 Cards on Loreweaver</span>
              <ArrowRight size={14} color="#bb8fdf" />
            </button>
          )}
        </div>
      </div>

      {/* Primary Free Tool CTA Banner */}
      <div 
        onClick={onGoToBuilder}
        style={{
          background: 'linear-gradient(135deg, rgba(147, 51, 234, 0.2), rgba(56, 189, 248, 0.15))',
          border: '1px solid rgba(192, 132, 252, 0.5)',
          borderRadius: '14px',
          padding: '16px 18px',
          marginBottom: '26px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          transition: 'transform 0.15s ease, border-color 0.15s ease'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #9333ea, #38bdf8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 14px rgba(168, 85, 247, 0.4)'
          }}>
            <Sparkles size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ fontSize: '0.98rem', fontWeight: 'bold', color: '#ffffff' }}>
              Free 100-Card Deck Architect
            </div>
            <div style={{ fontSize: '0.78rem', color: '#bb8fdf', marginTop: '2px' }}>
              Synthesize any commander with Karsten mana math in 15 seconds
            </div>
          </div>
        </div>
        <ChevronRight size={20} color="#c084fc" />
      </div>

      {/* Video Decks Backlog Section */}
      <div style={{ marginBottom: '28px' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '14px',
          flexWrap: 'wrap',
          gap: '8px'
        }}>
          <h2 style={{
            margin: 0,
            fontSize: '1.15rem',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span>📚 Video Deck Backlog</span>
            <span style={{
              fontSize: '0.72rem',
              padding: '2px 8px',
              borderRadius: '12px',
              background: 'rgba(192, 132, 252, 0.18)',
              color: '#c084fc'
            }}>
              {filteredDecks.length} Decks
            </span>
          </h2>

          {/* Filter Pills */}
          <div style={{ display: 'flex', gap: '6px' }}>
            <button
              onClick={() => setSelectedFilter('all')}
              style={{
                background: selectedFilter === 'all' ? '#9333ea' : 'rgba(28, 15, 53, 0.6)',
                border: '1px solid rgba(192, 132, 252, 0.3)',
                color: '#ffffff',
                padding: '4px 10px',
                borderRadius: '12px',
                fontSize: '0.72rem',
                cursor: 'pointer',
                fontWeight: selectedFilter === 'all' ? 'bold' : 'normal'
              }}
            >
              All
            </button>
            <button
              onClick={() => setSelectedFilter('budget')}
              style={{
                background: selectedFilter === 'budget' ? '#9333ea' : 'rgba(28, 15, 53, 0.6)',
                border: '1px solid rgba(192, 132, 252, 0.3)',
                color: '#ffffff',
                padding: '4px 10px',
                borderRadius: '12px',
                fontSize: '0.72rem',
                cursor: 'pointer',
                fontWeight: selectedFilter === 'budget' ? 'bold' : 'normal'
              }}
            >
              Under $50
            </button>
          </div>
        </div>

        {/* Deck Cards List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {filteredDecks.map((deck) => (
            <div
              key={deck.id}
              style={{
                background: 'rgba(28, 15, 53, 0.75)',
                border: '1px solid rgba(59, 38, 104, 0.6)',
                borderRadius: '12px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                transition: 'border-color 0.15s ease, background 0.15s ease'
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                  <span style={{ fontWeight: 'bold', fontSize: '0.92rem', color: '#ffffff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {deck.commander}
                  </span>
                  <span style={{
                    fontSize: '0.68rem',
                    padding: '2px 6px',
                    borderRadius: '8px',
                    background: 'rgba(56, 189, 248, 0.15)',
                    color: '#38bdf8',
                    fontWeight: '600',
                    flexShrink: 0
                  }}>
                    {deck.budgetLabel}
                  </span>
                </div>
                <div style={{ fontSize: '0.78rem', color: '#bb8fdf' }}>
                  {deck.title} • {deck.bracketLabel}
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                {onOpenDeck && (
                  <button
                    onClick={() => onOpenDeck(deck.params)}
                    style={{
                      background: 'rgba(147, 51, 234, 0.2)',
                      border: '1px solid rgba(192, 132, 252, 0.4)',
                      color: '#ffffff',
                      padding: '6px 10px',
                      borderRadius: '8px',
                      fontSize: '0.74rem',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                    title="View deck in Loreweaver Architect"
                  >
                    View
                  </button>
                )}

                <button
                  onClick={(e) => handleBuyDeck(deck, e)}
                  style={{
                    background: copiedId === deck.id 
                      ? 'rgba(34, 197, 94, 0.25)' 
                      : 'linear-gradient(135deg, rgba(56, 189, 248, 0.25), rgba(14, 165, 233, 0.35))',
                    border: copiedId === deck.id ? '1px solid #22c55e' : '1px solid #38bdf8',
                    color: copiedId === deck.id ? '#4ade80' : '#38bdf8',
                    padding: '6px 12px',
                    borderRadius: '8px',
                    fontSize: '0.74rem',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                  title="Buy 100 cards on Mana Pool (5% affiliate support)"
                >
                  <ShoppingCart size={13} />
                  <span>Buy</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Universal Commerce & Supporter Links */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        marginBottom: '32px'
      }}>
        {/* Mana Pool Storefront Link */}
        <a
          href="https://manapool.com/?ref=loreweaver"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '13px 18px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.15), rgba(14, 165, 233, 0.22))',
            border: '1px solid #38bdf8',
            color: '#38bdf8',
            textDecoration: 'none',
            fontWeight: 'bold',
            fontSize: '0.92rem',
            boxShadow: '0 0 14px rgba(56, 189, 248, 0.2)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
            <ShoppingCart size={18} style={{ flexShrink: 0 }} />
            <span style={{ wordBreak: 'break-word' }}>⚡ Shop Singles & Sealed on Mana Pool (5% Supports Us)</span>
          </div>
          <ExternalLink size={16} style={{ flexShrink: 0, marginLeft: '8px' }} />
        </a>

        {/* Ko-fi Support Link */}
        <a
          href="https://ko-fi.com/loreweaver_mtg"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '13px 18px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.18), rgba(234, 179, 8, 0.25))',
            border: '1px solid #f59e0b',
            color: '#fef08a',
            textDecoration: 'none',
            fontWeight: 'bold',
            fontSize: '0.92rem'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Coffee size={18} color="#f59e0b" />
            <span>☕ Buy Me a Coffee / Support on Ko-fi</span>
          </div>
          <ExternalLink size={16} />
        </a>

        {/* GitHub Star */}
        <a
          href="https://github.com/jowens-dev/Loreweaver"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '13px 18px',
            borderRadius: '12px',
            background: 'rgba(28, 15, 53, 0.8)',
            border: '1px solid rgba(59, 38, 104, 0.7)',
            color: '#ffffff',
            textDecoration: 'none',
            fontWeight: '600',
            fontSize: '0.88rem'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Star size={18} color="#eab308" />
            <span>⭐ Star Loreweaver on GitHub (Open Source)</span>
          </div>
          <ExternalLink size={16} />
        </a>
      </div>

      {/* Footer Info */}
      <div style={{
        textAlign: 'center',
        fontSize: '0.75rem',
        color: 'var(--text-muted, #7c6899)',
        lineHeight: '1.5'
      }}>
        <div>Portions of Loreweaver are unofficial Fan Content permitted under the Wizards of the Coast Fan Content Policy.</div>
        <div style={{ marginTop: '4px' }}>
          Contact & Inquiries: <a href="mailto:contact@lore-weaver.app" style={{ color: '#38bdf8', textDecoration: 'none' }}>contact@lore-weaver.app</a>
        </div>
      </div>
    </div>
  );
}
