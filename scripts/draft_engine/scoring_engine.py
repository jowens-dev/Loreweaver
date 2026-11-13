"""Mathematical MTG Draft Pick Scoring Engine inspired by Draftsmith.

Evaluates draft candidates across five core dimensions:
1. Baseline Score: derived from Game-In-Hand win rate (GIH WR), Improvement When Drawn (IWD),
   or algorithmic fallbacks based on card rarity, CMC curve-efficiency, and EDHREC popularity rank.
2. Color Commitment Weight: Bayesian probability model updating over all 10 two-color archetypes.
   Maintains open flexibility in early Pack 1, aggressively penalizing off-color picks in Pack 2/3
   unless determined to be viable splash candidates.
3. Curve Adjustment: dynamic mana curve regulation rewarding scarce 2-drops and penalizing
   saturation of 5+ CMC high-end spells as draft progresses.
4. Synergy Bonus: integrates state transition input/output vectors from scripts/synergy_engine.py
   to identify closed mechanical feedback loops and trigger/fuel complementarities.
5. Composite Rating: calibrated to 1.0 - 55.0 scale with Draftsmith tier badges
   ('S', 'A', 'B', 'C', 'D', 'F') and actionable micro-insight explanations.
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Ensure workspace root is accessible for imports
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

# Optional import of synergy engine with fallback
try:
    from scripts.synergy_engine import (
        CardVector,
        compile_card_vector,
        evaluate_pairwise_synergy,
        ALL_DOMAINS,
    )
except ImportError:
    # Graceful standalone fallback if synergy_engine is relocated
    @dataclass
    class CardVector:  # type: ignore[no-redef]
        name: str
        type_line: str
        cmc: float
        oracle_text: str
        inputs: dict[str, float] = field(default_factory=dict)
        outputs: dict[str, float] = field(default_factory=dict)
        is_permanent: bool = False
        is_repeatable: bool = False

    ALL_DOMAINS = [  # type: ignore[no-redef]
        "creature_etb", "artifact_etb", "creature_dies", "artifact_dies",
        "card_draw", "card_discard", "life_gain", "life_loss",
        "counter_placed", "token_created", "graveyard_fill", "spells_cast",
        "land_etb", "mana_ramp"
    ]

    def compile_card_vector(card: dict[str, Any]) -> CardVector:  # type: ignore[misc]
        name = str(card.get("name") or "")
        t_line = str(card.get("type_line") or "").lower()
        cmc = float(card.get("cmc") or 0.0)
        oracle = str(card.get("oracle_text") or "").lower()
        inputs: dict[str, float] = {}
        outputs: dict[str, float] = {}
        if "draw" in oracle:
            outputs["card_draw"] = 1.0
        if "creature" in t_line:
            outputs["creature_etb"] = 1.0
        if "sacrifice" in oracle or "dies" in oracle:
            inputs["creature_dies"] = 1.0
        return CardVector(
            name=name, type_line=t_line, cmc=cmc, oracle_text=oracle,
            inputs=inputs, outputs=outputs,
            is_permanent="creature" in t_line or "artifact" in t_line,
            is_repeatable=False
        )

    def evaluate_pairwise_synergy(  # type: ignore[misc]
        card_a: CardVector, card_b: CardVector, is_commander: bool = False
    ) -> tuple[float, list[str], bool]:
        score = 0.0
        notes: list[str] = []
        for d in ALL_DOMAINS:
            out_a = card_a.outputs.get(d, 0.0)
            in_b = card_b.inputs.get(d, 0.0)
            if out_a > 0.0 and in_b > 0.0:
                score += out_a * in_b * 15.0
                notes.append(f"Synergizes with {card_b.name} on {d}")
        return (score, notes, False)


# Two-color draft archetype constants
ARCHETYPE_PAIRS: list[str] = [
    "WU", "UB", "BR", "RG", "GW", "WB", "BG", "GU", "UR", "RW"
]

ARCHETYPE_NAMES: dict[str, str] = {
    "WU": "Azorius",
    "UB": "Dimir",
    "BR": "Rakdos",
    "RG": "Gruul",
    "GW": "Selesnya",
    "WB": "Orzhov",
    "BG": "Golgari",
    "GU": "Simic",
    "UR": "Izzet",
    "RW": "Boros",
}

ARCHETYPE_COLOR_SETS: dict[str, set[str]] = {
    pair: set(pair) for pair in ARCHETYPE_PAIRS
}

VALID_COLORS: set[str] = {"W", "U", "B", "R", "G"}

# Tier threshold bounds
TIER_THRESHOLDS = [
    (46.0, "S"),
    (38.0, "A"),
    (30.0, "B"),
    (22.0, "C"),
    (14.0, "D"),
    (0.0,  "F"),
]


def extract_card_colors(card: dict[str, Any]) -> set[str]:
    """Safely extract MTG color identity set from various representation formats."""
    colors = set()

    # 1. Inspect 'colors' field
    raw_colors = card.get("colors")
    if isinstance(raw_colors, (list, tuple, set)):
        for c in raw_colors:
            if isinstance(c, str):
                c_clean = c.strip().upper()
                if c_clean in VALID_COLORS:
                    colors.add(c_clean)
    elif isinstance(raw_colors, str):
        for ch in raw_colors.upper():
            if ch in VALID_COLORS:
                colors.add(ch)

    # 2. Inspect 'color_identity' if colors empty
    if not colors:
        raw_id = card.get("color_identity")
        if isinstance(raw_id, (list, tuple, set)):
            for c in raw_id:
                if isinstance(c, str) and c.strip().upper() in VALID_COLORS:
                    colors.add(c.strip().upper())
        elif isinstance(raw_id, str):
            for ch in raw_id.upper():
                if ch in VALID_COLORS:
                    colors.add(ch)

    # 3. Fallback to mana_cost parsing
    if not colors:
        mana_cost = str(card.get("mana_cost") or "").upper()
        for c in VALID_COLORS:
            if f"{{{c}}}" in mana_cost or f"/{c}" in mana_cost or f"{c}/" in mana_cost:
                colors.add(c)

    return colors


def count_colored_pips(mana_cost: str) -> dict[str, int]:
    """Count colored mana pips in a card's mana cost string."""
    pips: dict[str, int] = {c: 0 for c in VALID_COLORS}
    if not mana_cost:
        return pips

    symbols = re.findall(r"\{([^}]+)\}", mana_cost.upper())
    for sym in symbols:
        # Standard single pips
        if sym in VALID_COLORS:
            pips[sym] += 1
        # Hybrid symbols like W/U or 2/R
        elif "/" in sym:
            parts = sym.split("/")
            for p in parts:
                if p in VALID_COLORS:
                    pips[p] += 1
    return pips


