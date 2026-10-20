# Evaluation Plan: Loreweaver MTG Deck Analyzer

**Document:** Evaluation Framework & Benchmark Design (Phase 2)  
**Status:** Ready to Implement  
**Principle:** Defined Before Implementation; Clear Pass/Fail Thresholds; Anti-Circular Validation  

---

## 1. Executive Summary & Epistemic Guardrails

Loreweaver's core value proposition is to judge whether a card earns its slot based on how it actually plays in context with the other cards in the deck, rather than evaluating cards in isolation or relying on raw popularity metrics. Currently, the system has no objective definition of "correct."

To ensure engineering rigor, this evaluation plan establishes:
1. **A Tripartite Golden Benchmark Set:** Including the recorded Belbe case study, an independently audited second deck, and a blind, held-out evaluation set.
2. **Standardized Quantitative Metrics:** Evaluating precision, chain recall, stability, false-cut rates, latency, and cost.
3. **Comparative Baselines:** Benchmarking against the current regex heuristics, a naive non-LLM frequency baseline, and an unconstrained one-shot LLM baseline.
4. **Pre-Registered Pass/Fail Thresholds:** Defining explicit acceptance criteria *before* any implementation or model tuning begins.

> **CRITICAL EPISTEMIC CAUTION (Anti-Circularity Rule):**  
> The recorded manual decisions for *Belbe, Corrupted Observer* originated from an earlier exploratory run of this same two-tier architecture. Agreement with those decisions demonstrates **model consistency**, not objective **ground-truth correctness**. Under no circumstances may the Belbe deck be used as the sole validation gate. True correctness requires independent human expert validation conducted blind to model outputs.

---

## 2. Benchmark Deck Sets

```
+---------------------------------------------------------------------------------------------------+
|                                  TRIPARTITE EVALUATION DATASETS                                   |
+---------------------------------------------------------------------------------------------------+

  [ 1. CALIBRATION DECK ]             [ 2. INDEPENDENT DECK ]            [ 3. HELD-OUT SUITE ]
  Belbe, Corrupted Observer           Prosper, Tome-Bound                5 Archetype-Diverse Decks
  (BG Colorless Big-Mana)             (BR Impulse/Treasure)              (Never Seen During Tuning)
  +--------------------------+        +--------------------------+       +--------------------------+
  | Prior decisions recorded |        | Pre-audited by owner     |       | Blind benchmark suite:   |
  | Used for consistency and |        | before seeing model run  |       | - Spellslinger (UR)      |
  | regression testing only  |        | Validates external       |       | - Aristocrats (WB)       |
  |                          |        | ground truth             |       | - Blink/ETB (WU)         |
  |                          |        |                          |       | - Enchantress (GW)       |
  |                          |        |                          |       | - Landfall (GU)          |
  +--------------------------+        +--------------------------+       +--------------------------+
```

