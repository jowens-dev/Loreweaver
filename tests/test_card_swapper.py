"""Unit, regression, and Popperian adversarial verification tests for the Card Swapper engine."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from api import app  # noqa: E402
import card_swapper  # noqa: E402
import db  # noqa: E402


client = TestClient(app)


def test_swap_candidates_endpoint_structure():
    """Verify endpoint response contract and presence of all required fields."""
    response = client.get("/api/swap-candidates", params={
        "card_name": "Arcane Signet",
        "commander": "Belbe, Corrupted Observer",
        "category": "ramp",
        "bracket": 3,
        "limit": 6
    })

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert len(data) <= 6

    required_keys = {"name", "mana_cost", "cmc", "type_line", "oracle_text", "image_url", "reason"}
    for card in data:
        assert required_keys.issubset(card.keys())
        assert isinstance(card["name"], str) and len(card["name"]) > 0
        assert isinstance(card["cmc"], (int, float))
        assert isinstance(card["type_line"], str)
        assert isinstance(card["reason"], str) and len(card["reason"]) > 0
        # Replaced card must never be suggested
        assert card["name"].lower() != "arcane signet"


def test_color_identity_enforcement():
    """Ensure candidate cards strictly respect single, multi, and partner color identities."""
    conn = db.get_connection()

    # 1. Mono-Green Commander: Omnath, Locus of Mana
    omnath_cands = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Cultivate",
        commander_name="Omnath, Locus of Mana",
        category="ramp",
        bracket=3,
        limit=10
    )
    assert len(omnath_cands) > 0
    for c in omnath_cands:
        card_row = db.get_card_by_name(conn, c["name"])
        assert card_row is not None
        assert set(card_row["color_identity"]).issubset({"G"})

    # 2. Golgari Commander: Belbe, Corrupted Observer
    belbe_cands = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Go for the Throat",
        commander_name="Belbe, Corrupted Observer",
        category="removal",
        bracket=3,
        limit=10
    )
    assert len(belbe_cands) > 0
    for c in belbe_cands:
        card_row = db.get_card_by_name(conn, c["name"])
        assert card_row is not None
        assert set(card_row["color_identity"]).issubset({"B", "G"})

    # 3. 4-Color Partner Commanders: Thrasios (GU) + Tymna (WB) -> {G, U, W, B}
    partner_cands = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Swords to Plowshares",
        commander_name="Thrasios, Triton Hero / Tymna the Weaver",
        category="removal",
        bracket=4,
        limit=10
    )
    assert len(partner_cands) > 0
    for c in partner_cands:
        card_row = db.get_card_by_name(conn, c["name"])
        assert card_row is not None
        assert set(card_row["color_identity"]).issubset({"G", "U", "W", "B"})
        # Must not contain Red
        assert "R" not in card_row["color_identity"]

    # 4. Colorless Commander: Kozilek, the Great Distortion
    colorless_cands = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Worn Powerstone",
        commander_name="Kozilek, the Great Distortion",
        category="ramp",
        bracket=3,
        limit=10
    )
    assert len(colorless_cands) > 0
    for c in colorless_cands:
        card_row = db.get_card_by_name(conn, c["name"])
        assert card_row is not None
        assert len(card_row["color_identity"]) == 0

    conn.close()


def test_exclusion_list_and_zero_duplicates():
    """Verify that excluded cards (including cards with commas) are completely omitted."""
    excluded = [
        "Elvish Archdruid",
        "Marwyn, the Nurturer",
        "Llanowar Elves",
        "Sol Ring"
    ]

    response = client.get("/api/swap-candidates", params={
        "card_name": "Arcane Signet",
        "commander": "Belbe, Corrupted Observer",
        "category": "ramp",
        "bracket": 3,
        "exclude": excluded,
        "limit": 10
    })

    assert response.status_code == 200
    candidates = response.json()
    names = [c["name"].lower() for c in candidates]

    for ex in excluded:
        assert ex.lower() not in names, f"Excluded card '{ex}' was returned in candidates"

    # Also ensure commander cannot be returned as a 99 swap candidate
    assert "belbe, corrupted observer" not in names
    # And replaced card cannot be returned
    assert "arcane signet" not in names


def test_format_banned_cards_excluded():
    """Verify that format-banned cards (Mana Crypt, Jeweled Lotus, Dockside, etc.) are never returned."""
    conn = db.get_connection()
    all_roles = ["ramp", "draw", "removal", "win_con", "synergy", "lands"]

    for role in all_roles:
        cands = card_swapper.get_swap_candidates(
            conn=conn,
            card_name="Sol Ring",
            commander_name="Kenrith, the Returned King",  # 5-color commander
            category=role,
            bracket=5,  # even in max cEDH bracket, format-banned cards must be illegal
            limit=25
        )
        returned_names = {c["name"].lower() for c in cands}
        for banned in card_swapper.FORMAT_BANNED_CARDS:
            assert banned not in returned_names, f"Banned card '{banned}' was returned in {role} candidates"

    conn.close()


def test_bracket_restrictions():
    """Verify that fast mana, cheap tutors, and infinite combos are excluded in lower brackets."""
    conn = db.get_connection()

    # 1. Bracket 1: No Sol Ring, no fast mana, no cheap tutors, no infinite combos
    b1_ramp = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Mind Stone",
        commander_name="Kenrith, the Returned King",
        category="ramp",
        bracket=1,
        limit=30
    )
    b1_names = {c["name"].lower() for c in b1_ramp}
    assert "sol ring" not in b1_names
    assert "mana vault" not in b1_names
    assert "grim monolith" not in b1_names
    assert "mox diamond" not in b1_names

    # 2. Bracket 2: Sol Ring allowed, but no fast mana or cheap tutors
    b2_ramp = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Mind Stone",
        commander_name="Kenrith, the Returned King",
        category="ramp",
        bracket=2,
        limit=30
    )
    b2_names = {c["name"].lower() for c in b2_ramp}
    assert "mana vault" not in b2_names
    assert "grim monolith" not in b2_names

    # 3. Bracket 2 combos disallowed
    b2_combos = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Craterhoof Behemoth",
        commander_name="Kenrith, the Returned King",
        category="win_con",
        bracket=2,
        limit=30
    )
    b2_combo_names = {c["name"].lower() for c in b2_combos}
    assert "thassa's oracle" not in b2_combo_names
    assert "twinflame" not in b2_combo_names
    assert "dualcaster mage" not in b2_combo_names
    assert "walking ballista" not in b2_combo_names

    conn.close()


def test_operational_lane_integrity():
    """Verify that candidates for each operational role strictly match that role."""
    conn = db.get_connection()

    # Lands must be lands
    lands = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Forest",
        commander_name="Belbe, Corrupted Observer",
        category="lands",
        bracket=3,
        limit=8
    )
    for l in lands:
        assert "land" in l["type_line"].lower()

    # Removal must be non-land removal
    removal = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Infernal Grasp",
        commander_name="Belbe, Corrupted Observer",
        category="removal",
        bracket=3,
        limit=8
    )
    for r in removal:
        assert "land" not in r["type_line"].lower()

    # Draw must be non-land card draw
    draw = card_swapper.get_swap_candidates(
        conn=conn,
        card_name="Read the Bones",
        commander_name="Belbe, Corrupted Observer",
        category="draw",
        bracket=3,
        limit=8
    )
    for d in draw:
        assert "land" not in d["type_line"].lower()

    conn.close()
