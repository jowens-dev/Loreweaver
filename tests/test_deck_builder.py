"""Unit tests for the Objective Synergy Commander Deck Architect Engine."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import db  # noqa: E402
import deck_builder  # noqa: E402

BASIC_LAND_NAMES = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def test_deck_builder_100_cards_and_roles():
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Belbe, Corrupted Observer",
        deck_idea="big mana acceleration and colorless bombs",
        bracket=3,
        budget="moderate",
        preferred_win_con="combat"
    )
    conn.close()

    assert deck["total_cards"] == 100
    assert deck["commander"]["name"] == "Belbe, Corrupted Observer"
    assert len(deck["categories"]["lands"]) == 35
    assert len(deck["categories"]["ramp"]) >= 10
    assert len(deck["categories"]["draw"]) >= 10
    assert len(deck["categories"]["removal"]) >= 10
    assert len(deck["categories"]["win_con"]) == 4


def test_color_identity_compliance():
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Belbe, Corrupted Observer",
        bracket=4,
        preferred_win_con="combat"
    )
    conn.close()

    allowed = set(deck["commander"]["color_identity"])
    assert allowed == {"B", "G"}

    for role, card_list in deck["categories"].items():
        for card in card_list:
            card_id = set(card.get("color_identity", []))
            assert card_id.issubset(allowed), (
                f"Card {card['name']} with identity {card_id} violates commander identity {allowed}"
            )


def test_singleton_rule():
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Teysa Karlov",
        deck_idea="aristocrats sacrifice and drain",
        bracket=3,
        preferred_win_con="drain"
    )
    conn.close()

    counts: dict[str, int] = {}
    for role, card_list in deck["categories"].items():
        for card in card_list:
            name = card["name"]
            counts[name] = counts.get(name, 0) + 1

    for name, cnt in counts.items():
        if name not in BASIC_LAND_NAMES:
            assert cnt == 1, f"Non-basic card '{name}' appears {cnt} times in deck (violates singleton rule)"


def test_bracket_1_restrictions():
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Gisa and Geralf",
        deck_idea="zombie tribal graveyard reanimation",
        bracket=1,
        preferred_win_con="combat"
    )
    conn.close()

    assert deck["total_cards"] == 100
    assert deck["bracket"]["tier"] == 1
    assert len(deck["categories"]["lands"]) == 38

    # Fast mana and tutors must be strictly excluded in Bracket 1
    all_names = {c["name"].lower() for group in deck["categories"].values() for c in group}
    assert "sol ring" not in all_names
    assert "mana crypt" not in all_names
    assert "demonic tutor" not in all_names
    assert "vampiric tutor" not in all_names


def test_bracket_4_unrestricted_power():
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Belbe, Corrupted Observer",
        deck_idea="deal damage to all players on every turn to play huge colorless spells with flash or instant speed",
        bracket=4,
        preferred_win_con="combat"
    )
    deck_veyran = deck_builder.build_deck(
        conn=conn,
        commander_name="Veyran, Voice of Duality",
        deck_idea="spellslinger cantrips and storm",
        bracket=4,
        preferred_win_con="burn"
    )
    conn.close()

    assert deck["bracket"]["tier"] == 4
    all_names = {c["name"].lower() for group in deck["categories"].values() for c in group}
    assert "sol ring" in all_names
    assert "ancient tomb" in all_names
    # Big mana colorless bombs are embraced for Belbe
    assert any(c.get("cmc", 0) >= 6 for c in deck["categories"]["synergy"])
    # Standard Bracket 4 spellslinger maintains lean CMC
    assert deck_veyran["stats"]["avg_cmc"] < 2.8


def test_bracket_5_cedh_meta_staples():
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Talion, the Kindly Lord",
        deck_idea="cedh tournament combo",
        bracket=5,
        budget="unlimited",
        preferred_win_con="combo"
    )
    conn.close()

    assert deck["bracket"]["tier"] == 5
    assert len(deck["categories"]["lands"]) == 28
    # cEDH curve is razor-thin
    assert deck["stats"]["avg_cmc"] < 2.0

    all_names = {c["name"] for group in deck["categories"].values() for c in group}
    # Mandatory cEDH fast mana
    assert "Mana Crypt" in all_names
    assert "Mox Diamond" in all_names
    assert "Chrome Mox" in all_names
    assert "Lotus Petal" in all_names
    assert "Sol Ring" in all_names
    assert "Mana Vault" in all_names
    assert "Dark Ritual" in all_names

    # Mandatory cEDH interaction & win cons
    assert "Force of Will" in all_names
    assert "Thassa's Oracle" in all_names
    assert "Demonic Consultation" in all_names


def test_dynamic_commander_discovery():
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="",
        deck_idea="aristocrats sacrifice and death triggers",
        bracket=3,
        color_preference="Orzhov",
        preferred_win_con="drain"
    )
    conn.close()

    assert deck["commander"] is not None
    assert set(deck["commander"]["color_identity"]).issubset({"W", "B"})
    assert deck["total_cards"] == 100
    assert "drain" in deck["preferred_win_con"]
