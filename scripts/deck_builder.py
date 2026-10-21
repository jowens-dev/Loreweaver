"""Objective Synergy Commander Deck Architect Engine.

Builds complete, tournament-legal 100-card Commander decks from scratch based on:
1. Commander or Deck Idea prompt
2. Bracket preference (1: Exhibition, 2: Precon, 3: Optimized, 4: High-Power Unrestricted, 5: cEDH Meta)
3. Budget tier ('budget', 'moderate', 'unlimited')
4. Color preference
5. Preferred win condition ('combat', 'combo', 'drain', 'stax', 'burn', 'voltron', 'mill')
"""

from __future__ import annotations

import math
import re
import sqlite3
from typing import Any

try:
    from scripts import db
    from scripts.hybrid_engine import detect_resource_profile
    from scripts.math_utils import hypergeometric_cdf_ge, calculate_joint_consistency
except ImportError:
    import db
    from hybrid_engine import detect_resource_profile
    from math_utils import hypergeometric_cdf_ge, calculate_joint_consistency

# --- COLOR & ALIAS DICTIONARIES ---
COLOR_MAP: dict[str, set[str]] = {
    # Single colors
    "white": {"W"}, "w": {"W"}, "mono white": {"W"}, "monowhite": {"W"},
    "blue": {"U"}, "u": {"U"}, "mono blue": {"U"}, "monoblue": {"U"},
    "black": {"B"}, "b": {"B"}, "mono black": {"B"}, "monoblack": {"B"},
    "red": {"R"}, "r": {"R"}, "mono red": {"R"}, "monored": {"R"},
    "green": {"G"}, "g": {"G"}, "mono green": {"G"}, "monogreen": {"G"},
    "colorless": set(), "c": set(),
    # Guilds (2-color)
    "azorius": {"W", "U"}, "wu": {"W", "U"}, "uw": {"W", "U"},
    "dimir": {"U", "B"}, "ub": {"U", "B"}, "bu": {"U", "B"},
    "rakdos": {"B", "R"}, "br": {"B", "R"}, "rb": {"B", "R"},
    "gruul": {"R", "G"}, "rg": {"R", "G"}, "gr": {"R", "G"},
    "selesnya": {"W", "G"}, "wg": {"W", "G"}, "gw": {"W", "G"},
    "orzhov": {"W", "B"}, "wb": {"W", "B"}, "bw": {"W", "B"},
    "izzet": {"U", "R"}, "ur": {"U", "R"}, "ru": {"U", "R"},
    "golgari": {"B", "G"}, "bg": {"B", "G"}, "gb": {"B", "G"},
    "boros": {"W", "R"}, "wr": {"W", "R"}, "rw": {"W", "R"},
    "simic": {"U", "G"}, "ug": {"U", "G"}, "gu": {"U", "G"},
    # Shards & Wedges (3-color)
    "esper": {"W", "U", "B"},
    "grixis": {"U", "B", "R"},
    "jund": {"B", "R", "G"},
    "naya": {"W", "R", "G"},
    "bant": {"W", "U", "G"},
    "abzan": {"W", "B", "G"},
    "jeskai": {"W", "U", "R"},
    "sultai": {"B", "G", "U"},
    "mardu": {"W", "B", "R"},
    "temur": {"U", "R", "G"},
    # 4-color
    "glint-eye": {"U", "B", "R", "G"}, "chaos": {"U", "B", "R", "G"},
    "dune-brood": {"W", "B", "R", "G"}, "aggression": {"W", "B", "R", "G"},
    "ink-treader": {"W", "U", "R", "G"}, "altruism": {"W", "U", "R", "G"},
    "witch-maw": {"W", "U", "B", "G"}, "growth": {"W", "U", "B", "G"},
    "yore-tiller": {"W", "U", "B", "R"}, "artifice": {"W", "U", "B", "R"},
    # 5-color
    "5c": {"W", "U", "B", "R", "G"}, "five color": {"W", "U", "B", "R", "G"},
    "wubrg": {"W", "U", "B", "R", "G"}, "all": {"W", "U", "B", "R", "G"},
}

WUBRG_ORDER = ["W", "U", "B", "R", "G"]

# --- BRACKET CONFIGURATIONS ---
BRACKET_CONFIGS = {
    1: {
        "name": "Exhibition / Thematic",
        "description": "Narrative, tribal, or low-power theme. No fast mana, zero tutors, and zero infinite combos.",
        "target_lands": 38,
        "target_ramp": 8,
        "target_draw": 10,
        "target_removal": 8,
        "target_synergy": 32,
        "target_win_con": 3,
        "allow_fast_mana": False,
        "allow_sol_ring": False,
        "allow_tutors": False,
        "allow_combos": False,
        "cedh_meta": False,
        "target_avg_cmc": 3.8,
    },
    2: {
        "name": "Core Casual / Upgraded Precon",
        "description": "Upgraded preconstructed level. Fair, board-centric Magic. Standard ramp (Sol Ring, Signets, Cultivate). No 2-card infinites or cheap tutors.",
        "target_lands": 37,
        "target_ramp": 10,
        "target_draw": 10,
        "target_removal": 10,
        "target_synergy": 28,
        "target_win_con": 4,
        "allow_fast_mana": False,
        "allow_sol_ring": True,
        "allow_tutors": False,
        "allow_combos": False,
        "cedh_meta": False,
        "target_avg_cmc": 3.4,
    },
    3: {
        "name": "Optimized Casual",
        "description": "High synergy, focused win conditions, resilient mana base, responsive interaction, and multi-card combos.",
        "target_lands": 35,
        "target_ramp": 11,
        "target_draw": 11,
        "target_removal": 12,
        "target_synergy": 26,
        "target_win_con": 4,
        "allow_fast_mana": False,
        "allow_sol_ring": True,
        "allow_tutors": True,
        "allow_combos": True,
        "cedh_meta": False,
        "target_avg_cmc": 2.9,
    },
    4: {
        "name": "High-Power Unrestricted",
        "description": "Maximum power casual / fringe cEDH. Explosive fast mana, unrestricted combos, and top tutors without being locked into tournament cEDH meta staples.",
        "target_lands": 33,
        "target_ramp": 13,
        "target_draw": 12,
        "target_removal": 13,
        "target_synergy": 24,
        "target_win_con": 4,
        "allow_fast_mana": True,
        "allow_sol_ring": True,
        "allow_tutors": True,
        "allow_combos": True,
        "cedh_meta": False,
        "target_avg_cmc": 2.4,
    },
    5: {
        "name": "Competitive EDH (cEDH Meta)",
        "description": "The tournament cEDH metagame. Razor-thin curve, full fast mana suite, free counterspells, and compact tournament-winning combo lines.",
        "target_lands": 28,
        "target_ramp": 15,
        "target_draw": 12,
        "target_removal": 15,
        "target_synergy": 25,
        "target_win_con": 4,
        "allow_fast_mana": True,
        "allow_sol_ring": True,
        "allow_tutors": True,
        "allow_combos": True,
        "cedh_meta": True,
        "target_avg_cmc": 1.6,
    },
}

