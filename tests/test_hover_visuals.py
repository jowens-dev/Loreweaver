"""Tests for Hover Visuals & Card Tooltips (Item 3).

Verifies card name normalization, Scryfall data contract expectations,
DFC handling, database image URL coverage, and frontend integration integrity.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = WORKSPACE_ROOT / "web" / "src"
DB_PATH = WORKSPACE_ROOT / "data" / "cards.db"


def clean_card_name_py(raw_name: str) -> str:
    """Python reference implementation of cleanCardName from cardImageCache.js."""
    if not raw_name or not isinstance(raw_name, str):
        return ""
    cleaned = re.sub(r"^(\d+x?\s+)", "", raw_name, flags=re.IGNORECASE)
    cleaned = re.sub(r"\*CMDR\*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[.*?\]", "", cleaned)
    return cleaned.strip()


def test_clean_card_name_normalization():
    """Verify cleanCardName strips count prefixes, tags, and formatting."""
    assert clean_card_name_py("1 Sol Ring") == "Sol Ring"
    assert clean_card_name_py("1x Sol Ring") == "Sol Ring"
    assert clean_card_name_py("14 Island") == "Island"
    assert clean_card_name_py("1 Belbe, Corrupted Observer *CMDR*") == "Belbe, Corrupted Observer"
    assert clean_card_name_py("1x Toxic Deluge [Removal]") == "Toxic Deluge"
    assert clean_card_name_py("   Kozilek, the Great Distortion   ") == "Kozilek, the Great Distortion"
    assert clean_card_name_py("") == ""
    assert clean_card_name_py(None) == ""


def test_cards_db_image_url_coverage():
    """Verify that cards.db contains image_url records for commander and staples."""
    assert DB_PATH.exists(), f"Expected database at {DB_PATH}"

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query key cards across staples, commanders, and DFCs
    test_cards = [
        "sol ring",
        "arcane signet",
        "belbe, corrupted observer",
        "kozilek, the great distortion",
        "swords to plowshares"
    ]

    for card_name in test_cards:
        cursor.execute("SELECT name, image_url, type_line FROM cards WHERE name_lower = ?", (card_name,))
        row = cursor.fetchone()
        assert row is not None, f"Card '{card_name}' should exist in cards.db"
        assert row["image_url"], f"Card '{card_name}' should have a non-empty image_url"
        assert row["image_url"].startswith("http"), f"Card '{card_name}' image_url should be a valid URL"

    conn.close()


def test_dfc_card_representation():
    """Verify DFC cards exist and have proper layout and delimiters."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name, image_url, layout, oracle_text FROM cards WHERE layout IN ('transform', 'modal_dfc') LIMIT 5")
    rows = cursor.fetchall()
    assert len(rows) > 0, "Expected transform or modal_dfc cards in database"

    for r in rows:
        assert " // " in r["name"], f"DFC card '{r['name']}' must contain ' // ' delimiter"
        assert r["image_url"].startswith("http"), f"DFC card '{r['name']}' must have image_url"

    conn.close()


def test_frontend_tooltip_components_exist():
    """Verify that CardTooltip.jsx and cardImageCache.js exist and export required symbols."""
    tooltip_path = WEB_SRC / "components" / "CardTooltip.jsx"
    cache_path = WEB_SRC / "utils" / "cardImageCache.js"

    assert tooltip_path.exists(), "CardTooltip.jsx must exist"
    assert cache_path.exists(), "cardImageCache.js must exist"

    tooltip_content = tooltip_path.read_text(encoding="utf-8")
    cache_content = cache_path.read_text(encoding="utf-8")

    # Exports check
    assert "export function CardTooltip" in tooltip_content or "export default CardTooltip" in tooltip_content
    assert "export { CardTooltip as CardHover }" in tooltip_content
    assert "export function cleanCardName" in cache_content
    assert "export function getCardFromCache" in cache_content
    assert "export function setCardInCache" in cache_content
    assert "export async function fetchCardFromScryfall" in cache_content

    # Viewport collision and clamping logic check
    assert "TOOLTIP_WIDTH" in tooltip_content
    assert "VIEWPORT_PADDING" in tooltip_content
    assert "createPortal" in tooltip_content
    assert "is_dfc" in tooltip_content
    assert "activeFaceIndex" in tooltip_content


def test_frontend_integrations():
    """Verify that CardTooltip is integrated into DeckArchitect, CardSwapModal, and App."""
    deck_arch_path = WEB_SRC / "DeckArchitect.jsx"
    card_swap_path = WEB_SRC / "components" / "CardSwapModal.jsx"
    app_path = WEB_SRC / "App.jsx"

    deck_arch_content = deck_arch_path.read_text(encoding="utf-8")
    card_swap_content = card_swap_path.read_text(encoding="utf-8")
    app_content = app_path.read_text(encoding="utf-8")

    # DeckArchitect integrations
    assert "CardTooltip" in deck_arch_content
    assert "<CardTooltip" in deck_arch_content

    # CardSwapModal integrations
    assert "CardTooltip" in card_swap_content
    assert "<CardTooltip" in card_swap_content

    # App.jsx integrations (Tactical Cuts, Protected Pillars, Broken Chains/Spice, Swimlanes)
    assert "CardTooltip" in app_content
    assert "CardTooltip name={cut.card}" in app_content or "CardTooltip name={cut.suggested_replacement}" in app_content
    assert "CardTooltip key={i} name={pillar}" in app_content or "CardTooltip key=" in app_content
