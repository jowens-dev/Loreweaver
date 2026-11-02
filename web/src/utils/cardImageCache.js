/**
 * Loreweaver Card Image & Metadata In-Memory Cache
 * Fast, responsive Scryfall resolution with in-memory caching and request deduplication.
 */

// In-memory cache: normalized card name -> card metadata object
const cardCache = new Map();

// In-flight fetch promises to prevent redundant network requests
const inFlightRequests = new Map();

/**
 * Strips formatting artifacts like decklist counts ('1 ', '1x '),
 * format tags ('*CMDR*'), and bracket annotations ('[Ramp]').
 *
 * @param {string} rawName
 * @returns {string}
 */
export function cleanCardName(rawName) {
  if (!rawName || typeof rawName !== 'string') return '';
  return rawName
    .replace(/^(\d+x?\s+)/i, '')
    .replace(/\*CMDR\*/gi, '')
    .replace(/\[.*?\]/g, '')
    .trim();
}

/**
 * Normalizes card names for consistent cache lookup.
 *
 * @param {string} name
 * @returns {string}
 */
export function normalizeCardKey(name) {
  const cleaned = cleanCardName(name);
  return cleaned.toLowerCase();
}

/**
 * Retrieves a card from the in-memory cache if available.
 *
 * @param {string} name
 * @returns {Object|null}
 */
export function getCardFromCache(name) {
  const key = normalizeCardKey(name);
  return cardCache.get(key) || null;
}

/**
 * Explicitly sets or updates card data in the in-memory cache.
 * Also caches aliases (such as the front face of DFCs).
 *
 * @param {string} name
 * @param {Object} cardData
 */
export function setCardInCache(name, cardData) {
  if (!name || !cardData) return;
  const key = normalizeCardKey(name);
  cardCache.set(key, cardData);

  if (cardData.name && normalizeCardKey(cardData.name) !== key) {
    cardCache.set(normalizeCardKey(cardData.name), cardData);
  }

  // If double-faced, also index under each face's name
  if (cardData.faces && Array.isArray(cardData.faces)) {
    cardData.faces.forEach((face) => {
      if (face?.name) {
        cardCache.set(normalizeCardKey(face.name), cardData);
      }
    });
  }

  // Preload image URLs into browser cache
  if (cardData.image_url) {
    preloadImage(cardData.image_url);
  }
  if (cardData.back_image_url) {
    preloadImage(cardData.back_image_url);
  }
}

/**
 * Preloads an image into the browser's image cache.
 *
 * @param {string} url
 */
export function preloadImage(url) {
  if (!url || typeof window === 'undefined') return;
  try {
    const img = new Image();
    img.src = url;
  } catch {
    // Gracefully handle any image preloading error
  }
}

/**
 * Fetches card metadata and images from Scryfall API with graceful fallbacks.
 *
 * @param {string} cardName
 * @returns {Promise<Object|null>}
 */
export async function fetchCardFromScryfall(cardName) {
  const clean = cleanCardName(cardName);
  if (!clean) return null;

  const key = normalizeCardKey(clean);

  // 1. Check in-memory cache
  if (cardCache.has(key)) {
    return cardCache.get(key);
  }

  // 2. Check pending in-flight request
  if (inFlightRequests.has(key)) {
    return inFlightRequests.get(key);
  }

  // 3. Initiate request to Scryfall API
  const fetchPromise = (async () => {
    try {
      // First attempt: exact match
      let response = await fetch(
        `https://api.scryfall.com/cards/named?exact=${encodeURIComponent(clean)}`,
        { headers: { Accept: 'application/json' } }
      );

      // Second attempt: fuzzy match if exact is 404
      if (!response.ok && response.status === 404) {
        // If name has " // ", try front face first
        if (clean.includes(' // ')) {
          const frontOnly = clean.split(' // ')[0].trim();
          response = await fetch(
            `https://api.scryfall.com/cards/named?exact=${encodeURIComponent(frontOnly)}`,
            { headers: { Accept: 'application/json' } }
          );
        }

        if (!response.ok) {
          response = await fetch(
            `https://api.scryfall.com/cards/named?fuzzy=${encodeURIComponent(clean)}`,
            { headers: { Accept: 'application/json' } }
          );
        }
      }

      if (!response.ok) {
        return null;
      }

      const data = await response.json();
      if (!data || !data.name) return null;

      const faces = Array.isArray(data.card_faces) ? data.card_faces : [];
      const hasDfcFaces = faces.length >= 2 && Boolean(faces[0]?.image_uris || faces[1]?.image_uris);

      let frontImage = '';
      let backImage = '';
      let parsedFaces = null;

      if (hasDfcFaces) {
        frontImage =
          faces[0]?.image_uris?.normal ||
          faces[0]?.image_uris?.large ||
          faces[0]?.image_uris?.small ||
          '';
        backImage =
          faces[1]?.image_uris?.normal ||
          faces[1]?.image_uris?.large ||
          faces[1]?.image_uris?.small ||
          '';

        parsedFaces = faces.map((f, idx) => ({
          index: idx,
          name: f.name || data.name,
          mana_cost: f.mana_cost || '',
          type_line: f.type_line || '',
          oracle_text: f.oracle_text || '',
          image_url:
            f.image_uris?.normal ||
            f.image_uris?.large ||
            f.image_uris?.small ||
            (idx === 0 ? frontImage : backImage)
        }));
      } else {
        frontImage =
          data.image_uris?.normal ||
          data.image_uris?.large ||
          data.image_uris?.small ||
          (faces.length > 0 && faces[0]?.image_uris?.normal) ||
          '';
      }

      const cardResult = {
        name: data.name,
        mana_cost: hasDfcFaces ? (faces[0]?.mana_cost || data.mana_cost || '') : (data.mana_cost || ''),
        type_line: data.type_line || (faces.length > 0 ? faces.map(f => f.type_line).join(' // ') : ''),
        oracle_text: data.oracle_text || (faces.length > 0 ? faces.map(f => f.oracle_text).join('\n//\n') : ''),
        cmc: data.cmc ?? 0,
        colors: data.colors || [],
        color_identity: data.color_identity || [],
        image_url: frontImage,
        back_image_url: backImage,
        is_dfc: hasDfcFaces,
        faces: parsedFaces,
        layout: data.layout || 'normal',
        scryfall_uri: data.scryfall_uri || ''
      };

      setCardInCache(clean, cardResult);
      return cardResult;
    } catch (err) {
      console.warn(`[CardCache] Failed to resolve Scryfall metadata for "${clean}":`, err);
      return null;
    } finally {
      inFlightRequests.delete(key);
    }
  })();

  inFlightRequests.set(key, fetchPromise);
  return fetchPromise;
}