def parse_float_safely(val: Any) -> Optional[float]:
    """Safely parse float from string, float, or integer inputs."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace("%", "").replace("+", "").strip()
        try:
            parsed = float(cleaned)
            if math.isnan(parsed) or math.isinf(parsed):
                return None
            return parsed
        except ValueError:
            return None
    return None


def calculate_baseline_score(card: dict[str, Any]) -> tuple[float, list[str]]:
    """Compute baseline card power rating (0-52 scale) and micro-insight notes.

    Prioritizes 17lands Game-In-Hand Win Rate (GIH WR) and Improvement When Drawn (IWD).
    Falls back to rarity, CMC curve-efficiency, and EDHREC popularity rank.
    """
    insights: list[str] = []
    gih_wr_raw = parse_float_safely(card.get("gih_wr"))
    if gih_wr_raw is None:
        gih_wr_raw = parse_float_safely(card.get("win_rate"))

    iwd_raw = parse_float_safely(card.get("iwd"))

    cmc_raw = parse_float_safely(card.get("cmc"))
    cmc = cmc_raw if cmc_raw is not None and cmc_raw >= 0.0 else 2.0

    rarity = str(card.get("rarity") or "").strip().lower()

    if gih_wr_raw is not None:
        # Normalize percentage (e.g. 58.5 -> 0.585)
        gih_wr = gih_wr_raw / 100.0 if gih_wr_raw > 1.0 else gih_wr_raw
        gih_wr = max(0.35, min(0.75, gih_wr))

        # 40% GIH WR -> 10.0, 55% (average) -> 30.36, 68% (bomb) -> 48.0
        wr_norm = (gih_wr - 0.40) / 0.28
        base_score = 10.0 + (38.0 * wr_norm)

        # Improvement When Drawn (IWD) adjustment
        if iwd_raw is not None:
            iwd = iwd_raw / 100.0 if abs(iwd_raw) > 1.0 else iwd_raw
            iwd_clamped = max(-0.12, min(0.12, iwd))
            iwd_adjustment = iwd_clamped * 45.0
            base_score += iwd_adjustment
            if iwd > 0.03:
                insights.append(f"Strong top-deck impact (+{iwd*100:.1f}% IWD)")
            elif iwd < -0.03:
                insights.append(f"Opening-hand reliant ({iwd*100:.1f}% IWD)")

        pct_display = gih_wr * 100.0
        if gih_wr >= 0.60:
            insights.append(f"Format bomb ({pct_display:.1f}% GIH WR)")
        elif gih_wr >= 0.55:
            insights.append(f"Solid limited staple ({pct_display:.1f}% GIH WR)")
        elif gih_wr < 0.48:
            insights.append(f"Below average win rate ({pct_display:.1f}% GIH WR)")
    else:
        # Algorithmic fallback using Rarity, CMC curve value, and EDHREC rank
        rarity_bases = {
            "mythic": 38.0,
            "rare": 34.0,
            "special": 33.0,
            "uncommon": 28.0,
            "common": 24.0,
            "bonus": 27.0,
            "land": 12.0,
        }
        type_line = str(card.get("type_line") or "").lower()
        if "basic land" in type_line:
            base_score = 10.0
            insights.append("Basic land mana source")
        else:
            base_score = rarity_bases.get(rarity, 25.0)

            # CMC curve efficiency adjustments for limited
            if cmc == 2:
                base_score += 2.0
            elif cmc == 3:
                base_score += 1.5
            elif cmc == 4:
                base_score += 0.5
            elif cmc == 1:
                base_score += 0.0
            elif cmc == 5:
                base_score -= 1.0
            elif cmc == 6:
                base_score -= 2.5
            elif cmc >= 7:
                base_score -= 4.0
            elif cmc == 0:
                base_score -= 3.0

            # EDHREC popularity rank bonus/penalty
            edhrec_raw = parse_float_safely(card.get("edhrec_rank"))
            if edhrec_raw is not None and edhrec_raw > 0:
                rank_mod = max(-4.0, min(4.0, (10000.0 - edhrec_raw) / 2500.0))
                base_score += rank_mod

            rarity_label = rarity.capitalize() if rarity else "Common"
            insights.append(f"Heuristic rating based on {rarity_label} rarity and {int(cmc)} CMC")

    clamped_score = max(5.0, min(52.0, base_score))
    return round(clamped_score, 2), insights


def calculate_bayesian_archetype_probabilities(
    picked_cards: list[dict[str, Any]]
) -> dict[str, float]:
    """Compute posterior probability distribution over all 10 two-color archetypes.

    Starts with uniform prior P(A) = 0.10.
    Updates iteratively using likelihoods of drafted colored cards.
    """
    if not picked_cards:
        return {pair: 0.10 for pair in ARCHETYPE_PAIRS}

    log_probs: dict[str, float] = {pair: math.log(0.10) for pair in ARCHETYPE_PAIRS}

    for card in picked_cards:
        colors = extract_card_colors(card)
        if not colors:
            # Colorless artifacts and land don't sway archetype distribution
            continue

        for pair, pair_colors in ARCHETYPE_COLOR_SETS.items():
            if colors.issubset(pair_colors):
                # Strongly supports this archetype
                if len(colors) == 2:
                    likelihood = 1.85  # Dedicated gold signpost card
                else:
                    likelihood = 1.30  # Monocolor on-color spell
            else:
                # Off-color card
                overlap = colors.intersection(pair_colors)
                if overlap:
                    # Partial 1-color overlap but has an off-color splash
                    likelihood = 0.50
                else:
                    # Completely off-color
                    likelihood = 0.20

            log_probs[pair] += math.log(likelihood)

    # Softmax normalization for numerical stability
    max_log = max(log_probs.values())
    exp_probs = {pair: math.exp(lp - max_log) for pair, lp in log_probs.items()}
    total_exp = sum(exp_probs.values())
    if total_exp <= 0.0:
        return {pair: 0.10 for pair in ARCHETYPE_PAIRS}

    return {pair: exp_p / total_exp for pair, exp_p in exp_probs.items()}


def is_card_splashable(card: dict[str, Any], baseline_score: float) -> bool:
    """Determine whether an off-color candidate can viably be splashed in a draft deck."""
    cmc_raw = parse_float_safely(card.get("cmc"))
    cmc = cmc_raw if cmc_raw is not None else 3.0

    # Never splash 1-drops or 2-drops (tempo-critical on curve)
    if cmc < 3.0:
        return False

    mana_cost = str(card.get("mana_cost") or "").upper()
    pip_counts = count_colored_pips(mana_cost)

    # A card requiring multiple distinct off-colors cannot be splashed in a 2-color limited deck
    if len(pip_counts) > 1 and sum(pip_counts.values()) > 1:
        return False

    # Cards requiring double or triple off-color pips cannot be reliably splashed
    max_colored_pips = max(pip_counts.values()) if pip_counts else 0
    if max_colored_pips > 1:
        return False

    # Only splash high-impact cards or bombs
    if baseline_score < 30.0:
        return False

    return True


def calculate_color_commitment_weight(
    candidate: dict[str, Any],
    archetype_probs: dict[str, float],
    pack_num: int,
    pick_num: int,
    baseline_score: float
) -> tuple[float, list[str]]:
    """Calculate color commitment multiplier for a candidate pick.

    Pack 1: Drafter stays open; off-color cards receive minimal penalty.
    Pack 2/3: Drastically penalizes off-color cards unless splashable.
    """
    insights: list[str] = []
    card_colors = extract_card_colors(candidate)

    # Colorless cards fit in every archetype without friction
    if not card_colors:
        insights.append("Colorless flexibility (fits all archetypes)")
        return 1.0, insights

    splashable = is_card_splashable(candidate, baseline_score)

    # Evaluate compatibility with each archetype
    weighted_fit = 0.0
    top_archetypes = sorted(archetype_probs.items(), key=lambda kv: kv[1], reverse=True)
    best_archetype, best_prob = top_archetypes[0]

    for pair, pair_colors in ARCHETYPE_COLOR_SETS.items():
        prob = archetype_probs.get(pair, 0.10)
        if card_colors.issubset(pair_colors):
            fit = 1.12 if len(card_colors) == 2 else 1.02
        else:
            if splashable:
                fit = 0.45  # Viable splash
            else:
                fit = 0.10  # Harsh uncastable off-color penalty
        weighted_fit += prob * fit

    # Sigmoid progression factor t in [0.0, 1.0] across the draft
    # 3 packs * 14 picks = 42 total picks
    total_pick_idx = max(1, min(42, (pack_num - 1) * 14 + pick_num))
    t = (total_pick_idx - 1) / 41.0

    # Commitment stringency lambda(t)
    # Pack 1 Pick 1 (t=0.0): lambda ~ 0.06 -> drafter is ~94% open
    # Pack 2 Pick 1 (t=0.34): lambda ~ 0.48 -> picking up commitment
    # Pack 3 Pick 1 (t=0.68): lambda ~ 0.93 -> heavily committed
    lambda_t = 1.0 / (1.0 + math.exp(-8.0 * (t - 0.35)))

    weight = (1.0 - lambda_t) * 1.0 + lambda_t * weighted_fit
    weight = max(0.10, min(1.15, weight))

    # Insights generation
    is_on_primary = card_colors.issubset(ARCHETYPE_COLOR_SETS[best_archetype])
    arch_label = ARCHETYPE_NAMES.get(best_archetype, best_archetype)

    if is_on_primary and best_prob > 0.30:
        insights.append(f"Primary archetype fit: {arch_label} ({best_archetype}: {best_prob*100:.0f}% confidence)")
    elif not is_on_primary and splashable and pack_num >= 2:
        insights.append("Viable splash candidate (single colored pip)")
    elif not is_on_primary and pack_num >= 2:
        insights.append(f"Off-color in {arch_label} ({best_archetype})")

    return round(weight, 3), insights


def calculate_curve_adjustment(
    candidate: dict[str, Any],
    picked_cards: list[dict[str, Any]],
    pack_num: int,
    pick_num: int
) -> tuple[float, list[str]]:
    """Calculate curve balancing adjustment.

    Rewards 2-drops if currently lacking; penalizes 5+ drops if already saturated.
    Scales with draft progression.
    """
    insights: list[str] = []
    cmc_raw = parse_float_safely(candidate.get("cmc"))
    cmc = cmc_raw if cmc_raw is not None else 2.0

    type_line = str(candidate.get("type_line") or "").lower()
    if "land" in type_line and "creature" not in type_line:
        return 0.0, insights

    # Tally non-land curve in current picked pool
    picked_spells = [
        c for c in picked_cards
        if "land" not in str(c.get("type_line") or "").lower()
    ]
    total_spells = len(picked_spells)

    n_2drops = sum(1 for c in picked_spells if parse_float_safely(c.get("cmc")) == 2.0)
    n_high_drops = sum(1 for c in picked_spells if (parse_float_safely(c.get("cmc")) or 0.0) >= 5.0)

    total_pick_idx = max(1, min(42, (pack_num - 1) * 14 + pick_num))
    progress = (total_pick_idx - 1) / 41.0
    prog_multiplier = 0.30 + (0.70 * progress)

    adjustment = 0.0

    if cmc == 2.0:
        # Expected ~6 two-drops in a 23-spell deck (ratio ~0.26)
        expected_2drops = total_spells * (6.0 / 23.0)
        deficit = expected_2drops - n_2drops
        if deficit > 0.5:
            bonus = min(6.0, (1.5 + deficit * 1.5) * prog_multiplier)
            adjustment += bonus
            if total_spells >= 6:
                insights.append(f"Fills critical 2-drop curve deficit (+{bonus:.1f})")
        elif n_2drops >= 8:
            penalty = -1.5 * prog_multiplier
            adjustment += penalty
            insights.append("Sufficient 2-drops already drafted")
        else:
            adjustment += 0.5 * prog_multiplier

    elif cmc >= 5.0:
        # Limited decks only want 2-3 spells of CMC 5+
        if n_high_drops >= 3:
            excess = n_high_drops - 2
            penalty = -min(8.0, (1.5 + excess * 2.0) * prog_multiplier)
            adjustment += penalty
            insights.append(f"Penalized for 5+ CMC saturation ({n_high_drops} already drafted, {penalty:.1f})")
        elif n_high_drops == 2 and progress > 0.5:
            penalty = -1.0 * prog_multiplier
            adjustment += penalty
            insights.append("Approaching high-CMC threshold")

    elif cmc == 3.0:
        n_3drops = sum(1 for c in picked_spells if parse_float_safely(c.get("cmc")) == 3.0)
        if n_3drops >= 7:
            adjustment -= 1.5 * prog_multiplier

    elif cmc == 4.0:
        n_4drops = sum(1 for c in picked_spells if parse_float_safely(c.get("cmc")) == 4.0)
        if n_4drops >= 6:
            adjustment -= 2.0 * prog_multiplier

    clamped_adj = max(-8.0, min(6.0, adjustment))
    return round(clamped_adj, 2), insights


def calculate_synergy_bonus(
    candidate: dict[str, Any],
    picked_cards: list[dict[str, Any]]
) -> tuple[float, list[str], bool]:
    """Calculate mechanical synergy bonus and feedback loops with drafted cards.

    Uses CardVector representations and state transition inputs/outputs.
    """
    if not picked_cards:
        return 0.0, [], False

    cand_vec = compile_card_vector(candidate)
    raw_synergy = 0.0
    synergy_notes: list[str] = []
    has_closed_loop = False

    cand_name_norm = str(candidate.get("name") or "").strip().lower()

    for picked in picked_cards:
        p_name = str(picked.get("name") or "").strip().lower()
        if p_name == cand_name_norm:
            continue

        p_vec = compile_card_vector(picked)
        score, notes, is_loop = evaluate_pairwise_synergy(cand_vec, p_vec, is_commander=False)

        if score > 0.0:
            raw_synergy += score
            if notes and len(synergy_notes) < 3:
                synergy_notes.extend(notes)
            if is_loop:
                has_closed_loop = True

    # Scale raw synergy logarithmically/sub-linearly to 0-10 draft bonus
    if raw_synergy > 0.0:
        base_bonus = min(8.0, math.sqrt(raw_synergy) * 0.70)
        if has_closed_loop:
            bonus = min(10.0, base_bonus + 2.5)
            clean_notes = [f"Mechanical loop detected with drafted cards (+{bonus:.1f})"]
        else:
            bonus = base_bonus
            clean_notes = [f"Synergizes with pool (+{bonus:.1f})"]
        if synergy_notes:
            clean_notes.append(synergy_notes[0])
    else:
        bonus = 0.0
        clean_notes = []

    return round(bonus, 2), clean_notes, has_closed_loop


def get_tier_badge(composite_rating: float) -> str:
    """Map composite rating (1.0 - 55.0) to Draftsmith tier badge."""
    for threshold, tier in TIER_THRESHOLDS:
        if composite_rating >= threshold:
            return tier
    return "F"


@dataclass
class ScoredCard:
    """Structured evaluation output for an MTG draft candidate."""
    name: str
    composite_rating: float
    tier: str
    tier_badge: str
    baseline_score: float
    color_commitment_weight: float
    curve_adjustment: float
    synergy_bonus: float
    has_closed_loop: bool
    micro_insights: list[str]
    top_archetypes: list[tuple[str, float]]
    card_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard dictionary payload."""
        result = dict(self.card_data)
        result.update({
            "name": self.name,
            "composite_rating": self.composite_rating,
            "tier": self.tier,
            "tier_badge": self.tier_badge,
            "baseline_score": self.baseline_score,
            "color_commitment_weight": self.color_commitment_weight,
            "curve_adjustment": self.curve_adjustment,
            "synergy_bonus": self.synergy_bonus,
            "has_closed_loop": self.has_closed_loop,
            "micro_insights": self.micro_insights,
            "top_archetypes": self.top_archetypes,
        })
        return result


