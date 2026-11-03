import React, { useState, useEffect, useMemo } from 'react';
import { 
  Copy, Check, Download, ExternalLink, X, FileText, Table, Terminal, Layers, ShoppingCart
} from 'lucide-react';
import {
  exportToMoxfield,
  exportToTcgplayer,
  exportToManaPool,
  exportToArchidekt,
  exportToMtgo,
  exportToText,
  exportToCsv,
  countExportCards,
  downloadDeckFile,
  getCommanders,
  getTcgplayerMassEntryUrl,
  getManaPoolMassEntryUrl
} from '../utils/deckExport';

const EXPORT_FORMATS = [
  {
    id: 'manapool',
    name: 'Mana Pool',
    ext: '.txt',
    mime: 'text/plain;charset=utf-8',
    icon: ShoppingCart,
    badge: '5% Affiliate',
    desc: 'The independent, player-friendly card marketplace. Paste directly into Mana Pool Mass Entry with Cart Optimizer.'
  },
  {
    id: 'moxfield',
    name: 'Moxfield',
    ext: '.txt',
    mime: 'text/plain;charset=utf-8',
    icon: Layers,
    badge: 'Popular',
    desc: 'Paste directly into Moxfield bulk import. Commanders tagged with *CMDR* for automatic commander assignment.'
  },
  {
    id: 'tcgplayer',
    name: 'TCGplayer',
    ext: '.txt',
    mime: 'text/plain;charset=utf-8',
    icon: ShoppingCart,
    badge: 'Affiliate Commerce',
    desc: 'Clean 100-card Mass Entry list for fast ordering via TCGplayer Mass Entry.'
  },
  {
    id: 'archidekt',
    name: 'Archidekt',
    ext: '.txt',
    mime: 'text/plain;charset=utf-8',
    icon: Terminal,
    badge: 'Categorized',
    desc: 'Pre-categorized with bracket tags like [Ramp], [Removal], and [Lands] so Archidekt auto-sorts your deck.'
  },
  {
    id: 'mtgo',
    name: 'MTGO (.dec)',
    ext: '.dec',
    mime: 'text/plain;charset=utf-8',
    icon: FileText,
    badge: 'Native',
    desc: 'Official Magic Online .dec format separating // Commander and // Mainboard.'
  },
  {
    id: 'text',
    name: 'Plain Text (.txt)',
    ext: '.txt',
    mime: 'text/plain;charset=utf-8',
    icon: FileText,
    badge: 'Clean',
    desc: 'Clean, human-readable list organized by operational role with card counts.'
  },
  {
    id: 'csv',
    name: 'CSV Spreadsheet',
    ext: '.csv',
    mime: 'text/csv;charset=utf-8',
    icon: Table,
    badge: 'Data',
    desc: 'Comma-separated table with Count, Name, Category, CMC, and Type columns for Excel, Google Sheets, or custom scripts.'
  }
];

