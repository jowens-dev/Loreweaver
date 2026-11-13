"""Automated verification suite for Loreweaver Engine v2 (Synergy & Pricing Engine).

Verifies:
1. Logarithmic budget friction and sentinel handling
2. Obscurity / Spice bonus curve
3. Rules-text state vector compilation and closed loop detection
4. 2.5x Commander weight invariant
5. Mana Pool affiliate URL and slugification
6. Candidate swap integration & budget dominance over generic staples
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
import db
import pricing_engine
from pricing_engine import (
    calculate_price_penalty,
    calculate_spice_bonus,
    calculate_composite_score,
    to_manapool_slug,
    get_manapool_affiliate_url,
    get_card_price,
    get_bulk_prices,
    DEFAULT_SENTINEL_PRICE,
    DEFAULT_BETA,
)
import synergy_engine
from synergy_engine import (
    compile_card_vector,
    evaluate_pairwise_synergy,
    evaluate_candidate_in_deck,
)
import card_swapper


def test_logarithmic_price_penalty_monotonic_and_steep():
    """Verify price penalty increases monotonically with steep wall for expensive cards."""
    p_cheap = calculate_price_penalty(0.35)
    p_moderate = calculate_price_penalty(5.00)
    p_expensive = calculate_price_penalty(40.00)
    p_exorbitant = calculate_price_penalty(100.00)

    assert p_cheap < p_moderate < p_expensive < p_exorbitant
    assert p_cheap < 1.5  # $0.35 has minimal friction (~1.27)
    assert p_expensive > 15.0  # $40 faces severe friction (~16.2)
    # The jump from $5 to $40 is substantially higher than $0.35 to $5
    assert (p_expensive - p_moderate) > (p_moderate - p_cheap) * 2.0


def test_sentinel_price_for_missing_or_zero():
    """Verify unpriced, null, or zero price cards are assigned the $999 sentinel penalty."""
    p_none = calculate_price_penalty(None)
    p_zero = calculate_price_penalty(0.0)
    p_neg = calculate_price_penalty(-5.0)
    p_sentinel = calculate_price_penalty(DEFAULT_SENTINEL_PRICE)

    assert p_none == p_sentinel
    assert p_zero == p_sentinel
    assert p_neg == p_sentinel
    assert p_none > 50.0  # Sentinel drag is massive (~57.5)


def test_spice_bonus_curve():
    """Verify underplayed cards gain obscurity boost while top staples receive flat 1.0x."""
    assert calculate_spice_bonus(10) == 1.0
    assert calculate_spice_bonus(250) == 1.0
    assert calculate_spice_bonus(500) == 1.0

    bonus_2000 = calculate_spice_bonus(2000)
    assert 1.15 < bonus_2000 < 1.20

    bonus_5000 = calculate_spice_bonus(5000)
    assert 1.45 < bonus_5000 < 1.50

    bonus_10000 = calculate_spice_bonus(10000)
    assert bonus_10000 == 2.0

    bonus_ultra = calculate_spice_bonus(25000)
    assert bonus_ultra == 2.0  # Hard capped at 2.0x


def test_manapool_slugification_and_url():
    """Verify card names with punctuation, spaces, and accents produce exact Mana Pool URLs."""
    cases = [
        ("Sol Ring", "sol-ring"),
        ("Dina, Soul Steeper", "dina-soul-steeper"),
        ("Nadier's Nightblade", "nadiers-nightblade"),
        ("Lim-Dûl's Vault", "lim-duls-vault"),
        ('Kongming, "Sleeping Dragon"', "kongming-sleeping-dragon"),
        ("Æther Vial", "aether-vial"),
    ]

    for raw, expected_slug in cases:
        slug = to_manapool_slug(raw)
        assert slug == expected_slug, f"Failed slug for {raw}: got {slug}"

        url = get_manapool_affiliate_url(raw, ref="loreweaver", source="loreweaver_swap")
        assert f"https://manapool.com/card/{expected_slug}?ref=loreweaver&ref_meta=source:loreweaver_swap" == url


def test_zero_synergy_obscurity_inversion_eliminated():
    """Verify that a $0.05 obscure bulk card with ZERO synergy scores 0.0 and never beats real cards."""
    dina_card = {
        "name": "Dina, Soul Steeper",
        "type_line": "Legendary Creature — Dryad Druid",
        "cmc": 2.0,
        "oracle_text": "Whenever you gain life, each opponent loses 1 life. {1}, Sacrifice another creature: Dina gets +X/+X until end of turn."
    }

    zero_synergy_bulk = {
        "name": "Vanilla Goblin",
        "type_line": "Creature — Goblin",
        "cmc": 1.0,
        "oracle_text": "",
        "edhrec_rank": 15000
    }

    eval_zero = evaluate_candidate_in_deck(zero_synergy_bulk, dina_card, price=0.05)
    assert eval_zero["raw_synergy"] == 0.0
    assert eval_zero["composite_score"] == 0.0


def test_same_domain_consumption_no_false_feedback_loop():
    """Verify two mutual sacrifice outlets do not trigger a false-positive closed feedback loop."""
    outlet_a = {
        "name": "Ashnod's Altar",
        "type_line": "Artifact",
        "cmc": 3.0,
        "oracle_text": "Sacrifice a creature: Add {C}{C}."
    }

    outlet_b = {
        "name": "Yahenni, Undying Partisan",
        "type_line": "Legendary Creature — Vampire Aetherborn",
        "cmc": 3.0,
        "oracle_text": "Whenever a creature an opponent controls dies, put a +1/+1 counter on Yahenni. Sacrifice another creature: Yahenni gains indestructible until end of turn."
    }

    a_vec = compile_card_vector(outlet_a)
    b_vec = compile_card_vector(outlet_b)

    score, notes, is_closed = evaluate_pairwise_synergy(a_vec, b_vec, is_commander=False)
    # Neither card generates creatures, so this is NOT a closed feedback loop
    assert is_closed is False
    assert not any("closed feedback loop" in n.lower() for n in notes)


def test_commander_self_evaluation_prevention():
    """Verify candidate card does not evaluate against itself if matching commander name."""
    dina_card = {
        "name": "Dina, Soul Steeper",
        "type_line": "Legendary Creature — Dryad Druid",
        "cmc": 2.0,
        "oracle_text": "Whenever you gain life, each opponent loses 1 life. {1}, Sacrifice another creature: Dina gets +X/+X until end of turn."
    }

    eval_self = evaluate_candidate_in_deck(dina_card, dina_card, price=0.75)
    # Candidate should not link to itself
    assert eval_self["raw_synergy"] == 0.0
    assert eval_self["has_closed_loop"] is False


def test_vector_compilation_and_closed_loop_detection():
    """Verify mechanical state vectors detect closed feedback loops with commander."""
    dina_card = {
        "name": "Dina, Soul Steeper",
        "type_line": "Legendary Creature — Dryad Druid",
        "cmc": 2.0,
        "oracle_text": "Whenever you gain life, each opponent loses 1 life. {1}, Sacrifice another creature: Dina gets +X/+X until end of turn."
    }

    blood_artist_card = {
        "name": "Blood Artist",
        "type_line": "Creature — Vampire",
        "cmc": 2.0,
        "oracle_text": "Whenever Blood Artist or another creature dies, target player loses 1 life and you gain 1 life."
    }

    d_vec = compile_card_vector(dina_card)
    b_vec = compile_card_vector(blood_artist_card)

    assert "life_gain" in d_vec.inputs
    assert "life_loss" in d_vec.outputs
    assert "creature_dies" in d_vec.outputs

    assert "creature_dies" in b_vec.inputs
    assert "life_gain" in b_vec.outputs
    assert "life_loss" in b_vec.outputs

    score, notes, is_closed = evaluate_pairwise_synergy(b_vec, d_vec, is_commander=True)
    assert is_closed is True
    assert score > 150.0  # Loop multiplier (3.0x) + Commander multiplier (2.5x)
    assert any("closed feedback loop" in n.lower() for n in notes)


def test_budget_synergy_decisively_outscores_expensive_staple():
    """Verify that a $0.35 synergy card with loop or trigger dominates a $42 generic staple."""
    dina_card = {
        "name": "Dina, Soul Steeper",
        "type_line": "Legendary Creature — Dryad Druid",
        "cmc": 2.0,
        "oracle_text": "Whenever you gain life, each opponent loses 1 life. {1}, Sacrifice another creature: Dina gets +X/+X until end of turn."
    }

    obscure_synergy = {
        "name": "Nadier's Nightblade",
        "type_line": "Creature — Elf Warrior",
        "cmc": 3.0,
        "oracle_text": "Whenever a token you control leaves the battlefield, each opponent loses 1 life and you gain 1 life.",
        "edhrec_rank": 3200
    }

    expensive_staple = {
        "name": "Rhystic Study",
        "type_line": "Enchantment",
        "cmc": 3.0,
        "oracle_text": "Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.",
        "edhrec_rank": 15
    }

    eval_obscure = evaluate_candidate_in_deck(obscure_synergy, dina_card, price=0.35)
    eval_expensive = evaluate_candidate_in_deck(expensive_staple, dina_card, price=42.50)

    assert eval_obscure["composite_score"] > eval_expensive["composite_score"] * 50.0
    assert eval_obscure["price_penalty"] < 1.5
    assert eval_expensive["price_penalty"] > 16.0


def test_get_swap_candidates_returns_affiliate_and_notes():
    """Verify get_swap_candidates integration returns all v2 metadata fields."""
    conn = db.get_connection("data/cards.db")
    candidates = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Cultivate",
        commander_name="Dina, Soul Steeper",
        category="synergy",
        bracket=3,
        limit=4
    )
    conn.close()

    assert len(candidates) > 0
    for cand in candidates:
        assert "price" in cand
        assert "mana_pool_url" in cand
        assert "ref=loreweaver" in cand["mana_pool_url"]
        assert "ref_meta=source:loreweaver_swap" in cand["mana_pool_url"]
        assert "interaction_notes" in cand
        assert "composite_score" in cand
        assert "has_closed_loop" in cand


def test_mishra_possibility_storm_and_blood_funnel_synergy():
    """Verify that Mishra detects strong synergy with Possibility Storm and Blood Funnel."""
    mishra = {
        "name": "Mishra, Artificer Prodigy",
        "type_line": "Legendary Creature — Human Artificer",
        "cmc": 4.0,
        "oracle_text": "Whenever you cast an artifact spell, you may search your graveyard, hand, and/or library for a card with the same name as that spell and put it onto the battlefield. If you search your library this way, shuffle.",
        "edhrec_rank": 22722
    }
    pstorm = {
        "name": "Possibility Storm",
        "type_line": "Enchantment",
        "cmc": 5.0,
        "oracle_text": "Whenever a player casts a spell from their hand, that player exiles it, then exiles cards from the top of their library until they exile a card that shares a card type with it. That player may cast that card without paying its mana cost. Then they put all cards exiled with this enchantment on the bottom of their library in a random order.",
        "edhrec_rank": 4771
    }
    bfunnel = {
        "name": "Blood Funnel",
        "type_line": "Enchantment",
        "cmc": 2.0,
        "oracle_text": "Noncreature spells you cast cost {2} less to cast.\nWhenever you cast a noncreature spell, counter that spell unless you sacrifice a creature.",
        "edhrec_rank": 15050
    }

    eval_pstorm = evaluate_candidate_in_deck(pstorm, mishra, price=1.54)
    eval_bfunnel = evaluate_candidate_in_deck(bfunnel, mishra, price=0.35)

    assert eval_pstorm["raw_synergy"] > 0.0
    assert eval_pstorm["composite_score"] > 25.0
    assert any("mishra" in n.lower() for n in eval_pstorm["interaction_notes"])

    assert eval_bfunnel["raw_synergy"] > 0.0
    assert eval_bfunnel["composite_score"] > 50.0
    assert eval_bfunnel["spice_bonus"] == 2.0
    assert any("mishra" in n.lower() for n in eval_bfunnel["interaction_notes"])

