"""Tests for Cross-Tab Deck Translation between Weave Deck (DeckArchitect) and all other tabs."""

import re
from pathlib import Path
import pytest
from scripts import db, deck_builder
from scripts.deck_exporter import export_all_formats

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_JSX_PATH = REPO_ROOT / "web" / "src" / "App.jsx"
DECK_ARCHITECT_JSX_PATH = REPO_ROOT / "web" / "src" / "DeckArchitect.jsx"


def test_app_jsx_keeps_tabs_mounted():
    """Verify that App.jsx uses CSS display toggling instead of conditional unmounting for all tab panels.
    Conditional unmounting previously destroyed the woven deck and form state when navigating tabs.
    """
    assert APP_JSX_PATH.exists(), "App.jsx not found"
    content = APP_JSX_PATH.read_text(encoding="utf-8")

    # Verify that all 5 main tabs are rendered with persistent display styles
    tabs = ["input", "cohesion", "stress", "spice", "builder", "links"]
    for tab in tabs:
        pattern = rf'style=\{{\{{.*?display:\s*activeTab\s*===\s*[\'"]{tab}[\'"]'
        assert re.search(pattern, content, re.DOTALL), f"Tab panel '{tab}' is not using persistent display style"

    # Verify that old destructive conditional unmounting is absent
    destructive_patterns = [
        r'\{activeTab === \'builder\' &&',
        r'\{activeTab === \'cohesion\' &&',
        r'\{activeTab === \'stress\' &&',
        r'\{activeTab === \'spice\' &&',
        r'\{activeTab === \'input\' &&',
    ]
    for pattern in destructive_patterns:
        assert not re.search(pattern, content), f"Found destructive conditional unmount: {pattern}"


def test_deck_architect_prop_contracts():
    """Verify DeckArchitect accepts activeDeckResult and onDeckChange, and wires them into setDeckResult."""
    assert DECK_ARCHITECT_JSX_PATH.exists(), "DeckArchitect.jsx not found"
    content = DECK_ARCHITECT_JSX_PATH.read_text(encoding="utf-8")

    # Check function signature
    assert "activeDeckResult" in content, "DeckArchitect missing activeDeckResult prop"
    assert "onDeckChange" in content, "DeckArchitect missing onDeckChange prop"

    # Check setDeckResult callback notifies onDeckChange
    assert "onDeckChange(next)" in content, "setDeckResult does not call onDeckChange callback"

    # Check that View Deck Analysis button is present with correct label and function
    assert "View Deck Analysis" in content, "DeckArchitect missing 'View Deck Analysis' action"
    assert "handleSendToAnalyzer" in content, "handleSendToAnalyzer missing in DeckArchitect"


def test_app_jsx_syncs_woven_deck_and_auto_analyzes():
    """Verify App.jsx handles woven deck changes, synchronizes commander/decklist/bracket,
    and automatically primes Cohesion, Stress, and Spice via background runDeckAnalysis."""
    content = APP_JSX_PATH.read_text(encoding="utf-8")

    assert "handleWovenDeckChange" in content, "App.jsx missing handleWovenDeckChange handler"
    assert "activeWovenDeck" in content, "App.jsx missing activeWovenDeck state"
    assert "runDeckAnalysis" in content, "App.jsx missing runDeckAnalysis decoupled runner"

    # Verify background execution without tab-hijacking
    assert "runDeckAnalysis(text, cmdName, tier, false)" in content, (
        "handleWovenDeckChange does not run background analysis without tab switching"
    )

    # Verify DeckArchitect element receives the sync props
    assert "activeDeckResult={activeWovenDeck}" in content, "DeckArchitect missing activeDeckResult binding"
    assert "onDeckChange={handleWovenDeckChange}" in content, "DeckArchitect missing onDeckChange binding"


def test_loader_precedence_in_analysis_tabs():
    """Popperian check: loading state must take precedence over !analyzed in cohesion, stress, and spice.
    Previously, checking !analyzed first caused an unanalyzed deck to show a blank/dead error state
    rather than the active loader while background analysis was computing.
    """
    content = APP_JSX_PATH.read_text(encoding="utf-8")

    # In each analysis tab, verify loading ? <loader> comes before !analyzed
    for tab_title in ["Thematic Cohesion Dashboard", "Engine Stress-Tester Dashboard", "Proactive Spice Injector"]:
        tab_idx = content.find(tab_title)
        assert tab_idx != -1, f"Missing section: {tab_title}"
        section = content[tab_idx:tab_idx + 1200]

        loader_idx = section.find("loader-container")
        empty_idx = section.find("empty-state")
        assert loader_idx != -1, f"Loader container missing in {tab_title}"
        assert empty_idx != -1, f"Empty state missing in {tab_title}"
        assert loader_idx < empty_idx, f"Loader must precede empty-state in {tab_title}"


def test_active_deck_sync_banners_present():
    """Verify all tabs show the active deck synchronization banner and quick navigation buttons."""
    content = APP_JSX_PATH.read_text(encoding="utf-8")

    assert "Active Deck: " in content, "Missing active deck banner in analysis tabs"
    assert "Deck translated from" in content, "Missing deck translated banner in Audit tab"
    assert "Open in Weave Deck" in content, "Missing quick jump to Weave Deck in analysis tabs"
    assert "Return to Weave Deck" in content, "Missing return to Weave Deck button in Audit tab"


def test_woven_deck_text_compatibility_with_theme_engine():
    """Verify that a deck produced by deck_builder.build_deck translates cleanly into 100 cards
    usable by the theme engine and analyzer."""
    conn = db.get_connection()
    try:
        deck = deck_builder.build_deck(
            conn=conn,
            commander_name="Atraxa, Praetors' Voice",
            deck_idea="Proliferate and +1/+1 counters",
            bracket=3,
            budget="moderate",
            color_preference="W,U,B,G",
            preferred_win_con="combat"
        )
        assert deck["commander"]["name"] == "Atraxa, Praetors' Voice"
        assert deck["decklist_text"], "Missing decklist_text export"

        # Check line formats
        lines = [line.strip() for line in deck["decklist_text"].split("\n") if line.strip() and not line.startswith("//")]
        total_cards = 0
        for line in lines:
            parts = line.split(" ", 1)
            assert len(parts) == 2, f"Invalid deck line: {line}"
            qty = int(parts[0])
            total_cards += qty

        assert total_cards == 100, f"Expected 100 cards from build_deck, got {total_cards}"
    finally:
        conn.close()
