"""Interactive Card Swapper Engine for Loreweaver Deck Architect.

Enables interactive 1-click card swapping and re-rolling for individual slots
within an assembled 100-card Commander deck while strictly adhering to:
- Commander format legality (commander_legal = 1, banned cards excluded)
- Commander color identity constraints (including Partner pairings)
- Operational lane quotas and role relevance
- Bracket restrictions (no fast mana or 2-card combos in Brackets 1–2)
- Singleton deck consistency (strict non-basic duplicate exclusion)
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

try:
    from scripts import db
    from scripts import deck_builder
except ImportError:
    import db
    import deck_builder

# Format-banned cards in Commander (WotC / Commander Rules Committee banlist)
FORMAT_BANNED_CARDS: set[str] = {
    "mana crypt", "jeweled lotus", "dockside extortionist", "nadu, winged wisdom",
    "hullbreacher", "lutri, the spellchaser", "flash", "golos, tireless pilgrim",
    "leovold, emissary of trest", "griselbrand", "emrakul, the aeons torn",
    "trade secrets", "upheaval", "tinker", "black lotus", "mox pearl", "mox sapphire",
    "mox ruby", "mox jet", "mox emerald", "ancestral recall", "time walk", "time vault",
    "karakas", "tolarian academy", "channel", "fastbond", "paradox engine", "primeval titan",
    "prophet of kruphix", "rofellos, llanowar emissary", "sundering titan", "sylvan primordial",
    "worldfire", "yawgmoth's bargain", "limited resources", "biorhythm", "coalition victory",
    "erayo, soratami ascendant", "braids, cabal minion", "panoptic mirror", "iona, shield of emeria"
}

# 2-card infinite combos disallowed in Brackets 1 and 2
DISALLOWED_LOW_BRACKET_COMBOS: set[str] = {
    "dual caster mage", "dualcaster mage", "twinflame", "heliod, sun-crowned",
    "walking ballista", "thassa's oracle", "demonic consultation", "underworld breach",
    "kiki-jiki, mirror breaker", "zealous conscripts", "exquisite blood", "sanguine bond",
    "lion's eye diamond"
}

# High-power cEDH fast combo catalysts disallowed in Bracket 3
BRACKET_3_EXCLUDED_COMBOS: set[str] = {
    "thassa's oracle", "demonic consultation", "underworld breach", "lion's eye diamond"
}

# Fast mana rocks disallowed in Brackets 1, 2, and 3
FAST_MANA_CARDS: set[str] = {
    "mox diamond", "chrome mox", "lotus petal", "mox opal",
    "mana vault", "grim monolith", "ancient tomb", "lion's eye diamond"
}

# Cheap unconditional tutors disallowed in Brackets 1, 2, and 3
CHEAP_TUTORS: set[str] = {
    "demonic tutor", "vampiric tutor", "imperial seal", "worldly tutor",
    "mystical tutor", "enlightened tutor", "gamble", "personal tutor"
}

BASIC_LAND_NAMES: set[str] = {
    "plains", "island", "swamp", "mountain", "forest", "wastes",
    "snow-covered plains", "snow-covered island", "snow-covered swamp",
    "snow-covered mountain", "snow-covered forest", "snow-covered wastes"
}


def normalize_category(category: str) -> str:
    """Normalize user input category to canonical operational role."""
    clean = (category or "").strip().lower().replace(" ", "_").replace("-", "_")
    if clean in {"wincon", "win_con", "win", "finisher"}:
        return "win_con"
    if clean in {"land", "lands", "mana_base"}:
        return "lands"
    if clean in {"ramp", "acceleration", "mana_rock"}:
        return "ramp"
    if clean in {"draw", "card_draw", "card_advantage"}:
        return "draw"
    if clean in {"removal", "interaction", "removal_answers", "answers"}:
        return "removal"
    return "synergy"


def generate_swap_reason(
    card: dict[str, Any],
    category: str,
    commander: dict[str, Any] | None,
    replaced_card: dict[str, Any] | None,
    bracket: int
) -> str:
    """Generate an informative, context-aware reason for recommending this card."""
    name = card["name"]
    type_line = (card.get("type_line") or "").lower()
    oracle = (card.get("oracle_text") or "").lower()
    cmc = int(card.get("cmc") or 0)
    cmd_name = commander["name"] if commander else ""
    cmd_text = f"{commander['name']} {commander.get('oracle_text', '')}".lower() if commander else ""

    # Specific synergies based on commander archetype
    if commander:
        if ("opponent loses" in cmd_text or "lost life this turn" in cmd_text) and (
            "each opponent loses" in oracle or "damage to each opponent" in oracle or "each opponent who" in oracle
        ):
            return f"Upkeep bleed trigger activating {cmd_name}'s mana generation"
        if ("adds {c}{c}" in cmd_text or "belbe" in cmd_name.lower()) and (
            "as though they had flash" in oracle or "flash" in card.get("keywords", [])
        ):
            return f"Instant-speed flash enabler to deploy threats during opponents' turns"
        if ("sacrifice" in cmd_text or "dies" in cmd_text) and ("sacrifice" in oracle or "dies" in oracle):
            return f"Sacrifice payoff directly synergizing with {cmd_name}"
        if "+1/+1 counter" in cmd_text and ("+1/+1 counter" in oracle or "proliferate" in oracle):
            return f"Counter engine scaling with {cmd_name}'s counters"
        if "token" in cmd_text and ("create" in oracle and "token" in oracle):
            return f"Token generator multiplying board presence for {cmd_name}"
        if ("instant" in cmd_text or "sorcery" in cmd_text) and ("magecraft" in oracle or "copy" in oracle):
            return f"Spellslinger payoff multiplying spell velocity"
        if ("enchantment" in cmd_text or "aura" in cmd_text) and ("enchantment" in type_line or "constellation" in oracle):
            return f"Enchantress engine rewarding enchantment deployment"

    if category == "ramp":
        if name in {"Sol Ring", "Arcane Signet", "Fellwar Stone", "Thought Vessel", "Mind Stone"}:
            return f"Premier {cmc} CMC mana rock accelerating your curve"
        if "search your library for a" in oracle and "land" in oracle:
            return f"Land ramp spell putting resources directly into play"
        if "treasure" in oracle:
            return f"Burst treasure generator fueling high-impact turns"
        if "{t}: add" in oracle or "add {" in oracle:
            return f"Efficient {cmc} CMC mana acceleration"
        return f"Ramp acceleration advancing mana development"

    if category == "removal":
        if "counter target" in oracle:
            return f"Stack interaction countering critical opponent spells"
        if "destroy all" in oracle or "exile all" in oracle or "each opponent sacrifices" in oracle:
            return f"High-impact sweeper stabilizing the battlefield"
        if "instant" in type_line and ("destroy target" in oracle or "exile target" in oracle):
            return f"Instant-speed spot removal answering key threats"
        if "deals" in oracle and "damage to" in oracle:
            return f"Direct burn removal handling creatures and planeswalkers"
        return f"Targeted removal maintaining board control"

    if category == "draw":
        if "whenever" in oracle and ("draw" in oracle or "draws" in oracle):
            return f"Repeatable card draw engine generating persistent card advantage"
        if cmc <= 2 and ("draw a card" in oracle or "look at the top" in oracle):
            return f"Low-cost cantrip / velocity piece smoothing your draws"
        if "draw" in oracle and ("three" in oracle or "two" in oracle or "x cards" in oracle):
            return f"Burst card advantage refueling your hand"
        return f"Card advantage keeping your engine supplied with resources"

    if category == "win_con":
        if "trample" in oracle or "overrun" in oracle or "+x/+x" in oracle or "+5/+5" in oracle:
            return f"Overrun combat finisher delivering decisive lethal damage"
        if "each opponent loses" in oracle or "drain" in oracle or "life loss" in oracle:
            return f"Drain engine closing out games through life attrition"
        if "win the game" in oracle or "infinite" in oracle or name in {"Thassa's Oracle", "Underworld Breach"}:
            return f"Compact combo finisher aligned with Bracket {bracket}"
        return f"Decisive win condition designed to close out the game"

    if category == "lands":
        if "dual" in oracle or len(card.get("color_identity", [])) >= 2:
            return f"Color-fixing dual land ensuring smooth mana colors"
        if "boseiju" in name.lower() or "urborg" in name.lower() or "yavimaya" in name.lower() or "bog" in name.lower():
            return f"High-utility land providing tactical advantage from the land slot"
        if name in {"Command Tower", "Exotic Orchard", "Reflecting Pool", "Mana Confluence"}:
            return f"Universal rainbow land fixing all commander colors"
        return f"Reliable mana base land supporting color requirements"

    # Default synergy reason
    if replaced_card:
        old_cmc = int(replaced_card.get("cmc") or 0)
        if cmc < old_cmc:
            return f"Lower curve alternative ({cmc} CMC vs {old_cmc}) with strong synergy"
        if cmc == old_cmc:
            return f"Direct {cmc} CMC lateral upgrade with high synergy score"
    return f"High-synergy tactical piece reinforcing your deck's core strategy"


def get_swap_candidates(
    conn: sqlite3.Connection,
    card_name: str,
    commander_name: str = "",
    category: str = "synergy",
    bracket: int = 3,
    exclude: list[str] | set[str] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Retrieve scored, legal swap candidates for a specific card slot.

    Args:
        conn: SQLite database connection to cards.db.
        card_name: The name of the card being replaced.
        commander_name: Commander name(s) to resolve legal color identity.
        category: Operational lane ('ramp', 'draw', 'removal', 'win_con', 'synergy', 'lands').
        bracket: Commander power tier from 1 to 5.
        exclude: List or set of card names already in the deck to prevent duplicates.
        limit: Maximum number of candidate cards to return (default: 8).

    Returns:
        List of candidate dictionaries: [{ name, mana_cost, cmc, type_line, oracle_text, image_url, reason }]
    """
    bracket = max(1, min(5, int(bracket)))
    category_norm = normalize_category(category)
    limit = max(1, min(50, int(limit)))
    cursor = conn.cursor()

    # 1. Resolve Commander(s) & Allowed Color Identity
    commanders: list[dict[str, Any]] = []
    if commander_name and commander_name.strip():
        raw = commander_name.strip()
        names = []
        if " // " in raw and "land" not in raw.lower():
            resolved = db.get_card_by_name(conn, raw)
            if resolved and resolved.get("is_commander"):
                names = [raw]
            else:
                names = [p.strip() for p in raw.split(" // ") if p.strip()]
        elif " / " in raw:
            names = [p.strip() for p in raw.split(" / ") if p.strip()]
        elif " & " in raw:
            names = [p.strip() for p in raw.split(" & ") if p.strip()]
        else:
            names = [raw]

        for n in names[:2]:
            cmd = db.get_card_by_name(conn, n)
            if cmd:
                commanders.append(cmd)

    # If commander not found by name, attempt fallback from card_name's color identity
    replaced_card = db.get_card_by_name(conn, card_name) if card_name else None

    allowed_colors: set[str] = set()
    if commanders:
        for c in commanders:
            allowed_colors.update(c.get("color_identity", []))
    elif replaced_card:
        allowed_colors = set(replaced_card.get("color_identity", []))
    else:
        # Default fallback: 5-color
        allowed_colors = {"W", "U", "B", "R", "G"}

    primary_commander = commanders[0] if commanders else None

    # 2. Build Exclusion Set (case-insensitive lowercase)
    exclude_set: set[str] = set()
    if exclude:
        items = [exclude] if isinstance(exclude, str) else list(exclude)
        for item in items:
            if not item:
                continue
            s_item = str(item).strip().lower()
            if not s_item:
                continue
            exclude_set.add(s_item)
            # If item contains commas, verify if it's a single card or delimited list
            if "," in s_item:
                cursor.execute("SELECT 1 FROM cards WHERE name_lower = ? LIMIT 1", (s_item,))
                if not cursor.fetchone():
                    for part in s_item.split(","):
                        p_clean = part.strip()
                        if p_clean:
                            exclude_set.add(p_clean)

    # Always exclude the card being replaced
    if card_name:
        exclude_set.add(card_name.strip().lower())
        if replaced_card:
            exclude_set.add(replaced_card["name_lower"])

    # Always exclude commanders from the 99 candidate slots
    for cmd in commanders:
        exclude_set.add(cmd["name_lower"])

    # 3. Query Database for Color-Legal Candidates
    legal_identities = db.get_legal_color_identities(allowed_colors)
    placeholders = ",".join("?" * len(legal_identities))
    cursor = conn.cursor()

    candidates_raw: list[dict[str, Any]] = []

    if category_norm == "lands":
        # Lands candidate query
        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND edhrec_rank IS NOT NULL
              AND (types LIKE '%land%' OR type_line LIKE '%Land%')
            ORDER BY edhrec_rank ASC
            LIMIT 250
        """
        cursor.execute(sql, legal_identities)
        candidates_raw = [db.parse_card_row(r) for r in cursor.fetchall()]

    else:
        # Non-land candidate queries tailored to operational role
        type_land_filter = "AND (types NOT LIKE '%land%' AND type_line NOT LIKE '%Land%')"

        # Primary role-targeted SQL condition
        role_filter = ""
        if category_norm == "ramp":
            role_filter = """
                AND (
                    name_lower IN ('sol ring', 'arcane signet', 'fellwar stone', 'thought vessel', 'mind stone', 'talisman', 'signet')
                    OR oracle_text LIKE '%{T}: Add%'
                    OR oracle_text LIKE '%{t}: add%'
                    OR oracle_text LIKE '%add %mana%'
                    OR oracle_text LIKE '%search your library for a %land%'
                    OR oracle_text LIKE '%create%treasure%'
                )
            """
        elif category_norm == "draw":
            role_filter = """
                AND (
                    oracle_text LIKE '%draw %card%'
                    OR oracle_text LIKE '%draw a card%'
                    OR oracle_text LIKE '%draws a card%'
                    OR oracle_text LIKE '%look at the top%'
                    OR oracle_text LIKE '%investigate%'
                )
            """
        elif category_norm == "removal":
            role_filter = """
                AND (
                    oracle_text LIKE '%destroy target%'
                    OR oracle_text LIKE '%exile target%'
                    OR oracle_text LIKE '%counter target%'
                    OR oracle_text LIKE '%destroy all%'
                    OR oracle_text LIKE '%exile all%'
                    OR oracle_text LIKE '%damage to target%'
                    OR oracle_text LIKE '%damage to any target%'
                    OR oracle_text LIKE '%sacrifices a creature%'
                )
            """

        sql = f"""
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank,
                   is_commander, commander_legal
            FROM cards
            WHERE color_identity IN ({placeholders})
              AND commander_legal = 1
              AND edhrec_rank IS NOT NULL
              {type_land_filter}
              {role_filter}
            ORDER BY edhrec_rank ASC
            LIMIT 400
        """
        cursor.execute(sql, legal_identities)
        candidates_raw = [db.parse_card_row(r) for r in cursor.fetchall()]

        # Complement with targeted synergy pool only for synergy category
        if category_norm == "synergy" and primary_commander:
            try:
                targeted = deck_builder.query_targeted_synergy_candidates(
                    conn=conn,
                    allowed_colors=allowed_colors,
                    commander=primary_commander,
                    prompt_tokens=set()
                )
                candidates_raw.extend(targeted)
            except Exception:
                pass

        # If win_con category, inject win-condition packages
        if category_norm == "win_con":
            for pkg_name, pkg_cards in deck_builder.WIN_CON_PACKAGES.items():
                for item in pkg_cards:
                    if item["colors"].issubset(allowed_colors):
                        c = db.get_card_by_name(conn, item["name"])
                        if c:
                            candidates_raw.append(c)

    # 4. Filter Candidates & Score
    scored: list[tuple[float, dict[str, Any]]] = []
    seen_names: set[str] = set()

    STOP_WORDS = {"the", "and", "for", "with", "from", "that", "this", "into", "your", "card", "deck", "lord"}
    prompt_tokens: set[str] = set()
    if primary_commander:
        prompt_tokens = {
            w.lower() for w in re.findall(r"\b\w{3,}\b", primary_commander["name"])
            if w.lower() not in STOP_WORDS
        }

    for card in candidates_raw:
        nl = card["name_lower"]
        if nl in seen_names:
            continue
        seen_names.add(nl)

        # Exclude cards in exclude list (enforcing singleton non-basics)
        if nl in exclude_set:
            continue

        # Strict Land vs Non-Land separation
        is_land_card = "land" in card.get("types", []) or "land" in card.get("type_line", "").lower()
        if category_norm == "lands":
            if not is_land_card:
                continue
        else:
            if is_land_card:
                continue

        # Format Banlist filter
        if nl in FORMAT_BANNED_CARDS or not card.get("commander_legal"):
            continue

        # Bracket Restrictions
        if bracket <= 3:
            if nl in FAST_MANA_CARDS:
                continue
            if nl in BRACKET_3_EXCLUDED_COMBOS:
                continue

        if bracket <= 2:
            if nl in CHEAP_TUTORS:
                continue
            if nl in DISALLOWED_LOW_BRACKET_COMBOS:
                continue
            if bracket == 1 and nl == "sol ring":
                continue

        # Color Identity Invariant Check
        card_colors = set(card.get("color_identity", []))
        if not card_colors.issubset(allowed_colors):
            continue

        # Role & Functional Classification
        roles = deck_builder.classify_card_role(card)
        oracle = (card.get("oracle_text") or "").lower()
        cmc = float(card.get("cmc") or 0.0)
        rank = card.get("edhrec_rank") or 15000

        # Strict Role Eligibility Gates
        is_blink = "return" in oracle and "battlefield" in oracle and "you control" in oracle

        if category_norm == "ramp":
            # Exclude counterspells and opponent treasure creation falsely flagged as ramp
            if "counter target" in oracle:
                continue
            if "its controller creates" in oracle:
                continue
            if "opponent creates" in oracle:
                continue
            if "when this creature dies" in oracle and "treasure" in oracle:
                continue

            is_ramp = (
                "ramp" in roles or
                nl in {"sol ring", "arcane signet", "fellwar stone", "thought vessel", "mind stone"} or
                "{t}: add" in oracle or "{t}: create" in oracle or "add {" in oracle or
                ("search your library for" in oracle and "land" in oracle) or
                ("treasure" in oracle and ("create" in oracle or "token" in oracle))
            )
            if not is_ramp:
                continue

        elif category_norm == "removal":
            if is_blink and "destroy" not in oracle and "exile target creature an opponent" not in oracle:
                continue
            has_damage_removal = (
                "damage to target" in oracle or
                "damage to any target" in oracle or
                "damage to each creature" in oracle or
                "damage to all creatures" in oracle or
                bool(re.search(r"deals?\s+(\d+|x)\s+damage\s+to\s+(target|any\s+target)", oracle))
            )
            is_removal = (
                "removal" in roles or
                "destroy target" in oracle or
                "exile target" in oracle or
                "counter target" in oracle or
                "destroy all" in oracle or
                "exile all" in oracle or
                has_damage_removal or
                "sacrifices a creature" in oracle or
                "sacrifices a permanent" in oracle or
                "each opponent sacrifices" in oracle or
                "all creatures get -" in oracle
            )
            if not is_removal:
                continue

        elif category_norm == "draw":
            if is_blink and "draw" not in oracle:
                continue
            is_draw = (
                "draw" in roles or
                "draw a card" in oracle or
                "draws a card" in oracle or
                "draw two" in oracle or
                "draw three" in oracle or
                "draw x cards" in oracle or
                "draw cards" in oracle or
                "draw that many" in oracle or
                "look at the top" in oracle or
                "investigate" in oracle
            )
            if not is_draw:
                continue

        # Baseline EDHREC Popularity Score
        score = max(0.0, (15000.0 - rank) / 500.0)

        # Synergy with Commander
        if primary_commander:
            score += deck_builder.score_synergy(
                card=card,
                commander=primary_commander,
                prompt_tokens=prompt_tokens,
                win_con="combat",
                bracket=bracket
            )

        # Category / Role specific weighting
        if category_norm == "lands":
            score += 100.0
            # Prioritize duals, fetches, and high utility lands
            if len(card_colors) >= 2 or "dual" in oracle:
                score += 35.0
            if rank < 500:
                score += 25.0
            # Slight penalty for basic lands when swapping so user gets interesting options
            if nl in BASIC_LAND_NAMES:
                score -= 40.0

        elif category_norm == "ramp":
            score += 120.0
            if cmc <= 2:
                score += 25.0
            elif cmc > 4:
                score -= 15.0

        elif category_norm == "draw":
            score += 120.0
            if cmc <= 3:
                score += 20.0

        elif category_norm == "removal":
            score += 120.0
            if cmc <= 3:
                score += 20.0

        elif category_norm == "win_con":
            is_finisher = cmc >= 5 or "overrun" in oracle or "trample" in oracle or "infinite" in oracle or "damage to each" in oracle
            if is_finisher:
                score += 120.0
            else:
                score += 30.0

        elif category_norm == "synergy":
            score += 80.0

        # Proximity to replaced card's CMC
        if replaced_card:
            old_cmc = float(replaced_card.get("cmc") or 0.0)
            cmc_diff = abs(cmc - old_cmc)
            if cmc_diff <= 1.0:
                score += 15.0
            elif cmc_diff >= 4.0:
                score -= 10.0

        scored.append((score, card))

    # Sort descending by calculated score
    scored.sort(key=lambda x: x[0], reverse=True)

    # 5. Format & Return Top Candidates
    results: list[dict[str, Any]] = []
    for _, card in scored[:limit]:
        reason = generate_swap_reason(
            card=card,
            category=category_norm,
            commander=primary_commander,
            replaced_card=replaced_card,
            bracket=bracket
        )

        results.append({
            "name": card["name"],
            "mana_cost": card.get("mana_cost") or "",
            "cmc": float(card.get("cmc") or 0.0),
            "type_line": card.get("type_line") or "",
            "oracle_text": card.get("oracle_text") or "",
            "image_url": card.get("image_url") or "",
            "reason": reason
        })

    return results
