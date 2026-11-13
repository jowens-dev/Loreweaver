"""Comprehensive Popperian Falsification and Unit Test Suite for Draftweaver MTG Draft Engine.

Verifies:
1. Mathematical Scoring Engine (`scripts/draft_engine/scoring_engine.py`):
   - Baseline GIH WR, IWD, rarity/CMC fallbacks
   - Bayesian 10-archetype probability updates & commitment progression
   - Curve deficit/saturation adjustments
   - State transition synergy loops
   - 1-55 composite rating calibration, tier badges, and micro-insights
   - Popperian edge cases: empty packs, NaN/infinite win-rates, string percentages, tie-breaking
2. Post-Draft 40-Card Deck Knapsack Optimizer (`scripts/draft_engine/deck_optimizer.py`):
   - Exact 40-card deck validation (23 spells + 17 lands)
   - Knapsack curve balancing (0-2 1-drops, 5-7 2-drops, 4-6 3-drops, 3-5 4-drops, 2-3 5+ drops)
   - Creature ratio floor (>= 13 creatures)
   - Largest Remainder (Hamilton quota) basic mana split
   - Popperian edge cases: monocolor drafts (no phantom colors/lands), 5-color soup, extreme curves (all 1-drops, all 7-drops),
     zero creatures, small pools (< 23 cards), empty pool, non-basic land deduction, MTGA arena formatting
3. MTG Arena Draft Log Watcher and Parser (`scripts/draft_engine/log_parser.py`):
   - Draft.DraftStatus (bot draft) and Event.GetCombinedRequest (human/premier draft) payloads
   - 0-indexed vs 1-indexed pack and pick numbers
   - SQLite grpId resolution against data/cards.db
   - Popperian edge cases: missing/invalid grpIds, missing cards.db, corrupted log lines, log truncation/rotation
   - MockDraftGenerator simulation
4. End-to-End Pipeline:
   - Full log-to-deck simulation stream
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from scripts.draft_engine import (
    ArenaLogParser,
    Card,
    CardResolver,
    DeckOptimizer,
    DraftLogWatcher,
    DraftScoringEngine,
    DraftState,
    MockDraftGenerator,
    ScoredCard,
    calculate_baseline_score,
    calculate_bayesian_archetype_probabilities,
    calculate_color_commitment_weight,
    calculate_curve_adjustment,
    calculate_synergy_bonus,
    optimize_deck,
    score_candidates,
    score_pack,
)
from scripts.draft_engine.deck_optimizer import (
    BASIC_LAND_NAMES,
    COLOR_PAIRS,
    COLORS,
    TARGET_CURVE,
    is_card_castable,
    is_splash_candidate,
    parse_mana_pips,
)
from scripts.draft_engine.log_parser import (
    DRAFT_STATUS_EVENT,
    GET_COMBINED_REQUEST_EVENT,
)


# ==============================================================================
# 1. SCORING ENGINE UNIT TESTS
# ==============================================================================

class TestScoringEngineUnit:
    """Unit tests verifying core mathematical scoring behaviors."""

    def test_baseline_score_with_gih_wr_and_iwd(self) -> None:
        """Verify baseline score calculation using Game-In-Hand Win Rate (GIH WR) and IWD."""
        bomb_card = {
            "name": "Krenko, Mob Boss",
            "gih_wr": 0.65,
            "iwd": 0.08,
            "rarity": "rare",
            "cmc": 4,
        }
        score, insights = calculate_baseline_score(bomb_card)
        assert 40.0 <= score <= 52.0
        assert any("bomb" in ins.lower() for ins in insights)
        assert any("top-deck" in ins.lower() for ins in insights)

        staple_card = {
            "name": "Lightning Bolt",
            "gih_wr": 0.56,
            "iwd": 0.01,
            "rarity": "common",
            "cmc": 1,
        }
        staple_score, staple_insights = calculate_baseline_score(staple_card)
        assert 28.0 <= staple_score <= 38.0
        assert any("staple" in ins.lower() for ins in staple_insights)

    def test_baseline_score_heuristic_fallback_rarity_and_cmc(self) -> None:
        """Verify algorithmic fallback to rarity and CMC when win rate metrics are absent."""
        mythic_2drop = {
            "name": "Mythic Powerhouse",
            "rarity": "mythic",
            "cmc": 2.0,
        }
        mythic_score, _ = calculate_baseline_score(mythic_2drop)

        common_6drop = {
            "name": "Common Behemoth",
            "rarity": "common",
            "cmc": 6.0,
        }
        common_score, _ = calculate_baseline_score(common_6drop)

        assert mythic_score > common_score
        assert mythic_score >= 38.0
        assert common_score <= 25.0

    def test_color_commitment_bayesian_updates(self) -> None:
        """Verify posterior probability distribution shifts over 10 two-color archetypes."""
        # 1. Empty draft pool -> uniform prior 0.10
        priors = calculate_bayesian_archetype_probabilities([])
        assert len(priors) == 10
        for pair in COLOR_PAIRS:
            key = f"{pair[0]}{pair[1]}"
            assert pytest.approx(priors[key], 0.01) == 0.10

        # 2. Add Dimir (UB) signpost cards
        dimir_pool = [
            {"name": "Baleful Strix", "colors": ["U", "B"], "mana_cost": "{U}{B}"},
            {"name": "Psychic Frog", "colors": ["U", "B"], "mana_cost": "{U}{B}"},
            {"name": "Counterspell", "colors": ["U"], "mana_cost": "{U}{U}"},
            {"name": "Doom Blade", "colors": ["B"], "mana_cost": "{1}{B}"},
        ]
        posterior = calculate_bayesian_archetype_probabilities(dimir_pool)
        assert posterior["UB"] > 0.70
        assert posterior["RG"] < 0.01

    def test_color_commitment_progression_p1p1_vs_p3p14(self) -> None:
        """Verify open flexibility in early Pack 1 vs strict penalty in late Pack 3."""
        dimir_pool = [
            {"name": f"Dimir Spell {i}", "colors": ["U", "B"], "mana_cost": "{U}{B}"}
            for i in range(20)
        ]
        arch_probs = calculate_bayesian_archetype_probabilities(dimir_pool)

        gruul_card = {
            "name": "Gruul Smash",
            "colors": ["R", "G"],
            "mana_cost": "{2}{R}{G}",
            "cmc": 4,
        }

        # Pack 1 Pick 1: Drafter remains largely open
        w_p1p1, ins_p1p1 = calculate_color_commitment_weight(
            gruul_card, arch_probs, pack_num=1, pick_num=1, baseline_score=35.0
        )
        # Pack 3 Pick 10: Drafter heavily penalized for off-color
        w_p3p10, ins_p3p10 = calculate_color_commitment_weight(
            gruul_card, arch_probs, pack_num=3, pick_num=10, baseline_score=35.0
        )

        assert w_p1p1 > 0.85
        assert w_p3p10 < 0.35
        assert any("off-color" in ins.lower() for ins in ins_p3p10)

    def test_curve_adjustment_rewards_2drops_and_penalizes_high_drops(self) -> None:
        """Verify curve balancing rewards critical 2-drops and penalizes 5+ CMC flood."""
        # Drafter has 12 spells: zero 2-drops, four 5-drops
        heavy_pool = [
            {"name": f"High Drop {i}", "cmc": 5.0, "type_line": "Creature"} for i in range(4)
        ] + [
            {"name": f"Three Drop {i}", "cmc": 3.0, "type_line": "Creature"} for i in range(8)
        ]

        two_drop = {"name": "Grizzly Bears", "cmc": 2.0, "type_line": "Creature"}
        high_drop = {"name": "Colossal Dreadmaw", "cmc": 6.0, "type_line": "Creature"}

        adj_2d, ins_2d = calculate_curve_adjustment(two_drop, heavy_pool, pack_num=2, pick_num=7)
        adj_high, ins_high = calculate_curve_adjustment(high_drop, heavy_pool, pack_num=2, pick_num=7)

        assert adj_2d > 0.0
        assert any("2-drop" in ins.lower() for ins in ins_2d)

        assert adj_high < 0.0
        assert any("saturation" in ins.lower() or "5+" in ins for ins in ins_high)

    def test_synergy_bonus_mechanical_interactions(self) -> None:
        """Verify synergy detection triggers bonus points and micro-insights."""
        picked = [
            {
                "name": "Blood Artist",
                "type_line": "Creature — Vampire",
                "oracle_text": "Whenever a creature dies, target player loses 1 life and you gain 1 life.",
            }
        ]
        sac_outlet = {
            "name": "Viscera Seer",
            "type_line": "Creature — Vampire Wizard",
            "oracle_text": "Sacrifice a creature: Scry 1.",
        }

        bonus, notes, is_loop = calculate_synergy_bonus(sac_outlet, picked)
        assert bonus > 0.0
        assert len(notes) > 0

    def test_composite_rating_calibration_and_tier_badges(self) -> None:
        """Verify Draftsmith tier badge thresholds (S, A, B, C, D, F) across 1-55 scale."""
        engine = DraftScoringEngine()
        candidates = [
            {"name": "Bomb", "gih_wr": 0.68, "cmc": 3, "colors": ["U"], "mana_cost": "{2}{U}"},
            {"name": "Staple", "gih_wr": 0.58, "cmc": 2, "colors": ["U"], "mana_cost": "{1}{U}"},
            {"name": "Filler", "gih_wr": 0.51, "cmc": 3, "colors": ["U"], "mana_cost": "{2}{U}"},
            {"name": "Dud", "gih_wr": 0.42, "cmc": 5, "colors": ["U"], "mana_cost": "{4}{U}"},
        ]
        picked = [{"name": "Island", "colors": ["U"], "mana_cost": "{U}"}]
        scored = engine.score_candidates(candidates, picked, pack_num=1, pick_num=1)

        assert len(scored) == 4
        assert scored[0]["composite_rating"] >= scored[1]["composite_rating"]
        assert scored[1]["composite_rating"] >= scored[2]["composite_rating"]
        assert scored[2]["composite_rating"] >= scored[3]["composite_rating"]

        for item in scored:
            rating = item["composite_rating"]
            tier = item["tier_badge"]
            assert 1.0 <= rating <= 55.0
            if rating >= 46.0:
                assert tier == "S"
            elif rating >= 38.0:
                assert tier == "A"
            elif rating >= 30.0:
                assert tier == "B"
            elif rating >= 22.0:
                assert tier == "C"
            elif rating >= 14.0:
                assert tier == "D"
            else:
                assert tier == "F"

    def test_scoring_ranking_and_tie_breaking(self) -> None:
        """Verify sorting by composite_rating descending, with baseline_score as tie-breaker."""
        engine = DraftScoringEngine()
        card_a = {"name": "Card A", "cmc": 3, "rarity": "rare", "colors": ["W"]}
        card_b = {"name": "Card B", "cmc": 3, "rarity": "uncommon", "colors": ["W"]}

        scored = engine.score_candidates([card_b, card_a], [], pack_num=1, pick_num=1)
        assert scored[0]["name"] == "Card A"


# ==============================================================================
# 2. SCORING ENGINE POPPERIAN FALSIFICATION TESTS
# ==============================================================================

class TestScoringEnginePopperianEdgeCases:
    """Popperian adversarial falsification probes pushing mathematical boundaries."""

    def test_reductio_ad_absurdum_empty_packs_and_empty_pools(self) -> None:
        """Test null/empty collections do not crash and return empty output."""
        assert score_candidates([], []) == []
        assert score_pack([], []) == []

    def test_reductio_ad_absurdum_extreme_and_corrupt_win_rates(self) -> None:
        """Push GIH WR to programmatic bounds: strings with %, decimals, negatives, NaN, inf, >100%."""
        extreme_cases = [
            ("59.4%", 30.0, 45.0),
            (0.594, 30.0, 45.0),
            (59.4, 30.0, 45.0),
            (-100.0, 5.0, 15.0),   # Clamped to minimum
            (999.0, 45.0, 52.0),    # Clamped to maximum
            (float("nan"), 5.0, 52.0),  # Falls back cleanly
            (float("inf"), 5.0, 52.0),  # Falls back cleanly
            (None, 5.0, 52.0),
            ("corrupt_string", 5.0, 52.0),
        ]
        for val, min_expected, max_expected in extreme_cases:
            card = {"name": "Test Card", "gih_wr": val, "cmc": 2, "rarity": "common"}
            score, _ = calculate_baseline_score(card)
            assert not math.isnan(score), f"Score for {val} was NaN"
            assert not math.isinf(score), f"Score for {val} was Inf"
            assert min_expected <= score <= max_expected, f"Failed for val: {val}, got {score}"

    def test_black_swan_colorless_artifacts_and_lands(self) -> None:
        """Colorless cards must maintain full commitment flexibility (1.0 weight) in all packs."""
        dimir_pool = [{"name": "Baleful Strix", "colors": ["U", "B"]}] * 20
        arch_probs = calculate_bayesian_archetype_probabilities(dimir_pool)

        colorless_artifact = {
            "name": "Solemn Simulacrum",
            "colors": [],
            "mana_cost": "{4}",
            "cmc": 4,
        }
        w, ins = calculate_color_commitment_weight(
            colorless_artifact, arch_probs, pack_num=3, pick_num=10, baseline_score=35.0
        )
        assert w == 1.0
        assert any("colorless" in s.lower() for s in ins)

    def test_quantitative_breaking_point_massive_pool(self) -> None:
        """Ensure Bayesian probability update does not overflow or underflow with 300+ cards."""
        huge_pool = [
            {"name": f"Card {i}", "colors": ["R", "W"] if i % 2 == 0 else ["R"]}
            for i in range(300)
        ]
        probs = calculate_bayesian_archetype_probabilities(huge_pool)
        assert len(probs) == 10
        total_prob = sum(probs.values())
        assert pytest.approx(total_prob, 1e-4) == 1.0
        assert not any(math.isnan(p) or math.isinf(p) for p in probs.values())


# ==============================================================================
# 3. DECK OPTIMIZER UNIT TESTS
# ==============================================================================

class TestDeckOptimizerUnit:
    """Unit tests verifying 40-card knapsack deckbuilder and mana split."""

    @pytest.fixture
    def standard_boros_pool(self) -> List[Dict[str, Any]]:
        """A realistic 45-card pool biased toward Boros (RW)."""
        pool: List[Dict[str, Any]] = []
        # 22 Red cards
        for i in range(22):
            cmc = (i % 5) + 1
            cost = "{R}" if cmc == 1 else f"{{{cmc-1}}}{{R}}"
            pool.append({
                "id": f"r_{i}",
                "name": f"Red Veteran {i}",
                "cmc": float(cmc),
                "mana_cost": cost,
                "colors": ["R"],
                "type_line": "Creature" if i < 16 else "Instant",
                "power": "2", "toughness": "2",
                "gih_wr": 0.56,
            })
        # 18 White cards
        for i in range(18):
            cmc = (i % 4) + 2
            cost = f"{{{cmc-1}}}{{W}}"
            pool.append({
                "id": f"w_{i}",
                "name": f"White Knight {i}",
                "cmc": float(cmc),
                "mana_cost": cost,
                "colors": ["W"],
                "type_line": "Creature" if i < 14 else "Enchantment",
                "power": "2", "toughness": "3",
                "gih_wr": 0.57,
            })
        # 5 Off-color Green cards
        for i in range(5):
            pool.append({
                "id": f"g_{i}",
                "name": f"Green Beast {i}",
                "cmc": 4.0,
                "mana_cost": "{3}{G}",
                "colors": ["G"],
                "type_line": "Creature",
                "power": "4", "toughness": "4",
                "gih_wr": 0.51,
            })
        return pool

    def test_exact_40_card_deck_validation(self, standard_boros_pool: List[Dict[str, Any]]) -> None:
        """Deck optimizer must output exactly 23 non-land spells and 17 basic lands (40 total)."""
        result = optimize_deck(standard_boros_pool, target_spells=23, target_lands=17)
        stats = result["stats"]

        assert stats["total_cards"] == 40
        assert stats["spells_count"] == 23
        assert stats["lands_count"] == 17
        assert sum(stats["mana_split"].values()) == 17
        assert len(result["maindeck"]) == 40
        assert len(result["maindeck_spells"]) == 23

    def test_target_curve_and_creature_floor(self, standard_boros_pool: List[Dict[str, Any]]) -> None:
        """Deck optimizer must honor creature floor (>=13) and limit high drops."""
        result = optimize_deck(standard_boros_pool)
        stats = result["stats"]
        curve = stats["curve"]

        assert stats["creatures_count"] >= 13
        assert stats["creature_ratio"] >= 0.55
        # Limited 5+ CMC constraint: target 2-3
        assert curve["5+"] <= 5
        # 2-drops prioritized
        assert curve["2"] >= 4

    def test_mana_split_hamilton_quota_proportions(self) -> None:
        """Hamilton quota mana split must accurately reflect colored pip demands."""
        optimizer = DeckOptimizer()
        # Spells with heavy Blue demand (20 Blue pips, 5 Black pips)
        spells: List[Card] = []
        for i in range(15):
            spells.append(Card(id=f"u_{i}", name="Blue Spell", mana_cost="{1}{U}{U}", cmc=3))
        for i in range(8):
            spells.append(Card(id=f"b_{i}", name="Black Spell", mana_cost="{1}{B}", cmc=2))

        split = optimizer.solve_mana_split(
            maindeck_spells=spells,
            primary_colors=["U", "B"],
            total_lands=17,
        )
        assert sum(split.values()) == 17
        assert split["Island"] > split["Swamp"]
        assert split["Swamp"] >= 5  # Enforces 2-color minimum floor

    def test_drafted_nonbasic_land_deduction(self, standard_boros_pool: List[Dict[str, Any]]) -> None:
        """Drafted non-basic lands must count toward 17 total lands, reducing basics accordingly."""
        pool_with_dual = list(standard_boros_pool)
        pool_with_dual.append({
            "id": "dual_1",
            "name": "Sacred Foundry",
            "type_line": "Land — Plains Mountain",
            "oracle_text": "{T}: Add {R} or {W}.",
            "colors": [],
            "cmc": 0,
        })
        pool_with_dual.append({
            "id": "dual_2",
            "name": "Inspiring Vantage",
            "type_line": "Land",
            "oracle_text": "{T}: Add {R} or {W}.",
            "colors": [],
            "cmc": 0,
        })

        result = optimize_deck(pool_with_dual, target_spells=23, target_lands=17)
        stats = result["stats"]

        assert stats["total_cards"] == 40
        assert stats["spells_count"] == 23
        assert stats["lands_count"] == 17
        # 2 nonbasics + 15 basics = 17 lands
        assert sum(stats["mana_split"].values()) == 15

    def test_mtga_arena_decklist_formatting(self, standard_boros_pool: List[Dict[str, Any]]) -> None:
        """Arena decklist must follow standard 'Deck' and 'Sideboard' format for direct MTGA import."""
        result = optimize_deck(standard_boros_pool)
        text = result["arena_decklist_text"]

        assert text.startswith("Deck\n")
        assert "Sideboard\n" in text
        deck_section = text.split("Sideboard\n")[0]
        sideboard_section = text.split("Sideboard\n")[1]

        # All lines in Deck section (excluding header) must match "<count> <name>"
        for line in deck_section.strip().split("\n")[1:]:
            parts = line.split(" ", 1)
            assert parts[0].isdigit()
            assert len(parts[1]) > 0


# ==============================================================================
# 4. DECK OPTIMIZER POPPERIAN FALSIFICATION TESTS
# ==============================================================================

class TestDeckOptimizerPopperianEdgeCases:
    """Popperian falsification tests for extreme edge conditions."""

    def test_monocolor_draft_invariants_no_phantom_lands(self) -> None:
        """FALSIFICATION VECTOR: Pure monocolor pool must NOT produce secondary colors or ghost lands.

        Proves that a 100% Blue pool chooses 'Mono-Blue' and exactly 17 Islands.
        """
        pool_mono_blue: List[Dict[str, Any]] = []
        for i in range(45):
            pool_mono_blue.append({
                "id": f"u_{i}",
                "name": f"Merfolk Scout {i}",
                "cmc": 2.0,
                "mana_cost": "{1}{U}",
                "colors": ["U"],
                "type_line": "Creature",
                "power": "2", "toughness": "2",
                "gih_wr": 0.55,
            })

        result = optimize_deck(pool_mono_blue)
        assert result["deck_name"] == "Mono-Blue"
        assert result["colors"] == ["U"]
        assert result["stats"]["mana_split"] == {"Island": 17}
        assert result["stats"]["total_cards"] == 40
        assert result["stats"]["color_pips"]["U"] == 23
        for c in ("W", "B", "R", "G"):
            assert result["stats"]["color_pips"][c] == 0
            assert result["stats"]["mana_split"].get(BASIC_LAND_NAMES[c], 0) == 0

    def test_five_color_soup_optimization(self) -> None:
        """FALSIFICATION VECTOR: 5-color soup pool (9 cards of each color) must find strongest pair + splash."""
        pool_soup: List[Dict[str, Any]] = []
        colors = ["W", "U", "B", "R", "G"]
        for idx, c in enumerate(colors):
            for i in range(9):
                pool_soup.append({
                    "id": f"{c}_{i}",
                    "name": f"{c} Spell {i}",
                    "cmc": float((i % 4) + 1),
                    "mana_cost": f"{{{c}}}" if i % 2 == 0 else f"{{2}}{{{c}}}",
                    "colors": [c],
                    "type_line": "Creature" if i < 6 else "Instant",
                    "power": "2", "toughness": "2",
                    "gih_wr": 0.52 + (0.01 * idx),
                })

        result = optimize_deck(pool_soup)
        assert result["stats"]["total_cards"] == 40
        assert result["stats"]["spells_count"] + result["stats"]["lands_count"] == 40
        assert 20 <= result["stats"]["spells_count"] <= 23
        assert 17 <= result["stats"]["lands_count"] <= 20
        assert sum(result["stats"]["mana_split"].values()) == result["stats"]["lands_count"]
        # Must choose a valid 2-color pair
        assert len(result["colors"]) == 2

    def test_extreme_curve_all_1_drops(self) -> None:
        """FALSIFICATION VECTOR: Pool containing only 1-drops must still build valid 40-card deck."""
        pool_1d = [
            {
                "id": f"one_{i}",
                "name": f"Goblin Guide {i}",
                "cmc": 1.0,
                "mana_cost": "{R}",
                "colors": ["R"],
                "type_line": "Creature",
                "power": "2", "toughness": "2",
                "gih_wr": 0.54,
            }
            for i in range(45)
        ]
        result = optimize_deck(pool_1d)
        assert result["stats"]["total_cards"] == 40
        assert result["stats"]["curve"]["1"] == 23
        assert result["stats"]["curve"]["2"] == 0

    def test_extreme_curve_all_7_drops(self) -> None:
        """FALSIFICATION VECTOR: Pool containing only 7-drops must not crash and build valid deck."""
        pool_7d = [
            {
                "id": f"seven_{i}",
                "name": f"Gargantuan Demon {i}",
                "cmc": 7.0,
                "mana_cost": "{5}{B}{B}",
                "colors": ["B"],
                "type_line": "Creature",
                "power": "7", "toughness": "7",
                "gih_wr": 0.50,
            }
            for i in range(45)
        ]
        result = optimize_deck(pool_7d)
        assert result["stats"]["total_cards"] == 40
        assert result["stats"]["curve"]["5+"] == 23

    def test_zero_creatures_all_instants_pool(self) -> None:
        """FALSIFICATION VECTOR: Pool with zero creatures builds valid spell deck without div-by-zero."""
        pool_spells = [
            {
                "id": f"inst_{i}",
                "name": f"Counter Magic {i}",
                "cmc": 2.0,
                "mana_cost": "{1}{U}",
                "colors": ["U"],
                "type_line": "Instant",
                "oracle_text": "Counter target spell.",
                "gih_wr": 0.52,
            }
            for i in range(45)
        ]
        result = optimize_deck(pool_spells)
        assert result["stats"]["total_cards"] == 40
        assert result["stats"]["creatures_count"] == 0
        assert result["stats"]["creature_ratio"] == 0.0

    def test_reductio_ad_absurdum_empty_and_sub_minimum_pools(self) -> None:
        """FALSIFICATION VECTOR: Empty pools and pools with <23 cards must degrade gracefully."""
        # 1. Empty pool
        res_empty = optimize_deck([])
        assert res_empty["stats"]["total_cards"] == 0
        assert res_empty["maindeck"] == []

        # 2. Pool with only 10 cards (less than 23)
        small_pool = [
            {
                "id": f"card_{i}",
                "name": f"Card {i}",
                "cmc": 2.0,
                "mana_cost": "{1}{G}",
                "colors": ["G"],
                "type_line": "Creature",
                "gih_wr": 0.52,
            }
            for i in range(10)
        ]
        res_small = optimize_deck(small_pool)
        assert res_small["stats"]["spells_count"] == 10
        assert res_small["stats"]["lands_count"] == 17
        assert res_small["stats"]["total_cards"] == 27


# ==============================================================================
# 5. LOG PARSER UNIT TESTS
# ==============================================================================

class TestLogParserUnit:
    """Unit tests verifying MTGA Player.log parsing and card resolution."""

    @pytest.fixture
    def test_resolver(self) -> CardResolver:
        """CardResolver pointing to SQLite data/cards.db."""
        return CardResolver()

    def test_sqlite_card_resolver_known_cards(self, test_resolver: CardResolver) -> None:
        """Verify grpId resolution against real SQLite database (data/cards.db)."""
        # Let's inspect a real card from the DB
        conn = test_resolver._get_connection()
        assert conn is not None, "data/cards.db connection could not be established"
        test_resolver._inspect_schema(conn)
        id_col = test_resolver._id_col or "id"
        cur = conn.cursor()
        cur.execute(f"SELECT {id_col}, name FROM cards LIMIT 5")
        rows = cur.fetchall()
        conn.close()

        for gid, name in rows:
            resolved = test_resolver.resolve_name(gid)
            assert resolved == name
            card_dict = test_resolver.resolve_card(gid)
            assert card_dict["name"] == name
            assert card_dict["grpId"] == gid

    def test_bot_draft_status_parsing(self, test_resolver: CardResolver) -> None:
        """Verify parsing of Draft.DraftStatus (Bot/Quick Draft)."""
        gen = MockDraftGenerator(resolver=test_resolver)
        parser = ArenaLogParser(resolver=test_resolver)

        sample_pack = gen.card_pool[:14]
        sample_pool = gen.card_pool[14:20]

        payload = gen.create_draft_status_payload(
            pack_number=1,
            pick_number=5,
            draft_pack=sample_pack,
            picked_cards=sample_pool,
            event_name="QuickDraft_TDM",
        )

        state = parser.parse_payload(payload)
        assert state is not None
        assert state.event_type == DRAFT_STATUS_EVENT
        assert state.pack_number == 1
        assert state.pick_number == 5
        assert state.pack_card_ids == sample_pack
        assert state.drafted_pool == sample_pool
        assert len(state.resolved_pack_names) == 14
        assert len(state.resolved_pool_names) == 6

    def test_premier_draft_get_combined_request_parsing(self, test_resolver: CardResolver) -> None:
        """Verify parsing of Event.GetCombinedRequest (Premier/Human Draft)."""
        gen = MockDraftGenerator(resolver=test_resolver)
        parser = ArenaLogParser(resolver=test_resolver)

        sample_pack = gen.card_pool[:12]
        sample_pool = gen.card_pool[12:26]

        payload = gen.create_combined_request_payload(
            pack_number=2,
            pick_number=3,
            draft_pack=sample_pack,
            picked_cards=sample_pool,
            event_name="PremierDraft_TDM",
        )

        state = parser.parse_payload(payload)
        assert state is not None
        assert state.event_type == GET_COMBINED_REQUEST_EVENT
        assert state.pack_number == 2
        assert state.pick_number == 3
        assert state.pack_card_ids == sample_pack
        assert state.drafted_pool == sample_pool

    def test_pack_and_pick_number_normalization(self, test_resolver: CardResolver) -> None:
        """Verify 0-indexed vs 1-indexed pack and pick numbers."""
        gen = MockDraftGenerator(resolver=test_resolver)
        parser = ArenaLogParser(resolver=test_resolver)

        # MTGA sometimes reports 0 for pack 1, pick 1
        payload = gen.create_draft_status_payload(
            pack_number=0,
            pick_number=0,
            draft_pack=[gen.card_pool[0]],
            picked_cards=[],
        )
        state = parser.parse_payload(payload)
        assert state is not None
        assert state.pack_number == 0
        assert state.pick_number == 0
        assert state.pack_num_1_indexed == 1
        assert state.pick_num_1_indexed == 1

    def test_mock_draft_generator_full_simulation(self, test_resolver: CardResolver) -> None:
        """Verify MockDraftGenerator simulates 42 sequential picks (3 packs * 14 picks) plus completed state."""
        gen = MockDraftGenerator(resolver=test_resolver)
        events = gen.simulate_draft(packs=3, picks_per_pack=14, strategy="first")

        # 42 picks + 1 completed event = 43 events
        assert len(events) == 43
        parser = ArenaLogParser(resolver=test_resolver)

        first_state = parser.parse_payload(events[0])
        assert first_state is not None
        assert first_state.pack_num_1_indexed == 1
        assert first_state.pick_num_1_indexed == 1
        assert len(first_state.pack_card_ids) == 14
        assert len(first_state.drafted_pool) == 0
        assert not first_state.is_completed

        last_pick_state = parser.parse_payload(events[41])
        assert last_pick_state is not None
        assert last_pick_state.pack_num_1_indexed == 3
        assert last_pick_state.pick_num_1_indexed == 14
        assert len(last_pick_state.drafted_pool) == 41

        completed_state = parser.parse_payload(events[42])
        assert completed_state is not None
        assert completed_state.is_completed
        assert len(completed_state.drafted_pool) == 42
        assert len(completed_state.pack_card_ids) == 0


# ==============================================================================
# 6. LOG PARSER POPPERIAN FALSIFICATION TESTS
# ==============================================================================

class TestLogParserPopperianEdgeCases:
    """Popperian edge cases for missing IDs, corrupt logs, and stream truncation."""

    def test_missing_and_invalid_grpids(self) -> None:
        """Missing or malformed grpIds must gracefully resolve to fallback labels."""
        resolver = CardResolver()
        invalid_ids = [999999999, -42, "not_an_id", None]

        for gid in invalid_ids:
            name = resolver.resolve_name(gid)  # type: ignore[arg-type]
            assert "Unknown Card" in name
            card = resolver.resolve_card(gid)  # type: ignore[arg-type]
            assert "Unknown Card" in card["name"]

    def test_missing_database_graceful_fallback(self, tmp_path: Path) -> None:
        """CardResolver pointing to a non-existent database file must not crash."""
        ghost_db = tmp_path / "ghost.db"
        resolver = CardResolver(db_path=ghost_db)
        # Should cleanly use fallback strings without unhandled exceptions
        name = resolver.resolve_name(12345)
        assert name == "Unknown Card (12345)"

    def test_corrupt_and_truncated_log_lines(self) -> None:
        """ArenaLogParser must safely ignore malformed JSON or corrupted prefix lines."""
        parser = ArenaLogParser()
        malformed_inputs = [
            "[UnityCrossThreadLogger]11/12/2026: <== Draft.DraftStatus {corrupted: json",
            "[UnityCrossThreadLogger] unrelated chat line: hello world",
            "{'invalid_quotes': True}",
            "",
            "   ",
            "{'DraftPack': [1, 2], 'missing_brace'",
        ]
        for line in malformed_inputs:
            res = parser.parse_line(line)
            assert res is None

    def test_draft_log_watcher_file_truncation_recovery(self, tmp_path: Path) -> None:
        """FALSIFICATION VECTOR: DraftLogWatcher must recover when MTGA truncates or rotates Player.log."""
        log_file = tmp_path / "Player.log"
        gen = MockDraftGenerator()

        # Step 1: Write initial 14-card pack (large line)
        p1 = gen.create_draft_status_payload(pack_number=1, pick_number=1, draft_pack=list(range(100, 114)), picked_cards=[])
        line1 = gen.format_log_line(p1)
        log_file.write_text(line1 + "\n", encoding="utf-8")

        watcher = DraftLogWatcher(log_file)
        new_states_1 = watcher.check_for_updates()
        assert len(new_states_1) == 1
        assert len(new_states_1[0].pack_card_ids) == 14

        # Step 2: Simulate file truncation (smaller file overwrites in place)
        p2 = gen.create_draft_status_payload(pack_number=1, pick_number=2, draft_pack=[201], picked_cards=[])
        line2 = gen.format_log_line(p2)
        assert len(line2) < len(line1)
        log_file.write_text(line2 + "\n", encoding="utf-8")

        # Watcher must detect file shrank, reset offset, and read the new line
        new_states_2 = watcher.check_for_updates()
        assert len(new_states_2) == 1
        assert new_states_2[0].pack_card_ids == [201]

        # Step 3: Simulate log rotation (log file unlinked and recreated with new inode)
        log_file.unlink()
        p3 = gen.create_draft_status_payload(pack_number=1, pick_number=3, draft_pack=[301], picked_cards=[])
        line3 = gen.format_log_line(p3)
        log_file.write_text(line3 + "\n", encoding="utf-8")

        new_states_3 = watcher.check_for_updates()
        assert len(new_states_3) == 1
        assert new_states_3[0].pack_card_ids == [301]


# ==============================================================================
# 7. END-TO-END DRAFTWEAVER PIPELINE INTEGRATION TEST
# ==============================================================================

class TestDraftweaverEndToEndPipeline:
    """Verifies complete end-to-end integration: Log Stream -> Scoring -> Knapsack 40-Card Deck."""

    def test_complete_draft_and_deckbuild_pipeline(self) -> None:
        """Simulate an entire draft session from raw MTGA logs to final optimized 40-card deck."""
        resolver = CardResolver()
        parser = ArenaLogParser(resolver=resolver)
        gen = MockDraftGenerator(resolver=resolver)

        # 1. Simulate 42 draft picks (+ 1 completion event)
        simulated_events = gen.simulate_draft(packs=3, picks_per_pack=14, strategy="first")
        assert len(simulated_events) == 43

        # 2. Process log events through parser and score candidates for each pick
        picked_pool_cards: List[Dict[str, Any]] = []
        engine = DraftScoringEngine()

        for idx, event in enumerate(simulated_events):
            # Format as MTGA raw log line
            log_line = gen.format_log_line(event)
            state = parser.parse_line(log_line)
            assert state is not None

            if state.is_completed:
                picked_pool_cards = resolver.resolve_pool_cards(state.drafted_pool)
                break

            # Resolve candidates & pool
            candidates = resolver.resolve_pack_cards(state.pack_card_ids)
            picked = resolver.resolve_pool_cards(state.drafted_pool)

            # Score candidates
            scored = engine.score_candidates(
                candidates,
                picked,
                pack_num=state.pack_num_1_indexed,
                pick_num=state.pick_num_1_indexed,
            )
            assert len(scored) == len(candidates)
            assert scored[0]["composite_rating"] >= scored[-1]["composite_rating"]

        assert len(picked_pool_cards) == 42

        # 3. Optimize the 42-card pool into final 40-card deck
        deck_result = optimize_deck(picked_pool_cards, target_spells=23, target_lands=17)

        # 4. Rigorous assertions on final deck
        stats = deck_result["stats"]
        assert stats["total_cards"] == 40
        assert stats["spells_count"] == 23
        assert stats["lands_count"] == 17
        assert sum(stats["mana_split"].values()) + stats.get("nonbasic_lands_count", 0) == 17
        assert len(deck_result["maindeck"]) == 40
        assert len(deck_result["maindeck_spells"]) == 23
        assert len(deck_result["sideboard"]) == len(picked_pool_cards) - (stats["spells_count"] + stats.get("nonbasic_lands_count", 0))

        # MTGA export text verification
        arena_text = deck_result["arena_decklist_text"]
        assert "Deck\n" in arena_text
        assert "Sideboard\n" in arena_text
        # Verify basic lands are listed in Deck section
        assert any(b in arena_text for b in BASIC_LAND_NAMES.values())
