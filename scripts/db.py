"""Database access layer for Loreweaver SQLite card repository."""

from __future__ import annotations

import itertools
import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "cards.db"
WUBRG_ORDER = ["W", "U", "B", "R", "G"]


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


def parse_card_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """Parse a database row into a structured card dictionary."""
    card_dict = dict(row)
    card_dict["types"] = json.loads(card_dict["types"]) if card_dict.get("types") else []
    card_dict["subtypes"] = json.loads(card_dict["subtypes"]) if card_dict.get("subtypes") else []
    card_dict["keywords"] = json.loads(card_dict["keywords"]) if card_dict.get("keywords") else []
    card_dict["colors"] = [c.strip() for c in card_dict["colors"].split(",") if c.strip()] if card_dict.get("colors") else []
    card_dict["color_identity"] = [c.strip() for c in card_dict["color_identity"].split(",") if c.strip()] if card_dict.get("color_identity") else []
    return card_dict


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
    return parse_card_row(row)


def get_legal_color_identities(allowed_colors: list[str] | set[str] | str) -> list[str]:
    """Compute all legal comma-separated color identity strings within allowed colors in WUBRG order."""
    if isinstance(allowed_colors, str):
        allowed = set(c.strip().upper() for c in allowed_colors.replace(",", " ").split() if c.strip())
    else:
        allowed = set(c.upper() for c in allowed_colors if c)

    sorted_allowed = sorted(allowed, key=lambda c: WUBRG_ORDER.index(c) if c in WUBRG_ORDER else 99)
    legal = [""]
    for r in range(1, len(sorted_allowed) + 1):
        for combo in itertools.combinations(sorted_allowed, r):
            legal.append(",".join(combo))
    return legal


def get_cards_by_identity(
    conn: sqlite3.Connection,
    allowed_colors: list[str] | set[str] | str,
    limit: int = 500
) -> list[dict[str, Any]]:
    """Query cards whose color identity is legal under the given commander identity using indexed subset matching."""
    legal_identities = get_legal_color_identities(allowed_colors)
    placeholders = ",".join("?" * len(legal_identities))

    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
               subtypes, colors, color_identity, oracle_text, flavor_text,
               set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
        FROM cards
        WHERE color_identity IN ({placeholders})
          AND set_type NOT IN ('funny', 'alchemy')
          AND edhrec_rank IS NOT NULL
        ORDER BY edhrec_rank ASC
        LIMIT ?
        """,
        (*legal_identities, limit)
    )

    return [parse_card_row(row) for row in cursor.fetchall()]


def search_commanders(
    conn: sqlite3.Connection,
    query: str = "",
    allowed_colors: list[str] | set[str] | str | None = None,
    limit: int = 50
) -> list[dict[str, Any]]:
    """Search for legendary creatures and planeswalkers legal as Commander."""
    cursor = conn.cursor()
    params: list[Any] = []
    conditions = [
        "(type_line LIKE '%Legendary%Creature%' OR oracle_text LIKE '%can be your commander%')",
        "set_type NOT IN ('funny', 'alchemy')",
        "edhrec_rank IS NOT NULL"
    ]

    if query.strip():
        conditions.append("name_lower LIKE ?")
        params.append(f"%{query.strip().lower()}%")

    if allowed_colors is not None:
        legal_identities = get_legal_color_identities(allowed_colors)
        placeholders = ",".join("?" * len(legal_identities))
        conditions.append(f"color_identity IN ({placeholders})")
        params.extend(legal_identities)

    sql = f"""
        SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
               subtypes, colors, color_identity, oracle_text, flavor_text,
               set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
        FROM cards
        WHERE {' AND '.join(conditions)}
        ORDER BY edhrec_rank ASC
        LIMIT ?
    """
    params.append(limit)
    cursor.execute(sql, params)
    return [parse_card_row(row) for row in cursor.fetchall()]


def search_cards_predictive(
    conn: sqlite3.Connection,
    query: str,
    commanders_only: bool = True,
    limit: int = 8
) -> list[dict[str, Any]]:
    """Predictive search for cards by prefix/word-boundary with popularity ranking."""
    clean_q = query.strip().lower()
    if not clean_q:
        return []

    cursor = conn.cursor()
    conditions = [
        "set_type NOT IN ('funny', 'alchemy')",
        "edhrec_rank IS NOT NULL"
    ]
    if commanders_only:
        conditions.append("(type_line LIKE '%Legendary%Creature%' OR oracle_text LIKE '%can be your commander%')")

    conditions.append("(name_lower LIKE ? OR name_lower LIKE ?)")
    params = [f"{clean_q}%", f"% {clean_q}%"]

    sql = f"""
        SELECT id, name, name_lower, mana_cost, cmc, type_line, types,
               subtypes, colors, color_identity, oracle_text, flavor_text,
               set_code, set_type, layout, reprint, keywords, image_url, edhrec_rank
        FROM cards
        WHERE {' AND '.join(conditions)}
        ORDER BY 
            CASE 
                WHEN name_lower = ? THEN 0
                WHEN name_lower LIKE ? THEN 1
                ELSE 2
            END,
            edhrec_rank ASC
        LIMIT ?
    """
    cursor.execute(sql, [*params, clean_q, f"{clean_q}%", limit])
    return [parse_card_row(row) for row in cursor.fetchall()]


def get_term_frequencies(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Retrieve global frequency counts for subtypes and keywords."""
    cursor = conn.cursor()
    cursor.execute("SELECT category, term, count FROM frequencies")
    frequencies: dict[str, dict[str, int]] = {"subtypes": {}, "keywords": {}}
    for row in cursor.fetchall():
        cat = "subtypes" if row["category"] == "subtype" else "keywords"
        frequencies[cat][row["term"]] = int(row["count"])
    return frequencies
