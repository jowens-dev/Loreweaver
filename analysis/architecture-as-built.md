# Architecture As-Built: Loreweaver MTG Deck Analyzer

**Target Repository:** `/Users/yella4jella/workspace/Loreweaver`  
**Date of Audit:** October 19, 2026  
**Auditor Classification:** Primary Auditor & Adversarial Review Team  
**Status:** Complete Forensic Reconnaissance  

---

## 1. Discrepancies Against Brief (Finding #1: Product Intent vs. Code Reality)

> **EPISTEMIC RULE:** *The mission brief was written from the owner's notes, not from the code. If code contradicts it, that is finding #1; report it before anything else.*

A comprehensive, line-by-line inspection of the Loreweaver repository reveals that the architecture described in the owner's notes diverges fundamentally from the software actually built. Below is the direct comparison between product intent and the code as it exists:

| Dimension | Owner's Notes / Brief Specification | Reality in Codebase (As-Built) | Status & Evidence |
| :--- | :--- | :--- | :--- |
| **Tier 2 LLM Engine** | "Tier 2 (LLM): synergy and cut-quality judgment... All judgment lives here." | **Zero LLM integration exists.** There are no LLM API clients (`openai`, `anthropic`, `gemini`, `langchain`, etc.), no prompt templates, and no model calls anywhere in the repo or its git history. | **VERIFIED**<br>`grep -r` across repo; `git log -S "openai" -S "prompt"`; `requirements.txt:1-2` |
| **Backend Architecture** | "FastAPI backend... wire oracle text into tier-2 prompt." | **`api.py` is an unintegrated 21-line mock stub.** It exposes a single endpoint `/api/recommendations` that returns 3 hardcoded cards (`Blood Artist`, `Viscera Seer`, `Spice Engine`) with a TODO comment. It performs no deck analysis and does not connect to the analysis engine. | **VERIFIED**<br>`api.py:1-21` |
| **Database & Ingestion** | "Scryfall Oracle Cards bulk file ingested by `ingest.py` into SQLite." | **No SQLite database or `ingest.py` exists.** Ingestion script `ingest.py` is absent. `recommend_deck.py` loads an unindexed 179.4 MB JSON file (`scripts/oracle-cards.json`) directly into RAM using `json.load()`. | **VERIFIED**<br>`scripts/recommend_deck.py:91-163`; `find . -name "ingest.py"` returns 0 results |
| **Analysis Execution Location** | Backend service processing deck lists and evaluating synergies. | **100% Client-Side In-Browser Execution.** All deck parsing, Scryfall metadata fetching, cohesion scoring, stress testing, and bracket validation run inside the user's browser via React/JavaScript. | **VERIFIED**<br>`web/src/App.jsx:207-295`; `web/src/utils/themeEngine.js:1-380` |
| **Synergy Evaluation Premise** | "Evaluate each card against the other cards in the deck... decide whether a card earns its slot." | **Static Regex Keyword Matching.** The system never compares card A to card B. It counts keyword occurrences against the commander or fixed regex lists, computing simple scalar sums. | **VERIFIED**<br>`scripts/recommend_deck.py:300-345`; `web/src/utils/themeEngine.js:88-160` |
| **Hosting & Hardware** | "AWS EC2 t3.micro, us-east-1." | **Dual Deployment Found:** Frontend deployed on Vercel (`loreweaver-web` under team `Oracle Logic Studios`); backend targeted AWS EC2 `us-east-1` (`54.87.157.40`, key `loreweaver_app_key`), with DNS `api.lore-weaver.app` pointing to it. `t3.micro` (1 GB RAM) cannot execute the Python recommender: loading `oracle-cards.json` requires 1.31 GB of RAM, triggering the Linux kernel Out-Of-Memory (OOM) killer. | **VERIFIED**<br>`web/.vercel/project.json`; `dig api.lore-weaver.app`; `~/Documents/Keys/loreweaver_app_key.pem`; `resource.getrusage` benchmark = 1,312 MB RSS |
| **Taxonomy Constraint** | "Hard constraint: No hardcoded commander-archetype taxonomy." | **Multiple hardcoded taxonomies exist.** `map_32_deck_matrix.py` hardcodes 32 rigid guild/color philosophies; `recommend_deck.py` hardcodes 11 mechanical themes, 4 intent profiles, and 11 plane clashes. | **VERIFIED**<br>`scripts/map_32_deck_matrix.py:7-40`; `scripts/recommend_deck.py:613-649` |