# --- CARD RESTRICTION LISTS ---
FAST_MANA_CARDS = {
    "mana crypt", "mox diamond", "chrome mox", "lotus petal", "mox opal",
    "mana vault", "grim monolith", "ancient tomb", "jeweled lotus", "lion's eye diamond"
}

CHEAP_TUTORS = {
    "demonic tutor", "vampiric tutor", "imperial seal", "worldly tutor",
    "mystical tutor", "enlightened tutor", "gamble", "personal tutor"
}

EXPENSIVE_RESERVED_LIST = {
    "black lotus", "mox pearl", "mox sapphire", "mox jet", "mox ruby", "mox emerald",
    "ancestral recall", "time walk", "timetwister", "gaea's cradle", "tabernacle at pendrell vale",
    "candelabra of tawnos", "mishra's workshop", "bazaar of baghdad", "underground sea",
    "volcanic island", "tropical island", "tundra", "bayou", "scrubland", "taiga",
    "badlands", "savannah", "plateau", "mox diamond", "lion's eye diamond", "gilded drake"
}

# --- CEDH META STAPLES BY COLOR (BRACKET 5 ONLY) ---
CEDH_STAPLES_BY_COLOR: dict[str, list[str]] = {
    "colorless": [
        "Mana Crypt", "Mox Diamond", "Chrome Mox", "Lotus Petal", "Sol Ring",
        "Mana Vault", "Fellwar Stone", "Arcane Signet", "The One Ring"
    ],
    "W": [
        "Esper Sentinel", "Silence", "Grand Abolisher", "Ranger-Captain of Eos",
        "Swords to Plowshares", "Trouble in Pairs", "Drannith Magistrate", "Enlightened Tutor"
    ],
    "U": [
        "Force of Will", "Force of Negation", "Mindbreak Trap", "Fierce Guardianship",
        "Mental Misstep", "Pact of Negation", "Rhystic Study", "Mystic Remora",
        "Flusterstorm", "Swan Song", "Chain of Vapor", "Cyclonic Rift", "Gitaxian Probe"
    ],
    "B": [
        "Demonic Tutor", "Vampiric Tutor", "Imperial Seal", "Orcish Bowmasters",
        "Dark Ritual", "Cabal Ritual", "Necropotence", "Ad Nauseam", "Deadly Rollick", "Tainted Pact"
    ],
    "R": [
        "Underworld Breach", "Red Elemental Blast", "Pyroblast", "Deflecting Swat",
        "Jeska's Will", "Simian Spirit Guide", "Wheel of Fortune", "Gamble", "Twinflame", "Dualcaster Mage"
    ],
    "G": [
        "Birds of Paradise", "Delighted Halfling", "Elvish Mystic", "Fyndhorn Elves",
        "Llanowar Elves", "Worldly Tutor", "Sylvan Library", "Veil of Summer",
        "Chord of Calling", "Crop Rotation", "Elvish Spirit Guide"
    ],
}

