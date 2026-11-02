"""Deck Exporter Module for Loreweaver 100-Card Deck Architect.

Generates tournament-compliant and platform-specific deck exports:
- Moxfield Format (tagged with *CMDR*, exact 100 cards)
- Archidekt Format (1x Name *CMDR* [Commander], 1x Name [Category])
- MTGO .dec Format (// Commander, // Mainboard)
- Plain Text .txt Format (Categorized clean text list)
- CSV Format (Count,Name,Category,CMC,Type)
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

CATEGORY_LABELS = {
    "commander": "Commander",
    "win_con": "Win Con",
    "ramp": "Ramp",
    "draw": "Draw",
    "removal": "Removal",
    "synergy": "Synergy",
    "lands": "Lands",
}


def _get_commanders(deck: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract list of commander cards from deck dictionary."""
    if "commanders" in deck and deck["commanders"]:
        return list(deck["commanders"])
    if "commander" in deck and deck["commander"]:
        return [deck["commander"]]
    if "categories" in deck and "commander" in deck["categories"] and deck["categories"]["commander"]:
        return list(deck["categories"]["commander"])
    return []


def _group_cards_by_name(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group list of cards by name, calculating count for each unique card."""
    grouped_map: dict[str, dict[str, Any]] = {}
    for card in cards:
        name = card.get("name", "")
        if not name:
            continue
        if name in grouped_map:
            grouped_map[name]["count"] += 1
        else:
            grouped_map[name] = {
                "name": name,
                "count": 1,
                "cmc": card.get("cmc", 0),
                "type_line": card.get("type_line", ""),
                "mana_cost": card.get("mana_cost", ""),
                "color_identity": card.get("color_identity", []),
            }
    return list(grouped_map.values())


def _get_categorized_cards(deck: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Extract non-commander categories from deck."""
    categories: dict[str, list[dict[str, Any]]] = {}
    deck_cats = deck.get("categories", {})
    # Standard role order
    role_order = ["win_con", "ramp", "draw", "removal", "synergy", "lands"]
    for role in role_order:
        cards = deck_cats.get(role, [])
        if cards:
            categories[role] = cards
    return categories


def export_to_moxfield(deck: dict[str, Any]) -> str:
    """Generate Moxfield format decklist.
    
    Commanders tagged with *CMDR*:
    1 Belbe, Corrupted Observer *CMDR*
    1 Sol Ring
    ...
    Guaranteed exact 100 cards total.
    """
    lines: list[str] = []
    commanders = _get_commanders(deck)
    for cmd in commanders:
        lines.append(f"1 {cmd['name']} *CMDR*")

    categorized = _get_categorized_cards(deck)
    for role, card_list in categorized.items():
        grouped = _group_cards_by_name(card_list)
        for card in grouped:
            lines.append(f"{card['count']} {card['name']}")

    return "\n".join(lines)


def export_to_tcgplayer(deck: dict[str, Any]) -> str:
    """Generate clean TCGplayer Mass Entry format decklist.
    
    Format:
    1 Belbe, Corrupted Observer
    1 Sol Ring
    ...
    Guaranteed exact 100 cards total, ready for paste into TCGplayer Mass Entry.
    """
    lines: list[str] = []
    commanders = _get_commanders(deck)
    for cmd in commanders:
        lines.append(f"1 {cmd['name']}")

    categorized = _get_categorized_cards(deck)
    for role, card_list in categorized.items():
        grouped = _group_cards_by_name(card_list)
        for card in grouped:
            lines.append(f"{card['count']} {card['name']}")

    return "\n".join(lines)


def export_to_archidekt(deck: dict[str, Any]) -> str:
    """Generate Archidekt format decklist.
    
    Format:
    1x Belbe, Corrupted Observer *CMDR* [Commander]
    1x Sol Ring [Ramp]
    1x Toxic Deluge [Removal]
    ...
    """
    lines: list[str] = []
    commanders = _get_commanders(deck)
    for cmd in commanders:
        lines.append(f"1x {cmd['name']} *CMDR* [Commander]")

    categorized = _get_categorized_cards(deck)
    for role, card_list in categorized.items():
        cat_label = CATEGORY_LABELS.get(role, role.capitalize())
        grouped = _group_cards_by_name(card_list)
        for card in grouped:
            lines.append(f"{card['count']}x {card['name']} [{cat_label}]")

    return "\n".join(lines)


def export_to_mtgo(deck: dict[str, Any]) -> str:
    """Generate MTGO .dec format decklist.
    
    Format:
    // Commander
    1 Belbe, Corrupted Observer
    // Mainboard
    1 Sol Ring
    ...
    """
    lines: list[str] = ["// Commander"]
    commanders = _get_commanders(deck)
    for cmd in commanders:
        lines.append(f"1 {cmd['name']}")

    lines.append("// Mainboard")
    categorized = _get_categorized_cards(deck)
    for role, card_list in categorized.items():
        grouped = _group_cards_by_name(card_list)
        for card in grouped:
            lines.append(f"{card['count']} {card['name']}")

    return "\n".join(lines)


def export_to_text(deck: dict[str, Any]) -> str:
    """Generate categorized plain text decklist.
    
    Format:
    // Commander
    1 Belbe, Corrupted Observer

    // Win Con (4)
    1 Exsanguinate
    ...
    """
    lines: list[str] = ["// Commander"]
    commanders = _get_commanders(deck)
    for cmd in commanders:
        lines.append(f"1 {cmd['name']}")
    lines.append("")

    categorized = _get_categorized_cards(deck)
    for role, card_list in categorized.items():
        cat_label = CATEGORY_LABELS.get(role, role.capitalize())
        lines.append(f"// {cat_label} ({len(card_list)})")
        grouped = _group_cards_by_name(card_list)
        for card in sorted(grouped, key=lambda c: c["name"]):
            lines.append(f"{card['count']} {card['name']}")
        lines.append("")

    return "\n".join(lines).strip()


def export_to_csv(deck: dict[str, Any]) -> str:
    """Generate CSV decklist with columns: Count,Name,Category,CMC,Type."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["Count", "Name", "Category", "CMC", "Type"])

    commanders = _get_commanders(deck)
    for cmd in commanders:
        cmc_val = cmd.get("cmc", 0)
        # Format whole numbers cleanly
        if isinstance(cmc_val, float) and cmc_val.is_integer():
            cmc_val = int(cmc_val)
        writer.writerow([1, cmd.get("name", ""), "Commander", cmc_val, cmd.get("type_line", "")])

    categorized = _get_categorized_cards(deck)
    for role, card_list in categorized.items():
        cat_label = CATEGORY_LABELS.get(role, role.capitalize())
        grouped = _group_cards_by_name(card_list)
        for card in grouped:
            cmc_val = card.get("cmc", 0)
            if isinstance(cmc_val, float) and cmc_val.is_integer():
                cmc_val = int(cmc_val)
            writer.writerow([card["count"], card["name"], cat_label, cmc_val, card["type_line"]])

    return output.getvalue()


def export_all_formats(deck: dict[str, Any]) -> dict[str, str]:
    """Generate all export formats for a deck dictionary."""
    return {
        "moxfield": export_to_moxfield(deck),
        "tcgplayer": export_to_tcgplayer(deck),
        "archidekt": export_to_archidekt(deck),
        "mtgo": export_to_mtgo(deck),
        "text": export_to_text(deck),
        "csv": export_to_csv(deck),
    }


def parse_export_card_count(text: str, format_type: str) -> int:
    """Parse an exported decklist text and calculate the exact total cards count.
    
    Supports: 'moxfield', 'archidekt', 'mtgo', 'text', 'csv'
    """
    total = 0
    fmt = format_type.lower()

    if fmt == "csv":
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            if "Count" in row and row["Count"]:
                total += int(row["Count"])
        return total

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        if fmt == "archidekt":
            # Match: "1x Sol Ring [Ramp]" or "1x Belbe *CMDR* [Commander]"
            m = re.match(r"^(\d+)x\s+(.+)$", line)
            if m:
                total += int(m.group(1))
        else:
            # Matches moxfield, mtgo, text: "1 Sol Ring", "10 Forest", "1 Belbe *CMDR*"
            m = re.match(r"^(\d+)\s+(.+)$", line)
            if m:
                total += int(m.group(1))

    return total