### Dataset 1: Calibration Case (Belbe, Corrupted Observer)
* **Commander:** `Belbe, Corrupted Observer` ({B}{G})
* **Archetype:** Colorless Big-Mana Acceleration / Symmetric Burn Exploitation.
* **Core Engine:** Precombat damage to 3 opponents $\rightarrow$ Belbe generates $\{C\}\{C\}\{C\}\{C\}\{C\}\{C\}$ (6 colorless mana) in postcombat main phase $\rightarrow$ casts high-CMC colorless bombs on Turns 2–3.
* **Recorded Audit Decisions (Calibration Target):**
  1. **Cut `Triskaidekaphobia` ({3}{B}) $\rightarrow$ Add `Swiftfoot Boots` ({2}):**
     - *Rationale:* Triskaidekaphobia is an off-tempo 4-mana gimmick that does not trigger Belbe on entry. Swiftfoot Boots provides hexproof, protecting Belbe from removal, and haste, enabling pingers to attack immediately.
  2. **Cut `Deathrite Shaman` ({B/G}) $\rightarrow$ Add `Eternal Witness` ({1}{G}{G}):**
     - *Rationale:* Deathrite Shaman's damage trigger requires an instant/sorcery in an opponent's graveyard (unreliable on Turn 2). Eternal Witness provides essential recursion for high-value threats removed by opponents.
  3. **Cut `Conduit of Ruin` ({6}) $\rightarrow$ Add `Diabolic Tutor` ({2}{B}{B}) [FLAWED CALIBRATION CHECK]:**
     - *Special Epistemic Test:* Conduit of Ruin costs exactly {6} generic (paid entirely by Belbe's postcombat trigger) and tutors a high-CMC colorless creature to the top of the library. Diabolic Tutor costs {2}{B}{B}, requiring two colored mana pips that Belbe cannot produce. An engine that blindly recommends this swap without verifying colored mana pip availability fails engine calibration.
  4. **Cut `Llanowar Elves` ({G}):**
     - *Rationale:* Fragile 1-mana dork that dies to the deck's 4 creature sweepers; redundant when Belbe accelerates from 2 mana straight to 8 mana.
  5. **Cut `Chromatic Orrery` ({7}):**
     - *Rationale:* Redundant, non-disruptive ramp that costs 7 mana without impacting the board or pressuring opponents.
  6. **Retain `Portal to Phyrexia` ({9}):**
     - *Rationale:* Primary win-condition / board-breaking bomb castable on Turn 3 via Belbe's mana engine.
  7. **Reject Addition of `Karn, Legacy Reforged` ({5}):**
     - *Rationale:* Adds mana during upkeep (which empties before the main phase), restricts mana to artifact spells only, and represents redundant mana production.

### Dataset 2: Independent Ground-Truth Deck (Prosper, Tome-Bound)
* **Specification Protocol:** To eliminate circularity, the product owner must select and audit a second deck **prior to viewing any system output**:
  - **Commander:** `Prosper, Tome-Bound` ({1}{B}{R})
  - **Archetype:** Exile-Cast / Treasure Synergies.
  - **Protocol:** The owner lists:
    1. Top 5 load-bearing engine cards that must **never** be cut (e.g. *Birgi, God of Storytelling*, *Academy Manufactor*, *Passionate Archaeologist*, *Xorn*, *Marionette Master*).
    2. Exactly 3 cards designated as the weakest in-role slots that **should** be cut (e.g. off-theme generic burn or high-CMC non-impulse spells).
    3. Exactly 3 suggested replacement cards with explicit operational rationales.
  - This ground truth must be frozen in a signed JSON file (`analysis/ground_truth_prosper.json`) before running any test.

### Dataset 3: Held-Out Benchmark Suite (Blind Evaluation)
* **Purpose:** Measure generalization across archetypes never touched during heuristic design.
* **Composition:** 5 complete 100-card Commander decklists from distinct archetype families:
  1. **Spellslinger:** *Veyran, Voice of Duality* (UR)
  2. **Aristocrats:** *Teysa Karlov* (WB)
  3. **Blink / ETB:** *Brago, King Eternal* (WU)
  4. **Enchantress:** *Sythis, Harvest's Hand* (GW)
  5. **Landfall:** *Aesi, Tyrant of Gyre Strait* (GU)
* **Evaluation Criteria:** Pre-annotated by a panel of 3 experienced Commander players (Bracket 2–3 specialists) documenting load-bearing pillars, dead cards, and win-condition chains.

---

## 3. Quantitative Evaluation Metrics

```
                                  METRIC SUMMARY
  +----------------------------+-----------------------------------------------------------+
  | Metric                     | Formula / Definition                                      |
  +----------------------------+-----------------------------------------------------------+
  | Cut Precision@K (P@K)      | True Recommended Cuts / Total Cuts Suggested (K=5)        |
  | Cut Concordance (CC)       | Overlap with Expert-Approved Cut Candidates (%)           |
  | Chain Recall (CR)          | Identified Win/Resource Chains / Ground-Truth Chains (%)  |
  | False-Cut Rate (FCR)       | Core Load-Bearing Cards Flagged for Removal (%)           |
  | Run-to-Run Stability (RRS) | Jaccard Similarity of Verdicts across 5 Identical Runs     |
  | Latency per Analysis (LAT) | Wall-clock time from submission to verdict (seconds)      |
  | Cost per Analysis (CPA)    | External API costs per 100-card analysis ($ USD)          |
  +----------------------------+-----------------------------------------------------------+
```

### Metric 1: Cut Precision@K & Cut Concordance
* **Definition:** Measures whether cards recommended for removal are genuinely the weakest cards in their respective roles.
* **Formulas:**
  $$\text{Cut Precision@5} = \frac{\sum_{i=1}^{5} \mathbb{I}(\text{Card}_i \in \text{Expert Cut Set})}{5}$$
  $$\text{Cut Concordance} = \frac{|\text{Model Suggested Cuts} \cap \text{Expert Approved Cut Pool}|}{|\text{Model Suggested Cuts}|} \times 100\%$$

### Metric 2: Chain Recall (Engine Comprehension)
* **Definition:** Evaluates whether the analyzer identifies the deck's true primary resource engine and win paths (e.g. recognizing Belbe's "Precombat Damage $\rightarrow$ Postcombat Colorless Mana $\rightarrow$ High-CMC Artifact Bomb" sequence).
* **Measurement:** Binary verification across 3 standardized stages:
  - *Trigger/Enabler Recognition:* Did the engine identify the catalyst? (Yes/No)
  - *Converter/Generator Recognition:* Did the engine identify the resource transformation? (Yes/No)
  - *Payoff/Finisher Recognition:* Did the engine identify the win condition? (Yes/No)
  $$\text{Chain Recall} = \frac{\text{Stages Recognized}}{3} \times 100\%$$

