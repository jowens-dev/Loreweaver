"""Mana Pool Pricing Engine & Logarithmic Budget Friction for Loreweaver.

Provides:
- Asymmetric logarithmic cost penalty: Penalty(P) = [ln(e + P)]^beta (beta ≈ 2.1)
- Obscurity / Spice bonus: up to 2.0x multiplier for underplayed cards (rank > 500)
- Sentinel pricing ($999.00) for unpriced/null cards to prevent budget evasion
- SQLite price caching in card_prices table
- Mana Pool affiliate URL and slug generation (ref=loreweaver&ref_meta=source:loreweaver_swap)
- Scryfall/Mana Pool bulk singles pricing pipeline
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import unicodedata
import urllib.request
from typing import Any

DEFAULT_SENTINEL_PRICE = 999.00
DEFAULT_BETA = 2.1
DEFAULT_MANAPOOL_REF = "loreweaver"

# Deterministic seed pricing for key format staples & test baseline
SEED_PRICES: dict[str, float] = {
    # High-dollar format staples ($25 - $100+)
    "rhystic study": 42.50,
    "demonic tutor": 45.00,
    "cyclonic rift": 38.00,
    "vampiric tutor": 40.00,
    "mana crypt": 180.00,
    "dockside extortionist": 75.00,
    "fierce guardianship": 48.00,
    "force of will": 65.00,
    "smothering tithe": 22.00,
    "the one ring": 95.00,
    "esika, god of the tree": 14.50,
    "craterhoof behemoth": 35.00,
    "doubling season": 45.00,
    "parallel lives": 32.00,
    "anointed procession": 48.00,
    "the chain veil": 18.00,
    "oath of teferi": 4.50,
    "vorinclex, monstrous raider": 38.00,
    "toxic deluge": 12.00,
    "supreme verdict": 4.00,
    "damnation": 16.00,

    # Moderate staples ($3 - $10)
    "heroic intervention": 8.50,
    "lightning greaves": 6.50,
    "swiftfoot boots": 2.50,
    "skullclamp": 6.00,
    "blood artist": 2.50,
    "zulaport cutthroat": 1.25,
    "dina, soul steeper": 0.75,
    "belbe, corrupted observer": 1.50,
    "sol ring": 1.25,
    "arcane signet": 0.85,
    "fellwar stone": 0.95,
    "thought vessel": 1.50,
    "mind stone": 0.35,
    "commander's sphere": 0.25,
    "wayfarer's bauble": 0.45,
    "rampant growth": 0.35,
    "cultivate": 0.45,
    "kodama's reach": 0.45,
    "farseek": 1.20,
    "sakura-tribe elder": 0.75,

    # Budget high-synergy "Secret Tech" / underplayed gems ($0.15 - $0.75)
    "nadier's nightblade": 0.35,
    "essence warden": 0.65,
    "prosperous innkeeper": 0.45,
    "creeping bloodsucker": 0.30,
    "syr konrad, the grim": 0.65,
    "marionette apprentice": 0.45,
    "night market lookout": 0.20,
    "vitor, thorn of the dusk rose": 3.50,
    "starscape cleric": 0.25,
    "valley rotcaller": 0.35,
    "throne of the god-pharaoh": 3.80,
    "bastion of remembrance": 0.95,
    "mirkwood bats": 0.45,
    "spiteful prankster": 0.25,
    "morbid opportunist": 0.35,
    "falkenrath noble": 0.25,
    "vindictive vampire": 0.25,
    "poison-tip archer": 0.45,
    "grim guardian": 0.30,
    "cruel celebrant": 0.75,
    "corpse knight": 0.35,
    "bloodletter of aclazotz": 16.00,
}


def to_manapool_slug(name: str) -> str:
    """Convert card name to canonical Mana Pool URL slug.

    Examples:
        'Sol Ring' -> 'sol-ring'
        'Dina, Soul Steeper' -> 'dina-soul-steeper'
        'Nadier\'s Nightblade' -> 'nadiers-nightblade'
        'Lim-Dûl\'s Vault' -> 'lim-duls-vault'
        'Æther Vial' -> 'aether-vial'
    """
    if not name:
        return ""
    # Expand Latin ligatures before ascii stripping
    expanded = name.replace("Æ", "Ae").replace("æ", "ae").replace("Œ", "Oe").replace("œ", "oe")
    # Normalize unicode accents
    norm = unicodedata.normalize("NFKD", expanded).encode("ascii", "ignore").decode("utf-8")
    # Strip apostrophes, quotes, punctuation
    cleaned = re.sub(r"['\",()!?.:]", "", norm)
    # Convert non-alphanumeric to hyphens
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", cleaned).strip("-").lower()
    return slug


def get_manapool_affiliate_url(
    card_name: str,
    ref: str = DEFAULT_MANAPOOL_REF,
    source: str = "loreweaver_swap"
) -> str:
    """Construct direct single-card Mana Pool affiliate URL."""
    slug = to_manapool_slug(card_name)
    if not slug:
        return f"https://manapool.com/?ref={ref}"
    return f"https://manapool.com/card/{slug}?ref={ref}&ref_meta=source:{source}"


def calculate_price_penalty(price: float | None, beta: float = DEFAULT_BETA) -> float:
    """Calculate steep asymmetric logarithmic drag penalty.

    Formula: Penalty(P) = [ln(e + P)]^beta
    If card lacks price (null/<=0), assign sentinel price ($999.00) so unpriced
    cards never register as free $0.00 budget picks.
    """
    effective_p = float(price) if (price is not None and price > 0.0) else DEFAULT_SENTINEL_PRICE
    return math.pow(math.log(math.e + effective_p), beta)


def calculate_spice_bonus(edhrec_rank: int | None) -> float:
    """Calculate obscurity / secret-tech multiplier based on EDHREC rank.

    - Generic top-500 staples receive a flat 1.0x (no bonus).
    - Underplayed cards (rank > 500) receive up to a 2.0x multiplier.
    - Capped at 2.0x for rank >= 10,000.
    """
    if edhrec_rank is None or edhrec_rank <= 500:
        return 1.0
    return 1.0 + min(1.0, max(0.0, (edhrec_rank - 500) / 9500.0))


def calculate_composite_score(
    synergy_score: float,
    price: float | None,
    edhrec_rank: int | None,
    beta: float = DEFAULT_BETA
) -> float:
    """Calculate Final Composite Score.

    FinalScore(c) = (SynergyScore(c) * SpiceBonus(c)) / PricePenalty(P_c)
    """
    penalty = calculate_price_penalty(price, beta=beta)
    spice = calculate_spice_bonus(edhrec_rank)
    return (float(synergy_score) * spice) / penalty


def init_price_table(conn: sqlite3.Connection) -> None:
    """Ensure the card_prices table exists in cards.db."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS card_prices (
            name_lower TEXT PRIMARY KEY,
            price_usd REAL NOT NULL,
            source TEXT DEFAULT 'seed',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def seed_default_prices(conn: sqlite3.Connection) -> None:
    """Populate default seed prices into SQLite cache if empty."""
    init_price_table(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM card_prices")
    count = cursor.fetchone()[0]
    if count == 0:
        for name_lower, price in SEED_PRICES.items():
            cursor.execute(
                "INSERT OR REPLACE INTO card_prices (name_lower, price_usd, source) VALUES (?, ?, ?)",
                (name_lower, price, "seed")
            )
        conn.commit()


def get_card_price(
    conn: sqlite3.Connection | None,
    card_name: str,
    fallback_to_seed: bool = True
) -> float:
    """Retrieve lowest USD paper price for a card. Returns sentinel $999.00 if unpriced."""
    if not card_name:
        return DEFAULT_SENTINEL_PRICE

    nl = card_name.strip().lower()

    # 1. Check SQLite database if connection provided
    if conn is not None:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT price_usd FROM card_prices WHERE name_lower = ?", (nl,))
            row = cursor.fetchone()
            if row and row[0] is not None and float(row[0]) > 0.0:
                return float(row[0])
        except Exception:
            pass

    # 2. Check in-memory seed dictionary
    if fallback_to_seed and nl in SEED_PRICES:
        return SEED_PRICES[nl]

    # 3. Default to sentinel price
    return DEFAULT_SENTINEL_PRICE


def get_bulk_prices(
    conn: sqlite3.Connection | None,
    card_names: list[str]
) -> dict[str, float]:
    """Retrieve prices for a list of card names."""
    results: dict[str, float] = {}
    if not card_names:
        return results

    clean_names = [n.strip() for n in card_names if n and n.strip()]
    lower_map = {n.lower(): n for n in clean_names}

    if conn is not None:
        try:
            init_price_table(conn)
            placeholders = ",".join("?" * len(lower_map))
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT name_lower, price_usd FROM card_prices WHERE name_lower IN ({placeholders})",
                list(lower_map.keys())
            )
            for row in cursor.fetchall():
                original_name = lower_map.get(row[0])
                if original_name:
                    results[original_name] = float(row[1])
        except Exception:
            pass

    # Fill missing from SEED_PRICES or sentinel
    for n in clean_names:
        if n not in results:
            nl = n.lower()
            results[n] = SEED_PRICES.get(nl, DEFAULT_SENTINEL_PRICE)

    return results


