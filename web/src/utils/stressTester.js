// Helper: Combination math nCr
function combinations(n, k) {
  if (k < 0 || k > n) return 0;
  if (k === 0 || k === n) return 1;
  let targetK = k;
  if (targetK > n / 2) targetK = n - targetK;
  
  let result = 1;
  for (let i = 1; i <= targetK; i++) {
    result *= (n - targetK + i);
    result /= i;
  }
  return Math.round(result);
}

// Multivariate hypergeometric consistency solver
export function calculateJointConsistency(
  N, // Deck Size (99)
  n, // Sample Size (13 cards by turn 6)
  K_lands, k_lands, // Lands available and needed
  K_ramp, k_ramp,   // Ramp available and needed
  K_draw, k_draw    // Draw available and needed
) {
  let totalProb = 0.0;
  const K_other = N - (K_lands + K_ramp + K_draw);
  const den = combinations(N, n);
  if (den === 0) return 0.0;

  for (let x_lands = k_lands; x_lands <= Math.min(n, K_lands); x_lands++) {
    for (let x_ramp = k_ramp; x_ramp <= Math.min(n - x_lands, K_ramp); x_ramp++) {
      for (let x_draw = k_draw; x_draw <= Math.min(n - x_lands - x_ramp, K_draw); x_draw++) {
        const x_other = n - (x_lands + x_ramp + x_draw);
        if (x_other < 0 || x_other > K_other) continue;

        const num = combinations(K_lands, x_lands) *
                    combinations(K_ramp, x_ramp) *
                    combinations(K_draw, x_draw) *
                    combinations(K_other, x_other);
        totalProb += num / den;
      }
    }
  }

  return totalProb;
}

