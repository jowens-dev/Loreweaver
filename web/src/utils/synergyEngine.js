/**
 * Client-Side Synergy Engine & Mana Pool Monetization Utilities for Loreweaver.
 *
 * Implements:
 * - Asymmetric logarithmic cost penalty: Penalty(P) = [ln(e + P)]^beta (beta = 2.1)
 * - Obscurity / Spice bonus: up to 2.0x multiplier for underplayed cards
 * - Mana Pool slugification & single-card affiliate outbound links
 * - Format interaction notes & micro-insights
 */

export const DEFAULT_SENTINEL_PRICE = 999.0;
export const DEFAULT_BETA = 2.1;
export const DEFAULT_MANAPOOL_REF = 'loreweaver';

/**
 * Normalizes a card name into a clean Mana Pool URL slug.
 * Example: "Sol Ring" -> "sol-ring"
 * Example: "Nadier's Nightblade" -> "nadiers-nightblade"
 * Example: "Dina, Soul Steeper" -> "dina-soul-steeper"
 * Example: "Æther Vial" -> "aether-vial"
 */
export function toManaPoolSlug(name = '') {
  if (!name) return '';
  return name
    .replace(/Æ/g, 'Ae')
    .replace(/æ/g, 'ae')
    .replace(/Œ/g, 'Oe')
    .replace(/œ/g, 'oe')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // remove accent diacritics
    .replace(/['",()!?.:]/g, '') // strip punctuation
    .replace(/[^a-zA-Z0-9]+/g, '-') // replace non-alphanumeric with hyphens
    .replace(/^-+|-+$/g, '') // trim leading/trailing hyphens
    .toLowerCase();
}

/**
 * Constructs direct single-card Mana Pool affiliate URL.
 * https://manapool.com/card/<card_slug>?ref=YOUR_REF_CODE&ref_meta=source:loreweaver_swap
 */
export function getManaPoolCardUrl(cardName = '', source = 'loreweaver_swap') {
  const ref = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_MANAPOOL_REF) || DEFAULT_MANAPOOL_REF;
  const slug = toManaPoolSlug(cardName);
  if (!slug) {
    return `https://manapool.com/?ref=${encodeURIComponent(ref)}`;
  }
  return `https://manapool.com/card/${slug}?ref=${encodeURIComponent(ref)}&ref_meta=source:${encodeURIComponent(source)}`;
}

/**
 * Calculates asymmetric logarithmic price drag penalty.
 * Penalty(P) = [ln(e + P)]^beta
 */
export function calculatePricePenalty(price, beta = DEFAULT_BETA) {
  const numP = Number(price);
  const p = (!isNaN(numP) && Number.isFinite(numP) && numP > 0) ? numP : DEFAULT_SENTINEL_PRICE;
  return Math.pow(Math.log(Math.E + p), beta);
}

/**
 * Calculates obscurity / spice multiplier from EDHREC rank.
 */
export function calculateSpiceBonus(edhrecRank) {
  if (!edhrecRank || edhrecRank <= 500) {
    return 1.0;
  }
  return 1.0 + Math.min(1.0, Math.max(0.0, (edhrecRank - 500) / 9500.0));
}

/**
 * Calculates Composite Value Score.
 * FinalScore(c) = (SynergyScore(c) * SpiceBonus(c)) / PricePenalty(P_c)
 */
export function calculateCompositeScore(synergyScore, price, edhrecRank, beta = DEFAULT_BETA) {
  const penalty = calculatePricePenalty(price, beta);
  const spice = calculateSpiceBonus(edhrecRank);
  return (Number(synergyScore || 0) * spice) / penalty;
}

/**
 * Formats a clean price string for display (e.g., "$0.35" or "$1.25").
 */
export function formatCardPrice(price) {
  if (price === null || price === undefined) return null;
  const num = Number(price);
  if (!Number.isFinite(num) || num >= DEFAULT_SENTINEL_PRICE || num <= 0) {
    return null;
  }
  return `$${num.toFixed(2)}`;
}