export default function DeckExportModal({ isOpen, onClose, deck, initialFormat = 'moxfield' }) {
  const [activeFormat, setActiveFormat] = useState(initialFormat);
  const [copied, setCopied] = useState(false);

  // Sync initialFormat when opened
  useEffect(() => {
    if (initialFormat) {
      setActiveFormat(initialFormat);
    }
  }, [initialFormat, isOpen]);

  // Handle escape key to close modal
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

  const commanders = useMemo(() => getCommanders(deck), [deck]);
  const primaryName = commanders[0]?.name || 'commander_deck';
  const safeFilenameBase = primaryName.replace(/[^a-zA-Z0-9_-]/g, '_');

  // Compute text for active format
  const exportText = useMemo(() => {
    if (!deck) return '';
    switch (activeFormat) {
      case 'manapool':
        return deck.exports?.tcgplayer || exportToManaPool(deck);
      case 'moxfield':
        return deck.exports?.moxfield || exportToMoxfield(deck);
      case 'tcgplayer':
        return deck.exports?.tcgplayer || exportToTcgplayer(deck);
      case 'archidekt':
        return deck.exports?.archidekt || exportToArchidekt(deck);
      case 'mtgo':
        return deck.exports?.mtgo || exportToMtgo(deck);
      case 'text':
        return deck.exports?.text || exportToText(deck);
      case 'csv':
        return deck.exports?.csv || exportToCsv(deck);
      default:
        return exportToManaPool(deck);
    }
  }, [deck, activeFormat]);

  const cardCount = useMemo(() => {
    return countExportCards(exportText, activeFormat);
  }, [exportText, activeFormat]);

  if (!isOpen || !deck) return null;

  const currentFormatMeta = EXPORT_FORMATS.find((f) => f.id === activeFormat) || EXPORT_FORMATS[0];

  const handleCopy = () => {
    if (!exportText) return;
    navigator.clipboard.writeText(exportText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2400);
  };

  const handleDownload = () => {
    if (!exportText) return;
    let filename = `${safeFilenameBase}_${activeFormat}${currentFormatMeta.ext}`;
    if (activeFormat === 'mtgo') {
      filename = `${safeFilenameBase}.dec`;
    } else if (activeFormat === 'csv') {
      filename = `${safeFilenameBase}.csv`;
    } else if (activeFormat === 'text') {
      const bracketTier = deck.bracket?.tier ? `_bracket_${deck.bracket.tier}` : '';
      filename = `${safeFilenameBase}${bracketTier}.txt`;
    }
    downloadDeckFile(exportText, filename, currentFormatMeta.mime);
  };

  return (
    <div 
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        backgroundColor: 'rgba(5, 2, 12, 0.78)',
        backdropFilter: 'blur(6px)',
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
          maxWidth: '720px',
          maxHeight: '92vh',
          backgroundColor: 'var(--bg-panel, #1c0f35)',
          border: '1px solid var(--border-purple, #3b2668)',
          borderRadius: '16px',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.65), 0 0 25px rgba(168, 85, 247, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div style={{
          padding: '18px 22px',
          borderBottom: '1px solid var(--border-purple, #3b2668)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'linear-gradient(135deg, rgba(37, 22, 66, 0.7), rgba(28, 15, 53, 0.95))'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #9333ea, #38bdf8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 12px rgba(168, 85, 247, 0.5)'
            }}>
              <Download size={20} color="#ffffff" />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-white, #ffffff)', fontWeight: 'bold' }}>
                Export 100-Card Deck
              </h3>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-accent, #bb8fdf)', marginTop: '2px' }}>
                {commanders.map((c) => c.name).join(' & ')} • Bracket {deck.bracket?.tier || 3}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{
              padding: '4px 10px',
              borderRadius: '20px',
              fontSize: '0.78rem',
              fontWeight: 'bold',
              background: cardCount === 100 ? 'rgba(39, 174, 96, 0.18)' : 'rgba(230, 126, 34, 0.18)',
              border: `1px solid ${cardCount === 100 ? 'var(--color-green, #27ae60)' : 'var(--color-orange, #e67e22)'}`,
              color: cardCount === 100 ? 'var(--color-green, #27ae60)' : 'var(--color-orange, #e67e22)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              {cardCount === 100 ? <Check size={13} /> : null}
              {cardCount} / 100 Cards
            </span>

            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-accent, #bb8fdf)',
                padding: '6px',
                borderRadius: '8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'background 0.15s, color 0.15s'
              }}
              title="Close (Esc)"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Format Tabs Bar */}
        <div style={{
          padding: '12px 20px',
          background: 'var(--bg-input, #100522)',
          borderBottom: '1px solid var(--border-purple, #3b2668)',
          display: 'flex',
          gap: '8px',
          overflowX: 'auto'
        }}>
          {EXPORT_FORMATS.map((fmt) => {
            const isActive = activeFormat === fmt.id;
            const Icon = fmt.icon;
            return (
              <button
                key={fmt.id}
                onClick={() => {
                  setActiveFormat(fmt.id);
                  setCopied(false);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 13px',
                  borderRadius: '10px',
                  fontSize: '0.82rem',
                  fontWeight: isActive ? 'bold' : '500',
                  cursor: 'pointer',
                  border: isActive ? '1px solid #c084fc' : '1px solid rgba(59, 38, 104, 0.6)',
                  background: isActive ? 'linear-gradient(135deg, rgba(147, 51, 234, 0.35), rgba(56, 189, 248, 0.25))' : 'rgba(28, 15, 53, 0.6)',
                  color: isActive ? '#ffffff' : 'var(--text-accent, #bb8fdf)',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s ease',
                  boxShadow: isActive ? '0 0 12px rgba(168, 85, 247, 0.35)' : 'none'
                }}
              >
                <Icon size={14} />
                <span>{fmt.name}</span>
                {fmt.badge && (
                  <span style={{
                    fontSize: '0.65rem',
                    padding: '1px 5px',
                    borderRadius: '6px',
                    background: isActive ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.3)',
                    color: isActive ? '#ffffff' : 'var(--text-accent, #bb8fdf)',
                    marginLeft: '2px'
                  }}>
                    {fmt.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Modal Body */}
        <div style={{
          padding: '18px 22px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          {/* Format Description Banner */}
          <div style={{
            background: 'rgba(25, 14, 48, 0.65)',
            border: '1px solid rgba(59, 38, 104, 0.5)',
            borderRadius: '8px',
            padding: '10px 14px',
            fontSize: '0.82rem',
            color: 'var(--text-main, #e9dfff)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap'
          }}>
            <div style={{ flex: 1, minWidth: '240px' }}>
              <span style={{ color: 'var(--text-accent, #bb8fdf)', fontWeight: 'bold' }}>
                {currentFormatMeta.name} Integration:
              </span>{' '}
              {currentFormatMeta.desc}
            </div>

            {/* Quick Links for Mana Pool / Moxfield / Archidekt / TCGplayer */}
            {activeFormat === 'manapool' && (
              <a
                href={getManaPoolMassEntryUrl(deck)}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: '#38bdf8',
                  fontSize: '0.78rem',
                  textDecoration: 'none',
                  fontWeight: '600',
                  padding: '5px 10px',
                  borderRadius: '6px',
                  background: 'rgba(56, 189, 248, 0.15)',
                  border: '1px solid rgba(56, 189, 248, 0.4)'
                }}
              >
                <ShoppingCart size={13} />
                <span>Open in Mana Pool Mass Entry</span>
                <ExternalLink size={12} />
              </a>
            )}

            {activeFormat === 'moxfield' && (
              <a
                href="https://www.moxfield.com/decks/personal"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  color: '#38bdf8',
                  fontSize: '0.78rem',
                  textDecoration: 'none',
                  fontWeight: '600',
                  padding: '4px 8px',
                  borderRadius: '6px',
                  background: 'rgba(56, 189, 248, 0.1)',
                  border: '1px solid rgba(56, 189, 248, 0.3)'
                }}
              >
                <span>Open Moxfield</span>
                <ExternalLink size={12} />
              </a>
            )}

            {activeFormat === 'tcgplayer' && (
              <a
                href={getTcgplayerMassEntryUrl(deck)}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: '#fbbf24',
                  fontSize: '0.78rem',
                  textDecoration: 'none',
                  fontWeight: '600',
                  padding: '5px 10px',
                  borderRadius: '6px',
                  background: 'rgba(245, 158, 11, 0.15)',
                  border: '1px solid rgba(245, 158, 11, 0.4)'
                }}
              >
                <ShoppingCart size={13} />
                <span>Open in TCGplayer Mass Entry</span>
                <ExternalLink size={12} />
              </a>
            )}

            {activeFormat === 'archidekt' && (
              <a
                href="https://archidekt.com/decks/create"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  color: '#f59e0b',
                  fontSize: '0.78rem',
                  textDecoration: 'none',
                  fontWeight: '600',
                  padding: '4px 8px',
                  borderRadius: '6px',
                  background: 'rgba(245, 158, 11, 0.1)',
                  border: '1px solid rgba(245, 158, 11, 0.3)'
                }}
              >
                <span>Open Archidekt</span>
                <ExternalLink size={12} />
              </a>
            )}
          </div>

          {/* Mana Pool Affiliate Explanatory Note */}
          {activeFormat === 'manapool' && (
            <div style={{
              background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.12), rgba(14, 165, 233, 0.08))',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: '8px',
              padding: '10px 14px',
              fontSize: '0.8rem',
              color: '#bae6fd',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
              lineHeight: '1.45'
            }}>
              <span style={{ fontSize: '1.1rem', lineHeight: '1' }}>⚡</span>
              <div>
                <strong>Support Loreweaver with Mana Pool!</strong> Copy this list and open Mana Pool Mass Entry to use their Cart Optimizer and independent seller marketplace. <strong>Loreweaver earns a 5% affiliate commission</strong> at zero extra cost to you.
              </div>
            </div>
          )}

          {/* TCGplayer Affiliate Explanatory Note */}
          {activeFormat === 'tcgplayer' && (
            <div style={{
              background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(180, 83, 9, 0.08))',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              borderRadius: '8px',
              padding: '10px 14px',
              fontSize: '0.8rem',
              color: '#fef08a',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
              lineHeight: '1.45'
            }}>
              <span style={{ fontSize: '1.1rem', lineHeight: '1' }}>🛒</span>
              <div>
                Copy this list and paste into TCGplayer Mass Entry to automatically load all 100 cards into your cart. Purchasing through this link supports Loreweaver hosting costs at no extra charge to you!
              </div>
            </div>
          )}

          {/* Decklist Textarea Preview */}
          <div style={{ position: 'relative' }}>
            <textarea
              readOnly
              value={exportText}
              onFocus={(e) => e.target.select()}
              style={{
                width: '100%',
                height: '280px',
                padding: '14px',
                borderRadius: '10px',
                border: '1px solid var(--border-purple, #3b2668)',
                backgroundColor: 'var(--bg-input, #100522)',
                color: '#f8fafc',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                fontSize: '0.82rem',
                lineHeight: '1.5',
                resize: 'none',
                outline: 'none',
                boxShadow: 'inset 0 2px 8px rgba(0, 0, 0, 0.5)'
              }}
            />
            <div style={{
              position: 'absolute',
              bottom: '12px',
              right: '16px',
              fontSize: '0.72rem',
              color: 'var(--text-accent, #bb8fdf)',
              background: 'rgba(19, 9, 36, 0.85)',
              padding: '2px 8px',
              borderRadius: '6px',
              border: '1px solid rgba(59, 38, 104, 0.5)',
              pointerEvents: 'none'
            }}>
              {exportText.split('\n').filter(Boolean).length} lines • {cardCount} cards
            </div>
          </div>
        </div>

        {/* Modal Footer Action Bar */}
        <div style={{
          padding: '16px 22px',
          borderTop: '1px solid var(--border-purple, #3b2668)',
          backgroundColor: 'var(--bg-input, #100522)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          flexWrap: 'wrap'
        }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-accent, #bb8fdf)' }}>
            Click text to select all or use the buttons to copy/download.
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              onClick={handleDownload}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 16px',
                borderRadius: '8px',
                fontSize: '0.84rem',
                fontWeight: '600',
                cursor: 'pointer',
                background: 'rgba(37, 22, 66, 0.9)',
                border: '1px solid var(--border-purple, #3b2668)',
                color: 'var(--text-white, #ffffff)',
                transition: 'all 0.15s ease'
              }}
            >
              <Download size={15} />
              <span>Download {currentFormatMeta.ext}</span>
            </button>

            <button
              onClick={handleCopy}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 20px',
                borderRadius: '8px',
                fontSize: '0.84rem',
                fontWeight: 'bold',
                cursor: 'pointer',
                border: copied ? '1px solid #22c55e' : '1px solid #c084fc',
                background: copied 
                  ? 'linear-gradient(135deg, #15803d, #22c55e)' 
                  : 'linear-gradient(135deg, #9333ea, #7b2cbf)',
                color: '#ffffff',
                boxShadow: copied 
                  ? '0 0 16px rgba(34, 197, 94, 0.5)' 
                  : '0 0 16px rgba(168, 85, 247, 0.4)',
                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                transform: copied ? 'scale(1.02)' : 'scale(1)'
              }}
            >
              {copied ? (
                <>
                  <Check size={16} />
                  <span>Copied to Clipboard!</span>
                </>
              ) : (
                <>
                  <Copy size={16} />
                  <span>Copy {currentFormatMeta.name}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