---

## 2. System Architecture as Built

Loreweaver is currently split across three distinct, partially disconnected sub-systems:
1. **The Web Application (`web/`):** A client-side Single Page Application (SPA) built with React 19 and Vite 8 that directly queries the public Scryfall REST API and executes regex heuristics locally.
2. **The Python CLI & Desktop Engine (`scripts/`):** A standalone collection-filtering script (`recommend_deck.py`) and a legacy Tkinter desktop visualization script (`mana_curve.py`) packaged via PyInstaller (`Loreweaver.spec`).
3. **The FastAPI Stub (`api.py`):** An isolated 21-line mock service intended to serve recommendations to the web frontend but returning static placeholder data.

```
+---------------------------------------------------------------------------------------------------+
|                                  LOREWEAVER AS-BUILT TOPOLOGY                                     |
+---------------------------------------------------------------------------------------------------+

     [ BROWSER CLIENT (web/) ]
     +----------------------------------------------------------------------------------------+
     | React 19 / Vite 8 SPA (App.jsx)                                                       |
     |                                                                                        |
     |  [Input Tab]                                                                           |
     |       |                                                                                |
     |       v                                                                                |
     |  parseDecklistText() ---------------------------------------------------------------+  |
     |       |                                                                             |  |
     |       v                                                                             |  |
     |  fetchCardsMetadata() ===== HTTP POST (chunks of 75) ====> [ Public Scryfall API ]  |  |
     |       |                                                    api.scryfall.com        |  |
     |       v                                                    /cards/collection        |  |
     |  In-Memory JS Card DB <=============================================================+  |
     |       |                                                                                |
     |       +-------------------+--------------------+-------------------+                   |
     |       |                   |                    |                   |                   |
     |       v                   v                    v                   v                   |
     |  calculateCohesion()  analyzeStress()      detectBrokenChains() analyzeIntentional()   |
     |  (themeEngine.js)     (stressTester.js)    (spiceInjector.js)   (cfpRules.js)          |
     |       |                   |                    |                   |                   |
     |       v                   v                    v                   v                   |
     |  [Cohesion Tab]       [Stress Tab]         [Spice Tab]         [CFP Warnings]          |
     +----------------------------------------------------------------------------------------+
             |                                                |
             | (Builder Tab)                                  | (Spice Tab Recs)
             v                                                v
     HTTP GET /api/recommendations?commander=...       HTTP GET /api/recommendations?...
             |                                                |
             +-----------------------+------------------------+
                                     |
                                     v (HTTP localhost:8000)
                     +-------------------------------+
                     |   BACKEND STUB (api.py)       |
                     |   FastAPI / Uvicorn           |
                     |   Returns 3 Hardcoded Cards   |
                     |   (DISCONNECTED FROM SCRIPTS) |
                     +-------------------------------+
                                     x (NO CONNECTION)
                                     x
                     +-------------------------------+
                     |   PYTHON CLI (scripts/)       |
                     |   recommend_deck.py           |
                     |   mana_curve.py (Tkinter)     |
                     |   Loads 179MB JSON into RAM   |
                     |   Math/Hypergeometric metrics |
                     +-------------------------------+
```

---

## 3. Entry Points & Code Modules

