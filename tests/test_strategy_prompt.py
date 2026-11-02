"""Pytest verification for semantic strategy intent parsing, planeswalker multi-activation engines,
and explanatory game state blueprint generation.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest
try:
    from scripts import db
    from scripts.deck_builder import build_deck, extract_strategy_intents
except ImportError:
    import db
    from deck_builder import build_deck, extract_strategy_intents


@pytest.fixture(scope="module")
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


class TestSemanticStrategyIntentParser:
    """Tests for extract_strategy_intents morphological stemming and intent classification."""

    def test_planeswalker_multi_activation_stax_detection(self):
        prompt = "I would like to be able to activate planeswalkers on everyones turn and multiple times."
        win_con = "stax"
        intents = extract_strategy_intents(prompt, win_con)

        assert intents["is_planeswalker_theme"] is True
        assert intents["is_multi_activation"] is True
        assert intents["is_stax"] is True
        assert "planeswalker" in intents["tokens"]
        assert "turn" in intents["tokens"]
        assert intents["is_tokens"] is False
        assert intents["is_sacrifice"] is False

    def test_apostrophe_and_punctuation_handling(self):
        prompt = "I want to activate planeswalkers on everyone's turn, twice or multiple times!"
        intents = extract_strategy_intents(prompt, "combat")

        assert intents["is_planeswalker_theme"] is True
        assert intents["is_multi_activation"] is True
        assert intents["is_stax"] is False

    def test_superfriends_keyword_detection(self):
        prompt = "5-color superfriends loyalty proliferation"
        intents = extract_strategy_intents(prompt, "combo")

        assert intents["is_planeswalker_theme"] is True
        assert intents["is_counters"] is True
        assert "superfriends" in intents["normalized_text"]


class TestStrategyPromptDeckArchitect:
    """End-to-end deck generation tests for Planeswalker multi-activation stax prompt."""

    def test_primary_planeswalker_multi_activation_stax_prompt(self, conn):
        prompt = "I would like to be able to activate planeswalkers on everyones turn and multiple times."
        win_con = "stax"

        result = build_deck(
            conn=conn,
            deck_idea=prompt,
            preferred_win_con=win_con,
            bracket=3
        )

        all_cards = []
        for cat, cards in result["categories"].items():
            all_cards.extend(cards)

        # 1. Total cards invariant: Exactly 100 tournament-legal cards
        assert result["total_cards"] == 100
        assert len(all_cards) == 100

        # 2. Singleton invariant: Zero non-basic duplicate cards
        non_basics = [c["name"] for c in all_cards if "Basic" not in c.get("type_line", "")]
        duplicates = [name for name in set(non_basics) if non_basics.count(name) > 1]
        assert len(duplicates) == 0, f"Found non-basic duplicates: {duplicates}"

        # 3. Planeswalker Core Quota: At least 12 planeswalkers drafted into the 99
        planeswalkers = [c for c in all_cards if "Planeswalker" in c.get("type_line", "")]
        pw_names = [c["name"] for c in planeswalkers]
        assert len(planeswalkers) >= 12, f"Expected >= 12 planeswalkers, got {len(planeswalkers)}: {pw_names}"
        assert len(planeswalkers) <= 18, f"Expected <= 18 planeswalkers, got {len(planeswalkers)}"

        # 4. Multi-Activation & Timing Enablers: Must include The Chain Veil and/or Oath of Teferi / Teferi
        all_card_names = {c["name"] for c in all_cards}
        enablers_found = all_card_names.intersection({
            "The Chain Veil", "Oath of Teferi", "Teferi, Temporal Archmage",
            "Teferi, Master of Time", "Ichormoon Gauntlet", "Displacer Kitten"
        })
        assert len(enablers_found) >= 2, f"Expected at least 2 multi-activation enablers, found {enablers_found}"
        assert "The Chain Veil" in all_card_names or "Oath of Teferi" in all_card_names

        # 5. Stax Protection Package: Must include key stax pieces
        stax_found = all_card_names.intersection({
            "Rule of Law", "Archon of Emeria", "Deafening Silence",
            "Drannith Magistrate", "Dauthi Voidwalker"
        })
        assert len(stax_found) >= 3, f"Expected at least 3 stax pieces, found {stax_found}"

        # 6. Explanatory Game State Blueprint
        blueprint = result["win_con_execution"]
        assert "⚡ Tactical Concept" in blueprint
        assert "⚙️ Game State Engine" in blueprint
        assert "🎯 Planeswalker Arsenal" in blueprint
        assert "🛡️ Win Condition Synergy" in blueprint
        assert "📈 Turn-by-Turn Game Progression" in blueprint

        # Must mention multi-activation engine and planeswalkers in the blueprint
        assert "The Chain Veil" in blueprint or "Oath of Teferi" in blueprint
        assert "Rule of Law" in blueprint or "Archon of Emeria" in blueprint
        assert "Turns 1–3" in blueprint
        assert "Turns 4–5" in blueprint
        assert "Endgame" in blueprint

    def test_planeswalker_with_color_restriction_esper(self, conn):
        prompt = "activate planeswalkers multiple times each turn"
        win_con = "stax"

        result = build_deck(
            conn=conn,
            deck_idea=prompt,
            color_preference="esper",
            preferred_win_con=win_con,
            bracket=3
        )

        all_cards = []
        for cat, cards in result["categories"].items():
            all_cards.extend(cards)

        assert result["total_cards"] == 100
        # All cards must be within Esper (W, U, B) identity
        for card in all_cards:
            assert set(card.get("color_identity", [])).issubset({"W", "U", "B"})

        planeswalkers = [c for c in all_cards if "Planeswalker" in c.get("type_line", "")]
        assert len(planeswalkers) >= 12

        all_card_names = {c["name"] for c in all_cards}
        assert "The Chain Veil" in all_card_names or "Oath of Teferi" in all_card_names

    def test_planeswalker_non_stax_win_con_combat(self, conn):
        prompt = "Planeswalker superfriends multiple activations"
        win_con = "combat"

        result = build_deck(
            conn=conn,
            deck_idea=prompt,
            preferred_win_con=win_con,
            bracket=3
        )

        assert result["total_cards"] == 100
        planeswalkers = [c for c in result["categories"]["synergy"] + result["categories"]["draw"] + result["categories"]["removal"] if "Planeswalker" in c.get("type_line", "")]
        assert len(planeswalkers) >= 12

        blueprint = result["win_con_execution"]
        assert "Tactical Concept" in blueprint
        assert "COMBAT" in blueprint.upper()
