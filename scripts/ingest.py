#!/usr/bin/env python3
"""Ingest Scryfall bulk Oracle JSON into a lightweight, indexed SQLite database."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

NOISE_TYPES = {
    "legendary", "basic", "snow", "world", "ongoing",
    "creature", "artifact", "enchantment", "instant", "sorcery",
    "planeswalker", "land", "battle", "tribal", "hero", "scheme", "vanguard",
    "plains", "island", "swamp", "mountain", "forest", "wastes"
}

EXCLUDED_LAYOUTS = {
    "token", "double_faced_token", "art_series", "emblem",
    "vanguard", "planar", "scheme"
}


def normalize_color_identity(colors: list[str] | str | None) -> str:
    """Normalize color identity into a sorted comma-delimited string (e.g. 'B,G')."""
    if not colors:
        return ""
    if isinstance(colors, str):
        colors = [c.strip().upper() for c in colors.replace(",", " ").split() if c.strip()]
    valid_colors = [c for c in dict.fromkeys(colors) if c in "WUBRG"]
    order = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}
    valid_colors.sort(key=lambda c: order.get(c, 99))
    return ",".join(valid_colors)


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the SQLite database schema and indexes."""
    cursor = connection.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            name_lower TEXT NOT NULL UNIQUE,
            mana_cost TEXT,
            cmc REAL,
            type_line TEXT,
            types TEXT,
            subtypes TEXT,
            colors TEXT,
            color_identity TEXT,
            oracle_text TEXT,
            flavor_text TEXT,
            set_code TEXT,
            set_type TEXT,
            layout TEXT,
            reprint INTEGER,
            keywords TEXT,
            image_url TEXT,
            edhrec_rank INTEGER,
            is_commander INTEGER DEFAULT 0,
            commander_legal INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS card_aliases (
            alias_lower TEXT PRIMARY KEY,
            canonical_name_lower TEXT NOT NULL,
            FOREIGN KEY (canonical_name_lower) REFERENCES cards(name_lower)
        );

        CREATE TABLE IF NOT EXISTS frequencies (
            category TEXT NOT NULL,
            term TEXT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY (category, term)
        );

        CREATE INDEX IF NOT EXISTS idx_cards_name_lower ON cards(name_lower);
        CREATE INDEX IF NOT EXISTS idx_cards_color_identity ON cards(color_identity);
        CREATE INDEX IF NOT EXISTS idx_cards_edhrec_rank ON cards(edhrec_rank);
        CREATE INDEX IF NOT EXISTS idx_cards_is_commander ON cards(is_commander);
        CREATE INDEX IF NOT EXISTS idx_cards_commander_legal ON cards(commander_legal);
        CREATE INDEX IF NOT EXISTS idx_aliases_canonical ON card_aliases(canonical_name_lower);
    """)
    connection.commit()


def ingest_oracle_data(json_path: Path, db_path: Path) -> tuple[int, int]:
    """Parse Scryfall JSON array into SQLite database with full data hygiene."""
    if not json_path.exists():
        raise FileNotFoundError(f"Oracle cards JSON not found: {json_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    connection = sqlite3.connect(str(db_path))
    connection.execute("PRAGMA synchronous = OFF")
    connection.execute("PRAGMA journal_mode = MEMORY")
    create_schema(connection)

    print(f"Reading {json_path}...")
    t0 = time.time()
    with json_path.open("r", encoding="utf-8") as f:
        raw_cards = json.load(f)
    print(f"Loaded {len(raw_cards)} raw objects in {time.time() - t0:.2f}s.")

    subtype_counts: dict[str, int] = defaultdict(int)
    keyword_counts: dict[str, int] = defaultdict(int)
    inserted_cards = 0
    aliases: list[tuple[str, str]] = []

    insert_sql = """
        INSERT OR REPLACE INTO cards (
            name, name_lower, mana_cost, cmc, type_line, types, subtypes,
            colors, color_identity, oracle_text, flavor_text, set_code,
            set_type, layout, reprint, keywords, image_url, edhrec_rank,
            is_commander, commander_legal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    card_rows = []

    for card in raw_cards:
        name = card.get("name", "").strip()
        if not name:
            continue

        layout = card.get("layout", "normal").lower()
        type_line = card.get("type_line", "")
        set_type = card.get("set_type", "").lower()

        # Data Hygiene: Exclude tokens, emblems, art series, vanguards, schemes
        if layout in EXCLUDED_LAYOUTS or set_type == "token":
            continue
        if "Token" in type_line and layout not in ("transform", "modal_dfc", "adventure", "split"):
            continue

        name_lower = name.lower()
        color_identity = normalize_color_identity(card.get("color_identity", []))
        cmc = float(card.get("cmc", 0.0))
        set_code = card.get("set", "")
        reprint = 1 if card.get("reprint", False) else 0
        edhrec_rank = card.get("edhrec_rank")

        # Handle double-faced, split, and adventure cards
        if "card_faces" in card and isinstance(card["card_faces"], list) and card["card_faces"]:
            faces = card["card_faces"]
            mana_cost = faces[0].get("mana_cost", "")
            type_line = " // ".join(f.get("type_line", "") for f in faces if f.get("type_line")) or type_line
            oracle_text = "\n//\n".join(f.get("oracle_text", "") for f in faces if f.get("oracle_text"))
            flavor_text = "\n//\n".join(f.get("flavor_text", "") for f in faces if f.get("flavor_text")) or card.get("flavor_text", "")
            combined_colors = set(card.get("colors", []))
            for f in faces:
                combined_colors.update(f.get("colors", []))
            colors = normalize_color_identity(list(combined_colors))
            
            # Image URL from front face if missing at root
            image_url = ""
            if card.get("image_uris"):
                image_url = card["image_uris"].get("normal") or card["image_uris"].get("small") or ""
            elif faces[0].get("image_uris"):
                image_url = faces[0]["image_uris"].get("normal") or faces[0]["image_uris"].get("small") or ""
        else:
            mana_cost = card.get("mana_cost", "")
            oracle_text = card.get("oracle_text", "") or ""
            flavor_text = card.get("flavor_text", "") or ""
            colors = normalize_color_identity(card.get("colors", []))
            image_uris = card.get("image_uris", {})
            image_url = image_uris.get("normal") or image_uris.get("small") or ""

        # Parse types and subtypes across the entire type line
        clean_types = type_line.replace("—", " ").replace("-", " ").replace("//", " ").lower().split()
        subtypes = [t for t in dict.fromkeys(clean_types) if t not in NOISE_TYPES and len(t) > 2]
        primary_types = [t for t in dict.fromkeys(clean_types) if t in NOISE_TYPES and t not in ("legendary", "basic", "snow", "world", "ongoing")]

        # Keywords
        raw_keywords = [kw.lower() for kw in card.get("keywords", []) if kw]

        # Update global frequency counters
        for sub in subtypes:
            subtype_counts[sub] += 1
        for kw in raw_keywords:
            keyword_counts[kw] += 1

        # Register alias for split / DFC / adventure front face
        if " // " in name:
            front_face = name.split(" // ")[0].strip().lower()
            aliases.append((front_face, name_lower))

        # Check format legality and commander eligibility (MTG CR 903.3 & 712.8a)
        cmd_legality = card.get("legalities", {}).get("commander", "not_legal")
        commander_legal = 1 if cmd_legality == "legal" else 0

        is_commander = 0
        if commander_legal == 1:
            if "card_faces" in card and isinstance(card["card_faces"], list) and card["card_faces"]:
                front = card["card_faces"][0]
                front_tl = front.get("type_line", "")
                front_ot = front.get("oracle_text", "").lower()
                root_ot = card.get("oracle_text", "").lower()
                if (
                    ("Legendary" in front_tl and "Creature" in front_tl) or
                    ("can be your commander" in front_ot) or
                    ("can be your commander" in root_ot) or
                    (name == "Grist, the Hunger Tide")
                ):
                    is_commander = 1
            else:
                tl = card.get("type_line", "")
                ot = card.get("oracle_text", "").lower()
                if (
                    ("Legendary" in tl and "Creature" in tl) or
                    ("can be your commander" in ot) or
                    (name == "Grist, the Hunger Tide")
                ):
                    is_commander = 1

        card_rows.append((
            name,
            name_lower,
            mana_cost,
            cmc,
            type_line,
            json.dumps(primary_types),
            json.dumps(subtypes),
            colors,
            color_identity,
            oracle_text,
            flavor_text,
            set_code,
            set_type,
            layout,
            reprint,
            json.dumps(raw_keywords),
            image_url,
            edhrec_rank,
            is_commander,
            commander_legal
        ))

    print(f"Inserting {len(card_rows)} tournament-legal card records into SQLite...")
    connection.executemany(insert_sql, card_rows)

    # Insert aliases
    if aliases:
        print(f"Inserting {len(aliases)} card name aliases...")
        connection.executemany(
            "INSERT OR IGNORE INTO card_aliases (alias_lower, canonical_name_lower) VALUES (?, ?)",
            aliases
        )

    # Insert frequency metrics
    print("Writing obscurity frequency counters...")
    freq_rows = []
    for sub, count in subtype_counts.items():
        freq_rows.append(("subtype", sub, count))
    for kw, count in keyword_counts.items():
        freq_rows.append(("keyword", kw, count))

    connection.executemany(
        "INSERT OR REPLACE INTO frequencies (category, term, count) VALUES (?, ?, ?)",
        freq_rows
    )

    connection.commit()
    connection.close()

    total_cards = len(card_rows)
    total_aliases = len(aliases)
    db_size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"Ingestion complete: {total_cards} cards, {total_aliases} aliases written to {db_path} ({db_size_mb:.2f} MB).")
    return total_cards, total_aliases