### A. Web Application (`web/`)
* **`web/src/main.jsx`:** React application root; mounts `<App />` inside `#root` in `index.html`.
* **`web/src/App.jsx` (935 lines):** Primary application shell. Implements a 6-tab navigation bar (`Input`, `Cohesion`, `Stress`, `Spice`, `Builder`, `Legal`). Handles decklist pasting, orchestrates Scryfall API calls, executes analysis engines, and manages state.
* **`web/src/LoreweaverDashboard.jsx` (520 lines):** Alternative "Builder" interface embedded inside the 5th tab of `App.jsx`. Styled with Tailwind CSS, features swimlanes, suggested commanders, and calls `RECOMMENDATION_API_URL`.
* **`web/src/utils/themeEngine.js` (380 lines):** Client-side decklist text parser, 11 mechanical theme regex classifiers, dominant subtype/theme density calculator, Vorthos plane clash detector, and Intentional Experience (IX) bracket analyzer.
* **`web/src/utils/stressTester.js` (295 lines):** Multivariate hypergeometric consistency solver (`calculateJointConsistency`), permanent fragility indexer, multiplayer table-pressure indexer, and Commander Dependency Index (CDI) calculator.
* **`web/src/utils/spiceInjector.js` (160 lines):** Heuristic detector for broken theme chains (Token generators vs. payoffs, Counter generators vs. payoffs, Sacrifice fodder vs. outlets vs. payoffs). Calls Scryfall search API to suggest non-staple cards.
* **`web/src/utils/cfpRules.js` (75 lines):** Official Commander Format Panel (CFP) Game Changers list (40 cards), mass land denial regex, tutor regex, and extra turn regex.
* **`web/src/utils/scryfall.js` (85 lines):** Batching utility that splits card name lists into 75-card chunks and queries `https://api.scryfall.com/cards/collection` via HTTP POST.

### B. Backend Service (`api.py`)
* **`api.py` (21 lines):** Minimal FastAPI instance with wildcard CORS middleware (`allow_origins=["*"]`). Exposes a single GET endpoint `/api/recommendations` returning mock card dictionaries.

### C. Python Analytics Engine (`scripts/`)
* **`scripts/recommend_deck.py` (1,048 lines):** Standalone CLI script. Loads bulk Scryfall JSON (`oracle-cards.json`), parses owned collection CSV, filters by commander color identity, scores cards using the "Spice Weighting Algorithm", partitions into role slots (Lands, Ramp, Draw, Removal, Synergy), computes fragility, table pressure, and joint draw probabilities, and outputs a formatted text report.
* **`scripts/mana_curve.py` (720 lines):** Legacy desktop GUI built with Python `tkinter` and `ttk`. Renders mana curve bar charts, fragility ratings, and thematic cluster trees.
* **`scripts/math_utils.py` (75 lines):** Multivariate hypergeometric probability functions (`hypergeometric_pmf`, `hypergeometric_cdf_ge`, `calculate_joint_consistency`).
* **`scripts/Loreweaver.spec` (48 lines):** PyInstaller build specification bundling `mana_curve.py` with `oracle-cards.json` and assets into a standalone macOS desktop bundle (`Loreweaver.app`).
* **`scripts/tag_color_identity.py` (160 lines):** Helper script to tag an inventory CSV with Scryfall color identities via an optional SQLite database or HTTP API.
* **`scripts/build_gauntlet.py` (85 lines):** Filters tagged inventory CSVs by color identity and budget thresholds.
* **`scripts/find_commanders.py` (105 lines):** Scans inventory CSV against bulk oracle JSON to identify owned legendary creatures and count supported cards.
* **`scripts/map_32_deck_matrix.py` (120 lines):** Maps owned commanders to the 32 color-combination archetypes.

---

## 4. End-to-End Data Flows