# --- DEDICATED WIN-CONDITION PACKAGES ---
WIN_CON_PACKAGES: dict[str, list[dict[str, Any]]] = {
    "combat": [
        {"name": "Craterhoof Behemoth", "colors": {"G"}, "desc": "Haste mass overrun providing lethal trample damage."},
        {"name": "Moonshaker Cavalry", "colors": {"W"}, "desc": "White Craterhoof providing flying and massive power buff."},
        {"name": "Triumph of the Hordes", "colors": {"G"}, "desc": "Mass infect and trample for one-shot combat finishes."},
        {"name": "Beastmaster Ascension", "colors": {"G"}, "desc": "+5/+5 static anthem to all creatures once counters are charged."},
        {"name": "Akroma's Will", "colors": {"W"}, "desc": "Instant-speed unblockable, double strike, and indestructible alpha strike."},
        {"name": "Aggravated Assault", "colors": {"R"}, "desc": "Repeatable extra combat steps."},
        {"name": "Moraug, Fury of Akoum", "colors": {"R"}, "desc": "Landfall-triggered cascading combat steps."},
        {"name": "Pathbreaker Ibex", "colors": {"G"}, "desc": "Repeated trample overrun matching highest power."},
        {"name": "Elesh Norn, Grand Cenobite", "colors": {"W"}, "desc": "Asymmetric board lock and combat swing."},
        {"name": "Akroma's Memorial", "colors": set(), "desc": "Colorless haste, flying, and vigilance board enabler."}
    ],
    "drain": [
        {"name": "Blood Artist", "colors": {"B"}, "desc": "Targeted drain whenever any creature dies."},
        {"name": "Zulaport Cutthroat", "colors": {"B"}, "desc": "Drain each opponent whenever your creatures die."},
        {"name": "Cruel Celebrant", "colors": {"W", "B"}, "desc": "Each opponent loses 1 life whenever your creature dies."},
        {"name": "Bastion of Remembrance", "colors": {"B"}, "desc": "Enchantment-based aristocrats drain protected from sweepers."},
        {"name": "Elas il-Kor, Sadistic Pilgrim", "colors": {"W", "B"}, "desc": "Deathtouch drain engine for creature death triggers."},
        {"name": "Marionette Apprentice", "colors": {"B"}, "desc": "Drains opponents on creature or artifact death."},
        {"name": "Mayhem Devil", "colors": {"B", "R"}, "desc": "Direct ping damage whenever any player sacrifices a permanent."},
        {"name": "Syr Konrad, the Grim", "colors": {"B"}, "desc": "Mass drain whenever creatures enter or leave graveyards."},
        {"name": "Bolas's Citadel", "colors": {"B"}, "desc": "Sacrifice 10 permanents to deal 10 damage to each opponent."},
        {"name": "Exsanguinate", "colors": {"B"}, "desc": "Large X-mana drain wiping all opponents simultaneously."}
    ],
    "combo": [
        {"name": "Thassa's Oracle", "colors": {"U"}, "desc": "Primary cEDH win con paired with Consultation or Tainted Pact."},
        {"name": "Demonic Consultation", "colors": {"B"}, "desc": "Exiles entire library to enable instant Thassa's Oracle trigger."},
        {"name": "Underworld Breach", "colors": {"R"}, "desc": "Graveyard recursion loop enabling infinite storm/mana."},
        {"name": "Brain Freeze", "colors": {"U"}, "desc": "Storm finisher with Underworld Breach to mill entire table."},
        {"name": "Lion's Eye Diamond", "colors": set(), "desc": "Infinite mana catalyst with Underworld Breach."},
        {"name": "Heliod, Sun-Crowned", "colors": {"W"}, "desc": "Grants lifelink to Walking Ballista for infinite ping loop."},
        {"name": "Walking Ballista", "colors": set(), "desc": "Damage conduit for infinite mana or Heliod lifelink loop."},
        {"name": "Dualcaster Mage", "colors": {"R"}, "desc": "Infinite hasty copy combo with Twinflame."},
        {"name": "Twinflame", "colors": {"R"}, "desc": "Copy spell that loops infinitely with Dualcaster Mage."},
        {"name": "Food Chain", "colors": {"G"}, "desc": "Infinite creature mana generator with cast-from-exile creatures."},
        {"name": "Squee, the Immortal", "colors": {"R"}, "desc": "Castable from exile to fuel infinite Food Chain mana."},
        {"name": "Kiki-Jiki, Mirror Breaker", "colors": {"R"}, "desc": "Infinite haste creature copies with Zealous Conscripts."},
        {"name": "Zealous Conscripts", "colors": {"R"}, "desc": "Untaps Kiki-Jiki on ETB for infinite attacker swarm."},
        {"name": "Exquisite Blood", "colors": {"B"}, "desc": "Infinite lifegain/damage loop with Sanguine Bond / Vito."},
        {"name": "Sanguine Bond", "colors": {"B"}, "desc": "Causes opponents to lose life whenever you gain life."}
    ],
    "stax": [
        {"name": "Rule of Law", "colors": {"W"}, "desc": "Hard limit of one spell per turn shuts down storm and combo."},
        {"name": "Archon of Emeria", "colors": {"W"}, "desc": "Rule of Law on a flying body plus nonbasic lands enter tapped."},
        {"name": "Deafening Silence", "colors": {"W"}, "desc": "Limits noncreature spells to one per turn."},
        {"name": "Drannith Magistrate", "colors": {"W"}, "desc": "Prevents opponents from casting commanders or spells from exile/graveyard."},
        {"name": "Dauthi Voidwalker", "colors": {"B"}, "desc": "Complete one-sided graveyard exile with free spell theft."},
        {"name": "Opposition Agent", "colors": {"B"}, "desc": "Searches opponents' libraries whenever they search, stealing tutors."},
        {"name": "Aven Mindcensor", "colors": {"W"}, "desc": "Restricts opponent library searches to top 4 cards."},
        {"name": "Trinisphere", "colors": set(), "desc": "Forces all spells to cost at least 3 mana, punishing cheap cantrips."},
        {"name": "Collector Ouphe", "colors": {"G"}, "desc": "Shuts off all activated artifact abilities and fast mana rocks."},
        {"name": "Blood Moon", "colors": {"R"}, "desc": "Turns all nonbasic lands into Mountains, crippling greedy mana bases."}
    ],
    "burn": [
        {"name": "Guttersnipe", "colors": {"R"}, "desc": "Deals 2 damage to each opponent for every instant/sorcery cast."},
        {"name": "Torbran, Thane of Red Fell", "colors": {"R"}, "desc": "Adds +2 damage to all red sources and burn spells."},
        {"name": "Roiling Vortex", "colors": {"R"}, "desc": "Passive upkeep burn and 5 damage penalty for free spells."},
        {"name": "Sulfuric Vortex", "colors": {"R"}, "desc": "Shuts off lifegain while dealing 2 damage each upkeep."},
        {"name": "Torment of Hailfire", "colors": {"B"}, "desc": "Crushing X-spell forcing life loss, discard, and sacrifice."},
        {"name": "Exsanguinate", "colors": {"B"}, "desc": "Direct burn draining life from all opponents simultaneously."},
        {"name": "Vito, Thorn of the Dusk Rose", "colors": {"B"}, "desc": "Converts lifegain into direct target burn."},
        {"name": "Aetherflux Reservoir", "colors": set(), "desc": "50-damage laser beam fueled by storm lifegain."}
    ],
    "voltron": [
        {"name": "Swiftfoot Boots", "colors": set(), "desc": "Hexproof and haste protection for the commander."},
        {"name": "Lightning Greaves", "colors": set(), "desc": "0-equip shroud and haste engine."},
        {"name": "Blackblade Reforged", "colors": set(), "desc": "Massive legendary equipment scaling power with land count."},
        {"name": "Sword of Feast and Famine", "colors": set(), "desc": "Untaps lands on combat damage and forces opponent discard."},
        {"name": "Colossus Hammer", "colors": set(), "desc": "+10/+10 power boost for lethal commander damage."},
        {"name": "Shadowspear", "colors": set(), "desc": "Trample and lifelink plus hexproof/indestructible removal."},
        {"name": "Hammer of Nazahn", "colors": set(), "desc": "Auto-equips all equipment on entry while granting indestructible."},
        {"name": "Puresteel Paladin", "colors": {"W"}, "desc": "Card draw on equipment entry and free 0-mana equip costs."}
    ],
    "mill": [
        {"name": "Maddening Cacophony", "colors": {"U"}, "desc": "Kicked spell mills half of each opponent's library."},
        {"name": "Bruvac the Grandiloquent", "colors": {"U"}, "desc": "Doubles all cards opponents mill."},
        {"name": "Ruin Crab", "colors": {"U"}, "desc": "Landfall engine milling each opponent 3 cards."},
        {"name": "Tasha's Hideous Laughter", "colors": {"U"}, "desc": "Exiles opponent cards until total mana value reaches 20."},
        {"name": "Syr Konrad, the Grim", "colors": {"B"}, "desc": "Converts mill into massive table-wide life loss."},
        {"name": "Laboratory Maniac", "colors": {"U"}, "desc": "Win the game when attempting to draw from an empty library."},
        {"name": "Thassa's Oracle", "colors": {"U"}, "desc": "Alternate win when library count is less than or equal to devotion."}
    ]
}


