"""Tests for the Loreweaver SQLite database access layer."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import db  # noqa: E402


def test_db_connection_and_count():
    conn = db.get_connection()
    count = db.get_card_count(conn)
    conn.close()
    assert count >= 30000, f"Expected at least 30,000 cards in database, got {count}"


def test_alias_resolution():
    conn = db.get_connection()
    # Front-face alias for MDFC
    resolved = db.resolve_card_name(conn, "Bala Ged Recovery")
    assert "bala ged recovery // bala ged sanctuary" in resolved

    # Direct name
    direct = db.resolve_card_name(conn, "Llanowar Elves")
    assert direct == "llanowar elves"
    conn.close()


def test_get_card_by_name():
    conn = db.get_connection()
    card = db.get_card_by_name(conn, "Llanowar Elves")
    assert card is not None
    assert card["name"] == "Llanowar Elves"
    assert card["mana_cost"] == "{G}"
    assert "Creature" in card["type_line"]
    assert "elf" in card["subtypes"]
    assert card["color_identity"] == ["G"]

    belbe = db.get_card_by_name(conn, "Belbe, Corrupted Observer")
    assert belbe is not None
    assert set(belbe["color_identity"]) == {"B", "G"}
    conn.close()


def test_cards_by_identity_colorless():
    conn = db.get_connection()
    cards = db.get_cards_by_identity(conn, [], limit=50)
    conn.close()
    assert len(cards) > 0
    for card in cards:
        assert card["color_identity"] == [], f"Found colored card {card['name']} in colorless pool: {card['color_identity']}"


def test_cards_by_identity_golgari():
    conn = db.get_connection()
    cards = db.get_cards_by_identity(conn, ["B", "G"], limit=50)
    conn.close()
    assert len(cards) > 0
    allowed = {"B", "G"}
    for card in cards:
        assert set(card["color_identity"]).issubset(allowed), (
            f"Found illegal card {card['name']} with identity {card['color_identity']} in BG pool"
        )


def test_commander_legality_and_dfc_rules():
    """Verify that only cards whose FRONT face is a legal commander are marked is_commander=1."""
    conn = db.get_connection()

    # DFCs whose front face is NOT a legendary creature
    invalid_fronts = [
        "Westvale Abbey // Ormendahl, Profane Prince",
        "Nezumi Graverobber // Nighteyes the Desecrator",
        "Budoka Gardener // Dokai, Weaver of Life",
        "Bushi Tenderfoot // Kenzo the Hardhearted",
        "Invasion of Ikoria // Zilortha, Apex of Ikoria",
        "The Legend of Kuruk // Avatar Kuruk",
        "Elbrus, the Binding Blade // Withengar Unbound"
    ]
    for name in invalid_fronts:
        card = db.get_card_by_name(conn, name)
        assert card is not None, f"Card {name} should exist in database"
        assert card["is_commander"] == 0, f"{name} should NOT be eligible as a commander"
        assert card["commander_legal"] == 1, f"{name} should be legal in the 99"

    # DFCs whose front face IS a legendary creature
    valid_commanders = [
        "Extus, Oriq Overlord // Awaken the Blood Avatar",
        "Ral, Monsoon Mage // Ral, Leyline Prodigy",
        "Tamiyo, Inquisitive Student // Tamiyo, Seasoned Scholar",
        "Belbe, Corrupted Observer",
        "Atraxa, Praetors' Voice",
        "Grist, the Hunger Tide"
    ]
    for name in valid_commanders:
        card = db.get_card_by_name(conn, name)
        assert card is not None, f"Card {name} should exist in database"
        assert card["is_commander"] == 1, f"{name} MUST be eligible as a commander"
        assert card["commander_legal"] == 1, f"{name} must be format-legal in Commander"

    # Banned cards
    banned_cards = [
        "Golos, Tireless Pilgrim",
        "Nadu, Winged Wisdom",
        "Leovold, Emissary of Trest",
        "Mana Crypt",
        "Jeweled Lotus"
    ]
    for name in banned_cards:
        card = db.get_card_by_name(conn, name)
        assert card is not None, f"Card {name} should exist in database"
        assert card["is_commander"] == 0, f"{name} is banned and cannot be commander"
        assert card["commander_legal"] == 0, f"{name} is banned in Commander format"

    conn.close()


def test_predictive_search_filters_illegal_commanders():
    """Verify predictive search endpoint logic excludes illegal commanders."""
    conn = db.get_connection()

    # Searching 'west' with commanders_only=True should NOT return Westvale Abbey
    cmd_results = db.search_cards_predictive(conn, "west", commanders_only=True, limit=10)
    cmd_names = [c["name"] for c in cmd_results]
    assert not any("Westvale" in n for n in cmd_names), "Westvale Abbey must not appear in commander search"

    # Searching 'west' with commanders_only=False should return Westvale Abbey (legal in 99)
    all_results = db.search_cards_predictive(conn, "west", commanders_only=False, limit=10)
    all_names = [c["name"] for c in all_results]
    assert any("Westvale" in n for n in all_names), "Westvale Abbey should appear in card search for 99"

    # Searching banned cards with commanders_only=False should NEVER return them
    lotus_results = db.search_cards_predictive(conn, "jeweled lotus", commanders_only=False, limit=5)
    assert len(lotus_results) == 0, "Banned Jeweled Lotus must never appear in search"

    conn.close()
