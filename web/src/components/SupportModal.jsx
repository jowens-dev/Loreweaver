import React, { useEffect } from 'react';
import { Coffee, Star, MessageSquare, ExternalLink, X, Heart, ShoppingCart } from 'lucide-react';

export default function SupportModal({ isOpen, onClose }) {
  const kofiUrl = import.meta.env.VITE_KOFI_URL || 'https://ko-fi.com/loreweaver_mtg';
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

  if (!isOpen) return null;

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
          maxWidth: '560px',
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
        {/* Header */}
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
              background: 'linear-gradient(135deg, #f59e0b, #ec4899)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 12px rgba(245, 158, 11, 0.4)'
            }}>
              <Heart size={20} color="#ffffff" fill="#ffffff" />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-white, #ffffff)', fontWeight: 'bold' }}>
                Support Loreweaver
              </h3>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-accent, #bb8fdf)', marginTop: '2px' }}>
                Free, open-source Commander intelligence
              </div>
            </div>
          </div>

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

        {/* Modal Body */}
        <div style={{
          padding: '22px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px'
        }}>
          {/* Main message */}
          <p style={{
            margin: 0,
            fontSize: '0.92rem',
            lineHeight: '1.6',
            color: 'var(--text-main, #e9dfff)'
          }}>
            Loreweaver is 100% free, open-source, and built with love for the Commander community. If Loreweaver helped you brew your deck or saved you hours of theorycrafting, buying a coffee helps keep the servers running and supports ongoing development!
          </p>

          {/* Action buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {/* Ko-fi / Buy Me a Coffee */}
            <a
              href={kofiUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(234, 179, 8, 0.3))',
                border: '1px solid #f59e0b',
                color: '#fef08a',
                textDecoration: 'none',
                fontWeight: 'bold',
                fontSize: '0.92rem',
                transition: 'all 0.15s ease',
                boxShadow: '0 0 14px rgba(245, 158, 11, 0.2)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Coffee size={20} color="#f59e0b" />
                <span>☕ Buy Me a Coffee / Ko-fi</span>
              </div>
              <ExternalLink size={16} />
            </a>

            {/* Star on GitHub */}
            <a
              href="https://github.com/jowens-dev/Loreweaver"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: '10px',
                background: 'rgba(37, 22, 66, 0.9)',
                border: '1px solid var(--border-purple, #3b2668)',
                color: '#ffffff',
                textDecoration: 'none',
                fontWeight: '600',
                fontSize: '0.92rem',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Star size={20} color="#eab308" />
                <span>⭐ Star on GitHub</span>
              </div>
              <ExternalLink size={16} />
            </a>

            {/* Discord Community & Feedback */}
            <a
              href="https://discord.gg/loreweaver"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: '10px',
                background: 'rgba(37, 22, 66, 0.9)',
                border: '1px solid var(--border-purple, #3b2668)',
                color: '#ffffff',
                textDecoration: 'none',
                fontWeight: '600',
                fontSize: '0.92rem',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <MessageSquare size={20} color="#38bdf8" />
                <span>💬 Feedback & Discord Community</span>
              </div>
              <ExternalLink size={16} />
            </a>
          </div>

          {/* Friendly note about TCGplayer affiliate support */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(147, 51, 234, 0.15), rgba(56, 189, 248, 0.1))',
            border: '1px solid rgba(168, 85, 247, 0.3)',
            borderRadius: '10px',
            padding: '12px 14px',
            fontSize: '0.82rem',
            color: 'var(--text-accent, #bb8fdf)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            lineHeight: '1.45'
          }}>
            <ShoppingCart size={18} style={{ color: '#fbbf24', flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ color: '#ffffff' }}>Free Way to Support:</strong> You can also support us for free by using the &apos;Buy on TCGplayer&apos; button when ordering cards! We receive a small affiliate commission at no extra cost to you.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
