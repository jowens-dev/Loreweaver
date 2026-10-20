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