def fetch_and_cache_scryfall_batch(
    conn: sqlite3.Connection | None,
    card_names: list[str]
) -> dict[str, float]:
    """Fetch live market prices via Scryfall collection API in batches of up to 75 cards."""
    results: dict[str, float] = {}
    if not card_names:
        return results

    unique_names = list(dict.fromkeys(n.strip() for n in card_names if n and n.strip()))

    # Process in chunks of 75
    chunk_size = 75
    for i in range(0, len(unique_names), chunk_size):
        chunk = unique_names[i:i + chunk_size]
        payload = {"identifiers": [{"name": name} for name in chunk]}
        req = urllib.request.Request(
            "https://api.scryfall.com/cards/collection",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Loreweaver/2.0 (lore-weaver.app)"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.loads(res.read().decode("utf-8"))
                for card in data.get("data", []):
                    cname = card.get("name")
                    prices = card.get("prices", {})
                    p_usd = prices.get("usd") or prices.get("usd_foil")
                    price_val = float(p_usd) if p_usd else None

                    # Fallback to EUR * 1.1 if USD missing
                    if price_val is None and prices.get("eur"):
                        price_val = round(float(prices.get("eur")) * 1.1, 2)

                    if price_val is not None and price_val > 0.0:
                        results[cname] = price_val
                        if conn is not None:
                            try:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "INSERT OR REPLACE INTO card_prices (name_lower, price_usd, source) VALUES (?, ?, ?)",
                                    (cname.lower(), price_val, "scryfall")
                                )
                            except Exception:
                                pass
                if conn is not None:
                    try:
                        conn.commit()
                    except Exception:
                        pass
        except Exception:
            # On network timeout/error, fallback gracefully
            for name in chunk:
                results[name] = get_card_price(conn, name)

    return results
