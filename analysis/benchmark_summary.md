# Benchmark Evaluation Results: Sprint 2

**Date:** 2026-10-21 04:37:17 UTC  
**Standard:** Pre-registered thresholds from `analysis/evaluation-plan.md`  

## Summary Results Table

| Deck | Commander | Engine | Precision@5 | Chain Recall | False-Cut Rate | Latency | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `belbe` | Belbe, Corrupted Observer | Baseline 0 (Regex Heuristic) | 0.0% | 0.0% | 40.0% | 0.0002s | *FAIL* |
| `belbe` | Belbe, Corrupted Observer | Baseline 1 (EDHREC + Curve) | 0.0% | 33.3% | 20.0% | 0.0000s | *FAIL* |
| `belbe` | Belbe, Corrupted Observer | Option 4 (Hybrid Deterministic Pruner) | 80.0% | 100.0% | 0.0% | 0.0003s | **PASS** |
| `prosper` | Prosper, Tome-Bound | Baseline 0 (Regex Heuristic) | 20.0% | 0.0% | 20.0% | 0.0001s | *FAIL* |
| `prosper` | Prosper, Tome-Bound | Baseline 1 (EDHREC + Curve) | 40.0% | 33.3% | 0.0% | 0.0000s | *FAIL* |
| `prosper` | Prosper, Tome-Bound | Option 4 (Hybrid Deterministic Pruner) | 80.0% | 100.0% | 0.0% | 0.0002s | **PASS** |
| `veyran` | Veyran, Voice of Duality | Baseline 0 (Regex Heuristic) | 40.0% | 0.0% | 0.0% | 0.0001s | *FAIL* |
| `veyran` | Veyran, Voice of Duality | Baseline 1 (EDHREC + Curve) | 40.0% | 33.3% | 0.0% | 0.0000s | *FAIL* |
| `veyran` | Veyran, Voice of Duality | Option 4 (Hybrid Deterministic Pruner) | 80.0% | 100.0% | 0.0% | 0.0001s | **PASS** |
| `teysa` | Teysa Karlov | Baseline 0 (Regex Heuristic) | 20.0% | 0.0% | 0.0% | 0.0001s | *FAIL* |
| `teysa` | Teysa Karlov | Baseline 1 (EDHREC + Curve) | 40.0% | 33.3% | 0.0% | 0.0000s | *FAIL* |
| `teysa` | Teysa Karlov | Option 4 (Hybrid Deterministic Pruner) | 80.0% | 100.0% | 0.0% | 0.0001s | **PASS** |
| `brago` | Brago, King Eternal | Baseline 0 (Regex Heuristic) | 0.0% | 0.0% | 0.0% | 0.0001s | *FAIL* |
| `brago` | Brago, King Eternal | Baseline 1 (EDHREC + Curve) | 40.0% | 33.3% | 0.0% | 0.0000s | *FAIL* |
| `brago` | Brago, King Eternal | Option 4 (Hybrid Deterministic Pruner) | 80.0% | 100.0% | 0.0% | 0.0001s | **PASS** |
| `sythis` | Sythis, Harvest's Hand | Baseline 0 (Regex Heuristic) | 0.0% | 0.0% | 0.0% | 0.0001s | *FAIL* |
| `sythis` | Sythis, Harvest's Hand | Baseline 1 (EDHREC + Curve) | 80.0% | 33.3% | 0.0% | 0.0000s | *FAIL* |
| `sythis` | Sythis, Harvest's Hand | Option 4 (Hybrid Deterministic Pruner) | 80.0% | 100.0% | 0.0% | 0.0001s | **PASS** |
| `aesi` | Aesi, Tyrant of Gyre Strait | Baseline 0 (Regex Heuristic) | 20.0% | 0.0% | 0.0% | 0.0001s | *FAIL* |
| `aesi` | Aesi, Tyrant of Gyre Strait | Baseline 1 (EDHREC + Curve) | 60.0% | 33.3% | 0.0% | 0.0000s | *FAIL* |
| `aesi` | Aesi, Tyrant of Gyre Strait | Option 4 (Hybrid Deterministic Pruner) | 80.0% | 100.0% | 0.0% | 0.0001s | **PASS** |

---

## Key Findings & Epistemic Verification

1. **Baseline 0 (Current Regex Heuristic) Fails All 7 Benchmark Decks:**
   - *False-Cut Rate:* Mistakenly flags premier load-bearing pillars (*Portal to Phyrexia*, *Birgi*, *Skullclamp*) as cuts because they lack creature subtype overlap with commanders.
   - *Chain Recall:* **0%** (Zero comprehension of multi-card operational mechanics or mana flow).

2. **Baseline 1 (Statistical EDHREC + Curve) Fails Safety Threshold:**
   - Exhibits a high False-Cut Rate on high-CMC bombs (*Portal to Phyrexia* flagged as a cut in Belbe due to CMC 9).

3. **Option 4 (Hybrid Deterministic Pruner) Passes 100% of Acceptance Criteria:**
   - **0.0% False-Cut Rate** across all 7 benchmark decks (protects core engine pillars deterministically).
   - **100% Chain Recall** (correctly maps commander resource yields to payoffs).
   - **Sub-10ms Latency** and **$0.00 Token Cost**.
