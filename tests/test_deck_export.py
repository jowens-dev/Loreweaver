"""Unit and adversarial tests for the Loreweaver Deck Exporter."""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import db  # noqa: E402
import deck_builder  # noqa: E402
import deck_exporter  # noqa: E402


def test_single_commander_export_all_formats():
    """Verify that a single-commander deck generates exact 100-card exports across all platforms."""
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Belbe, Corrupted Observer",
        bracket=3,
        budget="moderate",
        preferred_win_con="combat"
    )
    conn.close()

    assert deck["total_cards"] == 100
    assert "exports" in deck

    # 1. Moxfield Format
    mox = deck["exports"]["moxfield"]
    assert "1 Belbe, Corrupted Observer *CMDR*" in mox
    mox_count = deck_exporter.parse_export_card_count(mox, "moxfield")
    assert mox_count == 100, f"Moxfield export had {mox_count} cards, expected 100"
    # Ensure only 1 commander tagged *CMDR*
    assert mox.count("*CMDR*") == 1

    # 2. Archidekt Format
    archi = deck["exports"]["archidekt"]
    assert "1x Belbe, Corrupted Observer *CMDR* [Commander]" in archi
    assert "[Ramp]" in archi or "[Draw]" in archi
    archi_count = deck_exporter.parse_export_card_count(archi, "archidekt")
    assert archi_count == 100, f"Archidekt export had {archi_count} cards, expected 100"

    # 3. MTGO .dec Format
    mtgo = deck["exports"]["mtgo"]
    assert "// Commander" in mtgo
    assert "// Mainboard" in mtgo
    assert "1 Belbe, Corrupted Observer" in mtgo
    mtgo_count = deck_exporter.parse_export_card_count(mtgo, "mtgo")
    assert mtgo_count == 100, f"MTGO export had {mtgo_count} cards, expected 100"

    # 4. Plain Text Format
    text_out = deck["exports"]["text"]
    assert "// Commander" in text_out
    assert "1 Belbe, Corrupted Observer" in text_out
    text_count = deck_exporter.parse_export_card_count(text_out, "text")
    assert text_count == 100, f"Text export had {text_count} cards, expected 100"

    # 5. CSV Export
    csv_out = deck["exports"]["csv"]
    csv_count = deck_exporter.parse_export_card_count(csv_out, "csv")
    assert csv_count == 100, f"CSV export had {csv_count} cards, expected 100"

    # Verify CSV headers & column integrity
    reader = csv.DictReader(io.StringIO(csv_out))
    assert reader.fieldnames == ["Count", "Name", "Category", "CMC", "Type"]
    rows = list(reader)
    commander_row = next(r for r in rows if r["Name"] == "Belbe, Corrupted Observer")
    assert commander_row["Count"] == "1"
    assert commander_row["Category"] == "Commander"
    assert commander_row["CMC"] == "2"
    assert "Legendary Creature" in commander_row["Type"]