### Flow A: Web Deck Analysis (Production Path)
1. **User Input (`web/src/App.jsx:385-450`):** The user enters a Commander name, selects an Intentional Experience target (e.g. "Aggro-Combat"), selects a target Power Bracket (1–5), pastes a plain-text decklist into a textarea, and clicks "Analyze Deck".
2. **Text Parsing (`web/src/utils/themeEngine.js:67-90`):** `parseDecklistText()` splits the raw string by newline, ignores lines starting with `//` or `#`, parses quantities via `^(\d+)\s+(.+)$`, strips parenthetical and bracketed set/collector codes via regex, and returns a flat array of card name strings.
3. **Commander Metadata Lookup (`web/src/App.jsx:212-240`):** The browser fires a GET request to `https://api.scryfall.com/cards/named?exact=${commanderName}`. If successful, extracts `type_line`, `types`, `subtypes`, `oracle_text`, and `color_identity`.
4. **Deck Metadata Batching (`web/src/utils/scryfall.js:10-75`):** `fetchCardsMetadata()` deduplicates card names, chunks them into batches of at most 75 identifiers, and sends HTTP POST requests to `https://api.scryfall.com/cards/collection`. Enforces a 600ms delay between batch requests. Constructs an in-memory dictionary mapping lowercase card names to card metadata objects.
5. **Heuristic Evaluation (`web/src/App.jsx:245-275`):**
   - `calculateCohesionScore()` counts creature subtypes and scans non-land cards against 11 hardcoded theme regexes, computing a 0–100 cohesion score.
   - `calculateFlavorProfile()` maps set codes to 9 planes and checks for forbidden plane clashes.
   - `analyzeIntentionalExperience()` scans for CFP Game Changers, mass land denial, tutors, extra turns, and finisher keywords.
   - `analyzeStress()` tallies permanent types, calculates fragility weights, evaluates Commander Dependency Index (CDI), and computes turn-6 joint draw consistency via hypergeometric distribution.
   - `detectBrokenChains()` evaluates ratio mismatches across Tokens, Counters, and Sacrifice roles.
6. **Presentation (`web/src/App.jsx:455-830`):** Updates React state (`results`, `analyzed = true`) and switches the view to the `Cohesion`, `Stress`, or `Spice` tab.

### Flow B: Web Recommendation (Builder / Spice Path)
1. **Trigger:** The user opens the "Builder" tab (`LoreweaverDashboard.jsx`) or the "Spice" tab in `App.jsx`, specifies a commander, and selects a spice level (0–100).
2. **HTTP Request:** The browser sends a GET request to `http://localhost:8000/api/recommendations?commander=${name}&spice=${level}`.
3. **Backend Execution:** `api.py` ignores all query parameters and immediately returns the hardcoded 3-card JSON payload.
4. **Rendering:** `mapRecommendationResponse()` sorts the 3 cards into swimlanes (`Blood Artist` -> Other/Synergy, `Viscera Seer` -> Other/Synergy, `Spice Engine` -> Other/Synergy).

### Flow C: Standalone Python Recommender (`scripts/recommend_deck.py`)
1. **Invocation:** CLI execution: `python3 scripts/recommend_deck.py --commander "Belbe, Corrupted Observer" --collection data/collection_tagged_bulk.csv`.
2. **Database Load:** `load_oracle_database()` reads `scripts/oracle-cards.json` (179.4 MB) into memory via `json.load()`, building a dictionary of 37,741 entries and computing subtype/keyword frequency tables.
3. **Collection Load:** `load_collection()` reads the CSV, resolves name and quantity columns, and builds a list of owned card strings.
4. **Color Filtering:** `generate_deck()` filters collection cards where `card_identity.issubset(comm_identity)`.
5. **Spice Scoring:** Scores every legal card via `calculate_spice_score() = synergy + scarcity + density`. Applies 2.0x multiplier for deep cuts, 3.0x for multiplayer scaling, and 1.5x for intent keywords.
6. **Slot Partitioning:** Sorts cards by score descending, then CMC ascending. Allocates 37 lands, 10 ramp, 10 draw, 8 removal, and 34 synergy spells using condition filters (`is_land`, `is_ramp`, etc.).
7. **Analytics Computation:** Calculates fragility rating, table pressure score, hypergeometric joint probability (Turn 6: 3 lands, 1 ramp, 1 draw), CFP bracket compliance, and finisher count.
8. **Output:** Formats and prints an ASCII summary report to stdout or writes to an output file.

---

## 5. Schemas & Data Stores

