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
    from scripts import deck_exporter
    from scripts.card_swapper import get_swap_candidates
except ImportError:
    import db
    from hybrid_engine import detect_resource_profile
    from math_utils import hypergeometric_cdf_ge, calculate_joint_consistency
    import deck_exporter
    from card_swapper import get_swap_candidates

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
    "mox diamond", "chrome mox", "lotus petal", "mox opal",
    "mana vault", "grim monolith", "ancient tomb", "lion's eye diamond"
}

NO_FAST_MANA_CARDS = FAST_MANA_CARDS | {
    "sol ring", "ancient tomb", "mox diamond", "chrome mox",
    "lotus petal", "mox opal", "mana vault", "grim monolith",
    "lion's eye diamond", "jeweled lotus", "mana crypt", "mox amber"
}

CHEAP_TUTORS = {
    "demonic tutor", "vampiric tutor", "imperial seal", "worldly tutor",
    "mystical tutor", "enlightened tutor", "gamble", "personal tutor"
}

NO_TUTORS_CARDS = CHEAP_TUTORS | {
    "diabolic intent", "grim tutor", "sylvan tutor", "merchant scroll",
    "wishclaw talisman", "tainted pact"
}

EXPENSIVE_RESERVED_LIST = {
    "timetwister", "gaea's cradle", "tabernacle at pendrell vale",
    "candelabra of tawnos", "mishra's workshop", "bazaar of baghdad", "underground sea",
    "volcanic island", "tropical island", "tundra", "bayou", "scrubland", "taiga",
    "badlands", "savannah", "plateau", "mox diamond", "lion's eye diamond", "gilded drake"
}

NO_FREE_SPELLS_CARDS = {
    "fierce guardianship", "force of will", "deflecting swat", "deadly rollick",
    "flawless maneuver", "force of negation", "pact of negation", "mental misstep",
    "mindbreak trap", "misdirection", "obscuring haze", "submerge", "snuff out",
    "force of vigor", "force of despair", "commandeer", "daze", "foil",
    "flare of denial", "flare of malice", "flare of cultivation", "flare of fortitude",
    "flare of duplication", "solitude", "fury", "endurance", "grief", "subtlety"
}

NO_STAX_CARDS = {
    "winter orb", "static orb", "stasis", "armageddon", "blood moon",
    "back to basics", "ruination", "smokestack", "trinisphere",
    "magus of the moon", "ravages of war", "jokulhaups", "obliterate",
    "decree of annihilation", "cataclysm", "sunder", "tangle wire",
    "orb of dreams", "hokori, dust drinker", "rising waters",
    "rule of law", "archon of emeria", "deafening silence", "drannith magistrate",
    "knowledge pool", "possibility storm", "damping sphere", "collector ouphe",
    "null rod", "stony silence", "rest in peace", "cursed totem", "chalice of the void",
    "lodestone golem", "sphere of resistance", "thorn of amethyst"
}

FETCHLANDS = {
    "polluted delta", "flooded strand", "bloodstained mire", "wooded foothills",
    "windswept heath", "marsh flats", "scalding tarn", "verdant catacombs",
    "arid mesa", "misty rainforest", "prismatic vista"
}

SHOCKLANDS = {
    "hallowed fountain", "watery grave", "blood crypt", "stomping ground",
    "temple garden", "godless shrine", "steam vents", "overgrown tomb",
    "sacred foundry", "breeding pool"
}

HIGH_VALUE_STAPLES = {
    "the one ring", "rhystic study", "smothering tithe", "esper sentinel",
    "cyclonic rift", "dockside extortionist", "mana drain", "demonic tutor",
    "vampiric tutor", "imperial seal", "sylvan library", "craterhoof behemoth",
    "bolas's citadel", "teferi's protection", "the meathook massacre", "meathook massacre",
    "sheoldred, the apocalypse", "orcish bowmasters", "trouble in pairs",
    "the great henge", "great henge", "parallel lives", "doubling season",
    "anointed procession", "urza's saga", "ancient tomb", "cavern of souls",
    "mana confluence", "city of brass", "boseiju, who endures", "field of the dead",
    "jeska's will", "wheel of fortune", "roaming throne", "finale of devastation",
    "consecrated sphinx", "grand abolisher", "ranger-captain of eos", "dauthi voidwalker",
    "opposition agent", "deflecting swat", "fierce guardianship", "deadly rollick",
    "force of will", "force of negation", "flawless maneuver", "pact of negation",
    "mindbreak trap", "mana vault", "grim monolith", "mox diamond", "chrome mox",
    "mox opal", "lotus petal", "lion's eye diamond"
}

DISALLOWED_LOW_BRACKET_COMBOS = {
    "dual caster mage", "dualcaster mage", "twinflame", "heliod, sun-crowned",
    "walking ballista", "thassa's oracle", "demonic consultation", "underworld breach",
    "kiki-jiki, mirror breaker", "zealous conscripts", "exquisite blood", "sanguine bond",
    "lion's eye diamond", "brain freeze", "tainted pact", "food chain", "squee, the immortal",
    "eternal scourge", "misthollow griffin", "mindcrank", "bloodchief ascension",
    "isochron scepter", "dramatic reversal", "chain of smog", "professor onyx",
    "abdel adrian, gorion's ward", "worldgorger dragon", "animate dead",
    "mikaeus, the unhallowed", "triskelion", "rings of brighthearth", "basalt monolith",
    "painter's servant", "grindstone"
}

COMPACT_COMBO_CARDS = DISALLOWED_LOW_BRACKET_COMBOS

BASIC_LANDS = {"plains", "island", "swamp", "mountain", "forest", "wastes"}


def is_card_excluded(
    card_name: str,
    budget: str = "moderate",
    house_rules: set[str] | None = None,
    custom_bans: set[str] | None = None,
    bracket: int = 3
) -> bool:
    """Check if a card is prohibited by budget constraints, house rules, or custom bans."""
    name_lower = card_name.strip().lower()

    # Basic lands are never banned (essential game pieces for 100-card invariant)
    if name_lower in BASIC_LANDS:
        return False

    # 1. Custom card bans
    if custom_bans and name_lower in custom_bans:
        return True

    # 2. House rules enforcement
    if house_rules:
        if "no_fast_mana" in house_rules and name_lower in NO_FAST_MANA_CARDS:
            return True
        if "no_combos" in house_rules and name_lower in COMPACT_COMBO_CARDS:
            return True
        if "no_free_spells" in house_rules and name_lower in NO_FREE_SPELLS_CARDS:
            return True
        if "no_stax" in house_rules and name_lower in NO_STAX_CARDS:
            return True
        if "no_tutors" in house_rules and name_lower in NO_TUTORS_CARDS:
            return True

    # 3. Budget tier enforcement
    if budget == "ultra_budget":
        if name_lower in FETCHLANDS:
            return True
        if name_lower in SHOCKLANDS:
            return True
        if name_lower in EXPENSIVE_RESERVED_LIST:
            return True
        if name_lower in NO_FAST_MANA_CARDS:
            return True
        if name_lower in HIGH_VALUE_STAPLES:
            return True
    elif budget == "budget":
        if name_lower in FETCHLANDS:
            return True
        if name_lower in EXPENSIVE_RESERVED_LIST:
            return True

    return False

