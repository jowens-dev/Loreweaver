"""Intrinsic Synergy Graph & Verb-Matching Engine for Loreweaver.

Evaluates cards through mechanical rules-text state transitions (Inputs / Triggers and Outputs / State Changes).
Identifies closed feedback loops (engines), weights direct Commander synergies at 2.5x,
and calculates composite scores using logarithmic budget drag and obscurity (spice) bonuses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:
    from scripts.pricing_engine import (
        calculate_price_penalty,
        calculate_spice_bonus,
        calculate_composite_score,
        get_manapool_affiliate_url,
        DEFAULT_SENTINEL_PRICE,
        DEFAULT_BETA
    )
except ImportError:
    from pricing_engine import (
        calculate_price_penalty,
        calculate_spice_bonus,
        calculate_composite_score,
        get_manapool_affiliate_url,
        DEFAULT_SENTINEL_PRICE,
        DEFAULT_BETA
    )

ALL_DOMAINS = [
    "creature_etb",
    "artifact_etb",
    "creature_dies",
    "artifact_dies",
    "card_draw",
    "card_discard",
    "life_gain",
    "life_loss",
    "counter_placed",
    "token_created",
    "graveyard_fill",
    "spells_cast",
    "land_etb",
    "mana_ramp",
]

DOMAIN_LABELS = {
    "creature_etb": "creature entering the battlefield",
    "artifact_etb": "artifact entering the battlefield",
    "creature_dies": "creature dying / death triggers",
    "artifact_dies": "artifact sacrifice / graveyard triggers",
    "card_draw": "drawing cards",
    "card_discard": "discarding cards",
    "life_gain": "gaining life",
    "life_loss": "opponent life loss / damage",
    "counter_placed": "+1/+1 and loyalty counters",
    "token_created": "creating tokens",
    "graveyard_fill": "filling the graveyard / milling",
    "spells_cast": "casting spells / magecraft",
    "land_etb": "landfall triggers",
    "mana_ramp": "mana acceleration",
}

# Regex patterns for card triggers / fuel requirements (Inputs)
INPUT_PATTERNS: dict[str, list[str]] = {
    "creature_etb": [
        r"whenever\s+.*(another\s+)?creature.*enters",
        r"when(ever)?\s+(this\s+creature|~)\s+enters",
        r"whenever\s+you\s+cast\s+a\s+creature\s+spell"
    ],
    "artifact_etb": [
        r"whenever\s+.*(an\s+)?artifact.*enters",
        r"whenever\s+you\s+cast\s+an\s+artifact"
    ],
    "creature_dies": [
        r"whenever\s+.*(creature|permanent).*\s+dies",
        r"when(ever)?\s+(this\s+creature|~)\s+dies",
        r"whenever\s+a\s+creature\s+is\s+put\s+into\s+a\s+graveyard",
        r"creature\s+you\s+control\s+dies"
    ],
    "artifact_dies": [
        r"whenever\s+an\s+artifact\s+(you\s+control\s+)?is\s+put\s+into\s+a\s+graveyard",
        r"whenever\s+you\s+sacrifice\s+an\s+artifact",
        r"whenever\s+a\s+treasure\s+is\s+sacrificed"
    ],
    "card_draw": [
        r"whenever\s+you\s+draw\s+a\s+card",
        r"whenever\s+a\s+player\s+draws\s+a\s+card",
        r"draw\s+your\s+second\s+card",
        r"more\s+cards\s+in\s+hand",
        r"cards\s+in\s+(your\s+)?hand",
        r"hand\s+size"
    ],
    "card_discard": [
        r"whenever\s+you\s+discard\s+a\s+card",
        r"whenever\s+an\s+opponent\s+discards",
        r"whenever\s+a\s+player\s+discards",
        r"more\s+cards\s+in\s+hand",
        r"fewer\s+cards\s+in\s+hand"
    ],
    "life_gain": [
        r"whenever\s+you\s+gain\s+life",
        r"for\s+each\s+1\s+life\s+you\s+gained"
    ],
    "life_loss": [
        r"whenever\s+an\s+opponent\s+loses\s+life",
        r"whenever\s+a\s+(player|opponent)\s+is\s+dealt\s+damage",
        r"deals\s+damage\s+to\s+(an\s+opponent|a\s+player)",
        r"lost\s+life\s+this\s+turn"
    ],
    "counter_placed": [
        r"whenever\s+.*counters?\s+(are|is)\s+put",
        r"whenever\s+you\s+put\s+.*counter",
        r"modified\s+creatures"
    ],
    "token_created": [
        r"whenever\s+you\s+create\s+.*token",
        r"if\s+one\s+or\s+more\s+tokens\s+would\s+be\s+created"
    ],
    "graveyard_fill": [
        r"whenever\s+a\s+card\s+is\s+put\s+into\s+your\s+graveyard",
        r"cards?\s+in\s+your\s+graveyard",
        r"undergrowth",
        r"return\s+.*\s+from\s+your\s+graveyard",
        r"leaves?\s+(your\s+)?graveyard",
        r"search\s+your\s+graveyard"
    ],
    "spells_cast": [
        r"whenever\s+(a\s+player|you)\s+casts?\s+(a\s+spell|an\s+instant|a\s+sorcery|a\s+noncreature|an\s+artifact)",
        r"magecraft",
        r"prowess",
        r"storm"
    ],
    "land_etb": [
        r"landfall",
        r"whenever\s+a\s+land\s+enters",
        r"sacrifice\s+a\s+(swamp|land|forest|mountain|island|plains)",
        r"whenever\s+a\s+land.*\s+is\s+put\s+into\s+a\s+graveyard"
    ],
    "mana_ramp": [
        r"whenever\s+you\s+tap\s+a\s+land\s+for\s+mana",
        r"whenever\s+you\s+add\s+mana"
    ],
}

# Regex patterns for state changes caused by card (Outputs)
OUTPUT_PATTERNS: dict[str, list[str]] = {
    "creature_etb": [
        r"create\s+(a|two|three|\d+|x)?\s*(tapped\s+)?.*creature\s+token",
        r"return\s+(target\s+)?creature\s+card\s+from\s+your\s+graveyard\s+to\s+the\s+battlefield",
        r"return\s+.*\s+from\s+your\s+graveyard\s+to\s+the\s+battlefield",
        r"put\s+a\s+creature\s+card\s+from\s+your\s+hand\s+onto\s+the\s+battlefield"
    ],
    "artifact_etb": [
        r"create\s+.*treasure\s+token",
        r"create\s+.*clue\s+token",
        r"create\s+.*food\s+token",
        r"create\s+.*blood\s+token",
        r"create\s+.*artifact\s+token",
        r"put\s+.*onto\s+the\s+battlefield"
    ],
    "creature_dies": [
        r"sacrifice\s+(a|another|one\s+or\s+more|two|\d+|x|a\s+nontoken)\s+creature",
        r"destroy\s+target\s+creature",
        r"each\s+player\s+sacrifices\s+a\s+creature",
        r"each\s+opponent\s+sacrifices\s+a\s+creature"
    ],
    "artifact_dies": [
        r"sacrifice\s+an\s+artifact",
        r"sacrifice\s+a\s+treasure",
        r"destroy\s+target\s+artifact"
    ],
    "card_draw": [
        r"draw\s+(a|\d+|x)?\s*cards?",
        r"investigate"
    ],
    "card_discard": [
        r"discard\s+(a|\d+|x)?\s*cards?",
        r"each\s+player\s+discards",
        r"each\s+opponent\s+discards"
    ],
    "life_gain": [
        r"you\s+gain\s+(\d+|x)?\s*life",
        r"lifelink",
        r"gains?\s+lifelink"
    ],
    "life_loss": [
        r"each\s+opponent\s+loses\s+(\d+|x)?\s*life",
        r"deals?\s+(\d+|x)?\s*damage\s+to\s+each\s+opponent",
        r"target\s+(player|opponent)\s+loses\s+(\d+|x)?\s*life",
        r"deals?\s+(\d+|x)?\s*damage\s+to\s+(any\s+target|target\s+opponent|target\s+player)"
    ],
    "counter_placed": [
        r"put\s+(a|one|two|\d+|x)?\s*(\+1\/\+1\s+)?counter",
        r"proliferate"
    ],
    "token_created": [
        r"create\s+.*token"
    ],
    "graveyard_fill": [
        r"mill\s+(\d+|x)?\s*cards?",
        r"surveil\s*(\d+|x)?",
        r"put\s+the\s+top\s+.*into\s+your\s+graveyard",
        r"counter\s+(that\s+spell|target\s+spell)"
    ],
    "spells_cast": [
        r"copy\s+target\s+(instant|sorcery)\s+spell",
        r"(you|that\s+player)\s+may\s+cast\s+.*without\s+paying"
    ],
    "land_etb": [
        r"you\s+may\s+play\s+an\s+additional\s+land",
        r"search\s+your\s+library\s+for\s+a\s+(basic\s+)?land.*onto\s+the\s+battlefield",
        r"sacrifice\s+a\s+(swamp|land)"
    ],
    "mana_ramp": [
        r"add\s+\{",
        r"adds\s+\{",
        r"adds?\s+.*mana"
    ],
}


@dataclass
class CardVector:
    """State transition vector representation of a Magic card."""
    name: str
    type_line: str
    cmc: float
    oracle_text: str
    inputs: dict[str, float] = field(default_factory=dict)
    outputs: dict[str, float] = field(default_factory=dict)
    is_permanent: bool = False
    is_repeatable: bool = False


def compile_card_vector(card: dict[str, Any]) -> CardVector:
    """Scan card oracle text and metadata to construct state transition input/output vectors."""
    name = str(card.get("name") or "")
    type_line = str(card.get("type_line") or "").lower()
    cmc = float(card.get("cmc") or 0.0)
    oracle = str(card.get("oracle_text") or "").lower()

    is_permanent = any(t in type_line for t in ["creature", "artifact", "enchantment", "planeswalker", "battle", "land"])

    # Determine if repeatable (permanents without once-per-turn limits)
    has_once_limit = "only once each turn" in oracle or "only once per turn" in oracle or "activate only as a sorcery and only once" in oracle
    is_repeatable = is_permanent and not has_once_limit and ("whenever" in oracle or "{" in oracle or "at the beginning" in oracle)

    inputs: dict[str, float] = {}
    outputs: dict[str, float] = {}

    for domain, patterns in INPUT_PATTERNS.items():
        weight = 0.0
        for pattern in patterns:
            if re.search(pattern, oracle, re.IGNORECASE):
                weight += 1.0
        if weight > 0.0:
            inputs[domain] = min(2.5, weight)

    for domain, patterns in OUTPUT_PATTERNS.items():
        weight = 0.0
        for pattern in patterns:
            if re.search(pattern, oracle, re.IGNORECASE):
                weight += 1.0
        if weight > 0.0:
            outputs[domain] = min(2.5, weight)

    # Inherent type line outputs
    if "instant" in type_line or "sorcery" in type_line:
        outputs["spells_cast"] = max(outputs.get("spells_cast", 0.0), 1.0)
    if "creature" in type_line:
        outputs["creature_etb"] = max(outputs.get("creature_etb", 0.0), 1.0)
    if "artifact" in type_line:
        outputs["artifact_etb"] = max(outputs.get("artifact_etb", 0.0), 1.0)
    if "land" in type_line:
        outputs["land_etb"] = max(outputs.get("land_etb", 0.0), 1.0)

    return CardVector(
        name=name,
        type_line=type_line,
        cmc=cmc,
        oracle_text=oracle,
        inputs=inputs,
        outputs=outputs,
        is_permanent=is_permanent,
        is_repeatable=is_repeatable
    )


def evaluate_pairwise_synergy(
    card_a: CardVector,
    card_b: CardVector,
    is_commander: bool = False
) -> tuple[float, list[str], bool]:
    """Calculate mechanical link strength and detect closed feedback loops between two cards.

    Returns:
        (score, interaction_notes, is_closed_loop)
    """
    fwd_matches: list[str] = []
    bwd_matches: list[str] = []

    fwd_link = 0.0
    for domain in ALL_DOMAINS:
        out_a = card_a.outputs.get(domain, 0.0)
        in_b = card_b.inputs.get(domain, 0.0)
        if out_a > 0.0 and in_b > 0.0:
            fwd_link += out_a * in_b
            fwd_matches.append(domain)

    bwd_link = 0.0
    for domain in ALL_DOMAINS:
        out_b = card_b.outputs.get(domain, 0.0)
        in_a = card_a.inputs.get(domain, 0.0)
        if out_b > 0.0 and in_a > 0.0:
            bwd_link += out_b * in_a
            bwd_matches.append(domain)

    total_base = fwd_link + bwd_link
    if total_base <= 0.0:
        return (0.0, [], False)

    # Closed loop requires cross-domain state transitions (fwd_domain != bwd_domain)
    # to prevent false cycles between two mutual consumers (e.g. creature_dies <-> creature_dies)
    is_closed_loop = (fwd_link > 0.0 and bwd_link > 0.0 and any(f_d != b_d for f_d in fwd_matches for b_d in bwd_matches))

    # Multiplier: 3.0x for repeatable permanent engine loops, 1.75x for general loops, 1.0x baseline
    if is_closed_loop:
        if card_a.is_repeatable and card_b.is_repeatable:
            loop_multiplier = 3.0
        else:
            loop_multiplier = 1.75
    else:
        loop_multiplier = 1.0

    # Commander Weight: Direct interactions with Commander weighted at 2.5x
    target_multiplier = 2.5 if is_commander else 1.0

    score = total_base * loop_multiplier * target_multiplier * 20.0

    notes: list[str] = []
    if is_closed_loop:
        fwd_str = fwd_matches[0] if fwd_matches else "fuel"
        bwd_str = bwd_matches[0] if bwd_matches else "trigger"
        notes.append(f"Forms closed feedback loop with {card_b.name}: ({fwd_str} ⇄ {bwd_str})")
    elif fwd_matches:
        d_label = DOMAIN_LABELS.get(fwd_matches[0], fwd_matches[0])
        notes.append(f"Generates {d_label} which triggers {card_b.name}")
    elif bwd_matches:
        d_label = DOMAIN_LABELS.get(bwd_matches[0], bwd_matches[0])
        notes.append(f"Fueled by {d_label} produced by {card_b.name}")

    return (score, notes, is_closed_loop)


def evaluate_candidate_in_deck(
    candidate_card: dict[str, Any],
    commander_card: dict[str, Any] | None,
    deck_cards: list[dict[str, Any]] | None = None,
    price: float | None = None,
    beta: float = DEFAULT_BETA
) -> dict[str, Any]:
    """Evaluate candidate card against Commander and 99 using rules-text vectors and logarithmic price drag."""
    cand_vec = compile_card_vector(candidate_card)
    raw_synergy = 0.0
    all_notes: list[str] = []
    has_closed_loop = False

    # 1. Commander Interaction (2.5x weight) - exclude self-evaluation
    cand_name_norm = candidate_card.get("name", "").strip().lower()
    if commander_card and commander_card.get("name", "").strip().lower() != cand_name_norm:
        cmd_vec = compile_card_vector(commander_card)
        cmd_score, cmd_notes, cmd_loop = evaluate_pairwise_synergy(cand_vec, cmd_vec, is_commander=True)
        raw_synergy += cmd_score
        all_notes.extend(cmd_notes)
        if cmd_loop:
            has_closed_loop = True

    # 2. Interactions with the 99 (1.0x weight)
    if deck_cards:
        for d_card in deck_cards:
            if not d_card or d_card.get("name", "").strip().lower() == cand_name_norm:
                continue
            d_vec = compile_card_vector(d_card)
            d_score, d_notes, d_loop = evaluate_pairwise_synergy(cand_vec, d_vec, is_commander=False)
            raw_synergy += d_score
            if d_notes and len(all_notes) < 4:
                all_notes.extend(d_notes)
            if d_loop:
                has_closed_loop = True

    # 3. Calculate Obscurity / Spice Bonus & Price Drag
    # If a card has zero actual mechanical synergy, it receives 0.0 to prevent zero-synergy obscurity inversion
    edhrec_rank = candidate_card.get("edhrec_rank")
    if raw_synergy > 0.0:
        raw_synergy = max(5.0, raw_synergy)
        spice_bonus = calculate_spice_bonus(edhrec_rank)
        price_penalty = calculate_price_penalty(price, beta=beta)
        composite_score = calculate_composite_score(raw_synergy, price, edhrec_rank, beta=beta)
    else:
        raw_synergy = 0.0
        spice_bonus = 1.0
        price_penalty = calculate_price_penalty(price, beta=beta)
        composite_score = 0.0

    # Clean & deduplicate interaction notes
    unique_notes = list(dict.fromkeys(all_notes))[:3]
    if not unique_notes:
        cmc = candidate_card.get("cmc", 0)
        unique_notes.append(f"Curve-efficient {cmc} CMC tactical role player")

    mana_pool_url = get_manapool_affiliate_url(candidate_card.get("name", ""))

    return {
        "name": candidate_card.get("name", ""),
        "price": price if price is not None else DEFAULT_SENTINEL_PRICE,
        "raw_synergy": round(raw_synergy, 2),
        "spice_bonus": round(spice_bonus, 2),
        "price_penalty": round(price_penalty, 2),
        "composite_score": round(composite_score, 2),
        "has_closed_loop": has_closed_loop,
        "interaction_notes": unique_notes,
        "mana_pool_url": mana_pool_url,
    }
