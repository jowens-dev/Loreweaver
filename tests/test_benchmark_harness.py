"""Unit tests for the benchmark evaluation harness and baseline engines."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import db  # noqa: E402
from evaluate_engine import (  # noqa: E402
    GOLDEN_DIR,
    load_decklist,
    load_ground_truth,
    run_baseline_0,
    run_baseline_1,
    run_hybrid_option_4,
    compute_metrics,
    verify_thresholds,
    run_belbe_specific_acceptance_tests,
)


def test_golden_decks_exist_and_have_100_cards():
    conn = db.get_connection()
    decks = ["belbe", "prosper", "veyran", "teysa", "brago", "sythis", "aesi"]

    for d in decks:
        deck_path = GOLDEN_DIR / f"{d}.txt"
        truth_path = GOLDEN_DIR / f"{d}_truth.json"
        assert deck_path.exists(), f"Missing decklist: {deck_path}"
        assert truth_path.exists(), f"Missing ground truth: {truth_path}"

        commander, mainboard = load_decklist(deck_path, conn)
        assert commander is not None, f"No commander found in {d}"
        assert len(mainboard) == 99, f"Deck {d} has {len(mainboard)} cards in mainboard, expected 99"

    conn.close()


def test_baseline_0_fails_safety_on_belbe():
    conn = db.get_connection()
    commander, deck = load_decklist(GOLDEN_DIR / "belbe.txt", conn)
    truth = load_ground_truth(GOLDEN_DIR / "belbe_truth.json")

    res = run_baseline_0(commander, deck)
    metrics = compute_metrics(res["cuts"], truth, res["stages_recognized"], res["latency"], res["cost"])
    verdict = verify_thresholds(metrics)

    # Baseline 0 must fail on safety (FCR > 0)
    assert metrics["false_cut_rate"] > 0.0
    assert not verdict["all_passed"]
    conn.close()


def test_option_4_passes_all_acceptance_thresholds_on_belbe():
    conn = db.get_connection()
    commander, deck = load_decklist(GOLDEN_DIR / "belbe.txt", conn)
    truth = load_ground_truth(GOLDEN_DIR / "belbe_truth.json")

    res = run_hybrid_option_4(commander, deck, conn)
    metrics = compute_metrics(res["cuts"], truth, res["stages_recognized"], res["latency"], res["cost"])
    verdict = verify_thresholds(metrics)

    assert verdict["all_passed"], f"Option 4 failed thresholds on Belbe: {metrics}"
    assert metrics["false_cut_rate"] == 0.0
    assert metrics["precision_at_5"] >= 60.0
    assert metrics["chain_recall"] == 100.0

    # Section 5 Specific Checks
    belbe_checks = run_belbe_specific_acceptance_tests(res["cuts"])
    assert belbe_checks["cut_triskaidekaphobia"]
    assert belbe_checks["cut_deathrite_shaman"]
    assert belbe_checks["cut_llanowar_elves"]
    assert belbe_checks["cut_chromatic_orrery"]
    assert belbe_checks["protect_portal_to_phyrexia"]
    assert belbe_checks["reject_karn_legacy_reforged"]
    conn.close()