### Metric 3: False-Cut Rate on Load-Bearing Cards (Safety)
* **Definition:** The percentage of designated "load-bearing engine pillars" mistakenly flagged as cuts or low-synergy dead weight.
  $$\text{False-Cut Rate} = \frac{|\text{Recommended Cuts} \cap \text{Load-Bearing Pillars}|}{|\text{Load-Bearing Pillars}|} \times 100\%$$
* *Requirement:* A false-cut rate on load-bearing pillars of $>0\%$ is a major defect. Flagging *Portal to Phyrexia* in Belbe or *Birgi* in Prosper is an instant failure.

### Metric 4: Run-to-Run Stability (Reproducibility)
* **Definition:** For non-deterministic models (LLMs), measures verdict consistency across repeated runs on the identical decklist.
  $$\text{Stability} = \frac{1}{\binom{N}{2}} \sum_{i < j} \frac{|C_i \cap C_j|}{|C_i \cup C_j|} \quad (\text{Jaccard index of cut sets across } N=5 \text{ runs})$$

### Metric 5: Latency & Cost per Analysis
* **Latency:** End-to-end wall-clock time from submission to rendered verdict.
* **Cost:** Total financial cost in LLM API tokens per 100-card deck evaluation.

---

## 4. Competitive Baselines

To prove that a new engine provides genuine mechanical comprehension rather than illusory intelligence, all candidates must be evaluated against three distinct baselines:

### Baseline 0: Current Loreweaver Heuristic Engine
* **Implementation:** The existing regex keyword counter (`scripts/recommend_deck.py` and `web/src/utils/themeEngine.js`).
* **Characteristics:** $0.00 token cost, 100% deterministic ($\text{RRS} = 1.0$), $<2\text{s}$ execution time.
* **Known Limitations:** Zero card-vs-card evaluation, blind to multi-card chains, penalizes efficient staples, zero awareness of resource flow.

### Baseline 1: Trivial Non-LLM Structural Baseline (EDHREC + Curve Quotas)
* **Implementation:** A simple Python script that:
  1. Queries EDHREC synergy percentages for the commander.
  2. Flags cards with $<10\%$ inclusion rates and CMC $>4$ as potential cuts.
  3. Enforces standard Frank Karsten mana curve ratios (37 lands, 10 ramp, 10 draw, 8 removal).