# --- CEDH META STAPLES BY COLOR (BRACKET 5 ONLY) ---
# Note: Format-banned cards (Mana Crypt, Jeweled Lotus, Dockside, Nadu) are strictly omitted.
CEDH_STAPLES_BY_COLOR: dict[str, list[str]] = {
    "colorless": [
        "Mox Diamond", "Chrome Mox", "Lotus Petal", "Sol Ring", "Grim Monolith",
        "Mana Vault", "Mox Opal", "Fellwar Stone", "Arcane Signet", "The One Ring"
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


def extract_strategy_intents(deck_idea: str, win_con: str = "") -> dict[str, Any]:
    """Semantic strategy parser extracting normalized intents, themes, and mechanics."""
    raw_idea = (deck_idea or "").strip()
    raw_win_con = (win_con or "").strip().lower()

    # Normalize text: lowercase and strip smart quotes / apostrophes
    normalized = raw_idea.lower()
    normalized = normalized.replace("’", "'")
    normalized_no_apos = normalized.replace("'", "")

    # Tokenize words (length >= 2)
    words = re.findall(r"\b[a-z0-9\+\-\/]{2,}\b", normalized_no_apos)

    # Stemming and morphological normalization map
    stemmed_tokens = set()
    for w in words:
        if w in {"planeswalkers", "planeswalker"}:
            stemmed_tokens.add("planeswalker")
        elif w in {"counters", "counter"}:
            stemmed_tokens.add("counter")
        elif w in {"tokens", "token"}:
            stemmed_tokens.add("token")
        elif w in {"turns", "turn"}:
            stemmed_tokens.add("turn")
        elif w in {"lands", "land"}:
            stemmed_tokens.add("land")
        elif w in {"flickers", "flickering", "blinks", "blinking"}:
            stemmed_tokens.add("blink")
        elif w in {"sacrifices", "sacrificing", "aristocrats"}:
            stemmed_tokens.add("sacrifice")
        elif w in {"enchantments", "enchantresses", "enchantress"}:
            stemmed_tokens.add("enchantress")
        elif w in {"spellslingers", "spellslinging"}:
            stemmed_tokens.add("spellslinger")
        elif w.startswith("proliferat"):
            stemmed_tokens.add("proliferate")
        else:
            stemmed_tokens.add(w)

    if raw_win_con:
        stemmed_tokens.add(raw_win_con)

    # 1. Planeswalker Theme
    is_planeswalker_theme = bool(
        "planeswalker" in stemmed_tokens or
        "superfriends" in normalized_no_apos or
        "loyalty" in normalized_no_apos or
        "planeswalker" in normalized_no_apos
    )

    # 2. Multi-Activation & Timing Enablers
    multi_activation_patterns = [
        "multiple times", "twice", "additional time", "additional times",
        "every turn", "everyones turn", "everyone turn", "opponents turn",
        "opponent turn", "each turn", "instant speed", "flash",
        "on each player", "each players turn", "each player's turn",
        "any player turn", "any players turn", "all turns"
    ]
    is_multi_activation = any(p in normalized_no_apos for p in multi_activation_patterns)

    # 3. Stax
    stax_patterns = ["stax", "rule of law", "tax", "resource denial", "hatebears", "lockdown"]
    is_stax = raw_win_con == "stax" or any(p in normalized_no_apos for p in stax_patterns)

    # 4. Counters
    is_counters = bool(
        "counter" in stemmed_tokens or "proliferate" in stemmed_tokens or "+1/+1" in normalized_no_apos or
        "proliferat" in normalized_no_apos or "counter" in normalized_no_apos
    )

    # 5. Tokens
    is_tokens = bool(
        "token" in stemmed_tokens or "populate" in normalized_no_apos or "go-wide" in normalized_no_apos
    )

    # 6. Sacrifice
    is_sacrifice = bool(
        "sacrifice" in stemmed_tokens or "aristocrats" in normalized_no_apos or "dies" in stemmed_tokens
    )

    # 7. Enchantress
    is_enchantress = bool(
        "enchantress" in stemmed_tokens or "enchantment" in normalized_no_apos or "constellation" in normalized_no_apos
    )

    # 8. Spellslinger
    is_spellslinger = bool(
        "spellslinger" in stemmed_tokens or "storm" in stemmed_tokens or "magecraft" in normalized_no_apos
    )

    # 9. Blink
    is_blink = bool(
        "blink" in stemmed_tokens or "flicker" in normalized_no_apos
    )

    # 10. Landfall
    is_landfall = bool(
        "landfall" in normalized_no_apos or "land" in stemmed_tokens
    )

    return {
        "is_planeswalker_theme": is_planeswalker_theme,
        "is_multi_activation": is_multi_activation,
        "is_stax": is_stax,
        "is_counters": is_counters,
        "is_tokens": is_tokens,
        "is_sacrifice": is_sacrifice,
        "is_enchantress": is_enchantress,
        "is_spellslinger": is_spellslinger,
        "is_blink": is_blink,
        "is_landfall": is_landfall,
        "tokens": stemmed_tokens,
        "raw_text": raw_idea,
        "normalized_text": normalized_no_apos
    }


def generate_planeswalker_blueprint(
    commanders: list[dict[str, Any]],
    deck_cards: dict[str, dict[str, Any]],
    preferred_win_con: str,
    bracket: int,
    intents: dict[str, Any]
) -> str:
    """Structure win_con_execution as a detailed 5-section Game State Blueprint."""
    # 1. Identify multi-activation & timing enablers present in deck
    enablers_all = [
        "The Chain Veil", "Oath of Teferi", "Teferi, Temporal Archmage",
        "Teferi, Master of Time", "Ichormoon Gauntlet", "Displacer Kitten",
        "Rings of Brighthearth", "Lithoform Engine"
    ]
    present_enablers = [name for name in enablers_all if name.lower() in deck_cards]

    # 2. Identify planeswalkers present
    deck_pws = [c for c in deck_cards.values() if "planeswalker" in c.get("type_line", "").lower()]
    deck_pws.sort(key=lambda c: c.get("edhrec_rank") or 99999)
    pw_names = [c["name"] for c in deck_pws[:6]]

    # 3. Identify stax pieces present
    stax_all = [
        "Rule of Law", "Archon of Emeria", "Drannith Magistrate",
        "Deafening Silence", "Dauthi Voidwalker", "Opposition Agent", "Aven Mindcensor"
    ]
    present_stax = [name for name in stax_all if name.lower() in deck_cards]

    cmd_display = " // ".join(c["name"] for c in commanders) if len(commanders) == 1 else " & ".join(c["name"] for c in commanders)
    bridge_mention = "the Prismatic Bridge" if "Esika" in cmd_display else cmd_display

    # Section 1: Tactical Concept
    if intents.get("is_stax"):
        concept_title = "⚡ Tactical Concept: Planeswalker Multi-Activation & Asymmetric Stax Lock"
    else:
        concept_title = f"⚡ Tactical Concept: Planeswalker Multi-Activation & {preferred_win_con.capitalize()} Engine"

    # Section 2: Game State Engine
    enabler_list_str = ", ".join(present_enablers) if present_enablers else "The Chain Veil, Oath of Teferi, Teferi, Temporal Archmage, and Teferi, Master of Time"
    engine_str = (
        f"⚙️ Game State Engine: Assembles the multi-activation engine using {enabler_list_str}. "
        f"These key pieces unlock compounding value by granting multiple loyalty activations per turn and unlocking "
        f"instant-speed loyalty activations during each opponent's turn. Activating planeswalkers on everyone's turn "
        f"accelerates loyalty velocity up to 4x per round of turns, achieving game-winning emblems in a single turn cycle."
    )

    # Section 3: Planeswalker Arsenal
    if pw_names:
        arsenal_str = (
            f"🎯 Planeswalker Arsenal: Anchored by {len(deck_pws)} planeswalkers, featuring {', '.join(pw_names)}. "
            f"Each planeswalker generates continuous card advantage, board control, and lethal ultimate abilities."
        )
    else:
        arsenal_str = "🎯 Planeswalker Arsenal: High-density superfriends suite commanding the battlefield."

    # Section 4: Win Condition Synergy
    if intents.get("is_stax"):
        stax_str = f" ({', '.join(present_stax)})" if present_stax else ""
        win_con_str = (
            f"🛡️ Win Condition Synergy: Asymmetric Stax Chokehold{stax_str}. Under Rule of Law and Archon of Emeria, "
            f"opponents can only cast one spell per turn, crippling combo attempts and storm velocity. "
            f"Crucially, Planeswalker loyalty abilities are activated abilities on existing permanents—completely bypassing "
            f"spell-casting restrictions. While opponents remain choked under stax, your planeswalkers generate repeated "
            f"value across every player's turn until ticking into game-ending ultimate emblems."
        )
    else:
        win_con_str = (
            f"🛡️ Win Condition Synergy: Converts loyalty acceleration directly into victory through {preferred_win_con.upper()}, "
            f"utilizing multi-activation triggers to dominate the board while maintaining defensive superiority."
        )

    # Section 5: Turn-by-Turn Game Progression
    enabler_example = present_enablers[0] if present_enablers else "The Chain Veil"
    progression_str = (
        f"📈 Turn-by-Turn Game Progression:\n"
        f"  • Turns 1–3 (Setup): Lay down mana acceleration and asymmetric stax locks.\n"
        f"  • Turns 4–5 (Engine Deployment): Deploy {bridge_mention} / Planeswalkers alongside {enabler_example} or Oath of Teferi.\n"
        f"  • Endgame (Lockdown & Ultimates): Activate loyalty abilities 2–4 times across every opponent's turn, ticking up to game-ending ultimate emblems (Teferi, Liliana, Chandra, Nicol Bolas) while opponents remain choked under stax."
    )

    return f"{concept_title}\n\n{engine_str}\n\n{arsenal_str}\n\n{win_con_str}\n\n{progression_str}"


def find_matching_commander(
    conn: sqlite3.Connection,
    prompt: str,
    color_pref: set[str] | None = None,
    win_con: str = "combat",
    bracket: int = 3,
    custom_bans: set[str] | None = None,
    intents: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Select the best matching legendary creature from cards.db based on prompt, colors, and bracket."""
    cursor = conn.cursor()
    color_filter = ""
    params: list[Any] = []

    if intents is None:
        intents = extract_strategy_intents(prompt, win_con)

    if color_pref is not None:
        legal_identities = db.get_legal_color_identities(color_pref)
        placeholders = ",".join("?" * len(legal_identities))
        color_filter = f"AND color_identity IN ({placeholders})"
        params.extend(legal_identities)

    sql = f"""
        SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
               subtypes, colors, color_identity, oracle_text, flavor_text,
               set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
               is_commander, commander_legal
        FROM cards
        WHERE is_commander = 1
          AND commander_legal = 1
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
    prompt_tokens.update(intents.get("tokens", set()))
    prompt_tokens.add(win_con.lower())

    best_card: dict[str, Any] | None = None
    best_score = -1e9

    for cand in candidates:
        if custom_bans and cand["name_lower"] in custom_bans:
            continue
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

        # Superfriends / Planeswalker Commander Boost
        if intents.get("is_planeswalker_theme"):
            superfriends_commanders = {
                "sisay, weatherlight captain",
                "atraxa, praetors' voice",
                "commodore guff",
                "carth the lion",
                "esika, god of the tree // the prismatic bridge",
                "teferi, temporal archmage"
            }
            if cand["name_lower"] in superfriends_commanders or any(s in cand["name_lower"] for s in ["esika", "prismatic bridge", "commodore guff", "carth the lion", "atraxa, praetors"]):
                score += 150.0
            if "planeswalker" in text or "loyalty" in text:
                score += 80.0
            if "proliferate" in text:
                score += 40.0

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
    bracket: int,
    intents: dict[str, Any] | None = None
) -> float:
    """Calculate objective synergy score between a card and the commander/theme."""
    name = card["name"].lower()
    oracle = card.get("oracle_text", "").lower()
    type_line = card.get("type_line", "").lower()
    types = [t.lower() for t in card.get("types", [])]
    subtypes = [s.lower() for s in card.get("subtypes", [])]
    cmd_name = commander["name"].lower()
    cmd_text = f"{commander['name']} {commander.get('oracle_text', '')}".lower()
    cmd_subtypes = [s.lower() for s in commander.get("subtypes", [])]
    cmc = card.get("cmc", 3.0)

    score = 0.0

    # 0. Planeswalker Theme & Multi-Activation Engine
    is_pw_theme = (intents.get("is_planeswalker_theme") if intents else ("planeswalker" in prompt_tokens or "superfriends" in prompt_tokens))
    is_multi_act = (intents.get("is_multi_activation") if intents else False)

    if is_pw_theme or is_multi_act:
        # A. All Planeswalkers (+55.0)
        if "planeswalker" in type_line:
            score += 55.0

        # B. Multi-activation & timing enablers (+75.0)
        multi_names = {
            "the chain veil", "oath of teferi", "ichormoon gauntlet", "displacer kitten",
            "teferi, temporal archmage", "teferi, master of time", "rings of brighthearth",
            "lithoform engine"
        }
        if name in multi_names or any(m in name for m in ["chain veil", "oath of teferi", "ichormoon", "displacer kitten"]):
            score += 75.0
        elif "loyalty abilities" in oracle or ("planeswalker" in oracle and ("activate" in oracle or "additional" in oracle)):
            score += 75.0

        # C. Proliferate / Counter Doubling (+45.0)
        prolif_names = {
            "deepglow skate", "doubling season", "vorinclex, monstrous raider",
            "flux channeler", "evolution sage", "inexorable tide", "karn's bastion",
            "contagion engine", "interplanar beacon"
        }
        if name in prolif_names or "proliferate" in oracle or "double the number of each kind of counter" in oracle:
            score += 45.0

        # D. Sweepers / Pillowfort protection (+35.0)
        prot_names = {
            "toxic deluge", "supreme verdict", "damnation", "cyclonic rift",
            "ghostly prison", "propaganda", "sphere of safety"
        }
        if name in prot_names or "creatures can't attack you" in oracle or ("destroy all creatures" in oracle and ("instant" in type_line or "sorcery" in type_line)):
            score += 35.0

    # Detect Big-Mana / Colorless Engine (e.g., Belbe, Zhulodok, Rakdos, Kozilek)
    is_big_mana_engine = (
        "adds {c}{c}" in cmd_text or "colorless mana" in cmd_text or
        "belbe" in cmd_name or "zhulodok" in cmd_name or "big mana" in prompt_tokens
    )

    # 1. Group Slug / Symmetric Bleed / Damage Catalysts
    if "opponent loses" in cmd_text or "damage to each opponent" in cmd_text or "lost life this turn" in cmd_text or "bleed" in prompt_tokens:
        if (
            "each opponent loses" in oracle or
            "damage to each opponent" in oracle or
            "each player loses" in oracle or
            "attacks, each opponent loses" in oracle or
            "becomes tapped, each opponent loses" in oracle or
            "deals 1 damage to each opponent" in oracle or
            "each opponent who doesn" in oracle or
            "deals 2 damage to each" in oracle
        ):
            score += 55.0
            # Extra bonus for cheap 1-2 CMC enablers that trigger on curve
            if cmc <= 2:
                score += 25.0

    # 2. Flash enablers for timing manipulation and phase mana consumption
    if is_big_mana_engine or "flash" in prompt_tokens:
        if (
            "as though they had flash" in oracle or
            "may cast spells this turn as though they had flash" in oracle or
            "may cast creature spells this turn as though they had flash" in oracle or
            ("flash" in oracle and ("colorless" in oracle or "artifact" in oracle)) or
            "flash" in card.get("keywords", [])
        ):
            score += 50.0

        # Big Colorless Bombs (CMC 6+)
        if cmc >= 6 and ("artifact" in types or "eldrazi" in subtypes or not card.get("color_identity")):
            score += 45.0

    # 3. Enchantress / Constellation
    if "enchantment" in cmd_text or "aura" in cmd_text or "enchantress" in prompt_tokens:
        if "enchantment" in type_line:
            score += 25.0
            if cmc <= 3:
                score += 15.0
        if "constellation" in oracle or "whenever you cast an enchantment" in oracle or "whenever an enchantment enters" in oracle:
            score += 45.0

    # 4. Blink / Flicker / ETB
    if ("exile" in cmd_text and ("return" in cmd_text or "enters" in cmd_text)) or "blink" in prompt_tokens or "flicker" in prompt_tokens:
        if ("when" in oracle or "whenever" in oracle) and ("enters the battlefield" in oracle or "enters" in oracle):
            score += 30.0
        if "exile target" in oracle and "return" in oracle:
            score += 40.0

    # 5. Spellslinger / Storm / Magecraft
    if "instant" in cmd_text or "sorcery" in cmd_text or "magecraft" in cmd_text or "spellslinger" in prompt_tokens:
        if "instant" in type_line or "sorcery" in type_line:
            score += 25.0
            if cmc <= 2:
                score += 15.0
        if "magecraft" in oracle or "whenever you cast an instant or sorcery" in oracle or "copy" in oracle:
            score += 40.0

    # 6. +1/+1 Counters / Proliferate
    if "+1/+1 counter" in cmd_text or "proliferate" in cmd_text or "counters" in prompt_tokens:
        if "+1/+1 counter" in oracle:
            score += 30.0
        if "proliferate" in oracle or "doubling season" in oracle or "hardened scales" in oracle:
            score += 40.0

    # 7. Tokens / Go-Wide
    if ("token" in cmd_text and "create" in cmd_text) or "token" in prompt_tokens:
        if "create" in oracle and "token" in oracle:
            score += 30.0
        if "populate" in oracle or "doubling season" in oracle or "parallel lives" in oracle or "anointed procession" in oracle:
            score += 40.0

    # 8. Landfall / Mass Lands
    if "land enters" in cmd_text or "additional land" in cmd_text or "landfall" in cmd_text or "landfall" in prompt_tokens:
        if "landfall" in oracle or "whenever a land enters" in oracle:
            score += 40.0
        if "play an additional land" in oracle or "search your library for a land" in oracle:
            score += 30.0

    # 9. Sacrifice / Aristocrats
    if "sacrifice" in cmd_text or "dies" in cmd_text or "dying" in cmd_text or "aristocrats" in prompt_tokens:
        if "sacrifice" in oracle:
            score += 25.0
        if "dies" in oracle or "dying" in oracle or "whenever another creature dies" in oracle:
            score += 35.0

    # 10. Graveyard / Reanimation
    if "graveyard" in cmd_text or "reanimate" in prompt_tokens:
        if "return" in oracle and "graveyard" in oracle:
            score += 30.0
        if "reanimate" in oracle or "from your graveyard" in oracle:
            score += 35.0

    # 11. Artifacts / Equipment / Voltron
    if ("artifact" in cmd_text or "equipment" in cmd_text) or win_con == "voltron":
        if "equipment" in type_line or "equip" in oracle:
            score += 30.0
        elif "artifact" in type_line:
            score += 20.0

    # 12. Shared Subtype / Typal Bonus
    for s in cmd_subtypes:
        if s not in {"legendary", "creature", "artifact"} and len(s) > 2:
            if s in subtypes:
                score += 30.0
            if f"all {s}" in oracle or f"other {s}" in oracle or f"whenever a {s}" in oracle:
                score += 40.0

    # 13. User prompt token matching
    for tok in prompt_tokens:
        if tok in name:
            score += 15.0
        elif tok in oracle:
            score += 12.0
        elif tok in type_line:
            score += 10.0

    # 14. Format ubiquity & quality via EDHREC rank
    rank = card.get("edhrec_rank")
    if rank:
        score += max(0.0, (15000.0 - rank) / 1000.0)

    # 15. Mana curve scoring based on bracket
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
    budget: str = "moderate",
    house_rules: set[str] | None = None,
    custom_bans: set[str] | None = None,
    intents: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Assemble a balanced, legal land base with staples, dual lands, and pip-proportional basics."""
    lands: list[dict[str, Any]] = []
    used_names: set[str] = set()

    def try_add(card_name: str) -> bool:
        if card_name.lower() in used_names:
            return False
        if is_card_excluded(card_name, budget=budget, house_rules=house_rules, custom_bans=custom_bans, bracket=bracket):
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
            if (bracket < 4 or budget in {"budget", "ultra_budget"}) and name in {"Ancient Tomb", "Eye of Ugin"}:
                continue
            try_add(name)

        wastes = db.get_card_by_name(conn, "Wastes")
        while len(lands) < target_lands and wastes:
            lands.append(wastes)
        return lands[:target_lands]

    # 2. Multi-color & Mono-color rainbow/utility staples
    rainbow_staples = ["Command Tower", "Exotic Orchard", "Path of Ancestry", "Reflecting Pool"]
    for s in rainbow_staples:
        if len(allowed_colors) >= 2:
            try_add(s)

    # Fast / High-power utility lands for Brackets 4 & 5
    if bracket >= 4 and budget not in {"budget", "ultra_budget"}:
        try_add("Ancient Tomb")
        try_add("City of Brass")
        try_add("Mana Confluence")

    # In-color utility lands & flash lands
    try_add("Emergence Zone")
    try_add("Winding Canyons")

    if budget not in {"ultra_budget"}:
        if "G" in allowed_colors:
            try_add("Boseiju, Who Endures")
            try_add("Yavimaya, Cradle of Growth")
        if "B" in allowed_colors:
            try_add("Urborg, Tomb of Yawgmoth")
            try_add("Bojuka Bog")
            try_add("Leechridden Swamp")
        if "W" in allowed_colors:
            try_add("High Market")
    else:
        if "B" in allowed_colors:
            try_add("Bojuka Bog")
    try_add("Reliquary Tower")

    # Thematic utility lands for Planeswalker & Counter strategies
    if intents and (intents.get("is_planeswalker_theme") or intents.get("is_counters")):
        try_add("Karn's Bastion")
        try_add("Interplanar Beacon")

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

    # Budget taplands & bounce lands
    bounce_map = {
        frozenset({"U", "B"}): "Dimir Aqueduct",
        frozenset({"B", "G"}): "Golgari Rot Farm",
        frozenset({"U", "R"}): "Izzet Boilerworks",
        frozenset({"W", "B"}): "Orzhov Basilica",
        frozenset({"R", "G"}): "Gruul Turf",
        frozenset({"W", "U"}): "Azorius Chancery",
        frozenset({"B", "R"}): "Rakdos Carnarium",
        frozenset({"W", "G"}): "Selesnya Sanctuary",
        frozenset({"W", "R"}): "Boros Garrison",
        frozenset({"U", "G"}): "Simic Growth Chamber"
    }

    temple_map = {
        frozenset({"U", "B"}): "Temple of Deceit",
        frozenset({"B", "G"}): "Temple of Malady",
        frozenset({"U", "R"}): "Temple of Epiphany",
        frozenset({"W", "B"}): "Temple of Silence",
        frozenset({"R", "G"}): "Temple of Abandon",
        frozenset({"W", "U"}): "Temple of Enlightenment",
        frozenset({"B", "R"}): "Temple of Malice",
        frozenset({"W", "G"}): "Temple of Plenty",
        frozenset({"W", "R"}): "Temple of Triumph",
        frozenset({"U", "G"}): "Temple of Mystery"
    }

    gain_map = {
        frozenset({"U", "B"}): "Dismal Backwater",
        frozenset({"B", "G"}): "Jungle Hollow",
        frozenset({"U", "R"}): "Swiftwater Cliffs",
        frozenset({"W", "B"}): "Scoured Barrens",
        frozenset({"R", "G"}): "Rugged Highlands",
        frozenset({"W", "U"}): "Tranquil Cove",
        frozenset({"B", "R"}): "Bloodfell Caves",
        frozenset({"W", "G"}): "Blossoming Sands",
        frozenset({"W", "R"}): "Wind-Scarred Crag",
        frozenset({"U", "G"}): "Thornwood Falls"
    }

    import itertools
    for pair in itertools.combinations(sorted(allowed_colors), 2):
        pair_set = frozenset(pair)
        if pair_set in dual_map:
            for d in dual_map[pair_set]:
                if len(lands) >= target_lands - len(allowed_colors):
                    break
                try_add(d)

        # In budget and ultra_budget, inject bounce lands, scry temples, and gainlands
        if budget in {"ultra_budget", "budget"} and len(lands) < target_lands - len(allowed_colors):
            if pair_set in bounce_map:
                try_add(bounce_map[pair_set])
            if pair_set in temple_map:
                try_add(temple_map[pair_set])
            if budget == "ultra_budget" and pair_set in gain_map:
                try_add(gain_map[pair_set])

    if budget in {"ultra_budget", "budget"} and len(allowed_colors) >= 2:
        try_add("Evolving Wilds")
        try_add("Terramorphic Expanse")
        try_add("Myriad Landscape")

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
    prompt_tokens: set[str],
    intents: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Query targeted archetypes from SQLite to ensure high-synergy enablers are included in the pool."""
    cursor = conn.cursor()
    legal_ids = db.get_legal_color_identities(allowed_colors)
    placeholders = ",".join("?" * len(legal_ids))
    cmd_text = f"{commander['name']} {commander.get('oracle_text', '')}".lower()

    targeted: list[dict[str, Any]] = []

    is_pw = intents.get("is_planeswalker_theme", False) if intents else ("planeswalker" in prompt_tokens or "superfriends" in prompt_tokens)
    is_multi = intents.get("is_multi_activation", False) if intents else False
    is_stax = intents.get("is_stax", False) if intents else ("stax" in prompt_tokens)

    # 0. Planeswalker & Multi-Activation targeted suite
    if is_pw or is_multi:
        # Query A: High-impact Planeswalkers in allowed colors
        sql_pw = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND type_line LIKE '%Planeswalker%'
              AND edhrec_rank IS NOT NULL
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql_pw, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

        # Query B: Multi-activation & timing enablers
        multi_activation_names = [
            "The Chain Veil", "Oath of Teferi", "Ichormoon Gauntlet", "Displacer Kitten",
            "Teferi, Temporal Archmage", "Teferi, Master of Time", "Rings of Brighthearth",
            "Lithoform Engine"
        ]
        q_multi = ",".join("?" * len(multi_activation_names))
        sql_multi = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND name IN ({q_multi})
        """
        cursor.execute(sql_multi, legal_ids + multi_activation_names)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

        # Query C: Loyalty acceleration & proliferate
        proliferate_names = [
            "Deepglow Skate", "Doubling Season", "Vorinclex, Monstrous Raider",
            "Flux Channeler", "Evolution Sage", "Inexorable Tide", "Karn's Bastion",
            "Contagion Engine", "Interplanar Beacon"
        ]
        q_prolif = ",".join("?" * len(proliferate_names))
        sql_prolif = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND (
                name IN ({q_prolif})
                OR oracle_text LIKE '%proliferate%'
              )
            ORDER BY edhrec_rank ASC LIMIT 50
        """
        cursor.execute(sql_prolif, legal_ids + proliferate_names)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

        # Query D: Creature sweepers & pillowfort protection
        protection_names = [
            "Toxic Deluge", "Supreme Verdict", "Damnation", "Cyclonic Rift",
            "Ghostly Prison", "Propaganda", "Sphere of Safety"
        ]
        q_prot = ",".join("?" * len(protection_names))
        sql_prot = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND (
                name IN ({q_prot})
                OR (
                    (type_line LIKE '%Sorcery%' OR type_line LIKE '%Instant%')
                    AND (oracle_text LIKE '%destroy all creatures%' OR oracle_text LIKE '%exile all creatures%')
                )
              )
            ORDER BY edhrec_rank ASC LIMIT 40
        """
        cursor.execute(sql_prot, legal_ids + protection_names)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    if is_stax:
        stax_names = [
            "Rule of Law", "Archon of Emeria", "Deafening Silence", "Drannith Magistrate",
            "Dauthi Voidwalker", "Opposition Agent", "Aven Mindcensor", "Trinisphere",
            "Collector Ouphe", "Grand Abolisher"
        ]
        q_stax = ",".join("?" * len(stax_names))
        sql_stax = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND name IN ({q_stax})
        """
        cursor.execute(sql_stax, legal_ids + stax_names)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    # 1. Pinger / Bleeder enablers if life loss / damage triggers commander
    if "opponent loses" in cmd_text or "damage to each opponent" in cmd_text or "lost life this turn" in cmd_text:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
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
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
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
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
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
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
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

    # 5. Enchantress / Constellation
    if "enchantment" in cmd_text or "aura" in cmd_text or "enchantress" in prompt_tokens:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND edhrec_rank IS NOT NULL
              AND (
                type_line LIKE '%Enchantment%'
                OR oracle_text LIKE '%constellation%'
                OR oracle_text LIKE '%cast an enchantment%'
              )
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    # 6. Blink / Flicker / ETB
    if ("exile" in cmd_text and ("return" in cmd_text or "enters" in cmd_text)) or "blink" in prompt_tokens:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND edhrec_rank IS NOT NULL
              AND (
                oracle_text LIKE '%exile%return%battlefield%'
                OR oracle_text LIKE '%when%enters the battlefield%'
                OR oracle_text LIKE '%whenever%enters the battlefield%'
              )
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    # 7. Spellslinger / Storm / Magecraft
    if "instant" in cmd_text or "sorcery" in cmd_text or "magecraft" in cmd_text or "spellslinger" in prompt_tokens:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND edhrec_rank IS NOT NULL
              AND (
                type_line LIKE '%Instant%'
                OR type_line LIKE '%Sorcery%'
                OR oracle_text LIKE '%magecraft%'
                OR oracle_text LIKE '%cast an instant or sorcery%'
              )
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    # 8. Landfall / Lands
    if "land enters" in cmd_text or "additional land" in cmd_text or "landfall" in cmd_text or "landfall" in prompt_tokens:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND edhrec_rank IS NOT NULL
              AND (
                oracle_text LIKE '%landfall%'
                OR oracle_text LIKE '%whenever a land enters%'
                OR oracle_text LIKE '%play an additional land%'
              )
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    # 9. +1/+1 Counters / Proliferate
    if "+1/+1 counter" in cmd_text or "proliferate" in cmd_text or "counters" in prompt_tokens:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND edhrec_rank IS NOT NULL
              AND (
                oracle_text LIKE '%+1/+1 counter%'
                OR oracle_text LIKE '%proliferate%'
              )
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    # 10. Tokens / Go-Wide
    if ("token" in cmd_text and "create" in cmd_text) or "token" in prompt_tokens:
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND edhrec_rank IS NOT NULL
              AND (
                oracle_text LIKE '%create%token%'
                OR oracle_text LIKE '%populate%'
              )
            ORDER BY edhrec_rank ASC LIMIT 80
        """
        cursor.execute(sql, legal_ids)
        targeted.extend([db.parse_card_row(r) for r in cursor.fetchall()])

    return targeted


def build_deck(
    conn: sqlite3.Connection,
    commander_name: str | list[str] = "",
    deck_idea: str = "",
    bracket: int = 3,
    budget: str = "moderate",
    color_preference: str | list[str] = "",
    preferred_win_con: str = "combat",
    house_rules: list[str] | set[str] | None = None,
    custom_bans: list[str] | set[str] | None = None
) -> dict[str, Any]:
    """Assemble a tournament-legal 100-card Commander deck meeting all constraints and synergy quotas."""
    bracket = max(1, min(5, int(bracket)))
    cfg = BRACKET_CONFIGS[bracket]
    preferred_win_con = preferred_win_con.lower()
    if preferred_win_con not in WIN_CON_PACKAGES:
        preferred_win_con = "combat"

    house_rules_set = {str(r).strip().lower() for r in (house_rules or []) if str(r).strip()}
    custom_bans_set = {str(b).strip().lower() for b in (custom_bans or []) if str(b).strip()}
    budget = budget.strip().lower() if budget else "moderate"
    if budget not in {"ultra_budget", "budget", "moderate", "unlimited"}:
        budget = "moderate"

    # Extract semantic strategy intents
    intents = extract_strategy_intents(deck_idea, preferred_win_con)

    # In Brackets 1 and 2 or with no_combos house rule, infinite combos are strictly disallowed
    if (not cfg["allow_combos"] or "no_combos" in house_rules_set) and preferred_win_con == "combo":
        preferred_win_con = "combat"

    raw_color_str = str(color_preference).strip().lower()
    pref_colors = resolve_color_identity(color_preference)
    is_explicit_colorless = raw_color_str in {"colorless", "c"}
    effective_color_pref = pref_colors if (pref_colors or is_explicit_colorless) else None

    # 1. Resolve Commander(s) - Supports Single Commanders and MTG Rule 903.3a Partner Pairings
    commanders: list[dict[str, Any]] = []
    raw_names = []
    if isinstance(commander_name, list):
        raw_names = [n.strip() for n in commander_name if n and n.strip()]
    elif isinstance(commander_name, str) and commander_name.strip():
        # Split on common partner delimiters (" / ", " // ", " & ", ",")
        if " // " in commander_name and "land" not in commander_name.lower():
            # Check if this is a DFC or a partner pair
            resolved_single = db.get_card_by_name(conn, commander_name.strip())
            if resolved_single and resolved_single.get("is_commander"):
                raw_names = [commander_name.strip()]
            else:
                raw_names = [p.strip() for p in commander_name.split(" // ") if p.strip()]
        elif " / " in commander_name:
            raw_names = [p.strip() for p in commander_name.split(" / ") if p.strip()]
        elif " & " in commander_name:
            raw_names = [p.strip() for p in commander_name.split(" & ") if p.strip()]
        else:
            raw_names = [commander_name.strip()]

    if raw_names:
        for r_name in raw_names[:2]:
            cmd = db.get_card_by_name(conn, r_name)
            if not cmd:
                raise ValueError(f"Commander '{r_name}' not found in tournament-legal database.")
            if not cmd.get("is_commander") or not cmd.get("commander_legal"):
                raise ValueError(f"Card '{cmd['name']}' is not a tournament-legal Commander.")
            if is_card_excluded(cmd["name"], budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
                raise ValueError(f"Commander '{cmd['name']}' is prohibited by current house rules or ban list.")
            commanders.append(cmd)
    else:
        discovered = find_matching_commander(
            conn=conn,
            prompt=deck_idea or preferred_win_con,
            color_pref=effective_color_pref,
            win_con=preferred_win_con,
            bracket=bracket,
            custom_bans=custom_bans_set,
            intents=intents
        )
        if not discovered:
            discovered = db.get_card_by_name(conn, "Belbe, Corrupted Observer")
        if not discovered or not discovered.get("is_commander") or not discovered.get("commander_legal") or is_card_excluded(discovered["name"], budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
            # Fallback to first legal commander not banned
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM cards WHERE is_commander = 1 AND commander_legal = 1 ORDER BY edhrec_rank ASC LIMIT 50")
            for row in cursor.fetchall():
                c_cand = db.get_card_by_name(conn, row[0])
                if c_cand and not is_card_excluded(c_cand["name"], budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
                    discovered = c_cand
                    break
        if not discovered:
            raise ValueError("Could not find or resolve a valid tournament-legal Commander.")
        commanders.append(discovered)

    primary_commander = commanders[0]
    num_commanders = len(commanders)

    allowed_colors = set()
    for cmd in commanders:
        allowed_colors.update(cmd.get("color_identity", []))

    prompt_tokens = {w.lower() for w in re.findall(r"\b\w{3,}\b", deck_idea)}
    prompt_tokens.update(intents.get("tokens", set()))
    prompt_tokens.add(preferred_win_con)

    # 2. Query Card Pools Legal in Commander Identity (General Pool + Targeted Synergy Pool)
    general_pool = db.get_cards_by_identity(conn, allowed_colors, limit=800)
    targeted_pool = query_targeted_synergy_candidates(conn, allowed_colors, primary_commander, prompt_tokens, intents=intents)

    # Deduplicate pool by canonical lowercase name
    combined_pool_map: dict[str, dict[str, Any]] = {}
    for c in targeted_pool + general_pool:
        if c["name_lower"] not in combined_pool_map:
            combined_pool_map[c["name_lower"]] = c

    pool = list(combined_pool_map.values())
    commander_names_lower = {cmd["name"].lower() for cmd in commanders}

    # 3. Filter pool by Bracket, Budget, House Rules, & Custom Bans
    filtered_pool: list[dict[str, Any]] = []
    for c in pool:
        name_lower = c["name"].lower()
        if name_lower in commander_names_lower:
            continue

        if is_card_excluded(c["name"], budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
            continue

        if not cfg["allow_fast_mana"] and name_lower in FAST_MANA_CARDS:
            continue
        if not cfg["allow_sol_ring"] and name_lower == "sol ring":
            continue
        if (not cfg["allow_tutors"] or bracket <= 3) and name_lower in CHEAP_TUTORS:
            continue
        if not cfg["allow_combos"] and name_lower in DISALLOWED_LOW_BRACKET_COMBOS:
            continue
        if bracket <= 3 and name_lower in {"thassa's oracle", "demonic consultation", "underworld breach", "lion's eye diamond"}:
            continue
        if budget in {"budget", "ultra_budget"} and name_lower in EXPENSIVE_RESERVED_LIST:
            continue

        filtered_pool.append(c)

    # 4. Universal Staples & Mandatory Bracket 5 cEDH Meta Staples
    deck_cards: dict[str, dict[str, Any]] = {}
    categorized: dict[str, list[dict[str, Any]]] = {
        "ramp": [], "draw": [], "removal": [], "win_con": [], "synergy": [], "lands": []
    }

    def add_card(card: dict[str, Any], role: str) -> bool:
        nl = card["name"].lower()
        if nl in deck_cards or nl in commander_names_lower:
            return False
        if is_card_excluded(card["name"], budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
            return False
        deck_cards[nl] = card
        categorized[role].append(card)
        return True

    # Format staple ramp (Sol Ring, Arcane Signet) for Brackets 2-5
    if cfg["allow_sol_ring"] and not is_card_excluded("Sol Ring", budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
        card = db.get_card_by_name(conn, "Sol Ring")
        if card and set(card["color_identity"]).issubset(allowed_colors):
            add_card(card, "ramp")

    if not is_card_excluded("Arcane Signet", budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
        card = db.get_card_by_name(conn, "Arcane Signet")
        if card and set(card["color_identity"]).issubset(allowed_colors):
            add_card(card, "ramp")

    # In budget or ultra_budget, inject common budget ramp options
    if budget in {"ultra_budget", "budget"}:
        budget_ramp = ["Mind Stone", "Commander's Sphere", "Wayfarer's Bauble", "Fellwar Stone"]
        if "G" in allowed_colors:
            budget_ramp.extend(["Rampant Growth", "Cultivate", "Kodama's Reach", "Sakura-Tribe Elder", "Farseek"])
        for r_name in budget_ramp:
            if not is_card_excluded(r_name, budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
                r_card = db.get_card_by_name(conn, r_name)
                if r_card and set(r_card["color_identity"]).issubset(allowed_colors):
                    add_card(r_card, "ramp")

    if cfg["cedh_meta"]:
        for s_name in CEDH_STAPLES_BY_COLOR["colorless"]:
            if is_card_excluded(s_name, budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
                continue
            card = db.get_card_by_name(conn, s_name)
            if card and set(card["color_identity"]).issubset(allowed_colors):
                role = "ramp" if "stone" in s_name.lower() or "mana" in s_name.lower() or "mox" in s_name.lower() or "sol" in s_name.lower() or "petal" in s_name.lower() or "signet" in s_name.lower() else "draw"
                add_card(card, role)

        for col in allowed_colors:
            for s_name in CEDH_STAPLES_BY_COLOR.get(col, []):
                if is_card_excluded(s_name, budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
                    continue
                card = db.get_card_by_name(conn, s_name)
                if card and set(card["color_identity"]).issubset(allowed_colors):
                    roles = classify_card_role(card)
                    role = "ramp" if "ramp" in roles else ("draw" if "draw" in roles else "removal")
                    add_card(card, role)

    # 5. Add Win-Condition Package (Target win cons)
    for pkg_item in WIN_CON_PACKAGES[preferred_win_con]:
        if len(categorized["win_con"]) >= cfg["target_win_con"]:
            break
        if is_card_excluded(pkg_item["name"], budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
            continue
        if pkg_item["colors"].issubset(allowed_colors):
            card = db.get_card_by_name(conn, pkg_item["name"])
            if card:
                nl = card["name"].lower()
                if (not cfg["allow_combos"] or "no_combos" in house_rules_set) and preferred_win_con == "combo":
                    continue
                if (not cfg["allow_fast_mana"] or "no_fast_mana" in house_rules_set) and nl in FAST_MANA_CARDS:
                    continue
                if bracket <= 3 and nl in {"thassa's oracle", "demonic consultation", "underworld breach", "lion's eye diamond"}:
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
        score = score_synergy(c, primary_commander, prompt_tokens, preferred_win_con, bracket, intents=intents)
        scored_candidates.append((score, c, roles))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    max_pw_quota = 16 if intents.get("is_planeswalker_theme") else 999

    def get_pw_count() -> int:
        return sum(1 for c in deck_cards.values() if "planeswalker" in c.get("type_line", "").lower())

    # Fill Ramp quota
    for score, card, roles in scored_candidates:
        if len(categorized["ramp"]) >= cfg["target_ramp"]:
            break
        if "ramp" in roles:
            if "planeswalker" in card.get("type_line", "").lower() and get_pw_count() >= 2:
                continue
            add_card(card, "ramp")

    # Fill Draw quota
    for score, card, roles in scored_candidates:
        if len(categorized["draw"]) >= cfg["target_draw"]:
            break
        if "draw" in roles:
            if "planeswalker" in card.get("type_line", "").lower() and get_pw_count() >= 3:
                continue
            add_card(card, "draw")

    # Fill Removal quota
    for score, card, roles in scored_candidates:
        if len(categorized["removal"]) >= cfg["target_removal"]:
            break
        if "removal" in roles:
            if "planeswalker" in card.get("type_line", "").lower() and get_pw_count() >= 5:
                continue
            add_card(card, "removal")

    # Priority Drafting for Planeswalker Theme & Multi-Activation Engine
    target_nonlands = 100 - num_commanders - cfg["target_lands"]
    current_nonlands = sum(len(v) for k, v in categorized.items() if k != "lands")

    if intents.get("is_planeswalker_theme") or intents.get("is_multi_activation"):
        # Priority A: Draft key legal multi-activation / timing enablers
        multi_activation_priority = [
            "The Chain Veil", "Oath of Teferi", "Teferi, Temporal Archmage",
            "Teferi, Master of Time", "Ichormoon Gauntlet", "Displacer Kitten"
        ]
        for name in multi_activation_priority:
            if current_nonlands >= target_nonlands:
                break
            if name.lower() not in deck_cards:
                cand_card = db.get_card_by_name(conn, name)
                if cand_card and set(cand_card.get("color_identity", [])).issubset(allowed_colors):
                    if not is_card_excluded(cand_card["name"], budget=budget, house_rules=house_rules_set, custom_bans=custom_bans_set, bracket=bracket):
                        if add_card(cand_card, "synergy"):
                            current_nonlands += 1

        # Priority B: Enforce Planeswalker Core Quota (draft at least 14 planeswalkers, up to 16)
        target_pw_quota = 15
        current_pw_count = get_pw_count()
        if current_pw_count < target_pw_quota:
            for score, card, roles in scored_candidates:
                if current_pw_count >= target_pw_quota or current_nonlands >= target_nonlands:
                    break
                if "planeswalker" in card.get("type_line", "").lower() and card["name"].lower() not in deck_cards:
                    if add_card(card, "synergy"):
                        current_nonlands += 1
                        current_pw_count += 1

    # Fill Synergy core with top remaining cards (accounting for single or partner commanders)
    for score, card, roles in scored_candidates:
        if current_nonlands >= target_nonlands:
            break
        if intents.get("is_planeswalker_theme") and "planeswalker" in card.get("type_line", "").lower():
            if get_pw_count() >= max_pw_quota:
                continue
        if add_card(card, "synergy"):
            current_nonlands += 1

    # Safety Guarantee: Enforce Planeswalker quota if non-planeswalkers filled slots early
    if intents.get("is_planeswalker_theme"):
        current_pw_count = get_pw_count()
        if current_pw_count < 14:
            available_pws = [c for score, c, roles in scored_candidates if "planeswalker" in c.get("type_line", "").lower() and c["name"].lower() not in deck_cards]
            for pw_card in available_pws:
                if current_pw_count >= 14:
                    break
                # Replace lowest scored non-planeswalker, non-enabler synergy card
                non_pw_synergy = [c for c in categorized["synergy"] if "planeswalker" not in c.get("type_line", "").lower() and c["name"].lower() not in {"the chain veil", "oath of teferi", "ichormoon gauntlet", "displacer kitten"}]
                if non_pw_synergy:
                    to_remove = non_pw_synergy[-1]
                    categorized["synergy"].remove(to_remove)
                    deck_cards.pop(to_remove["name"].lower(), None)
                    if add_card(pw_card, "synergy"):
                        current_pw_count += 1

    # Invariant Backfill: If nonlands are short of target, backfill from filtered pool
    if current_nonlands < target_nonlands:
        for c in filtered_pool:
            if current_nonlands >= target_nonlands:
                break
            if "land" not in classify_card_role(c):
                if add_card(c, "synergy"):
                    current_nonlands += 1

    # 7. Assemble Lands (Adaptive target_lands for 100-card invariant guarantee)
    spells = [c for c in deck_cards.values() if "land" not in classify_card_role(c)]
    target_lands = cfg["target_lands"]
    target_nonlands = 100 - num_commanders - target_lands
    if len(spells) < target_nonlands:
        target_lands = 100 - num_commanders - len(spells)

    lands = assemble_lands(
        conn=conn,
        allowed_colors=allowed_colors,
        target_lands=target_lands,
        spells=spells,
        bracket=bracket,
        budget=budget,
        house_rules=house_rules_set,
        custom_bans=custom_bans_set,
        intents=intents
    )
    
    # Invariant Land Guarantee: Ensure lands length matches target_lands exactly
    basic_lookup = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
    fallback_basic_name = basic_lookup[sorted(allowed_colors)[0]] if allowed_colors else "Wastes"
    fallback_basic = db.get_card_by_name(conn, fallback_basic_name)

    while len(lands) < target_lands and fallback_basic:
        lands.append(fallback_basic)
    if len(lands) > target_lands:
        lands = lands[:target_lands]

    # Absolute 100-card invariant guarantee
    current_total = num_commanders + len(spells) + len(lands)
    while current_total < 100 and fallback_basic:
        lands.append(fallback_basic)
        current_total += 1
    while current_total > 100 and len(lands) > 0:
        lands.pop()
        current_total -= 1

    categorized["lands"] = lands

    # 8. Compute Deck Statistics & Hypergeometric Consistency
    full_decklist_cards = commanders + list(deck_cards.values()) + lands
    nonland_spells = [c for c in full_decklist_cards if "land" not in classify_card_role(c) and c["name"] not in {cmd["name"] for cmd in commanders}]

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
    total_deck = num_commanders + len(spells) + len(lands)
    p_3_lands_t3 = hypergeometric_cdf_ge(total_deck, 9, land_count, 3) * 100.0
    p_turn2_ramp = calculate_joint_consistency(total_deck, 8, land_count, 2, ramp_count, 1, 0, 0) * 100.0
    consistency = {
        "p_3_lands_turn_3": f"{p_3_lands_t3:.1f}%",
        "p_land_and_ramp_turn_2": f"{p_turn2_ramp:.1f}%"
    }

    engine_dossier = detect_resource_profile(primary_commander)

    # Detailed Win Condition & Engine Walkthrough
    cmd_name = " & ".join(c["name"] for c in commanders)
    cmd_oracle = " ".join((c.get("oracle_text") or "").lower() for c in commanders)

    if intents.get("is_planeswalker_theme"):
        win_con_exec = generate_planeswalker_blueprint(commanders, deck_cards, preferred_win_con, bracket, intents)
    elif "adds {c}{c}" in cmd_oracle or "belbe" in cmd_name.lower():
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
    text_lines = [f"// Commander"]
    for cmd in commanders:
        text_lines.append(f"1 {cmd['name']}")
    text_lines.append("")

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
        "commander": primary_commander,
        "commanders": commanders,
        "deck_idea": deck_idea,
        "bracket": {
            "tier": bracket,
            "name": cfg["name"],
            "description": cfg["description"]
        },
        "budget": budget,
        "house_rules": sorted(house_rules_set),
        "custom_bans": sorted(custom_bans_set),
        "preferred_win_con": preferred_win_con,
        "win_con_execution": win_con_exec,
        "total_cards": num_commanders + len(spells) + len(lands),
        "stats": {
            "card_count": num_commanders + len(spells) + len(lands),
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
            "commander": commanders,
            "ramp": categorized["ramp"],
            "draw": categorized["draw"],
            "removal": categorized["removal"],
            "win_con": categorized["win_con"],
            "synergy": categorized["synergy"],
            "lands": categorized["lands"]
        },
        "decklist_text": export_decklist,
        "exports": deck_exporter.export_all_formats({
            "commanders": commanders,
            "commander": primary_commander,
            "categories": {
                "commander": commanders,
                "ramp": categorized["ramp"],
                "draw": categorized["draw"],
                "removal": categorized["removal"],
                "win_con": categorized["win_con"],
                "synergy": categorized["synergy"],
                "lands": categorized["lands"]
            }
        })
    }