class DraftScoringEngine:
    """Engine for computing draft pick scores and recommendations."""

    def __init__(self) -> None:
        pass

    def score_single_candidate(
        self,
        candidate: dict[str, Any],
        picked_cards: list[dict[str, Any]],
        pack_num: int = 1,
        pick_num: int = 1,
        cached_archetype_probs: Optional[dict[str, float]] = None
    ) -> ScoredCard:
        """Score a single candidate card given currently picked cards and draft progress."""
        pack_num = max(1, min(3, int(pack_num)))
        pick_num = max(1, min(14, int(pick_num)))

        name = str(candidate.get("name") or "Unknown Card")

        # 1. Baseline Score
        baseline, base_insights = calculate_baseline_score(candidate)

        # 2. Color Commitment Weight
        if cached_archetype_probs is None:
            cached_archetype_probs = calculate_bayesian_archetype_probabilities(picked_cards)

        color_weight, color_insights = calculate_color_commitment_weight(
            candidate=candidate,
            archetype_probs=cached_archetype_probs,
            pack_num=pack_num,
            pick_num=pick_num,
            baseline_score=baseline
        )

        # 3. Curve Adjustment
        curve_adj, curve_insights = calculate_curve_adjustment(
            candidate=candidate,
            picked_cards=picked_cards,
            pack_num=pack_num,
            pick_num=pick_num
        )

        # 4. Synergy Bonus
        synergy_pts, synergy_insights, has_loop = calculate_synergy_bonus(
            candidate=candidate,
            picked_cards=picked_cards
        )

        # 5. Composite Rating (1.0 to 55.0 scale)
        raw_composite = (baseline * color_weight) + curve_adj + synergy_pts
        composite_rating = round(max(1.0, min(55.0, raw_composite)), 1)
        tier = get_tier_badge(composite_rating)

        # Combine micro-insights (deduplicating and capping at 4)
        all_insights: list[str] = []
        for note in base_insights + color_insights + curve_insights + synergy_insights:
            if note and note not in all_insights:
                all_insights.append(note)

        top_archetypes = sorted(
            cached_archetype_probs.items(),
            key=lambda kv: kv[1],
            reverse=True
        )[:3]

        return ScoredCard(
            name=name,
            composite_rating=composite_rating,
            tier=tier,
            tier_badge=tier,
            baseline_score=baseline,
            color_commitment_weight=color_weight,
            curve_adjustment=curve_adj,
            synergy_bonus=synergy_pts,
            has_closed_loop=has_loop,
            micro_insights=all_insights[:4],
            top_archetypes=top_archetypes,
            card_data=candidate,
        )

    def score_candidates(
        self,
        candidate_cards: list[dict[str, Any]],
        picked_cards: list[dict[str, Any]],
        pack_num: int = 1,
        pick_num: int = 1
    ) -> list[dict[str, Any]]:
        """Score candidate cards and return list sorted descending by composite rating."""
        if not candidate_cards:
            return []

        # Precompute archetype probabilities once for the entire pack
        archetype_probs = calculate_bayesian_archetype_probabilities(picked_cards)

        scored_cards: list[ScoredCard] = []
        for card in candidate_cards:
            scored = self.score_single_candidate(
                candidate=card,
                picked_cards=picked_cards,
                pack_num=pack_num,
                pick_num=pick_num,
                cached_archetype_probs=archetype_probs
            )
            scored_cards.append(scored)

        # Sort by composite_rating descending, then baseline_score descending
        scored_cards.sort(
            key=lambda sc: (sc.composite_rating, sc.baseline_score),
            reverse=True
        )

        return [sc.to_dict() for sc in scored_cards]


# Global singleton instance & convenience functions
_DEFAULT_ENGINE = DraftScoringEngine()


def score_candidates(
    candidate_cards: list[dict[str, Any]],
    picked_cards: list[dict[str, Any]],
    pack_num: int = 1,
    pick_num: int = 1
) -> list[dict[str, Any]]:
    """Score candidate cards using default DraftScoringEngine."""
    return _DEFAULT_ENGINE.score_candidates(
        candidate_cards=candidate_cards,
        picked_cards=picked_cards,
        pack_num=pack_num,
        pick_num=pick_num
    )


def score_pack(
    candidate_cards: list[dict[str, Any]],
    picked_cards: list[dict[str, Any]],
    pack_num: int = 1,
    pick_num: int = 1
) -> list[dict[str, Any]]:
    """Alias for score_candidates."""
    return score_candidates(
        candidate_cards=candidate_cards,
        picked_cards=picked_cards,
        pack_num=pack_num,
        pick_num=pick_num
    )
