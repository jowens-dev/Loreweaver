"""Database access layer for Loreweaver SQLite card repository."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "cards.db"


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Return a connection to the SQLite database with Row factory enabled."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    if not path.exists():
        raise FileNotFoundError(f"Database not found at {path}. Run scripts/ingest.py first.")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def get_card_count(conn: sqlite3.Connection) -> int:
    """Return the total number of tournament-legal cards in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cards")
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def resolve_card_name(conn: sqlite3.Connection, name: str) -> str:
    """Resolve a potential card alias to its canonical lowercase name."""
    clean_name = name.strip().lower()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT canonical_name_lower FROM card_aliases WHERE alias_lower = ?",
        (clean_name,)
    )
    row = cursor.fetchone()
    if row:
        return str(row["canonical_name_lower"])
    return clean_name


def get_card_by_name(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    """Retrieve full card metadata by name or alias."""
    canonical = resolve_card_name(conn, name)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
               subtypes, colors, color_identity, oracle_text, flavor_text,
               set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
        FROM cards
        WHERE name_lower = ?
        """,
        (canonical,)
    )
    row = cursor.fetchone()
    if not row:
        return None

    card_dict = dict(row)
    card_dict["types"] = json.loads(card_dict["types"]) if card_dict.get("types") else []
    card_dict["subtypes"] = json.loads(card_dict["subtypes"]) if card_dict.get("subtypes") else []
    card_dict["keywords"] = json.loads(card_dict["keywords"]) if card_dict.get("keywords") else []
    card_dict["colors"] = [c.strip() for c in card_dict["colors"].split(",") if c.strip()] if card_dict.get("colors") else []
    card_dict["color_identity"] = [c.strip() for c in card_dict["color_identity"].split(",") if c.strip()] if card_dict.get("color_identity") else []
    return card_dict


def get_cards_by_identity(
    conn: sqlite3.Connection,
    allowed_colors: list[str] | set[str] | str,
    limit: int = 500
) -> list[dict[str, Any]]:
    """Query cards whose color identity is legal under the given commander identity."""
    if isinstance(allowed_colors, str):
        allowed = set(c.strip().upper() for c in allowed_colors.replace(",", " ").split() if c.strip())
    else:
        allowed = set(c.upper() for c in allowed_colors if c)

    cursor = conn.cursor()
    # Colorless commanders (allowed == empty set) can only run colorless cards (color_identity == '')
    if not allowed:
        cursor.execute(
            """
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
            FROM cards
            WHERE color_identity = ''
            ORDER BY edhrec_rank ASC NULLS LAST
            LIMIT ?
            """,
            (limit,)
        )
    else:
        # Pre-filter in SQL, refine in Python
        cursor.execute(
            """
            SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
                   subtypes, colors, color_identity, oracle_text, flavor_text,
                   set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
            FROM cards
            WHERE edhrec_rank IS NOT NULL
            ORDER BY edhrec_rank ASC
            LIMIT ?
            """,
            (limit * 2,)
        )

    results = []
    for row in cursor.fetchall():
        row_id = set(c.strip() for c in (row["color_identity"] or "").split(",") if c.strip())
        if row_id.issubset(allowed):
            card_dict = dict(row)
            card_dict["types"] = json.loads(card_dict["types"]) if card_dict.get("types") else []
            card_dict["subtypes"] = json.loads(card_dict["subtypes"]) if card_dict.get("subtypes") else []
            card_dict["keywords"] = json.loads(card_dict["keywords"]) if card_dict.get("keywords") else []
            card_dict["colors"] = [c.strip() for c in card_dict["colors"].split(",") if c.strip()] if card_dict.get("colors") else []
            card_dict["color_identity"] = list(row_id)
            results.append(card_dict)
            if len(results) >= limit:
                break

    return results


def get_term_frequencies(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Retrieve global frequency counts for subtypes and keywords."""
    cursor = conn.cursor()
    cursor.execute("SELECT category, term, count FROM frequencies")
    frequencies: dict[str, dict[str, int]] = {"subtypes": {}, "keywords": {}}
    for row in cursor.fetchall():
        cat = "subtypes" if row["category"] == "subtype" else "keywords"
        frequencies[cat][row["term"]] = int(row["count"])
    return frequencies
