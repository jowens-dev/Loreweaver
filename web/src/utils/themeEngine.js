import { isGameChanger, isMassLandDenial, isTutor, isExtraTurn } from './cfpRules.js';

const MECHANICAL_THEMES = {
  "Landfall / Lands": [/\blandfall\b/i, /whenever a land enters/i, /play an additional land/i],
  "Sacrifice / Aristocrats": [/sacrifice a/i, /whenever a.*dies/i, /die, you/i, /\baristocrat\b/i],
  "Graveyard / Reanimator": [/\bgraveyard\b/i, /return.*from your graveyard/i, /\breanimate\b/i, /\bdredge\b/i, /\bundergrowth\b/i],
  "Blink / Flicker": [/exile.*then return.*to the battlefield/i, /\bflicker\b/i, /\bblink\b/i, /enters the battlefield again/i],
  "Tokens": [/create.*token/i, /\bpopulate\b/i, /\bamass\b/i],
  "Counters (+1/+1 / Proliferate)": [/\+1\/\+1 counter/i, /\bproliferate\b/i, /doubling season/i, /hardened scales/i],
  "Spellslinger": [/whenever you cast an instant or sorcery/i, /instant or sorcery spell/i, /\bmagecraft\b/i],
  "Artifacts / Voltron": [/\bartifact\b/i, /\bequip\b/i, /enchant creature/i, /\baura\b/i, /\bvehicles\b/i],
  "Lifegain": [/gain life/i, /whenever you gain life/i, /\blifelink\b/i],
  "Discard / Madness": [/\bdiscard\b/i, /\bcycling\b/i, /\bmadness\b/i],
  "Planeswalkers / Superfriends": [/\bplaneswalker\b/i, /\bloyalty\b/i]
};

const STAPLES = new Set([
  "sol ring", "arcane signet", "command tower", "cyclonic rift", "rhystic study", 
  "smothering tithe", "swords to plowshares", "path to exile", "demonic tutor", 
  "vampiric tutor", "heroic intervention", "cultivate", "kodama's reach", 
  "beast within", "chaos warp", "counterspell", "fierce guardianship", 
  "deflecting swat", "deadly rollick", "flawless maneuver", "teferi's protection", 
  "swiftfoot boots", "lightning greaves", "skullclamp", "solemn simulacrum", 
  "eternal witness", "llanowar elves", "birds of paradise", "sylvan library", 
  "fabled passage", "rejuvenating springs", "undergrowth stadium", "spectator seating", 
  "vault of champions", "training center", "mana drain", "esper sentinel", 
  "an offer you can't refuse", "swan song", "fellwar stone", "panharmonicon",
  "doubling season", "anointed procession", "hardened scales", "parallel lives"
]);

/**
 * Scan card's oracle text and types to identify matching themes
 * @param {Object} cardInfo 
 * @returns {string[]} Matching theme names
 */
function scanMechanicalKeywords(cardInfo) {
  const matched = [];
  const text = cardInfo.oracle_text || "";
  const typeLine = cardInfo.raw_type || "";
  
  for (const [theme, regexes] of Object.entries(MECHANICAL_THEMES)) {
    for (const regex of regexes) {
      if (regex.test(text) || regex.test(typeLine)) {
        matched.push(theme);
        break; // Stop scanning this theme once it matches
      }
    }
  }
  return matched;
}

/**
 * Parse a full decklist and return a list of card name strings
 * @param {string} text 
 * @returns {string[]} List of card names matching quantity (e.g. 3 copies = 3 entries)
 */
export function parseDecklistText(text) {
  const cardNames = [];
  const lines = text.split("\n");
  for (let line of lines) {
    line = line.trim();
    if (!line || line.startsWith("//") || line.startsWith("#")) {
      continue;
    }
    
    const match = line.match(/^(\d+)\s+(.+)$/);
    if (!match) continue;
    
    const qty = parseInt(match[1], 10);
    let name = match[2].trim();
    
    name = name.replace(/\(.*\)/g, "").replace(/\[.*\]/g, "").trim();
    for (let i = 0; i < qty; i++) {
      cardNames.push(name);
    }
  }
  return cardNames;
}

/**
 * Calculates Cohesion score and builds theme breakdowns
 * @param {string[]} deckNames 
 * @param {Object} db 
 * @returns {Object} Cohesion stats
 */