def ensure_oracle_json(path: Path) -> Path:
    """Ensure the Scryfall bulk JSON file exists, downloading if necessary."""
    if path.exists() and path.stat().st_size > 0:
        return path

    print(f"{path} not found. Fetching latest bulk metadata from Scryfall API...")
    import urllib.request
    req = urllib.request.Request(
        "https://api.scryfall.com/bulk-data/oracle-cards",
        headers={"User-Agent": "Loreweaver/1.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        meta = json.loads(resp.read().decode("utf-8"))
        download_url = meta["download_uri"]

    print(f"Downloading bulk cards from {download_url} to {path}...")
    path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(download_url, path)
    print(f"Download complete: {path} ({path.stat().st_size / (1024 * 1024):.2f} MB).")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Scryfall Oracle bulk JSON into SQLite.")
    parser.add_argument("--input", default="scripts/oracle-cards.json", help="Path to raw Scryfall oracle JSON")
    parser.add_argument("--output", default="data/cards.db", help="Path to output SQLite database")
    args = parser.parse_args()

    input_path = ensure_oracle_json(Path(args.input))
    output_path = Path(args.output)

    try:
        total_cards, total_aliases = ingest_oracle_data(input_path, output_path)
        print(f"Successfully created {output_path} with {total_cards} cards.")
    except Exception as e:
        print(f"Error during ingestion: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