def resolve_color_identity(color_input: str | list[str] | set[str] | None) -> set[str]:
    """Parse flexible color strings or lists into a validated set of WUBRG letters."""
    if not color_input:
        return set()
    if isinstance(color_input, (list, set)):
        result = set()
        for item in color_input:
            result.update(resolve_color_identity(str(item)))
        return result

    raw = str(color_input).strip().lower()
    if raw in COLOR_MAP:
        return set(COLOR_MAP[raw])

    tokens = re.split(r"[,/\s]+", raw)
    colors = set()
    for tok in tokens:
        cleaned = tok.strip().upper()
        if cleaned in WUBRG_ORDER:
            colors.add(cleaned)
        elif tok in COLOR_MAP:
            colors.update(COLOR_MAP[tok])
    return colors


def find_matching_commander(
    conn: sqlite3.Connection,
    prompt: str,
    color_pref: set[str] | None = None,
    win_con: str = "combat",
    bracket: int = 3
) -> dict[str, Any] | None:
    """Select the best matching legendary creature from cards.db based on prompt, colors, and bracket."""
    cursor = conn.cursor()
    color_filter = ""
    params: list[Any] = []

    if color_pref is not None:
        legal_identities = db.get_legal_color_identities(color_pref)
        placeholders = ",".join("?" * len(legal_identities))
        color_filter = f"AND color_identity IN ({placeholders})"
        params.extend(legal_identities)

    sql = f"""
        SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
               subtypes, colors, color_identity, oracle_text, flavor_text,
               set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
        FROM cards
        WHERE (type_line LIKE '%Legendary%Creature%' OR oracle_text LIKE '%can be your commander%')
          AND set_type NOT IN ('funny', 'alchemy')
          AND edhrec_rank IS NOT NULL
          {color_filter}
        ORDER BY edhrec_rank ASC
        LIMIT 300
    """
    cursor.execute(sql, params)
    candidates = [db.parse_card_row(row) for row in cursor.fetchall()]

    if not candidates:
        return None

    prompt_tokens = {w.lower() for w in re.findall(r"\b\w{3,}\b", prompt)}
    prompt_tokens.add(win_con.lower())

    best_card: dict[str, Any] | None = None
    best_score = -1e9

    for cand in candidates:
        text = f"{cand['name']} {cand.get('oracle_text', '')} {cand.get('type_line', '')}".lower()
        score = 0.0

        # Color preference matching
        cand_colors = set(cand.get("color_identity", []))
        if color_pref:
            if cand_colors == color_pref:
                score += 50.0
            elif color_pref.issubset(cand_colors):
                score += 25.0
            else:
                score -= 40.0

        # Prompt token matches
        for tok in prompt_tokens:
            if tok in text:
                score += 15.0

        # EDHREC popularity bonus
        rank = cand.get("edhrec_rank") or 10000
        score += max(0.0, (10000.0 - rank) / 1000.0)

        # Bracket curve penalty for high CMC in brackets 4 and 5
        cmc = cand.get("cmc") or 4.0
        if bracket >= 4 and cmc > 4:
            score -= (cmc - 4) * 5.0
        elif bracket <= 2 and cmc >= 5:
            score += 3.0

        if score > best_score:
            best_score = score
            best_card = cand

    return best_card


def classify_card_role(card: dict[str, Any]) -> set[str]:
    """Classify a card into operational roles (land, ramp, draw, removal, protection, tutor)."""
    roles = set()
    name = card["name"].lower()
    type_line = card.get("type_line", "").lower()
    oracle = card.get("oracle_text", "").lower()
    types = [t.lower() for t in card.get("types", [])]

    if "land" in types or "land" in type_line:
        roles.add("land")
        return roles

    # Fast Mana & Ramp
    if name in FAST_MANA_CARDS or name in {"sol ring", "arcane signet", "fellwar stone"}:
        roles.add("ramp")
    elif re.search(r"({t}: add|add\s+{[wubrgc]}|create\s+.*treasure|search\s+your\s+library\s+for\s+a\s+.*land)", oracle):
        roles.add("ramp")

    # Card Draw & Card Advantage
    if re.search(r"(draw\s+(\w+|\d+)?\s*cards?|draws\s+a\s+card|look\s+at\s+the\s+top|investigate)", oracle):
        roles.add("draw")

    # Removal & Sweepers
    if re.search(r"(destroy|exile|counter)\s+target|deals?\s+(\d+|x)\s+damage\s+to\s+target", oracle):
        roles.add("removal")
    if re.search(r"(destroy\s+all|exile\s+all|each\s+opponent\s+sacrifices|all\s+creatures\s+get\s+-)", oracle):
        roles.add("removal")

    # Tutors
    if re.search(r"search\s+your\s+library\s+for\s+a\s+(card|creature|artifact|instant|sorcery|enchantment)", oracle):
        roles.add("tutor")

    # Protection
    if re.search(r"\b(hexproof|shroud|indestructible|phase\s+out|protection\s+from)\b", oracle):
        roles.add("protection")

    return roles