* **Cost:** \$0.00.
* **Purpose:** Proves whether an LLM or graph model outperforms basic statistical aggregation.

### Baseline 2: Unconstrained One-Shot LLM Baseline
* **Implementation:** A single prompt containing the entire 100-card decklist sent directly to GPT-4o or Claude 3.5 Sonnet:
  ```text
  You are an expert MTG Commander deckbuilder. Review this 100-card list for [Commander].
  List the 5 worst cards that should be cut, explain why in context, and suggest 5 replacements.
  ```
* **Cost:** ~\$0.02 – \$0.04 per call.
* **Known Failure Modes:** Hallucinates card text, overlooks subtle timing restrictions (CR 106.4, CR 605.5a), fails to count colored pips, suffers from context position bias (cutting cards listed at the bottom of the prompt).

---

## 5. Pre-Registered Pass/Fail Thresholds

To prevent moving goalposts after observing results, the following thresholds are pre-registered and locked:

| Metric | Target Standard | Minimum Passing Threshold | Failing Condition |
| :--- | :--- | :--- | :--- |
| **Cut Precision@5** | $\ge 80\%$ (4/5 agreed) | **$\ge 60\%$ (3/5 agreed)** | $< 60\%$ on any golden deck |
| **Cut Concordance** | $\ge 75\%$ overlap | **$\ge 60\%$ overlap** | $< 50\%$ overlap with expert pool |
| **Chain Recall** | $100\%$ (3/3 stages) | **$\ge 66.7\%$ (2/3 stages)** | $0\%$ (fails to identify core resource engine) |
| **False-Cut Rate** | $0.0\%$ (0 pillars cut) | **$\le 0.0\%$ (Strict Zero Tolerance)** | $\ge 1$ load-bearing card flagged for cut |
| **Run-to-Run Stability** | Jaccard $\ge 0.90$ | **Jaccard $\ge 0.80$** | Jaccard $< 0.70$ across 5 runs |
| **Latency** | $\le 5.0$ seconds | **$\le 15.0$ seconds** | $> 30.0$ seconds |
| **Cost per Analysis** | $\le \$0.05$ | **$\le \$0.15$** | $> \$0.50$ per analysis |

### Specific Acceptance Tests on Golden Set 1 (Belbe):
1. **Pass:** Recommends cutting *Triskaidekaphobia*; recommends adding *Swiftfoot Boots* with an explicit rationale citing protection for Belbe.
2. **Pass:** Identifies *Portal to Phyrexia* as a core payoff enabled by Belbe's postcombat mana; explicitly protects it from being cut.
3. **Pass:** Recommends cutting *Llanowar Elves* due to redundancy next to Belbe's 6-mana yield and vulnerability to the deck's sweepers.
4. **Pass:** Recommends cutting *Chromatic Orrery* as redundant mana generation.
5. **Pass:** Refuses to add *Karn, Legacy Reforged* due to upkeep mana emptying and artifact-only restrictions.
6. **Pass:** Explicitly flags the colored-mana pip limitation of *Diabolic Tutor* ({2}{B}{B}) versus *Conduit of Ruin* ({6}) when evaluating Belbe's colorless mana output.

---

## 6. Implementation Protocol

1. **Step 1: Freeze Golden Sets:** Commit `analysis/golden_decks/belbe.txt`, `analysis/golden_decks/prosper.txt`, and the 5 held-out decklists. Commit signed ground-truth JSON files.
2. **Step 2: Implement Test Harness:** Create `scripts/evaluate_engine.py` to execute evaluations across all baselines and candidates, logging token counts, latency, and metrics into a standardized CSV (`analysis/benchmark_results.csv`).
3. **Step 3: Run Baselines:** Execute Baseline 0 (current regex), Baseline 1 (EDHREC curve), and Baseline 2 (one-shot LLM) to establish empirical benchmarks.
4. **Step 4: Evaluate Candidate Options:** Test proposed remediations against the identical harness. Any candidate that fails the False-Cut Rate ($\le 0.0\%$) or Cost ($\le \$0.15$) threshold is disqualified.
