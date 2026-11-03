# Loreweaver

[![CI / CD Pipeline](https://github.com/jowens-dev/Loreweaver/actions/workflows/ci.yml/badge.svg)](https://github.com/jowens-dev/Loreweaver/actions)
[![Test Suite](https://img.shields.io/badge/tests-93%20passed-22c55e.svg)](https://github.com/jowens-dev/Loreweaver/tree/main/tests)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-3b82f6.svg)](https://www.python.org/)
[![Frontend](https://img.shields.io/badge/react-19%20%7C%20vite%208-8b5cf6.svg)](https://vitejs.dev/)
[![Production Status](https://img.shields.io/badge/live-lore--weaver.app-10b981.svg)](https://lore-weaver.app)
[![API Status](https://img.shields.io/badge/api-api.lore--weaver.app-f59e0b.svg)](https://api.lore-weaver.app/health)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Loreweaver** is an intelligent deck architect, tactical analyzer, and thematic companion for Magic: The Gathering (MTG) Commander format. It designs complete, tournament-legal 100-card decks from scratch and audits existing lists using objective synergy scoring, Frank Karsten hypergeometric mana quotas, and Commander Bracket rules.

- **Web Application:** [https://lore-weaver.app](https://lore-weaver.app)
- **Backend API:** [https://api.lore-weaver.app](https://api.lore-weaver.app)
- **Ko-fi Support:** [https://ko-fi.com/loreweaver_mtg](https://ko-fi.com/loreweaver_mtg)
- **Contact:** [`contact@lore-weaver.app`](mailto:contact@lore-weaver.app)

---

## Key features

### 1. 100-card Deck Architect (Build mode)
- **Full 100-card synthesis:** Assembles tournament-legal Commander decks from scratch satisfying the strict mathematical invariant: $N_{\text{commanders}} + N_{\text{mainboard}} = 100$ with guaranteed $0$ duplicate non-basic lands.
- **Partner commander support (MTG Rule 903.3a):** Seamlessly pairs partner commanders (e.g. *Thrasios / Tymna* $\rightarrow 2\text{ Commanders} + 98\text{ Mainboard} = 100$).
- **18-theme operational taxonomy:** Comprehends nuanced operational loops beyond surface creature types:
  - *Group Slug & Bleed* (e.g. Belbe's symmetric postcombat colorless acceleration)
  - *Big Mana & Colorless Payoffs* (*Portal to Phyrexia*, Eldrazi Titans)
  - *Flash & Instant Timing Enablers* (*Vedalken Orrery*, *Yeva*, *Liberator*)
  - *Planeswalkers & Superfriends* (*The Chain Veil*, *Oath of Teferi*, loyalty doubling)
  - *Blink/Flicker*, *Enchantress*, *Aristocrats*, *Tokens*, *Counters*, *Spellslinger*, *Landfall*, *Voltron*, *Reanimator*, *Wheels*, and *Stax*.
- **Pip-proportional land bases:** Calculates color pips across nonland spells to generate balanced basic, dual, and utility land allocations.

### 2. Commander bracket tuning (Tiers 1–5)
- **Bracket 1 (Exhibition / Narrative):** Low-power, narrative or tribal; zero fast mana, zero tutors, zero infinite combos, zero Sol Ring.
- **Bracket 2 (Core Casual / Upgraded Precon):** Board-centric Magic; standard ramp (Sol Ring, Signets, Cultivate); no 2-card infinites or cheap tutors.
- **Bracket 3 (Optimized Casual / FNM):** Focused win conditions, resilient mana base, responsive interaction; bars cheap tutors ($\le 2$ CMC) and compact 2-card tournament loops.
- **Bracket 4 (High-power Unrestricted):** Maximum casual power / fringe cEDH; explosive fast mana, unrestricted combos, and top tutors without tournament meta lock-in.
- **Bracket 5 (Competitive EDH / cEDH Meta):** Tournament cEDH metagame; razor-thin curve, full fast-mana suite (*Mox Diamond*, *Chrome Mox*, *Grim Monolith*, *Mana Vault*), free interaction (*Force of Will*, *Fierce Guardianship*), and compact win lines (*Thassa's Oracle + Demonic Consultation*).

### 3. Granular budget & house-rule ban filters
- **4 budget tiers:**
  - `ultra_budget` (<$50): Strictly excludes fetchlands, shocklands, expensive reserved list cards, fast mana, and high-value staples ($20+); substitutes Karoo bounce lands, scry temples, gainlands, and common ramp.
  - `budget` (<$100): Standard budget; excludes fetchlands and reserved list cards.
  - `moderate` (~$250): Balanced budget with standard fetch/shock land access.
  - `unlimited`: Full card pool with zero budget constraints.
- **House-rule ban toggles:**
  - 🚫 **No Infinite Combos:** Strips 2-card and compact combo loops across all brackets.
  - ⚡ **No Fast Mana:** Strips Sol Ring, Mana Vault, Grim Monolith, Mox Diamond, Chrome Mox, Lotus Petal, Mox Opal, and Ancient Tomb.
  - 🛡️ **No Free Spells:** Strips free interaction (*Force of Will*, *Fierce Guardianship*, *Deflecting Swat*, *Deadly Rollick*, *Flawless Maneuver*).
  - ⛓️ **No Stax / MLD:** Strips hard resource denial (*Winter Orb*, *Static Orb*, *Armageddon*, *Blood Moon*).
  - 🔍 **No Cheap Tutors:** Strips unconditional tutors (*Demonic*, *Vampiric*, *Worldly*, *Mystical*, *Enlightened*).
- **Custom card exclusion chips:** Predictive search bar to ban specific pet-peeve cards (e.g. *Rhystic Study*, *Smothering Tithe*, *Cyclonic Rift*) with 1-click chip removal.

### 4. Interactive card swapper & re-roller
- **Slot-level swapping:** Click **"Swap"** on any card in the 100-card grid to open the candidate replacement interface.
- **Dedicated candidate engine (`GET /api/swap-candidates`):** Queries legally compliant candidates matching color identity, bracket tier, and operational role (`ramp`, `draw`, `removal`, `win_con`, `synergy`, `lands`).
- **Context-aware reasoning:** Explanatory badges detail why each candidate fits the commander and role.
- **1-click quick re-roll:** Instantly replaces the slot with the #1 recommended card alternative.
- **Predictive slot search:** Type and slot in any legal card in the commander's color identity.
- **Dynamic updates:** Recalculates average CMC, mana curve distributions, and export texts in real time without rebuilding the deck.

### 5. Multi-platform exporters & affiliate commerce
- **Moxfield export:** 1-click copy with single or partner commanders tagged with `*CMDR*` (guaranteed 100 cards ready for bulk import).
- **Archidekt export:** Formatted card entries with bracket/role tags (`[Ramp]`, `[Draw]`, `[Removal]`, `[Synergy]`, `[Lands]`).
- **MTGO `.dec` download:** Native Magic Online deck file with separate `// Commander` and `// Mainboard` blocks.
- **Plain text `.txt` download:** Categorized, human-readable decklist.
- **Spreadsheet `.csv` export:** Structured tabular export (`Count,Name,Category,CMC,Type`) with RFC 4180 CSV escaping.
- **⚡ Buy on Mana Pool (5% affiliate):** 1-click cart transfer that copies the mass entry list and opens Mana Pool Mass Entry with Cart Optimizer and affiliate attribution (`ref=loreweaver`).
- **🛒 Buy on TCGplayer:** Mass entry list export for ordering via TCGplayer Mass Entry.

### 6. Dynamic hover visuals & card tooltips
- **Portal-based floating tooltip:** High-resolution Scryfall card imagery anywhere in the app (Architect, Analyzer, cuts, swimlanes, and swap modal).
- **Collision detection:** Viewport clamping prevents offscreen clipping on right, left, top, or bottom edges.
- **Double-faced card (DFC) flipping:** Visual face indicator banner (`Face 1/2`) and interactive face flip via button click, image click, or keyboard shortcut (<kbd>F</kbd>).
- **In-memory caching:** Zero-latency display with request deduplication to prevent redundant Scryfall network calls.

### 7. Hybrid deterministic deck analyzer (Audit mode)
- **Full decklist import:** Parses raw text, MTGO, or Arena decklists into structured card objects.
- **Commander operational engine dossier:** Maps and displays the commander's **Catalyst**, **Yield**, and **Payoff** chains.
- **Frank Karsten hypergeometric probabilities:**
  - $P(\ge 3\text{ lands on Turn 3})$
  - $P(\text{land + ramp spell on Turn 2})$
  - Disjoint population partitioning ensures mathematical consistency.
- **Tactical cut recommendations:** Identifies contested or off-theme cards with specific justification and suggested replacements.
- **Load-bearing pillar protection:** 0.0% False-Cut Rate guaranteeing load-bearing synergy pillars are never recommended for cuts.
- **Flavor spice dial:** Slider tuning recommendation swimlanes from reliable tournament staples ($0$) to hidden thematic deep cuts ($100$).

---

## Architecture overview

Loreweaver is engineered for extreme execution speed and low resource consumption (<20 MB RAM footprint, sub-millisecond query latency):

```
                      +-----------------------------+
                      |     Client Web Browser      |
                      |   (https://lore-weaver.app) |
                      +--------------+--------------+
                                     |
              +----------------------+----------------------+
              |                                             |
              v (Direct Scryfall Image CDN)                 v (REST / CORS)
    +-------------------+                         +-------------------+
    | cards.scryfall.io |                         |  Cloudflare Edge  |
    | (Image Tooltips)  |                         |  (Cache 24h/1h)   |
    +-------------------+                         +---------+---------+
                                                            |
                                                            v
                                                  +-------------------+
                                                  |   FastAPI Service |
                                                  | (api.lore-weaver) |
                                                  +---------+---------+
                                                            |
                                                            v
                                                  +-------------------+
                                                  |  cards.db SQLite  |
                                                  | (34,149 Cards WAL)|
                                                  +-------------------+
```

### Components
1. **Frontend single-page application (SPA):** Built with React 19, Vite, and Tailwind CSS. Hosted on Vercel at [lore-weaver.app](https://lore-weaver.app).
2. **Backend API service:** Built with FastAPI and Uvicorn. Exposes deck synthesis, role classification, swap candidates, predictive autocomplete, and analytics. Hosted on AWS EC2 at [api.lore-weaver.app](https://api.lore-weaver.app).
3. **Card database:** A high-performance, indexed SQLite database (`data/cards.db`, ~18.6 MB). Replaces multi-gigabyte in-memory JSON representations, enabling execution within strict server memory envelopes (<20 MB RAM footprint).
4. **Edge caching:** RFC-compliant `Cache-Control` headers allow Cloudflare and browser caches to serve autocomplete search results at the edge in <10ms, offloading up to 90% of backend traffic.

---

## API reference

### `GET /health`
Returns service health status and card database availability.

```json
{
  "status": "healthy",
  "database": "connected",
  "total_cards": 34149
}
```

---

### `GET /api/search`
Predictive autocomplete search for cards and commanders by name with 24-hour edge caching headers (`Cache-Control: public, max-age=86400, s-maxage=86400`).

#### Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `q` | string | Required | `""` | Card name prefix or query string. |
| `commanders_only` | boolean | Optional | `true` | Filter results to legal commanders. |
| `commander` | string | Optional | `""` | Optional commander name to filter results by legal color identity. |
| `limit` | integer | Optional | `8` | Maximum results to return (1–50). |

---

### `POST /api/build`
Builds a complete, tournament-legal 100-card Commander deck from objective synergy scores, bracket rules, and budget/ban constraints.

#### Request body
```json
{
  "commander": "Belbe, Corrupted Observer",
  "deck_idea": "Symmetric bleed into high-CMC colorless bombs with instant timing",
  "bracket": 4,
  "budget": "moderate",
  "preferred_win_con": "combat",
  "house_rules": ["no_fast_mana"],
  "custom_bans": ["Rhystic Study"]
}
```

#### Response structure
```json
{
  "commander": { "name": "Belbe, Corrupted Observer", "mana_cost": "{B}{G}", "cmc": 2.0 },
  "commanders": [{ "name": "Belbe, Corrupted Observer" }],
  "bracket": { "tier": 4, "name": "High-Power Unrestricted" },
  "budget": "moderate",
  "preferred_win_con": "combat",
  "total_cards": 100,
  "win_con_execution": "⚡ Belbe Operational Engine: Deploys cheap 1–2 CMC symmetric bleeders...",
  "stats": {
    "card_count": 100,
    "avg_cmc": 3.82,
    "mana_curve": { "0": 0, "1": 12, "2": 18, "3": 14, "4": 8, "5": 5, "6+": 13 },
    "hypergeometric_consistency": {
      "p_3_lands_turn_3": "78.4%",
      "p_land_and_ramp_turn_2": "62.1%"
    }
  },
  "categories": {
    "commander": [...],
    "ramp": [...],
    "draw": [...],
    "removal": [...],
    "win_con": [...],
    "synergy": [...],
    "lands": [...]
  },
  "exports": {
    "moxfield": "1 Belbe, Corrupted Observer *CMDR*\n1 Sol Ring\n...",
    "archidekt": "1x Belbe, Corrupted Observer *CMDR* [Commander]\n...",
    "tcgplayer": "1 Belbe, Corrupted Observer\n1 Sol Ring\n...",
    "mtgo": "// Commander\n1 Belbe, Corrupted Observer\n// Mainboard\n...",
    "text": "// Commander\n1 Belbe, Corrupted Observer\n\n// Ramp (12)\n...",
    "csv": "Count,Name,Category,CMC,Type\n1,Belbe, Corrupted Observer,Commander,2.0,Legendary Creature..."
  }
}
```

---

### `GET /api/swap-candidates`
Queries legally compliant candidate replacement cards matching color identity, bracket tier, and operational role, with 1-hour edge caching.

#### Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `card_name` | string | Required | — | Card name to be replaced. |
| `commander` | string | Required | — | Commander name to resolve color identity. |
| `category` | string | Required | `"synergy"` | Operational role (`ramp`, `draw`, `removal`, `win_con`, `synergy`, `lands`). |
| `bracket` | integer | Optional | `3` | Bracket tier (1–5). |
| `exclude` | list | Optional | `[]` | Card names already in the deck to prevent duplicate non-basics. |
| `limit` | integer | Optional | `8` | Maximum candidate count. |

---

### `POST /api/analyze`
Analyzes a full 100-card Commander decklist: calculates mana curve distributions, evaluates operational resource profiles, locks load-bearing pillars, and generates tactical cut recommendations with in-color replacements.

---

## Local development & setup

### Prerequisites
- **Python 3.10+** (with [`uv`](https://docs.astral.sh/uv/) recommended)
- **Node.js 18+** and **npm**

### 1. Ingest card database
To generate or refresh `data/cards.db`, run:

```bash
uv run python3 scripts/ingest.py
```

The ingestion script:
- Downloads the latest Oracle bulk card dump from Scryfall if not present.
- Filters out non-tournament objects (tokens, emblems, art series).
- Normalizes double-faced card (DFC) faces into unified searchable records.
- Indexes names, color identities, mana values, and EDHREC ranks.

### 2. Run backend API
Start the FastAPI development server:

```bash
uv run uvicorn api:app --reload --port 8000
```

Verify that the backend is running:

```bash
curl http://localhost:8000/health
```

### 3. Run frontend development server
In a separate terminal, install dependencies and start the Vite dev server:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. The frontend automatically communicates with your local backend at `http://localhost:8000`.

---

## Testing & verification

Loreweaver adheres strictly to **Cleanroom Rigor & Popperian Verification Axioms** (Epistemic Priority, Best-Faith Adversarial Falsification, and Clean-Room Panels of Judgment).

### Run Python test suite (93 tests)
```bash
uv run --with pytest --with httpx --with fastapi pytest
```

The test suite covers:
- **`test_popperian_falsification.py`**: Adversarial destruction tests across 9 operational vectors (Belbe bleed, Kozilek colorless invariants, 5-color Kenrith, partner pairs, zero banned leakage, sampling stress).
- **`test_benchmark_harness.py`**: 7 golden benchmark decks with 100% Chain Recall and 0.0% False-Cut Rate.
- **`test_deck_builder.py`**: 100-card synthesis, partner support, and bracket tuning.
- **`test_strategy_prompt.py`**: Semantic strategy parsing, planeswalker multi-activation engines, and game state blueprints.
- **`test_budget_and_bans.py`**: Ultra-budget (<$50) validation and house-rule ban enforcement.
- **`test_card_swapper.py`**: Candidate replacement scoring and non-duplicate guarantees.
- **`test_deck_export.py`**: Multi-platform export formatting across Moxfield, Archidekt, MTGO, CSV, and TXT.
- **`test_monetization_and_cache.py`**: Edge caching headers and TCGplayer mass entry validation.

### Run frontend linter & production build
```bash
cd web
npm run lint     # oxlint (0 errors, 0 warnings)
npm run build    # vite build production compilation
```

---

## Production deployment

### Frontend (Vercel)
- **Production URL:** [https://lore-weaver.app](https://lore-weaver.app)
- **Continuous Deployment:** Automated build on every push to `main`.
- **Framework:** Vite / React 19 SPA.

### Backend (AWS EC2)
- **Production Host:** [https://api.lore-weaver.app](https://api.lore-weaver.app)
- **Hardware:** Amazon Linux EC2 `t3.micro` (`us-east-1`, `98.87.6.129`).
- **Process Manager:** `systemd` running `uvicorn api:app --host 0.0.0.0 --port 8000`.
- **Reverse Proxy:** Nginx with Let's Encrypt TLS and Cloudflare Edge proxy.

---

## Support & community

Loreweaver is 100% free, open-source, and unmonetized by design. If Loreweaver helped you brew your deck or saved you hours of theorycrafting, consider supporting ongoing server hosting costs:

- **Ko-fi:** [https://ko-fi.com/loreweaver_mtg](https://ko-fi.com/loreweaver_mtg)
- **General contact:** [`contact@lore-weaver.app`](mailto:contact@lore-weaver.app)
- **Community greetings:** [`hello@lore-weaver.app`](mailto:hello@lore-weaver.app)
- **GitHub Issues:** [https://github.com/jowens-dev/Loreweaver/issues](https://github.com/jowens-dev/Loreweaver/issues)
- **Free way to support:** Order cards through the **"⚡ Buy on Mana Pool"** button; we receive a **5% affiliate commission** at zero extra cost to you.

---

## Legal disclaimer

Loreweaver is unofficial Fan Content permitted under the [Wizards of the Coast Fan Content Policy](https://company.wizards.com/fancontentpolicy). The literal and graphical information presented on this site about Magic: The Gathering, including card images and mana symbols, is copyright Wizards of the Coast, LLC, a subsidiary of Hasbro, Inc. Loreweaver is not produced by, endorsed by, supported by, or affiliated with Wizards of the Coast.
