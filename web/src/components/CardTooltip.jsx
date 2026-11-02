import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { RotateCw, AlertTriangle } from 'lucide-react';
import {
  cleanCardName,
  getCardFromCache,
  setCardInCache,
  fetchCardFromScryfall,
  preloadImage
} from '../utils/cardImageCache';

const TOOLTIP_WIDTH = 250;
const ESTIMATED_TOOLTIP_HEIGHT = 380;
const VIEWPORT_PADDING = 12;

/**
 * Reusable CardTooltip component for Loreweaver.
 *
 * Provides a responsive floating Scryfall card image tooltip with:
 * - Dynamic viewport collision detection & clamping
 * - In-memory image caching for instantaneous loads
 * - On-demand Scryfall API resolution for card names without images
 * - Double-faced card (DFC) indicator and smooth flipping
 * - Graceful fallback card frame if image fails
 * - Flicker-free hover management
 */
export function CardTooltip({
  children,
  card = null,
  name = '',
  disabled = false,
  className = '',
  style = {}
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [cardMeta, setCardMeta] = useState(null);
  const [activeFaceIndex, setActiveFaceIndex] = useState(0);
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [isFetching, setIsFetching] = useState(false);

  const triggerRef = useRef(null);
  const tooltipRef = useRef(null);
  const leaveTimerRef = useRef(null);
  const mountedRef = useRef(true);

  // Normalize card name and identity
  const resolvedName = (typeof card === 'string' ? card : (name || card?.name || '')).trim();
  const cleanName = cleanCardName(resolvedName);

  // Initialize or update metadata from props/cache
  const resolveMetadata = useCallback(async () => {
    if (!cleanName || disabled) return;

    // 1. If card object has an image_url already, prime the cache
    if (card && typeof card === 'object' && card.image_url) {
      const isDfcCandidate = Boolean(
        card.back_image_url ||
        card.name?.includes(' // ') ||
        card.layout === 'transform' ||
        card.layout === 'modal_dfc'
      );

      const localMeta = {
        name: card.name || cleanName,
        mana_cost: card.mana_cost || '',
        type_line: card.type_line || '',
        oracle_text: card.oracle_text || '',
        image_url: card.image_url,
        back_image_url: card.back_image_url || '',
        is_dfc: isDfcCandidate,
        faces: card.faces || null
      };

      setCardInCache(cleanName, localMeta);
      if (mountedRef.current) {
        setCardMeta(localMeta);
      }

      // If DFC lacks back_image_url, fetch full faces asynchronously in background
      if (isDfcCandidate && !card.back_image_url && cleanName.includes(' // ')) {
        fetchCardFromScryfall(cleanName).then((remoteData) => {
          if (remoteData && mountedRef.current) {
            setCardMeta(remoteData);
          }
        });
      }
      return;
    }

    // 2. Check in-memory cache
    const cached = getCardFromCache(cleanName);
    if (cached) {
      if (mountedRef.current) {
        setCardMeta(cached);
      }
      return;
    }

    // 3. Resolve via Scryfall API
    if (mountedRef.current) {
      setIsFetching(true);
    }

    try {
      const remoteData = await fetchCardFromScryfall(cleanName);
      if (mountedRef.current && remoteData) {
        setCardMeta(remoteData);
      }
    } catch {
      // Fallback handled gracefully by UI
    } finally {
      if (mountedRef.current) {
        setIsFetching(false);
      }
    }
  }, [card, cleanName, disabled]);

  // Recalculate collision-free tooltip coordinates
  const calculatePosition = useCallback(() => {
    if (!triggerRef.current || typeof window === 'undefined') return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let left = triggerRect.right + VIEWPORT_PADDING;

    // Viewport collision: check if overflows right edge
    if (left + TOOLTIP_WIDTH > vw - VIEWPORT_PADDING) {
      // Try positioning to the left of the trigger
      const leftCandidate = triggerRect.left - TOOLTIP_WIDTH - VIEWPORT_PADDING;
      if (leftCandidate >= VIEWPORT_PADDING) {
        left = leftCandidate;
      } else {
        // Clamp horizontally inside viewport
        left = Math.max(
          VIEWPORT_PADDING,
          Math.min(vw - TOOLTIP_WIDTH - VIEWPORT_PADDING, (vw - TOOLTIP_WIDTH) / 2)
        );
      }
    }

    // Vertically center tooltip with trigger element
    let top = triggerRect.top + triggerRect.height / 2 - ESTIMATED_TOOLTIP_HEIGHT / 2;

    // Viewport collision: clamp vertically
    const maxTop = vh - ESTIMATED_TOOLTIP_HEIGHT - VIEWPORT_PADDING;
    top = Math.max(VIEWPORT_PADDING, Math.min(top, maxTop));

    setPosition({ top, left });
  }, []);

  const handleMouseEnter = () => {
    if (disabled || !cleanName) return;
    if (leaveTimerRef.current) {
      clearTimeout(leaveTimerRef.current);
      leaveTimerRef.current = null;
    }

    calculatePosition();
    setIsOpen(true);
    setImageError(false);
    resolveMetadata();
  };

  const handleMouseLeave = () => {
    if (leaveTimerRef.current) {
      clearTimeout(leaveTimerRef.current);
    }
    // 140ms grace period allows seamless movement onto the tooltip
    leaveTimerRef.current = setTimeout(() => {
      if (mountedRef.current) {
        setIsOpen(false);
        setActiveFaceIndex(0);
      }
    }, 140);
  };

  const handleTooltipMouseEnter = () => {
    if (leaveTimerRef.current) {
      clearTimeout(leaveTimerRef.current);
      leaveTimerRef.current = null;
    }
  };

  const handleTooltipMouseLeave = () => {
    if (leaveTimerRef.current) {
      clearTimeout(leaveTimerRef.current);
    }
    leaveTimerRef.current = setTimeout(() => {
      if (mountedRef.current) {
        setIsOpen(false);
        setActiveFaceIndex(0);
      }
    }, 140);
  };

  const handleFlipCard = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setActiveFaceIndex((prev) => (prev === 0 ? 1 : 0));
    setImageLoaded(false);
    setImageError(false);
  };

  // Keyboard shortcut: Press 'F' while hovering to flip DFC
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if ((e.key === 'f' || e.key === 'F') && cardMeta?.is_dfc) {
        e.preventDefault();
        setActiveFaceIndex((prev) => (prev === 0 ? 1 : 0));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, cardMeta]);

  // Adjust position on scroll/resize while open
  useEffect(() => {
    if (!isOpen) return;

    const handleWindowChange = () => {
      calculatePosition();
    };

    window.addEventListener('scroll', handleWindowChange, { passive: true });
    window.addEventListener('resize', handleWindowChange);

    return () => {
      window.removeEventListener('scroll', handleWindowChange);
      window.removeEventListener('resize', handleWindowChange);
    };
  }, [isOpen, calculatePosition]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (leaveTimerRef.current) {
        clearTimeout(leaveTimerRef.current);
      }
    };
  }, []);

  // Preload image as soon as card metadata is determined
  useEffect(() => {
    if (cardMeta?.image_url) {
      preloadImage(cardMeta.image_url);
    }
    if (cardMeta?.back_image_url) {
      preloadImage(cardMeta.back_image_url);
    }
  }, [cardMeta]);

  // Determine active face details for display
  const currentFace =
    cardMeta?.faces && cardMeta.faces[activeFaceIndex]
      ? cardMeta.faces[activeFaceIndex]
      : null;

  const currentImageUrl =
    activeFaceIndex === 1
      ? cardMeta?.back_image_url || currentFace?.image_url || cardMeta?.image_url
      : currentFace?.image_url || cardMeta?.image_url;

  const currentDisplayName = currentFace?.name || cardMeta?.name || cleanName;
  const currentManaCost = currentFace?.mana_cost || cardMeta?.mana_cost || (card?.mana_cost || '');
  const currentTypeLine = currentFace?.type_line || cardMeta?.type_line || (card?.type_line || '');
  const currentOracleText = currentFace?.oracle_text || cardMeta?.oracle_text || (card?.oracle_text || '');

  return (
    <span
      ref={triggerRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`loreweaver-tooltip-trigger ${className}`}
      style={{
        display: 'inline-block',
        position: 'relative',
        ...style
      }}
    >
      {children}

      {isOpen &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            ref={tooltipRef}
            onMouseEnter={handleTooltipMouseEnter}
            onMouseLeave={handleTooltipMouseLeave}
            className="loreweaver-card-tooltip-portal"
            style={{
              position: 'fixed',
              top: `${position.top}px`,
              left: `${position.left}px`,
              width: `${TOOLTIP_WIDTH}px`,
              zIndex: 99999,
              pointerEvents: 'auto',
              borderRadius: '12px',
              backgroundColor: 'var(--bg-primary, #130924)',
              border: '1px solid var(--border-purple, #3b2668)',
              boxShadow:
                '0 10px 25px -5px rgba(0, 0, 0, 0.8), 0 8px 10px -6px rgba(0, 0, 0, 0.8), 0 0 15px rgba(106, 76, 147, 0.3)',
              overflow: 'hidden',
              animation: 'loreweaverFadeIn 0.16s ease-out',
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            {/* Top Toolbar for Double-Faced Cards */}
            {cardMeta?.is_dfc && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  backgroundColor: 'rgba(28, 15, 53, 0.95)',
                  borderBottom: '1px solid var(--border-purple, #3b2668)',
                  fontSize: '0.74rem'
                }}
              >
                <span style={{ color: 'var(--text-accent, #bb8fdf)', fontWeight: '600' }}>
                  Face {activeFaceIndex + 1}/2: {activeFaceIndex === 0 ? 'Front' : 'Back'}
                </span>
                <button
                  type="button"
                  onClick={handleFlipCard}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '0.72rem',
                    fontWeight: 'bold',
                    background: 'var(--accent-purple, #6a4c93)',
                    color: '#ffffff',
                    border: 'none',
                    cursor: 'pointer',
                    transition: 'background 0.15s ease'
                  }}
                  title="Click or press 'F' to flip face"
                >
                  <RotateCw size={11} />
                  <span>Flip</span>
                </button>
              </div>
            )}

            {/* Main Visual Presentation */}
            {currentImageUrl && !imageError ? (
              <div
                style={{
                  position: 'relative',
                  width: '100%',
                  aspectRatio: '2.5 / 3.5',
                  backgroundColor: 'var(--bg-card, #251642)',
                  overflow: 'hidden',
                  cursor: cardMeta?.is_dfc ? 'pointer' : 'default'
                }}
                onClick={cardMeta?.is_dfc ? handleFlipCard : undefined}
                title={cardMeta?.is_dfc ? 'Click to flip face' : undefined}
              >
                {/* Image Placeholder / Shimmer while loading */}
                {!imageLoaded && (
                  <div
                    style={{
                      position: 'absolute',
                      inset: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'linear-gradient(135deg, #1f1435, #100522)',
                      padding: '16px',
                      textAlign: 'center'
                    }}
                  >
                    <div
                      style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: '50%',
                        border: '3px solid var(--border-purple, #3b2668)',
                        borderTopColor: 'var(--accent-purple, #6a4c93)',
                        animation: 'spin 0.8s linear infinite',
                        marginBottom: '8px'
                      }}
                    />
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-accent, #bb8fdf)' }}>
                      Loading visual...
                    </span>
                  </div>
                )}

                <img
                  src={currentImageUrl}
                  alt={currentDisplayName}
                  onLoad={() => setImageLoaded(true)}
                  onError={() => setImageError(true)}
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    display: 'block',
                    opacity: imageLoaded ? 1 : 0,
                    transition: 'opacity 0.15s ease-out'
                  }}
                />
              </div>
            ) : (
              /* Sleek MTG Card Frame Fallback */
              <div
                style={{
                  padding: '14px',
                  background: 'linear-gradient(160deg, #251642 0%, #130924 100%)',
                  borderRadius: '12px',
                  color: 'var(--text-main, #e9dfff)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  minHeight: '320px'
                }}
              >
                {/* Header */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    gap: '6px',
                    borderBottom: '1px solid var(--border-purple, #3b2668)',
                    paddingBottom: '8px'
                  }}
                >
                  <strong
                    style={{
                      fontSize: '0.92rem',
                      lineHeight: '1.25',
                      color: 'var(--text-white, #ffffff)'
                    }}
                  >
                    {currentDisplayName}
                  </strong>
                  {currentManaCost && (
                    <span
                      style={{
                        fontSize: '0.74rem',
                        fontWeight: 'bold',
                        color: 'var(--text-accent, #bb8fdf)',
                        whiteSpace: 'nowrap',
                        background: 'rgba(0, 0, 0, 0.4)',
                        padding: '2px 6px',
                        borderRadius: '4px'
                      }}
                    >
                      {currentManaCost}
                    </span>
                  )}
                </div>

                {/* Type Line */}
                <div
                  style={{
                    fontSize: '0.74rem',
                    color: 'var(--text-accent, #bb8fdf)',
                    fontWeight: '500'
                  }}
                >
                  {currentTypeLine || 'Card Details'}
                </div>

                {/* Oracle Text Box */}
                <div
                  style={{
                    flex: 1,
                    backgroundColor: 'rgba(16, 5, 34, 0.7)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: '6px',
                    padding: '10px',
                    fontSize: '0.78rem',
                    lineHeight: '1.4',
                    whiteSpace: 'pre-line',
                    overflowY: 'auto',
                    maxHeight: '190px'
                  }}
                >
                  {isFetching ? (
                    <span style={{ color: 'var(--text-muted, #94a3b8)', fontStyle: 'italic' }}>
                      Resolving card text from Scryfall...
                    </span>
                  ) : currentOracleText ? (
                    currentOracleText
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f59e0b' }}>
                      <AlertTriangle size={14} />
                      <span>Visual unavailable; oracle record loaded.</span>
                    </div>
                  )}
                </div>

                {/* Card Frame Footer */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: '0.68rem',
                    color: 'var(--text-muted, #94a3b8)',
                    paddingTop: '4px'
                  }}
                >
                  <span>Loreweaver Archive</span>
                  {cardMeta?.is_dfc && (
                    <button
                      type="button"
                      onClick={handleFlipCard}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-accent, #bb8fdf)',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                        fontSize: '0.68rem'
                      }}
                    >
                      Flip to Face {activeFaceIndex === 0 ? '2' : '1'}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>,
          document.body
        )}
    </span>
  );
}

// Export CardHover alias for backward and ergonomic compatibility
export { CardTooltip as CardHover };
export default CardTooltip;