const COMMANDER_RAMP_REGEX = /treasure|add\s+{|search.*library.*land/i;
const COMMANDER_DRAW_REGEX = /draw|exile.*top.*library|look at.*top.*library/i;

// Classifier Regexes
const RAMP_REGEXES = [
  /\badd\b.*\bmana\b/i,
  /\badd\s+({[WUBRGCCX/]+}|\w+\s+mana)/i,
  /search\s+your\s+library\s+for\s+a\s+.*land/i,
  /create\s+.*Treasure/i
];

const DRAW_REGEXES = [
  /\bdraw\s+(\w+|\d+)?\s*cards?\b/i,
  /\bdraws\s+a\s+card\b/i
];

const REMOVAL_REGEXES = [
  /\b(destroy|exile|counter)\b\s+target/i,
  /deals?\s+(\d+|x)\s+damage\s+to\s+target/i,
  /damage\s+to\s+any\s+target/i,
  /counter\s+target\s+spell/i
];

const PROTECTION_REGEX = /\bhexproof\b|\bshroud\b|\bindestructible\b|\bphase out\b|\bregenerate\b|\bcounter target\b/i;
const MULTIPLAYER_REGEX = /each opponent|whenever an opponent|each player|number of opponents/i;

// Classifiers
export const isLand = (card) => (card.raw_type || "").toLowerCase().includes("land");

export const isRamp = (card) => {
  if (isLand(card)) return false;
  const text = card.oracle_text || "";
  return RAMP_REGEXES.some(r => r.test(text));
};

export const isDraw = (card) => {
  if (isLand(card)) return false;
  const text = card.oracle_text || "";
  return DRAW_REGEXES.some(r => r.test(text));
};

export const isRemoval = (card) => {
  if (isLand(card)) return false;
  const text = card.oracle_text || "";
  return REMOVAL_REGEXES.some(r => r.test(text));
};

export const isProtection = (card) => {
  if (isLand(card)) return false;
  const text = card.oracle_text || "";
  return PROTECTION_REGEX.test(text);
};

export const isMultiplayerScaling = (card) => {
  if (isLand(card)) return false;
  const text = card.oracle_text || "";
  return MULTIPLAYER_REGEX.test(text);
};

export function calculateFragilityWeight(card) {
  const typeLine = (card.raw_type || "").toLowerCase();
  if (typeLine.includes("land")) return 0.05;

  const weights = [];
  if (typeLine.includes("creature")) weights.push(0.8);
  if (typeLine.includes("planeswalker")) weights.push(0.7);
  if (typeLine.includes("artifact")) weights.push(0.6);
  if (typeLine.includes("enchantment")) weights.push(0.3);

  if (weights.length > 0) return Math.max(...weights);
  return 0.0;
}

/**
 * Calculates stress metrics for the parsed decklist
 */
export function analyzeStress(deckNames, db, commanderCardInfo = null, cohesionStats = null) {
  let landsCount = 0;
  let spellsCount = 0;
  let rampCount = 0;
  let drawCount = 0;
  let disjointRampCount = 0;
  let disjointDrawCount = 0;
  let protectionCount = 0;
  
  let creaturesCount = 0;
  let artifactsCount = 0;
  let enchantmentsCount = 0;
  let planeswalkersCount = 0;

  // Payoff and generator tallies for fodder awareness
  let tokenGenerators = 0;
  let tokenPayoffs = 0;
  let counterGenerators = 0;
  let counterPayoffs = 0;

  const nonLandPerms = [];
  const scalingSpells = [];

  for (const name of deckNames) {
    const card = db[name.toLowerCase()];
    if (!card) {
      // Basic lands fallback if not in Scryfall DB
      const lower = name.toLowerCase();
      if (lower.includes("wastes") || lower.includes("island") || lower.includes("forest") || 
          lower.includes("swamp") || lower.includes("mountain") || lower.includes("plains")) {
        landsCount++;
      }
      continue;
    }

    if (isLand(card)) {
      landsCount++;
    } else {
      spellsCount++;
      const rampMatch = isRamp(card);
      const drawMatch = isDraw(card);
      if (rampMatch) rampCount++;
      if (drawMatch) drawCount++;
      if (rampMatch) {
        disjointRampCount++;
      } else if (drawMatch) {
        disjointDrawCount++;
      }
      if (isProtection(card)) protectionCount++;
      if (isMultiplayerScaling(card)) {
        scalingSpells.push(card.name);
      }

      // Count resource generators and payoffs for CDI Fodder Awareness
      const text = card.oracle_text || "";
      if (/create.*token/i.test(text)) tokenGenerators++;
      if (/\bpopulate\b|\btoken\b.*(double|additional|whenever a.*enters)|sacrifice a.*token/i.test(text)) tokenPayoffs++;
      if (/put.*counter|proliferate/i.test(text)) counterGenerators++;
      if (/double.*number of.*counter|whenever a.*counter is placed|modified creature/i.test(text)) counterPayoffs++;

      const fragWeight = calculateFragilityWeight(card);
      if (fragWeight > 0.0) {
        nonLandPerms.push(card);
        const typeLine = (card.raw_type || "").toLowerCase();
        if (typeLine.includes("creature")) creaturesCount++;
        if (typeLine.includes("artifact")) artifactsCount++;
        if (typeLine.includes("enchantment")) enchantmentsCount++;
        if (typeLine.includes("planeswalker")) planeswalkersCount++;
      }
    }
  }

  // 1. Fragility calculations
  const totalFragility = nonLandPerms.reduce((sum, c) => sum + calculateFragilityWeight(c), 0);
  const avgFragility = nonLandPerms.length > 0 ? (totalFragility / nonLandPerms.length) : 0.0;
  const adjustedFragility = avgFragility - (protectionCount * 0.05);

  let fragilityRating = "Low Fragility";
  let fragilityColor = "#27AE60"; // Green
  if (adjustedFragility >= 0.6) {
    fragilityRating = "High Fragility";
    fragilityColor = "#E24A4A"; // Red
  } else if (adjustedFragility >= 0.35) {
    fragilityRating = "Medium Fragility";
    fragilityColor = "#E67E22"; // Orange
  }

  // 2. Table-Pressure index
  const scaleCount = scalingSpells.length;
  let tablePressureScore = Math.min(100, Math.round((scaleCount / 12) * 100));

  // 3. Commander Dependency Index (CDI) & Offsets
  let commanderFulfillsRamp = false;
  let commanderFulfillsDraw = false;
  if (commanderCardInfo) {
    const commText = (commanderCardInfo.oracle_text || "").toLowerCase();
    const commTypes = (commanderCardInfo.raw_type || "").toLowerCase();
    commanderFulfillsRamp = COMMANDER_RAMP_REGEX.test(commText) || COMMANDER_RAMP_REGEX.test(commTypes);
    commanderFulfillsDraw = COMMANDER_DRAW_REGEX.test(commText) || COMMANDER_DRAW_REGEX.test(commTypes);
  }

  let k_ramp = 1;
  let k_draw = 1;
  let rampTarget = 10;
  let drawTarget = 10;

  if (commanderFulfillsRamp) {
    k_ramp = 0; // Turn 0 ramp engine reduces hand draw requirement
    rampTarget = 7; // Reduce 99 success pool target by ~25%
  }
  if (commanderFulfillsDraw) {
    k_draw = 0; // Turn 0 draw engine reduces hand draw requirement
    drawTarget = 7; // Reduce 99 success pool target by ~25%
  }

  let cdiScore = 20;
  let cdiFodderOverrideActive = false;

  if (commanderCardInfo && cohesionStats) {
    const commText = (commanderCardInfo.oracle_text || "").toLowerCase();
    const commTypes = (commanderCardInfo.raw_type || "").toLowerCase();

    // Check Subtype dependency
    const dominantSubtype = cohesionStats.dominant_subtype;
    if (dominantSubtype && dominantSubtype !== "None") {
      if (commText.includes(dominantSubtype.toLowerCase()) || commTypes.includes(dominantSubtype.toLowerCase())) {
        cdiScore += 40;
      }
    }

    // Check Theme dependency keywords
    const dominantTheme = cohesionStats.dominant_theme;
    if (dominantTheme && dominantTheme !== "None") {
      const themeKeywords = {
        "Group Slug / Bleed": ["opponent loses", "damage", "lost life", "bleed", "player loses"],
        "Big Mana / Colorless": ["colorless", "adds", "eldrazi", "mana"],
        "Flash / Instant Timing": ["flash", "instant"],
        "Enchantress / Constellation": ["enchantment", "constellation", "aura"],
        "Landfall / Lands": ["land", "landfall"],
        "Sacrifice / Aristocrats": ["sacrifice", "dies"],
        "Graveyard / Reanimator": ["graveyard", "reanimate", "undergrowth", "dredge"],
        "Blink / Flicker": ["exile", "flicker", "blink", "enters"],
        "Tokens": ["token", "populate"],
        "Counters (+1/+1 / Proliferate)": ["counter", "proliferate"],
        "Spellslinger": ["instant", "sorcery", "magecraft"],
        "Artifacts / Voltron": ["artifact", "equip", "aura"],
        "Wheel / Draw-Punish": ["draw", "discard", "wheel"],
        "Stax / Resource Denial": ["can't", "cost", "tax", "tapped", "rule of law"],
        "Combat / Extra Turns": ["combat", "attack", "turn", "strike"],
        "Lifegain": ["life", "lifelink"],
        "Discard / Madness": ["discard", "cycling", "madness"],
        "Planeswalkers / Superfriends": ["planeswalker"]
      };

      const keywords = themeKeywords[dominantTheme] || [];
      const matchesTheme = keywords.some(k => commText.includes(k) || commTypes.includes(k));
      if (matchesTheme) {
        cdiScore += 40;
      }
    }

    // Fodder Awareness Override (Logic Fix 1.1)
    const commGeneratesTokens = /create.*token/i.test(commText);
    const commGeneratesCounters = /put.*counter|proliferate/i.test(commText);
    if ((tokenPayoffs >= 2 && tokenGenerators < 2 && commGeneratesTokens) ||
        (counterPayoffs >= 2 && counterGenerators < 2 && commGeneratesCounters)) {
      cdiScore = 85;
      cdiFodderOverrideActive = true;
    }
  }

  cdiScore = Math.min(100, cdiScore);
  const cdiRating = cdiScore >= 60 ? "HIGH" : cdiScore >= 40 ? "MEDIUM" : "LOW";
  const glassCannonAlert = cdiRating === "HIGH" && protectionCount < 8;

  // 4. Consistency Calculations (Ensures disjoint sets so K_other >= 0 unconditionally)
  const jointProb = calculateJointConsistency(99, 13, landsCount, 3, disjointRampCount, k_ramp, disjointDrawCount, k_draw);
  let consistencyRating = "Low Consistency";
  let consistencyColor = "#E24A4A";
  if (jointProb >= 0.70) {
    consistencyRating = "High Consistency";
    consistencyColor = "#27AE60";
  } else if (jointProb >= 0.50) {
    consistencyRating = "Medium Consistency";
    consistencyColor = "#E67E22";
  }

  return {
    landsCount,
    spellsCount,
    rampCount,
    drawCount,
    protectionCount,
    creaturesCount,
    artifactsCount,
    enchantmentsCount,
    planeswalkersCount,
    avgFragility,
    adjustedFragility,
    fragilityRating,
    fragilityColor,
    tablePressureScore,
    scalingSpells: [...new Set(scalingSpells)].sort(),
    jointProb,
    consistencyRating,
    consistencyColor,
    cdiScore,
    cdiRating,
    glassCannonAlert,
    commanderFulfillsRamp,
    commanderFulfillsDraw,
    rampTarget,
    drawTarget,
    cdiFodderOverrideActive
  };
}
