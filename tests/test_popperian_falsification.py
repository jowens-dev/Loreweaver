"""Popperian Adversarial Falsification Suite for Loreweaver.

Applies Karl Popper's principle of falsification across:
1. Vector A: Belbe Engine Refutation (Pingers + Flash + Big Colorless Payoffs)
2. Vector B: Quantitative Breaking Points (Bracket 1 vs Bracket 5 Power Compression)
3. Vector C: Zero Banned Cards Invariant (Format Legality)
4. Vector D: Reductio ad Absurdum & Color Bounds (Colorless, Mono, Wedge, 5-Color)
5. Vector E: Strict 100-Card Invariant
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
import deck_builder
import hybrid_engine

BANNED_CARDS = {
    "mana crypt", "jeweled lotus", "dockside extortionist", "nadu, winged wisdom",
    "golos, tireless pilgrim", "hullbreacher", "leovold, emissary of trest",
    "flash", "paradox engine", "prophet of kruphix", "primeval titan", "emrakul, the aeons torn",
    "black lotus", "mox pearl", "mox sapphire", "mox jet", "mox ruby", "mox emerald"
}


def test_falsification_vector_a_belbe_engine():
    """Refutation Test: Belbe MUST assemble pingers, flash, and big colorless threats."""
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Belbe, Corrupted Observer",
        deck_idea="deal damage to all players on every turn to play huge colorless spells with flash",
        bracket=4,
        budget="unlimited",
        preferred_win_con="combat"
    )
    conn.close()

    assert deck["total_cards"] == 100
    all_cards = [deck["commander"]] + list(deck["categories"]["ramp"]) + list(deck["categories"]["draw"]) + \
                list(deck["categories"]["removal"]) + list(deck["categories"]["win_con"]) + \
                list(deck["categories"]["synergy"]) + list(deck["categories"]["lands"])
    assert len(all_cards) == 100

    all_names = {c["name"].lower() for c in all_cards}

    # Must contain 0 format-banned cards
    banned_present = all_names.intersection(BANNED_CARDS)
    assert not banned_present, f"Falsification: Banned cards found in Belbe deck: {banned_present}"

    # 1. Pinger/Bleeder check
    has_pinger = any(
        "each opponent loses" in (c.get("oracle_text") or "").lower() or
        "damage to each opponent" in (c.get("oracle_text") or "").lower() or
        "each player loses" in (c.get("oracle_text") or "").lower() or
        "attacks, each opponent loses" in (c.get("oracle_text") or "").lower() or
        "becomes tapped, each opponent" in (c.get("oracle_text") or "").lower()
        for c in all_cards
    )
    assert has_pinger, "Falsification: Belbe deck lacks symmetric pingers/bleeders!"

    # 2. Flash enabler check
    has_flash = any(
        "as though they had flash" in (c.get("oracle_text") or "").lower() or
        "flash" in [kw.lower() for kw in c.get("keywords", [])]
        for c in all_cards if c.get("name") != "Belbe, Corrupted Observer"
    )
    assert has_flash, "Falsification: Belbe deck lacks flash timing enablers!"

    # 3. Big Colorless Bomb check (CMC >= 6)
    has_big_bomb = any(
        (c.get("cmc") or 0) >= 6 and ("artifact" in c.get("types", []) or not c.get("color_identity") or "eldrazi" in c.get("subtypes", []))
        for c in all_cards
    )
    assert has_big_bomb, "Falsification: Belbe deck lacks high-CMC colorless bombs!"


def test_falsification_vector_b_bracket_polarity():
    """Probe quantitative breaking points: Bracket 1 vs Bracket 5."""
    conn = db.get_connection()

    # Bracket 1: Casual/Jank
    b1_deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Sythis, Harvest's Hand",
        deck_idea="casual enchantments",
        bracket=1,
        budget="budget"
    )
    assert b1_deck["total_cards"] == 100
    assert len(b1_deck["categories"]["lands"]) == 38
    b1_names = {c["name"].lower() for group in b1_deck["categories"].values() for c in group}
    assert "sol ring" not in b1_names, "Falsification: Sol Ring leaked into Bracket 1!"
    assert "demonic tutor" not in b1_names

    # Bracket 5: cEDH Metagame
    b5_deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Talion, the Kindly Lord",
        deck_idea="cedh tournament combo",
        bracket=5,
        budget="unlimited",
        preferred_win_con="combo"
    )
    conn.close()

    assert b5_deck["total_cards"] == 100
    assert len(b5_deck["categories"]["lands"]) == 28
    assert b5_deck["stats"]["avg_cmc"] < 2.0, f"Falsification: cEDH curve too slow ({b5_deck['stats']['avg_cmc']})"

    b5_names = {c["name"].lower() for group in b5_deck["categories"].values() for c in group}
    assert "mox diamond" in b5_names
    assert "chrome mox" in b5_names
    assert "force of will" in b5_names
    assert "thassa's oracle" in b5_names


def test_falsification_vector_c_colorless_extremes():
    """Reductio ad Absurdum: Colorless Commander (Kozilek)."""
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Kozilek, the Great Distortion",
        deck_idea="colorless ramp and eldrazi",
        bracket=3,
        budget="moderate"
    )
    conn.close()

    assert deck["total_cards"] == 100
    all_cards = [deck["commander"]] + list(deck["categories"]["ramp"]) + list(deck["categories"]["draw"]) + \
                list(deck["categories"]["removal"]) + list(deck["categories"]["win_con"]) + \
                list(deck["categories"]["synergy"]) + list(deck["categories"]["lands"])
    
    # Invariant: ZERO colored pips in any card
    for c in all_cards:
        assert c.get("color_identity") == [], f"Falsification: Colored card {c['name']} in colorless Kozilek deck!"


def test_falsification_vector_d_5color_kenrith():
    """Boundary test: 5-color commander (Kenrith)."""
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Kenrith, the Returned King",
        deck_idea="5-color political reanimator",
        bracket=3,
        budget="moderate"
    )
    conn.close()

    assert deck["total_cards"] == 100
    assert len(deck["categories"]["lands"]) == 35


def test_falsification_vector_e_zero_banned_leakage():
    """Global Invariant: Banned cards must NEVER appear across any generated deck."""
    conn = db.get_connection()
    commanders = [
        ("Atraxa, Praetors' Voice", 4),
        ("Prosper, Tome-Bound", 3),
        ("Yuriko, the Tiger's Shadow", 4),
        ("Krenko, Mob Boss", 2),
        ("Urza, Lord High Artificer", 5)
    ]
    for cmd_name, b_tier in commanders:
        deck = deck_builder.build_deck(
            conn=conn,
            commander_name=cmd_name,
            bracket=b_tier,
            budget="unlimited"
        )
        assert deck["total_cards"] == 100, f"Deck for {cmd_name} size is {deck['total_cards']}, expected 100"
        all_names = {c["name"].lower() for group in deck["categories"].values() for c in group}
        leakage = all_names.intersection(BANNED_CARDS)
        assert not leakage, f"Banned cards {leakage} found in {cmd_name} bracket {b_tier}!"
    conn.close()


def test_falsification_vector_f_banned_commanders_rejected():
    """Adversarial check: Banned commanders MUST raise ValueError and never build decks."""
    conn = db.get_connection()
    banned_commanders = [
        "Golos, Tireless Pilgrim",
        "Nadu, Winged Wisdom",
        "Leovold, Emissary of Trest",
        "Rofellos, Llanowar Emissary",
        "Iona, Shield of Emeria",
        "Griselbrand"
    ]
    for b_cmd in banned_commanders:
        with pytest.raises(ValueError, match="tournament-legal"):
            deck_builder.build_deck(conn=conn, commander_name=b_cmd, bracket=3)

    # Autocomplete and search must also never return them
    for b_cmd in banned_commanders:
        results = db.search_cards_predictive(conn, b_cmd, commanders_only=True)
        assert len(results) == 0, f"Banned commander {b_cmd} returned by predictive search!"
    conn.close()


def test_falsification_vector_g_combos_and_fast_mana_barred_from_bracket_1_and_2():
    """Adversarial check: Brackets 1 and 2 must NEVER contain infinite combos or fast mana."""
    conn = db.get_connection()
    b1_deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Belbe, Corrupted Observer",
        bracket=1,
        preferred_win_con="combo"  # Attacker requests combo in bracket 1
    )
    b1_names = {c["name"].lower() for group in b1_deck["categories"].values() for c in group}
    disallowed = {
        "thassa's oracle", "demonic consultation", "underworld breach", "lion's eye diamond",
        "dualcaster mage", "twinflame", "heliod, sun-crowned", "walking ballista",
        "exquisite blood", "sanguine bond", "kiki-jiki, mirror breaker", "zealous conscripts"
    }
    assert not b1_names.intersection(disallowed), f"Disallowed combo cards in Bracket 1: {b1_names.intersection(disallowed)}"
    assert not b1_names.intersection(deck_builder.FAST_MANA_CARDS), "Fast mana in Bracket 1!"

    # Bracket 3 must disallow 2-card compact loops
    b3_deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Talion, the Kindly Lord",
        bracket=3,
        preferred_win_con="combo"
    )
    b3_names = {c["name"].lower() for group in b3_deck["categories"].values() for c in group}
    assert "thassa's oracle" not in b3_names, "Thassa's Oracle 2-card combo leaked into Bracket 3!"
    assert "demonic consultation" not in b3_names, "Demonic Consultation leaked into Bracket 3!"
    conn.close()


def test_falsification_vector_h_partner_commanders_thrasios_tymna():
    """Adversarial check: MTG Rule 903.3a Partner Pairings (2 commanders + 98 = 100)."""
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Thrasios, Triton Hero / Tymna the Weaver",
        bracket=5,
        budget="unlimited",
        preferred_win_con="combo"
    )
    conn.close()

    assert deck["total_cards"] == 100
    assert len(deck["commanders"]) == 2
    # Combined 4-color identity: WUBG
    assert set(deck["commander"]["color_identity"]).union(deck["commanders"][1]["color_identity"]) == {"W", "U", "B", "G"}
    # 28 lands + 70 nonlands + 2 commanders = 100
    assert len(deck["categories"]["lands"]) == 28
    nonlands = sum(len(v) for k, v in deck["categories"].items() if k not in {"lands", "commander"})
    assert nonlands == 70
    assert len(deck["categories"]["commander"]) == 2


def test_falsification_vector_i_multivariate_sampling_stress():
    """Run sampling across diverse color identities and brackets to prove universal invariants."""
    conn = db.get_connection()
    sample_targets = [
        ("Kozilek, the Great Distortion", 2),
        ("Krenko, Mob Boss", 1),
        ("Lathril, Blade of the Elves", 3),
        ("Sythis, Harvest's Hand", 4),
        ("Atraxa, Praetors' Voice", 5),
        ("Kenrith, the Returned King", 4),
        ("The Ur-Dragon", 3),
        ("Yuriko, the Tiger's Shadow", 4),
        ("Talion, the Kindly Lord", 5),
        ("Edgar Markov", 3)
    ]
    for cmd, brk in sample_targets:
        deck = deck_builder.build_deck(conn=conn, commander_name=cmd, bracket=brk)
        assert deck["total_cards"] == 100, f"Deck for {cmd} (bracket {brk}) size is {deck['total_cards']}"
        # Unique non-basics
        all_cards = deck["commanders"] + list(deck["categories"]["ramp"]) + list(deck["categories"]["draw"]) + \
                    list(deck["categories"]["removal"]) + list(deck["categories"]["win_con"]) + \
                    list(deck["categories"]["synergy"]) + list(deck["categories"]["lands"])
        non_basics = [c["name"].lower() for c in all_cards if c["name"] not in {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}]
        assert len(non_basics) == len(set(non_basics)), f"Duplicate non-basic found in {cmd} (bracket {brk})"
    conn.close()