def score_synergy(
    card: dict[str, Any],
    commander: dict[str, Any],
    prompt_tokens: set[str],
    win_con: str,
    bracket: int
) -> float:
    """Calculate objective synergy score between a card and the commander/theme."""
    name = card["name"].lower()
    oracle = card.get("oracle_text", "").lower()
    type_line = card.get("type_line", "").lower()
    types = [t.lower() for t in card.get("types", [])]
    subtypes = [s.lower() for s in card.get("subtypes", [])]
    cmd_text = f"{commander['name']} {commander.get('oracle_text', '')}".lower()
    cmc = card.get("cmc", 3.0)

    score = 0.0

    # Detect Big-Mana / Colorless Engine (e.g., Belbe, Zhulodok, Rakdos)
    is_big_mana_engine = (
        "adds {c}{c}" in cmd_text or "colorless mana" in cmd_text or
        "belbe" in cmd_text or "zhulodok" in cmd_text or "big mana" in prompt_tokens
    )

    # 1. Commander catalyst/resource alignment
    if "opponent loses" in cmd_text or "damage to each opponent" in cmd_text or "lost life this turn" in cmd_text:
        # Pinger / Bleeder detection
        if (
            "each opponent loses" in oracle or
            "damage to each opponent" in oracle or
            "each player loses" in oracle or
            "attacks, each opponent loses" in oracle or
            "becomes tapped, each opponent loses" in oracle or
            "deals 1 damage to each opponent" in oracle or
            "each opponent who doesn" in oracle
        ):
            score += 55.0
            # Extra bonus for cheap 1-2 CMC enablers that trigger on curve
            if cmc <= 2:
                score += 20.0

    # Flash enablers for big-mana phase commanders (e.g., to cast spells during opponents' postcombat phases)
    if is_big_mana_engine or "flash" in prompt_tokens:
        if (
            "as though they had flash" in oracle or
            "may cast spells this turn as though they had flash" in oracle or
            "may cast creature spells this turn as though they had flash" in oracle or
            ("flash" in oracle and ("colorless" in oracle or "artifact" in oracle))
        ):
            score += 50.0

        # Big Colorless Bombs (CMC 6+)
        if cmc >= 6 and ("artifact" in types or "eldrazi" in subtypes or not card.get("color_identity")):
            score += 45.0

    if "sacrifice" in cmd_text and "sacrifice" in oracle:
        score += 25.0
    if "dies" in cmd_text or "dying" in cmd_text:
        if "dies" in oracle or "dying" in oracle or "whenever another creature dies" in oracle:
            score += 30.0
    if "instant" in cmd_text or "sorcery" in cmd_text:
        if "instant" in type_line or "sorcery" in type_line or "spell" in oracle:
            score += 25.0
    if "artifact" in cmd_text and "artifact" in type_line:
        score += 25.0

    # 2. User prompt token matching
    for tok in prompt_tokens:
        if tok in name:
            score += 15.0
        elif tok in oracle:
            score += 12.0
        elif tok in type_line:
            score += 10.0

    # 3. Format ubiquity & quality via EDHREC rank
    rank = card.get("edhrec_rank")
    if rank:
        score += max(0.0, (15000.0 - rank) / 1000.0)

    # 4. Mana curve scoring based on bracket
    cfg = BRACKET_CONFIGS[bracket]

    if bracket == 5:
        # Bracket 5 penalizes anything above CMC 2 heavily
        if cmc == 0:
            score += 15.0
        elif cmc == 1:
            score += 10.0
        elif cmc == 2:
            score += 4.0
        else:
            score -= (cmc - 2) * 8.0
    elif bracket == 4:
        if cmc <= 2:
            score += 6.0
        # If this is a big-mana deck, DO NOT penalize 6+ CMC bombs!
        elif cmc >= 6 and not is_big_mana_engine:
            score -= 3.0
    elif bracket <= 2:
        if 4.0 <= cmc <= 7.0:
            score += 4.0

    return score