export function calculateCohesionScore(deckNames, db) {
  let spellsCount = 0;
  let creaturesCount = 0;
  const subtypeCounts = {};
  const themeCounts = {};

  for (const name of deckNames) {
    const cardInfo = db[name.toLowerCase()];
    if (!cardInfo) continue;

    const rawType = (cardInfo.raw_type || "").toLowerCase();
    
    // Skip lands unless they are also creatures
    if (rawType.includes("land") && !rawType.includes("creature")) {
      continue;
    }

    spellsCount++;

    // Creature subtype tallying
    if (rawType.includes("creature")) {
      creaturesCount++;
      const subs = cardInfo.subtypes || [];
      for (const sub of subs) {
        subtypeCounts[sub] = (subtypeCounts[sub] || 0) + 1;
      }
    }

    // Mechanical theme tallying
    const matchedThemes = scanMechanicalKeywords(cardInfo);
    for (const theme of matchedThemes) {
      themeCounts[theme] = (themeCounts[theme] || 0) + 1;
    }
  }

  // Calculate subtype density
  let maxSubtypeCount = 0;
  let dominantSubtype = "None";
  for (const [sub, count] of Object.entries(subtypeCounts)) {
    if (count > maxSubtypeCount) {
      maxSubtypeCount = count;
      dominantSubtype = sub;
    }
  }
  const subtypeDensity = creaturesCount > 0 ? (maxSubtypeCount / creaturesCount) * 100 : 0;

  // Calculate theme density
  let maxThemeCount = 0;
  let dominantTheme = "None";
  for (const [theme, count] of Object.entries(themeCounts)) {
    if (count > maxThemeCount) {
      maxThemeCount = count;
      dominantTheme = theme;
    }
  }
  const themeDensity = spellsCount > 0 ? (maxThemeCount / spellsCount) * 100 : 0;

  // Apply blend formula
  let cohesionScore = 0;
  if (creaturesCount < 10) {
    cohesionScore = Math.min(100, themeDensity * 1.5);
  } else {
    cohesionScore = Math.min(100, (subtypeDensity * 0.4) + (themeDensity * 0.9));
  }

  // Sort subtype and theme counts for breakdown
  const sortedSubtypes = Object.entries(subtypeCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .reduce((obj, [k, v]) => ({ ...obj, [k]: v }), {});

  const sortedThemes = Object.entries(themeCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .reduce((obj, [k, v]) => ({ ...obj, [k]: v }), {});

  return {
    cohesion_score: Math.round(cohesionScore),
    dominant_subtype: dominantSubtype,
    subtype_density: Math.round(subtypeDensity),
    dominant_theme: dominantTheme,
    theme_density: Math.round(themeDensity),
    subtype_counts: sortedSubtypes,
    theme_counts: sortedThemes
  };
}

/**
 * Redefine flavor based on mechanical spice ratio (unique non-staple cards)
 * @param {string[]} deckNames 
 * @param {Object} db 
 * @returns {Object} Flavor profile details
 */
export function calculateFlavorProfile(deckNames, db) {
  let uniqueSpellsCount = 0;
  let spiceCount = 0;
  const spicyCards = [];

  for (const name of deckNames) {
    const card = db[name.toLowerCase()];
    if (!card) continue;

    // Skip basic lands
    const rawType = (card.raw_type || "").toLowerCase();
    if (rawType.includes("land") && !rawType.includes("creature")) {
      continue;
    }

    uniqueSpellsCount++;
    const rank = card.edhrec_rank;
    const lowerName = card.name.toLowerCase().trim();

    // Spicy = not in top 50 staples list AND (rank > 1200 or no rank)
    const isStaple = STAPLES.has(lowerName);
    const isNiche = !rank || rank > 1200;

    if (!isStaple && isNiche) {
      spiceCount++;
      spicyCards.push(card.name);
    }
  }

  const spiceRatio = uniqueSpellsCount > 0 ? spiceCount / uniqueSpellsCount : 0.0;
  let flavorRating = "Generic / Staple-Heavy";
  let flavorColor = "#E24A4A"; // Red
  if (spiceRatio >= 0.4) {
    flavorRating = "High Flavor (Spicy)";
    flavorColor = "#27AE60"; // Green
  } else if (spiceRatio >= 0.2) {
    flavorRating = "Moderate Flavor (Synergistic)";
    flavorColor = "#E67E22"; // Orange
  }

  return {
    flavorRating,
    flavorColor,
    spiceRatio: Math.round(spiceRatio * 100),
    spicyCards: [...new Set(spicyCards)].sort()
  };
}

const FINISHER_REGEX = /win the game|loses the game|extra turn|additional combat phase|craterhoof behemoth|triumph of the hordes|overwhelming stampede|beastmaster ascension|akroma's will|torment of hailfire|insurrection|exquisite blood|thassa's oracle|laboratory maniac/i;

export function analyzeIntentionalExperience(deckNames, db, targetIX, targetBracket) {
  const alerts = [];
  
  const gameChangersFound = [];
  const landDenialFound = [];
  const tutorsFound = [];
  const extraTurnsFound = [];
  let finisherCount = 0;

  for (const name of deckNames) {
    const lowerName = name.trim().toLowerCase();
    const cardInfo = db[lowerName];

    // Check CFP classifications
    if (isGameChanger(name)) {
      gameChangersFound.push(name);
    }
    if (cardInfo) {
      if (isMassLandDenial(cardInfo)) {
        landDenialFound.push(cardInfo.name);
      }
      if (isTutor(cardInfo)) {
        tutorsFound.push(cardInfo.name);
      }
      if (isExtraTurn(cardInfo)) {
        extraTurnsFound.push(cardInfo.name);
      }

      // Check finishers/combo cards
      const text = cardInfo.oracle_text || "";
      const type = cardInfo.raw_type || "";
      if (FINISHER_REGEX.test(text) || FINISHER_REGEX.test(type) || FINISHER_REGEX.test(cardInfo.name)) {
        finisherCount++;
      }
    }
  }

  // Bracket 1: Exhibition
  if (targetBracket === 1) {
    if (gameChangersFound.length > 0) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Exhibition)",
        message: `Exhibition decks cannot run Game Changers. Found: ${gameChangersFound.join(", ")}.`
      });
    }
    if (finisherCount > 0) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Exhibition)",
        message: "Exhibition decks cannot run intentional combos or heavy game-ending finishers."
      });
    }
    if (landDenialFound.length > 0) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Exhibition)",
        message: `Exhibition decks cannot run mass land denial. Found: ${landDenialFound.join(", ")}.`
      });
    }
    if (extraTurnsFound.length > 0) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Exhibition)",
        message: `Exhibition decks cannot run extra-turn cards. Found: ${extraTurnsFound.join(", ")}.`
      });
    }
    if (tutorsFound.length > 2) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Exhibition)",
        message: `Tutors are too dense (${tutorsFound.length} found). Exhibition decks require sparse tutors (max 2).`
      });
    }
  }

  // Bracket 2: Core (Precon level)
  else if (targetBracket === 2) {
    if (gameChangersFound.length > 0) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Core)",
        message: `Core/Precon decks cannot run Game Changers. Found: ${gameChangersFound.join(", ")}.`
      });
    }
    if (finisherCount > 0) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Core)",
        message: "Core/Precon decks cannot run intentional two-card combos or cheap loop finishers."
      });
    }
    if (landDenialFound.length > 0) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Core)",
        message: `Core/Precon decks cannot run mass land denial. Found: ${landDenialFound.join(", ")}.`
      });
    }
    if (extraTurnsFound.length > 1) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Core)",
        message: `Extra-turn spells should only appear in low quantities (max 1). Found: ${extraTurnsFound.join(", ")}.`
      });
    }
    if (tutorsFound.length > 2) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Core)",
        message: `Tutors should be sparse (max 2). Found: ${tutorsFound.length} tutors.`
      });
    }
  }

  // Bracket 3: Upgraded
  else if (targetBracket === 3) {
    if (gameChangersFound.length > 3) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Upgraded)",
        message: `Upgraded decks can run a max of 3 Game Changers. You have ${gameChangersFound.length}: ${gameChangersFound.join(", ")}.`
      });
    }
    if (landDenialFound.length > 0) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Upgraded)",
        message: `Upgraded decks cannot run mass land denial. Found: ${landDenialFound.join(", ")}.`
      });
    }
    if (extraTurnsFound.length > 2) {
      alerts.push({
        type: "warning",
        title: "Bracket Mismatch (Upgraded)",
        message: `Extra-turn spells should only appear in low quantities (max 2). Found: ${extraTurnsFound.join(", ")}.`
      });
    }
    const hasCheapCombo = gameChangersFound.includes("thassa's oracle");
    if (hasCheapCombo) {
      alerts.push({
        type: "info",
        title: "Combo Advisory (Upgraded)",
        message: "Advisory: Early-game two-card infinite combos are discouraged in Upgraded (Bracket 3)."
      });
    }
  }

  // Generic value pile check
  if (finisherCount === 0 && targetBracket >= 2) {
    alerts.push({
      type: "info",
      title: "Value-Pile Alert",
      message: "Value-Pile: Deck lacks deterministic closing power. Consider adding 1-2 game-ending finishers."
    });
  }

  return {
    alerts,
    gameChangersFound,
    landDenialFound,
    tutorsFound,
    extraTurnsFound,
    finisherCount
  };
}
