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
 * Scan the decklist to identify broken theme chains (e.g. generators vs payoffs)
 */
export function detectBrokenChains(deckNames, db) {
  let tokenGenerators = 0;
  let tokenPayoffs = 0;
  
  let counterGenerators = 0;
  let counterPayoffs = 0;

  let sacFodder = 0;   // Token makers / recursive creatures
  let sacOutlets = 0;  // Free sac outlets
  let sacPayoffs = 0;  // Death triggers

  for (const name of deckNames) {
    const card = db[name.toLowerCase()];
    if (!card) continue;

    const text = card.oracle_text || "";

    // 1. Tokens Chain
    if (/create.*token/i.test(text)) {
      tokenGenerators++;
    }
    if (/\bpopulate\b|\btoken\b.*(double|additional|whenever a.*enters)|sacrifice a.*token/i.test(text)) {
      tokenPayoffs++;
    }

    // 2. Counters Chain
    if (/put.*counter|proliferate/i.test(text)) {
      counterGenerators++;
    }
    if (/double.*number of.*counter|whenever a.*counter is placed|modified creature/i.test(text)) {
      counterPayoffs++;
    }

    // 3. Sacrifice Chain
    if (/create.*token|return.*from.*graveyard|reassemble|recursive|persist|undying/i.test(text)) {
      sacFodder++;
    }
    if (/sacrifice a (creature|artifact|permanent)/i.test(text)) {
      sacOutlets++;
    }
    if (/whenever.*dies|whenever you sacrifice|blood artist|zulaport/i.test(text)) {
      sacPayoffs++;
    }
  }

  const brokenChains = [];

  // Tokens check
  if (tokenGenerators + tokenPayoffs >= 5) {
    if (tokenGenerators < 2) {
      brokenChains.push({
        theme: "Tokens",
        reason: "Token Payoffs lacking sufficient Token Generators",
        missingType: "token generator",
        queryKeyword: "create token"
      });
    } else if (tokenPayoffs < 2) {
      brokenChains.push({
        theme: "Tokens",
        reason: "Token Generators lacking Token Payoffs/Outlets",
        missingType: "token payoff",
        queryKeyword: "whenever token enters"
      });
    }
  }

  // Counters check
  if (counterGenerators + counterPayoffs >= 5) {
    if (counterGenerators < 2) {
      brokenChains.push({
        theme: "Counters (+1/+1)",
        reason: "Counter Payoffs lacking Counter placement cards",
        missingType: "counter generator",
        queryKeyword: "put +1/+1 counter"
      });
    } else if (counterPayoffs < 2) {
      brokenChains.push({
        theme: "Counters (+1/+1)",
        reason: "Counter Generators lacking Counter synergy/payoffs",
        missingType: "counter payoff",
        queryKeyword: "modified double counters"
      });
    }
  }

  // Sacrifice check
  if (sacFodder + sacOutlets + sacPayoffs >= 5) {
    if (sacFodder < 2) {
      brokenChains.push({
        theme: "Sacrifice / Aristocrats",
        reason: "Sacrifice outlets/payoffs lacking sacrificial fodder (tokens/recursion)",
        missingType: "fodder creator",
        queryKeyword: "create token dies graveyard"
      });
    } else if (sacOutlets < 2) {
      brokenChains.push({
        theme: "Sacrifice / Aristocrats",
        reason: "Sacrificial fodder/payoffs lacking sacrifice outlets (free sac engines)",
        missingType: "sacrifice outlet",
        queryKeyword: "sacrifice a creature"
      });
    } else if (sacPayoffs < 2) {
      brokenChains.push({
        theme: "Sacrifice / Aristocrats",
        reason: "Sacrificial fodder/outlets lacking death trigger payoffs",
        missingType: "payoff trigger",
        queryKeyword: "whenever a creature dies"
      });
    }
  }

  return brokenChains;
}

/**
 * Queries Scryfall search API for cards matching identity and keywords, filtering out staples
 */
export async function fetchSpiceRecommendations(queryKeyword, colorIdentity = []) {
  if (colorIdentity.length === 0) colorIdentity = ["C"];
  
  // Format color identity query (e.g. id<=wu)
  const colors = colorIdentity.join("").toLowerCase();
  const q = `id<=${colors} -t:land (oracle:"${queryKeyword}")`;
  
  const url = `https://api.scryfall.com/cards/search?q=${encodeURIComponent(q)}`;

  try {
    const response = await fetch(url);
    if (!response.ok) return [];

    const data = await response.json();
    if (!data.data) return [];

    // Filter out top staples to keep suggestions "spicy" and unique
    const filtered = data.data.filter(card => {
      const name = (card.name || "").toLowerCase();
      // Also reject cards with very high EDHREC rank (under 500) to keep it spicy
      return !STAPLES.has(name) && card.edhrec_rank && card.edhrec_rank > 600;
    });

    // Sort by EDHREC rank ascending (most playable among the niche ones)
    return filtered
      .sort((a, b) => (a.edhrec_rank || 10000) - (b.edhrec_rank || 10000))
      .slice(0, 5) // Return top 5 spicy suggestions
      .map(card => ({
        name: card.name,
        mana_cost: card.mana_cost || "",
        type_line: card.type_line || "",
        oracle_text: card.oracle_text || "",
        image_url: card.image_uris ? (card.image_uris.normal || card.image_uris.small) : "",
        edhrec_rank: card.edhrec_rank
      }));
  } catch (error) {
    console.error("Error fetching spice suggestions:", error);
    return [];
  }
}