def assemble_lands(
    conn: sqlite3.Connection,
    allowed_colors: set[str],
    target_lands: int,
    spells: list[dict[str, Any]],
    bracket: int,
    budget: str = "moderate"
) -> list[dict[str, Any]]:
    """Assemble a balanced, legal land base with staples, dual lands, and pip-proportional basics."""
    lands: list[dict[str, Any]] = []
    used_names: set[str] = set()

    def try_add(card_name: str) -> bool:
        if card_name.lower() in used_names:
            return False
        c = db.get_card_by_name(conn, card_name)
        if c and set(c["color_identity"]).issubset(allowed_colors):
            lands.append(c)
            used_names.add(card_name.lower())
            return True
        return False

    # 1. Colorless commander land suite
    if not allowed_colors:
        colorless_staples = [
            "Ancient Tomb", "Urza's Tower", "Urza's Power Plant", "Urza's Mine",
            "Eldrazi Temple", "Eye of Ugin", "Shrine of the Forsaken Gods",
            "Sanctum of Ugin", "War Room", "Reliquary Tower", "Blast Zone",
            "Scavenger Grounds", "Buried Ruin", "Inventors' Fair", "Darksteel Citadel"
        ]
        for name in colorless_staples:
            if len(lands) >= target_lands:
                break
            if budget == "budget" and name in {"Ancient Tomb", "Eye of Ugin"}:
                continue
            try_add(name)

        wastes = db.get_card_by_name(conn, "Wastes")
        while len(lands) < target_lands and wastes:
            lands.append(wastes)
        return lands

    # 2. Multi-color & Mono-color rainbow/utility staples
    rainbow_staples = ["Command Tower", "Exotic Orchard", "Path of Ancestry", "Reflecting Pool"]
    for s in rainbow_staples:
        if len(allowed_colors) >= 2:
            try_add(s)

    # Fast / High-power utility lands for Brackets 4 & 5
    if bracket >= 4 and budget != "budget":
        try_add("Ancient Tomb")
        try_add("City of Brass")
        try_add("Mana Confluence")

    # In-color utility lands & flash lands
    try_add("Emergence Zone")
    try_add("Winding Canyons")

    if "G" in allowed_colors:
        try_add("Boseiju, Who Endures")
        try_add("Yavimaya, Cradle of Growth")
    if "B" in allowed_colors:
        try_add("Urborg, Tomb of Yawgmoth")
        try_add("Bojuka Bog")
        try_add("Leechridden Swamp")
    if "W" in allowed_colors:
        try_add("High Market")
    try_add("Reliquary Tower")

    # Dual lands matching exact color pairs in commander identity
    dual_map = {
        frozenset({"U", "B"}): ["Watery Grave", "Morphic Pool", "Underground River", "Drowned Catacomb", "Polluted Delta"],
        frozenset({"B", "G"}): ["Overgrown Tomb", "Undergrowth Stadium", "Llanowar Wastes", "Woodland Cemetery", "Verdant Catacombs"],
        frozenset({"U", "R"}): ["Steam Vents", "Training Center", "Shivan Reef", "Sulfur Falls", "Scalding Tarn"],
        frozenset({"W", "B"}): ["Godless Shrine", "Vault of Champions", "Caves of Koilos", "Isolated Chapel", "Marsh Flats"],
        frozenset({"R", "G"}): ["Stomping Ground", "Spire Garden", "Karplusan Forest", "Rootbound Crag", "Wooded Foothills"],
        frozenset({"W", "U"}): ["Hallowed Fountain", "Sea of Clouds", "Adarkar Wastes", "Glacial Fortress", "Flooded Strand"],
        frozenset({"B", "R"}): ["Blood Crypt", "Luxury Suite", "Sulfurous Springs", "Dragonskull Summit", "Bloodstained Mire"],
        frozenset({"W", "G"}): ["Temple Garden", "Bountiful Promenade", "Brushland", "Sunpetal Grove", "Windswept Heath"],
        frozenset({"W", "R"}): ["Sacred Foundry", "Spectator Seating", "Battlefield Forge", "Clifftop Retreat", "Arid Mesa"],
        frozenset({"U", "G"}): ["Breeding Pool", "Rejuvenating Springs", "Yavimaya Coast", "Hinterland Harbor", "Misty Rainforest"]
    }

    import itertools
    for pair in itertools.combinations(sorted(allowed_colors), 2):
        pair_set = frozenset(pair)
        if pair_set in dual_map:
            for d in dual_map[pair_set]:
                if len(lands) >= target_lands - len(allowed_colors):
                    break
                if budget == "budget" and ("Catacombs" in d or "Delta" in d or "Tarn" in d or "Heath" in d or "Strand" in d or "Flats" in d or "Mire" in d or "Misty" in d):
                    continue
                try_add(d)

    # 3. Pip-proportional basic land allocation
    pip_counts = {c: 0 for c in allowed_colors}
    for sp in spells:
        cost = sp.get("mana_cost") or ""
        for c in allowed_colors:
            pip_counts[c] += cost.count(f"{{{c}}}")

    total_pips = sum(pip_counts.values()) or 1
    remaining_slots = max(0, target_lands - len(lands))

    basic_lookup = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
    allocated: dict[str, int] = {}
    for c in sorted(allowed_colors):
        prop = pip_counts[c] / total_pips
        count = max(1, round(prop * remaining_slots))
        allocated[c] = count

    diff = sum(allocated.values()) - remaining_slots
    if diff > 0 and len(allowed_colors) > 0:
        max_col = max(allocated, key=allocated.get)
        allocated[max_col] = max(1, allocated[max_col] - diff)
    elif diff < 0 and len(allowed_colors) > 0:
        min_col = min(allocated, key=allocated.get)
        allocated[min_col] += abs(diff)

    for c, cnt in allocated.items():
        b_card = db.get_card_by_name(conn, basic_lookup[c])
        if b_card:
            for _ in range(cnt):
                lands.append(b_card)

    first_basic = db.get_card_by_name(conn, basic_lookup[sorted(allowed_colors)[0]])
    while len(lands) < target_lands and first_basic:
        lands.append(first_basic)

    return lands[:target_lands]


def query_targeted_synergy_candidates(
    conn: sqlite3.Connection,
    allowed_colors: set[str],
    commander: dict[str, Any],
    prompt_tokens: set[str]
) -> list[dict[str, Any]]:
    """Query targeted archetypes from SQLite to ensure high-synergy enablers are included in the pool."""
    cursor = conn.cursor()
    legal_ids = db.get_legal_color_identities(allowed_colors)
    placeholders = ",".join("?" * len(legal_ids))
    cmd_text = f"{commander['name']} {commander.get('oracle_text', '')}".lower()

    targeted: list[dict[str, Any]] = []

    # 1. Pinger / Bleeder enablers if life loss / damage triggers commander
    if "opponent loses" in cmd_text or "damage to each opponent" in cmd_text or "lost life this turn" in cmd_text:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND set_type NOT IN ('funny', 'alchemy')
              AND edhrec_rank IS NOT NULL
              AND (
                oracle_text LIKE '%each opponent loses%'
                OR oracle_text LIKE '%damage to each opponent%'
                OR oracle_text LIKE '%each opponent who doesn%'
                OR oracle_text LIKE '%becomes tapped, each opponent loses%'
                OR oracle_text LIKE '%attacks, each opponent loses%'
              )
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    # 2. Flash enablers if big-mana engine or flash in prompt
    is_big_mana = "adds {c}{c}" in cmd_text or "colorless mana" in cmd_text or "flash" in prompt_tokens
    if is_big_mana:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND set_type NOT IN ('funny', 'alchemy')
              AND edhrec_rank IS NOT NULL
              AND (
                oracle_text LIKE '%as though they had flash%'
                OR oracle_text LIKE '%may cast%flash%'
              )
            ORDER BY edhrec_rank ASC LIMIT 30
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

        # 3. Big Colorless Bombs (CMC 6+)
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND set_type NOT IN ('funny', 'alchemy')
              AND edhrec_rank IS NOT NULL
              AND cmc >= 6
              AND (types LIKE '%artifact%' OR subtypes LIKE '%eldrazi%' OR color_identity = '')
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    # 4. Sacrifice / Aristocrats targeted pool
    if "sacrifice" in cmd_text or "dies" in cmd_text or "aristocrats" in prompt_tokens:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND set_type NOT IN ('funny', 'alchemy')
              AND edhrec_rank IS NOT NULL
              AND (
                oracle_text LIKE '%whenever another creature dies%'
                OR oracle_text LIKE '%whenever a creature you control dies%'
                OR oracle_text LIKE '%sacrifice a creature%'
              )
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    return targeted


