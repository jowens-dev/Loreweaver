"""Unit tests for Budget Tiers, House Rules, and Ban-List Filters in Loreweaver."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

import db
import deck_builder
from api import app

client = TestClient(app)

FETCHLAND_NAMES = {
    "Polluted Delta", "Flooded Strand", "Bloodstained Mire", "Wooded Foothills",
    "Windswept Heath", "Marsh Flats", "Scalding Tarn", "Verdant Catacombs",
    "Arid Mesa", "Misty Rainforest", "Prismatic Vista"
}

SHOCKLAND_NAMES = {
    "Hallowed Fountain", "Watery Grave", "Blood Crypt", "Stomping Ground",
    "Temple Garden", "Godless Shrine", "Steam Vents", "Overgrown Tomb",
    "Sacred Foundry", "Breeding Pool"
}

RESERVED_LIST_NAMES = {
    "Timetwister", "Gaea's Cradle", "Tabernacle at Pendrell Vale",
    "Candelabra of Tawnos", "Mishra's Workshop", "Bazaar of Baghdad", "Underground Sea",
    "Volcanic Island", "Tropical Island", "Tundra", "Bayou", "Scrubland", "Taiga",
    "Badlands", "Savannah", "Plateau", "Mox Diamond", "Lion's Eye Diamond", "Gilded Drake"
}

FAST_MANA_NAMES = {
    "Sol Ring", "Mana Vault", "Grim Monolith", "Mox Diamond",
    "Chrome Mox", "Lotus Petal", "Mox Opal", "Ancient Tomb", "Lion's Eye Diamond"
}

FREE_SPELL_NAMES = {
    "Fierce Guardianship", "Force of Will", "Deflecting Swat", "Deadly Rollick",
    "Flawless Maneuver", "Force of Negation", "Pact of Negation", "Mental Misstep",
    "Mindbreak Trap"
}

STAX_NAMES = {
    "Winter Orb", "Static Orb", "Stasis", "Armageddon", "Blood Moon",
    "Back to Basics", "Ruination", "Smokestack", "Trinisphere", "Rule of Law"
}

COMBO_NAMES = {
    "Thassa's Oracle", "Demonic Consultation", "Tainted Pact", "Underworld Breach",
    "Brain Freeze", "Lion's Eye Diamond", "Heliod, Sun-Crowned", "Walking Ballista",
    "Dualcaster Mage", "Twinflame", "Exquisite Blood", "Sanguine Bond"
}

TUTOR_NAMES = {
    "Demonic Tutor", "Vampiric Tutor", "Imperial Seal", "Worldly Tutor",
    "Mystical Tutor", "Enlightened Tutor", "Gamble"
}


def get_all_card_names(deck: dict) -> set[str]:
    """Helper to collect all card names from deck categories."""
    names = set()
    for cat_name, cards in deck["categories"].items():
        for c in cards:
            names.add(c["name"])
    return names


def test_no_fast_mana_strips_sol_ring_and_fast_mana_in_high_brackets():
    """Verify 'no_fast_mana' house rule strips Sol Ring and fast rocks in Brackets 4 and 5."""
    conn = db.get_connection()
    try:
        # Bracket 4
        deck_b4 = deck_builder.build_deck(
            conn=conn,
            commander_name="Belbe, Corrupted Observer",
            bracket=4,
            budget="unlimited",
            house_rules=["no_fast_mana"]
        )
        names_b4 = get_all_card_names(deck_b4)
        for fm in FAST_MANA_NAMES:
            assert fm not in names_b4, f"Fast mana '{fm}' leaked into Bracket 4 deck under 'no_fast_mana'"

        # Bracket 5 (cEDH)
        deck_b5 = deck_builder.build_deck(
            conn=conn,
            commander_name="Talion, the Kindly Lord",
            bracket=5,
            budget="unlimited",
            preferred_win_con="combo",
            house_rules=["no_fast_mana"]
        )
        names_b5 = get_all_card_names(deck_b5)
        for fm in FAST_MANA_NAMES:
            assert fm not in names_b5, f"Fast mana '{fm}' leaked into Bracket 5 deck under 'no_fast_mana'"
        assert deck_b5["total_cards"] == 100
    finally:
        conn.close()


def test_no_combos_house_rule_strips_combo_lines():
    """Verify 'no_combos' house rule strips 2-card and compact combo lines even in cEDH Bracket 5."""
    conn = db.get_connection()
    try:
        deck = deck_builder.build_deck(
            conn=conn,
            commander_name="Talion, the Kindly Lord",
            bracket=5,
            budget="unlimited",
            preferred_win_con="combo",
            house_rules=["no_combos"]
        )
        names = get_all_card_names(deck)
        for combo_card in COMBO_NAMES:
            assert combo_card not in names, f"Combo card '{combo_card}' leaked into deck with 'no_combos' active"
        assert deck["total_cards"] == 100
    finally:
        conn.close()


def test_no_free_spells_strips_free_counterspells_and_interaction():
    """Verify 'no_free_spells' strips free counterspells and free interaction in high power."""
    conn = db.get_connection()
    try:
        deck = deck_builder.build_deck(
            conn=conn,
            commander_name="Kenrith, the Returned King",
            bracket=5,
            budget="unlimited",
            house_rules=["no_free_spells"]
        )
        names = get_all_card_names(deck)
        for free_spell in FREE_SPELL_NAMES:
            assert free_spell not in names, f"Free spell '{free_spell}' leaked into deck with 'no_free_spells' active"
        assert deck["total_cards"] == 100
    finally:
        conn.close()


def test_no_stax_strips_stax_and_mass_land_destruction():
    """Verify 'no_stax' strips Winter Orb, Blood Moon, Trinisphere, etc."""
    conn = db.get_connection()
    try:
        deck = deck_builder.build_deck(
            conn=conn,
            commander_name="Kenrith, the Returned King",
            bracket=4,
            budget="unlimited",
            preferred_win_con="stax",
            house_rules=["no_stax"]
        )
        names = get_all_card_names(deck)
        for stax_card in STAX_NAMES:
            assert stax_card not in names, f"Stax card '{stax_card}' leaked into deck with 'no_stax' active"
        assert deck["total_cards"] == 100
    finally:
        conn.close()


def test_no_tutors_strips_cheap_tutors():
    """Verify 'no_tutors' strips Demonic Tutor, Vampiric Tutor, Imperial Seal, etc."""
    conn = db.get_connection()
    try:
        deck = deck_builder.build_deck(
            conn=conn,
            commander_name="Kenrith, the Returned King",
            bracket=5,
            budget="unlimited",
            house_rules=["no_tutors"]
        )
        names = get_all_card_names(deck)
        for tutor_card in TUTOR_NAMES:
            assert tutor_card not in names, f"Tutor '{tutor_card}' leaked into deck with 'no_tutors' active"
        assert deck["total_cards"] == 100
    finally:
        conn.close()


def test_custom_card_bans_guarantees_cards_never_appear():
    """Verify custom card bans (case-insensitive) strictly exclude specified cards."""
    conn = db.get_connection()
    try:
        banned = ["Rhystic Study", "Smothering Tithe", "The One Ring", "Esper Sentinel"]
        deck = deck_builder.build_deck(
            conn=conn,
            commander_name="Kenrith, the Returned King",
            bracket=4,
            budget="unlimited",
            custom_bans=["  rhystic STUDY ", "SMOTHERING tithe  ", "The One Ring", "Esper Sentinel"]
        )
        names = get_all_card_names(deck)
        for b in banned:
            assert b not in names, f"Custom banned card '{b}' appeared in deck!"
        assert deck["total_cards"] == 100
    finally:
        conn.close()


def test_ultra_budget_produces_100_valid_cards_with_zero_fetchlands_or_reserved_list():
    """Verify 'ultra_budget' (<$50) produces 100 cards with zero fetchlands, zero shocklands, and zero reserved list."""
    conn = db.get_connection()
    try:
        deck = deck_builder.build_deck(
            conn=conn,
            commander_name="Kenrith, the Returned King",
            bracket=3,
            budget="ultra_budget",
            preferred_win_con="combat"
        )
        names = get_all_card_names(deck)

        assert deck["total_cards"] == 100
        assert deck["budget"] == "ultra_budget"

        # Zero fetchlands
        for f in FETCHLAND_NAMES:
            assert f not in names, f"Fetchland '{f}' found in ultra_budget deck!"

        # Zero shocklands
        for s in SHOCKLAND_NAMES:
            assert s not in names, f"Shockland '{s}' found in ultra_budget deck!"

        # Zero reserved list
        for r in RESERVED_LIST_NAMES:
            assert r not in names, f"Reserved list card '{r}' found in ultra_budget deck!"

        # Zero fast mana
        for m in FAST_MANA_NAMES:
            assert m not in names, f"Fast mana '{m}' found in ultra_budget deck!"

        # Has valid budget alternatives (bounce lands, scry temples, or basics)
        lands = [c["name"] for c in deck["categories"]["lands"]]
        has_budget_fixing = any(
            "Aqueduct" in l or "Rot Farm" in l or "Boilerworks" in l or "Temple of" in l or
            "Wilds" in l or "Expanse" in l or "Landscape" in l
            for l in lands
        )
        assert has_budget_fixing, "Ultra-budget deck did not include budget replacement lands!"
    finally:
        conn.close()


def test_exact_100_card_invariant_under_extreme_bans():
    """Verify exact 100-card invariant is upheld even when all 5 house rules and extensive custom bans are active."""
    conn = db.get_connection()
    try:
        heavy_bans = [
            "Sol Ring", "Arcane Signet", "Command Tower", "Rhystic Study", "Smothering Tithe",
            "The One Ring", "Cyclonic Rift", "Swords to Plowshares", "Demonic Tutor",
            "Vampiric Tutor", "Bolas's Citadel", "Craterhoof Behemoth", "Cultivate",
            "Kodama's Reach", "Beast Within", "Fellwar Stone", "Mind Stone"
        ]
        deck = deck_builder.build_deck(
            conn=conn,
            commander_name="Kenrith, the Returned King",
            bracket=3,
            budget="ultra_budget",
            house_rules=["no_combos", "no_fast_mana", "no_free_spells", "no_stax", "no_tutors"],
            custom_bans=heavy_bans
        )
        names = get_all_card_names(deck)

        # 100 card invariant check
        assert deck["total_cards"] == 100
        for b in heavy_bans:
            assert b not in names, f"Heavy banned card '{b}' appeared in deck!"

        # Color identity validation
        allowed_colors = set(deck["commander"]["color_identity"])
        for cat_name, cards in deck["categories"].items():
            for c in cards:
                c_id = set(c.get("color_identity", []))
                assert c_id.issubset(allowed_colors), f"Card '{c['name']}' violates color identity {allowed_colors}"

        # Singleton rule verification (except basic lands)
        basic_names = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
        card_counts = {}
        for cat_name, cards in deck["categories"].items():
            for c in cards:
                if c["name"] not in basic_names:
                    card_counts[c["name"]] = card_counts.get(c["name"], 0) + 1

        duplicates = {k: v for k, v in card_counts.items() if v > 1}
        assert not duplicates, f"Singleton violation under extreme bans: {duplicates}"
    finally:
        conn.close()


def test_api_build_endpoint_with_budget_and_house_rules():
    """Verify POST /api/build accepts budget, house_rules, and custom_bans and enforces them."""
    payload = {
        "commander": "Belbe, Corrupted Observer",
        "bracket": 4,
        "budget": "ultra_budget",
        "house_rules": ["no_fast_mana", "no_combos"],
        "custom_bans": ["Sol Ring", "Mana Vault", "Wurmcoil Engine"]
    }
    response = client.post("/api/build", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_cards"] == 100
    assert data["budget"] == "ultra_budget"
    assert "no_fast_mana" in data["house_rules"]
    assert "no_combos" in data["house_rules"]

    deck_names = set()
    for cat_name, cards in data["categories"].items():
        for c in cards:
            deck_names.add(c["name"])

    assert "Sol Ring" not in deck_names
    assert "Mana Vault" not in deck_names
    assert "Wurmcoil Engine" not in deck_names
    assert "Overgrown Tomb" not in deck_names  # Shockland excluded in ultra_budget
    assert "Verdant Catacombs" not in deck_names  # Fetchland excluded in ultra_budget
