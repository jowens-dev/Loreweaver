# Loreweaver

Loreweaver is an intelligent deck analysis and thematic companion for Magic: The Gathering (MTG) Commander format. It evaluates decks based on mechanical synergy, thematic cohesion, mana curve efficiency, and operational resource chains.

---

## Architecture overview

Loreweaver consists of three primary components:

1. **Frontend single-page application (SPA):** Built with React 19, Vite, and Tailwind CSS. Provides decklist importing, bracket analysis (Casual Play / Game Changers), mana curve distributions, broken chain detection, and flavor spice recommendations. Hosted on Vercel at [lore-weaver.app](https://lore-weaver.app).
2. **Backend API service:** Built with FastAPI and Uvicorn. Exposes health monitoring, commander-filtered card pools, and categorized recommendation swimlanes.
3. **Card database:** A high-performance, indexed SQLite database (`data/cards.db`, ~18.6 MB). Replaces multi-gigabyte in-memory JSON representations, enabling execution within strict server memory envelopes (<20 MB RAM footprint).

```
                      +-----------------------------+
                      |     Client Web Browser      |
                      |   (https://lore-weaver.app) |
                      +--------------+--------------+
                                     |
              +----------------------+----------------------+
              |                                             |
              v (Direct Scryfall API)                       v (REST / CORS)
    +-------------------+                         +-------------------+
    |   api.scryfall    |                         |   FastAPI Service |
    | (Card Images/DFC) |                         | (api.lore-weaver) |
    +-------------------+                         +---------+---------+
                                                            |
                                                            v
                                                  +-------------------+
                                                  |   SQLite Database |
                                                  |   (data/cards.db) |
                                                  +-------------------+
```

---

## Prerequisites

Before running Loreweaver locally, ensure you have installed:

- **Python 3.10+** (with [`uv`](https://docs.astral.sh/uv/) recommended for fast environment management)
- **Node.js 18+** and **npm**

---

## Get started

### 1. Ingest card database

Loreweaver queries an indexed SQLite database rather than loading raw JSON files into memory.

To generate or refresh `data/cards.db`, run:

```bash
uv run python3 scripts/ingest.py
```

If `scripts/oracle-cards.json` does not exist locally, the ingestion script automatically downloads the latest Oracle bulk card dump from Scryfall.

The ingestion script:
- Filters out non-tournament objects (tokens, emblems, art series).
- Normalizes double-faced card (DFC) faces and aliases into a unified searchable schema.
- Indexes names, color identities, mana values, and EDHREC ranks.

### 2. Run the backend API

Start the FastAPI development server:

```bash
uv run uvicorn api:app --reload --port 8000
```

Verify that the backend is running by requesting the health check endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "total_cards": 34149
}
```

### 3. Run the frontend development server

In a separate terminal, navigate to the `web/` directory and install dependencies:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. The application automatically communicates with your local backend at `http://localhost:8000`.

---

## API reference

### `GET /health`

Returns service health status and card database availability.

#### Response

```json
{
  "status": "healthy",
  "database": "connected",
  "total_cards": 34149
}
```

---

### `GET /api/recommendations`

Returns categorized card recommendation swimlanes matching a commander's color identity and spice parameter.

#### Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `commander` | string | Optional | `""` | Name of the commander (for example, `Belbe, Corrupted Observer`). |
| `spice` | integer | Optional | `50` | Flavor spice level (`0` = Format Staples, `50` = Balanced, `100` = Deep Cuts). |

#### Example request

```bash
curl "http://localhost:8000/api/recommendations?commander=Belbe,%20Corrupted%20Observer&spice=75"
```

#### Response structure

```json
[
  {
    "title": "Ramp Spells",
    "cards": [
      {
        "name": "Incubation Druid",
        "mana_cost": "{1}{G}",
        "type_line": "Creature — Elf Druid",
        "oracle_text": "{T}: Add one mana of any type...",
        "image_url": "https://cards.scryfall.io/...",
        "edhrec_rank": 820,
        "category": "Ramp"
      }
    ]
  },
  {
    "title": "Card Advantage",
    "cards": []
  },
  {
    "title": "Removal & Answers",
    "cards": []
  },
  {
    "title": "Thematic Synergy",
    "cards": []
  },
  {
    "title": "Recommended Lands",
    "cards": []
  }
]
```

---

## Testing

### Python test suite

Run the unit and integration tests across the database layer, API endpoints, and analytics engine:

```bash
uv run --with pytest --with httpx --with fastapi pytest
```

### Frontend linting and build verification

Run the linter and production build to verify client code integrity:

```bash
cd web
npm run lint
npm run build
```

---

## Deployment

### Frontend (Vercel)

The frontend is deployed to Vercel with automatic continuous integration from the `main` branch.

- **Production URL:** [https://lore-weaver.app](https://lore-weaver.app)
- **Root directory:** `web`
- **Build command:** `vite build`
- **Output directory:** `dist`

### Backend (AWS EC2)

The backend service runs on an Amazon Linux EC2 instance (`t3.micro`, `us-east-1`):

- **Host:** `api.lore-weaver.app` (`54.87.157.40`)
- **Service manager:** `systemd` running `uvicorn api:app --host 0.0.0.0 --port 8000`
- **Reverse proxy:** Nginx with Let's Encrypt TLS certificate.

To deploy backend updates:

```bash
ssh -i ~/path/to/key.pem ec2-user@api.lore-weaver.app
cd Loreweaver
git pull origin main
uv run python3 scripts/ingest.py
sudo systemctl restart loreweaver
```

---

## Engineering style guidelines

All documentation, APIs, and code additions in this repository follow the [Google Developer Documentation Style Guide](https://developers.google.com/style):

- Use active voice and write in the second person ("you").
- Maintain sentence case for all section headers.
- Format all code symbols, endpoints, file paths, and parameter names in code font.
- Prioritize testability and verify memory bounds (<100 MB RAM) for all backend algorithms.