def build_deck(
    conn: sqlite3.Connection,
    commander_name: str = "",
    deck_idea: str = "",
    bracket: int = 3,
    budget: str = "moderate",
    color_preference: str | list[str] = "",
    preferred_win_con: str = "combat"
) -> dict[str, Any]:
    """Assemble a tournament-legal 100-card Commander deck meeting all constraints and synergy quotas."""
    bracket = max(1, min(5, int(bracket)))
    cfg = BRACKET_CONFIGS[bracket]
    preferred_win_con = preferred_win_con.lower()
    if preferred_win_con not in WIN_CON_PACKAGES:
        preferred_win_con = "combat"

    pref_colors = resolve_color_identity(color_preference)

    # 1. Resolve Commander
    commander: dict[str, Any] | None = None
    if commander_name.strip():
        commander = db.get_card_by_name(conn, commander_name.strip())
        if not commander:
            raise ValueError(f"Commander '{commander_name}' not found in tournament-legal database.")
    else:
        commander = find_matching_commander(
            conn=conn,
            prompt=deck_idea or preferred_win_con,
            color_pref=pref_colors if pref_colors or color_preference else None,
            win_con=preferred_win_con,
            bracket=bracket
        )
        if not commander:
            commander = db.get_card_by_name(conn, "Belbe, Corrupted Observer")

    if not commander:
        raise ValueError("Could not find or resolve a valid Commander.")

    allowed_colors = set(commander["color_identity"])
    prompt_tokens = {w.lower() for w in re.findall(r"\b\w{3,}\b", deck_idea)}
    prompt_tokens.add(preferred_win_con)

    # 2. Query Card Pools Legal in Commander Identity (General Pool + Targeted Synergy Pool)
    general_pool = db.get_cards_by_identity(conn, allowed_colors, limit=800)
    targeted_pool = query_targeted_synergy_candidates(conn, allowed_colors, commander, prompt_tokens)

    # Deduplicate pool by canonical lowercase name
    combined_pool_map: dict[str, dict[str, Any]] = {}
    for c in targeted_pool + general_pool:
        if c["name_lower"] not in combined_pool_map:
            combined_pool_map[c["name_lower"]] = c

    pool = list(combined_pool_map.values())

    # 3. Filter pool by Bracket & Budget rules
    filtered_pool: list[dict[str, Any]] = []
    for c in pool:
        name_lower = c["name"].lower()
        if name_lower == commander["name"].lower():
            continue

        if not cfg["allow_fast_mana"] and name_lower in FAST_MANA_CARDS:
            continue
        if not cfg["allow_sol_ring"] and name_lower == "sol ring":
            continue
        if not cfg["allow_tutors"] and name_lower in CHEAP_TUTORS:
            continue
        if budget == "budget" and name_lower in EXPENSIVE_RESERVED_LIST:
            continue

        filtered_pool.append(c)

    # 4. Universal Staples & Mandatory Bracket 5 cEDH Meta Staples
    deck_cards: dict[str, dict[str, Any]] = {}
    categorized: dict[str, list[dict[str, Any]]] = {
        "ramp": [], "draw": [], "removal": [], "win_con": [], "synergy": [], "lands": []
    }

    def add_card(card: dict[str, Any], role: str) -> bool:
        nl = card["name"].lower()
        if nl in deck_cards or nl == commander["name"].lower():
            return False
        deck_cards[nl] = card
        categorized[role].append(card)
        return True

    # Format staple ramp (Sol Ring, Arcane Signet) for Brackets 2-5
    if cfg["allow_sol_ring"]:
        for rock_name in ["Sol Ring", "Arcane Signet"]:
            card = db.get_card_by_name(conn, rock_name)
            if card and set(card["color_identity"]).issubset(allowed_colors):
                add_card(card, "ramp")

    if cfg["cedh_meta"]:
        for s_name in CEDH_STAPLES_BY_COLOR["colorless"]:
            card = db.get_card_by_name(conn, s_name)
            if card and set(card["color_identity"]).issubset(allowed_colors):
                role = "ramp" if "stone" in s_name.lower() or "mana" in s_name.lower() or "mox" in s_name.lower() or "sol" in s_name.lower() or "petal" in s_name.lower() or "signet" in s_name.lower() else "draw"
                add_card(card, role)

        for col in allowed_colors:
            for s_name in CEDH_STAPLES_BY_COLOR.get(col, []):
                card = db.get_card_by_name(conn, s_name)
                if card and set(card["color_identity"]).issubset(allowed_colors):
                    roles = classify_card_role(card)
                    role = "ramp" if "ramp" in roles else ("draw" if "draw" in roles else "removal")
                    add_card(card, role)

    # 5. Add Win-Condition Package (4 cards)
    for pkg_item in WIN_CON_PACKAGES[preferred_win_con]:
        if len(categorized["win_con"]) >= cfg["target_win_con"]:
            break
        if pkg_item["colors"].issubset(allowed_colors):
            card = db.get_card_by_name(conn, pkg_item["name"])
            if card:
                nl = card["name"].lower()
                if not cfg["allow_combos"] and preferred_win_con == "combo" and nl in {"thassa's oracle", "demonic consultation", "underworld breach"}:
                    continue
                add_card(card, "win_con")

    # 6. Fill Role Quotas from Filtered Pool
    scored_candidates = []
    for c in filtered_pool:
        if c["name"].lower() in deck_cards:
            continue
        roles = classify_card_role(c)
        if "land" in roles:
            continue
        score = score_synergy(c, commander, prompt_tokens, preferred_win_con, bracket)
        scored_candidates.append((score, c, roles))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    # Fill Ramp quota
    for score, card, roles in scored_candidates:
        if len(categorized["ramp"]) >= cfg["target_ramp"]:
            break
        if "ramp" in roles:
            add_card(card, "ramp")

    # Fill Draw quota
    for score, card, roles in scored_candidates:
        if len(categorized["draw"]) >= cfg["target_draw"]:
            break
        if "draw" in roles:
            add_card(card, "draw")

    # Fill Removal quota
    for score, card, roles in scored_candidates:
        if len(categorized["removal"]) >= cfg["target_removal"]:
            break
        if "removal" in roles:
            add_card(card, "removal")

    # Fill Synergy core with top remaining cards
    target_nonlands = 99 - cfg["target_lands"]
    current_nonlands = sum(len(v) for k, v in categorized.items() if k != "lands")

    for score, card, roles in scored_candidates:
        if current_nonlands >= target_nonlands:
            break
        if add_card(card, "synergy"):
            current_nonlands += 1

    # 7. Assemble Lands (Exactly target_lands)
    spells = [c for c in deck_cards.values() if "land" not in classify_card_role(c)]
    lands = assemble_lands(
        conn=conn,
        allowed_colors=allowed_colors,
        target_lands=cfg["target_lands"],
        spells=spells,
        bracket=bracket,
        budget=budget
    )
    categorized["lands"] = lands

    # 8. Compute Deck Statistics & Hypergeometric Consistency
    full_decklist_cards = [commander] + list(deck_cards.values()) + lands
    nonland_spells = [c for c in full_decklist_cards if "land" not in classify_card_role(c) and c["name"] != commander["name"]]

    avg_cmc = round(sum(c.get("cmc", 0.0) for c in nonland_spells) / max(1, len(nonland_spells)), 2)

    mana_curve: dict[str, int] = {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6+": 0}
    for c in nonland_spells:
        cmc_val = int(c.get("cmc", 0))
        if cmc_val >= 6:
            mana_curve["6+"] += 1
        else:
            mana_curve[str(cmc_val)] += 1

    land_count = len(lands)
    ramp_count = len(categorized["ramp"])
    total_deck = 1 + len(spells) + len(lands)
    p_3_lands_t3 = hypergeometric_cdf_ge(total_deck, 9, land_count, 3) * 100.0
    p_turn2_ramp = calculate_joint_consistency(total_deck, 8, land_count, 2, ramp_count, 1, 0, 0) * 100.0
    consistency = {
        "p_3_lands_turn_3": f"{p_3_lands_t3:.1f}%",
        "p_land_and_ramp_turn_2": f"{p_turn2_ramp:.1f}%"
    }

    engine_dossier = detect_resource_profile(commander)

    # Detailed Win Condition & Engine Walkthrough
    cmd_name = commander["name"]
    cmd_oracle = (commander.get("oracle_text") or "").lower()

    if "adds {c}{c}" in cmd_oracle or "belbe" in cmd_name.lower():
        win_con_exec = (
            f"⚡ Belbe Operational Engine: Deploys cheap 1–2 CMC symmetric bleeders (e.g. Creeping Bloodsucker, "
            f"Sanctum of Stone Fangs, Night Market Lookout, Thornbow Archer) to reliably trigger Belbe for up to 6 {{C}} "
            f"colorless mana. Leverages flash enablers (Liberator, Urza's Battlethopter, Shimmer Myr, Vedalken Orrery) "
            f"to consume mana generated during opponents' postcombat main phases, casting massive colorless bombs "
            f"(Portal to Phyrexia, Void Winnower, Wurmcoil Engine, Eldrazi Titans) at instant speed."
        )
    else:
        win_con_exec = (
            f"Executes victory through {preferred_win_con.upper()} using key cards: "
            f"{', '.join(c['name'] for c in categorized['win_con'][:3])}. "
            f"Engine catalyst: {engine_dossier.get('catalyst', 'Resource acceleration')}. "
            f"Tuned for Bracket {bracket} ({cfg['name']})."
        )

    # Exportable text decklist
    text_lines = [f"// Commander", f"1 {commander['name']}", ""]
    for role, group in categorized.items():
        if not group:
            continue
        text_lines.append(f"// {role.capitalize()} ({len(group)})")
        counts: dict[str, int] = {}
        for c in group:
            counts[c["name"]] = counts.get(c["name"], 0) + 1
        for name, cnt in sorted(counts.items()):
            text_lines.append(f"{cnt} {name}")
        text_lines.append("")

    export_decklist = "\n".join(text_lines).strip()

    return {
        "commander": commander,
        "deck_idea": deck_idea,
        "bracket": {
            "tier": bracket,
            "name": cfg["name"],
            "description": cfg["description"]
        },
        "budget": budget,
        "preferred_win_con": preferred_win_con,
        "win_con_execution": win_con_exec,
        "total_cards": 1 + len(spells) + len(lands),
        "stats": {
            "card_count": 1 + len(spells) + len(lands),
            "avg_cmc": avg_cmc,
            "mana_curve": mana_curve,
            "roles": {
                "lands": len(lands),
                "ramp": len(categorized["ramp"]),
                "draw": len(categorized["draw"]),
                "removal": len(categorized["removal"]),
                "win_con": len(categorized["win_con"]),
                "synergy": len(categorized["synergy"])
            },
            "hypergeometric_consistency": consistency
        },
        "engine_dossier": engine_dossier,
        "categories": {
            "commander": [commander],
            "ramp": categorized["ramp"],
            "draw": categorized["draw"],
            "removal": categorized["removal"],
            "win_con": categorized["win_con"],
            "synergy": categorized["synergy"],
            "lands": categorized["lands"]
        },
        "decklist_text": export_decklist
    }