### Data Stores
1. **`scripts/oracle-cards.json` (179,395,992 bytes):**
   - Uncompressed JSON array containing 37,741 Scryfall card objects.
   - Includes full card records: names, mana costs, type lines, oracle texts, colors, color identities, reprint status, set types, keywords, and layouts.
   - *Data Hygiene Issue:* Contains 1,194 tokens, 80 double-faced tokens, 2,243 art series cards, 87 emblems, 207 planar cards, 107 vanguards, and 102 scheme cards.
2. **`data/collection_tagged_bulk.csv` (1,943 rows, 19 columns):**
   - TCGPlayer inventory export containing columns: `Product ID`, `TCGplayer Id`, `Product Name`, `Rarity`, `Condition`, `TCG Market Price`, `Total Quantity`, `Color Identity`.
3. **`data/intent_profile.json` (55 bytes):**
   - JSON config: `{"target_ix": "Aggro-Combat", "bracket_level": 2, "win_cons_needed": 3}`.
4. **`data/32_deck_matrix.csv` (208 rows):**
   - Pre-computed mapping of owned commanders across the 32 MTG color combinations.

---

## 6. Dependencies, Tooling, & Configuration

### Python Environment
* **Declared Dependencies (`requirements.txt`):**
  ```text
  fastapi==0.139.2
  uvicorn==0.51.0
  ```
* **Runtime Python Version:** Python 3.13.12 / 3.14.8.
* **Missing Tooling:** No `pytest` in `requirements.txt` or `.venv`; tests require external test runner invocation (`uv run --with pytest pytest tests/`).

### Node.js / Web Environment
* **Dependencies (`web/package.json`):**
  - Production: `react@^19.2.7`, `react-dom@^19.2.7`, `tailwindcss@^4.3.3`, `@tailwindcss/vite@^4.3.3`, `lucide-react@^1.26.0`.
  - Development: `vite@^8.1.1`, `@vitejs/plugin-react@^6.0.3`, `oxlint@^1.71.0`.
* **Configuration:**
  - `web/vite.config.js`: Integrates `@vitejs/plugin-react` and `@tailwindcss/vite`.
  - `web/.env` & `web/.env.example`: `VITE_API_URL=http://localhost:8000`.
  - `web/vercel.json`: Content Security Policy and deployment routing.
  - `web/.oxlintrc.json`: Linter rule configuration.

---

## 7. Test Suite Status & Execution Verification

Running the test suite via `uv` in the repository root:
```bash
$ /Users/yella4jella/.local/bin/uv run --with pytest pytest tests/
============================== 26 passed in 0.15s ==============================
```

### Breakdown of Existing Tests
* **`tests/test_recommend_deck.py` (7 tests):** Tests role classifiers (`is_land`, `is_ramp`, `is_draw`, `is_removal`), scarcity scoring, text density scoring, spice scoring, commander keyword extraction, synergy scoring, and deck generation.
  * *Limitation:* All tests execute against hand-crafted mock dictionaries; none run against `oracle-cards.json` or live Scryfall data.
* **`tests/test_advanced_analytics.py` (7 tests):** Tests hypergeometric PMF/CDF, joint consistency, permanent fragility weights, protection detection, multiplayer scaling, and multiplayer spice multipliers.
* **`tests/test_intent_engine.py` (3 tests):** Tests intent keyword multipliers (1.5x), bracket fast-mana warnings, and win-condition density auditing.
* **`tests/test_build_gauntlet.py` (4 tests):** Tests CSV price column resolution, color identity filtering, TCGPlayer header parsing, and error handling.
* **`tests/test_tag_color_identity.py` (5 tests):** Tests name column resolution, color identity normalization, Scryfall API batching mock, and SQLite tagging.

### What Is Untested / Untestable
1. **`api.py`:** Zero unit, integration, or regression tests.
2. **`scripts/mana_curve.py`:** Zero tests; Tkinter UI event loops are tightly coupled to logic.
3. **Web Application (`web/src/`):** Zero tests. `package.json` contains no test runner (`vitest` or `jest` are absent). All UI state management, Scryfall fetching, and client-side analysis algorithms in `web/src/utils/` are completely unverified by automated tests.
4. **End-to-End API Integration:** No tests verify communication between the React frontend and `api.py`.