def test_partner_commanders_export_all_formats():
    """Verify that a partner-commander deck generates exact 100-card exports with both commanders tagged."""
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Thrasios, Triton Hero / Tymna the Weaver",
        bracket=4,
        preferred_win_con="combo"
    )
    conn.close()

    assert deck["total_cards"] == 100
    assert len(deck["commanders"]) == 2

    # 1. Moxfield Format: Both commanders tagged *CMDR*, exact 100 cards
    mox = deck_exporter.export_to_moxfield(deck)
    assert "1 Thrasios, Triton Hero *CMDR*" in mox
    assert "1 Tymna the Weaver *CMDR*" in mox
    assert mox.count("*CMDR*") == 2
    mox_count = deck_exporter.parse_export_card_count(mox, "moxfield")
    assert mox_count == 100, f"Partner Moxfield export had {mox_count} cards, expected 100"

    # 2. Archidekt Format: Both commanders tagged *CMDR* [Commander]
    archi = deck_exporter.export_to_archidekt(deck)
    assert "1x Thrasios, Triton Hero *CMDR* [Commander]" in archi
    assert "1x Tymna the Weaver *CMDR* [Commander]" in archi
    archi_count = deck_exporter.parse_export_card_count(archi, "archidekt")
    assert archi_count == 100, f"Partner Archidekt export had {archi_count} cards, expected 100"

    # 3. MTGO .dec Format: Both commanders listed under // Commander
    mtgo = deck_exporter.export_to_mtgo(deck)
    cmdr_section, main_section = mtgo.split("// Mainboard")
    assert "1 Thrasios, Triton Hero" in cmdr_section
    assert "1 Tymna the Weaver" in cmdr_section
    mtgo_count = deck_exporter.parse_export_card_count(mtgo, "mtgo")
    assert mtgo_count == 100, f"Partner MTGO export had {mtgo_count} cards, expected 100"

    # 4. Plain Text Format
    text_out = deck_exporter.export_to_text(deck)
    assert "1 Thrasios, Triton Hero" in text_out
    assert "1 Tymna the Weaver" in text_out
    text_count = deck_exporter.parse_export_card_count(text_out, "text")
    assert text_count == 100, f"Partner Text export had {text_count} cards, expected 100"

    # 5. CSV Export
    csv_out = deck_exporter.export_to_csv(deck)
    csv_count = deck_exporter.parse_export_card_count(csv_out, "csv")
    assert csv_count == 100, f"Partner CSV export had {csv_count} cards, expected 100"

    reader = csv.DictReader(io.StringIO(csv_out))
    rows = list(reader)
    cmdr_rows = [r for r in rows if r["Category"] == "Commander"]
    assert len(cmdr_rows) == 2
    cmdr_names = {r["Name"] for r in cmdr_rows}
    assert cmdr_names == {"Thrasios, Triton Hero", "Tymna the Weaver"}


def test_export_edge_cases_and_adversarial_inputs():
    """Popperian stress test: boundary cases, special characters, and missing fields."""
    mock_deck = {
        "commanders": [
            {
                "name": "Kozilek, the Great Distortion",
                "cmc": 10.0,
                "type_line": "Legendary Creature — Eldrazi",
            }
        ],
        "categories": {
            "commander": [
                {
                    "name": "Kozilek, the Great Distortion",
                    "cmc": 10.0,
                    "type_line": "Legendary Creature — Eldrazi",
                }
            ],
            "ramp": [
                {"name": "Sol Ring", "cmc": 1, "type_line": "Artifact"},
                {"name": "Mana Crypt", "cmc": 0, "type_line": "Artifact"},
            ],
            "lands": [
                {"name": "Wastes", "cmc": 0, "type_line": "Basic Land"},
                {"name": "Wastes", "cmc": 0, "type_line": "Basic Land"},
                {"name": "Wastes", "cmc": 0, "type_line": "Basic Land"},
            ]
        }
    }

    # Moxfield check
    mox = deck_exporter.export_to_moxfield(mock_deck)
    assert "1 Kozilek, the Great Distortion *CMDR*" in mox
    assert "3 Wastes" in mox
    assert deck_exporter.parse_export_card_count(mox, "moxfield") == 6

    # Archidekt check
    archi = deck_exporter.export_to_archidekt(mock_deck)
    assert "1x Kozilek, the Great Distortion *CMDR* [Commander]" in archi
    assert "3x Wastes [Lands]" in archi
    assert deck_exporter.parse_export_card_count(archi, "archidekt") == 6

    # CSV comma escaping check: "Kozilek, the Great Distortion" has a comma in the name
    csv_out = deck_exporter.export_to_csv(mock_deck)
    reader = csv.DictReader(io.StringIO(csv_out))
    rows = list(reader)
    assert len(rows) == 4  # 1 cmdr + 2 ramp + 1 grouped wastes
    assert rows[0]["Name"] == "Kozilek, the Great Distortion"
    assert rows[0]["CMC"] == "10"
    assert rows[3]["Name"] == "Wastes"
    assert rows[3]["Count"] == "3"

    # Empty categories test
    empty_deck = {"commanders": [], "categories": {}}
    assert deck_exporter.export_to_moxfield(empty_deck) == ""
    assert deck_exporter.export_to_archidekt(empty_deck) == ""
    assert deck_exporter.export_to_mtgo(empty_deck) == "// Commander\n// Mainboard"
