"""Post-draft 40-card knapsack deckbuilder for Magic: The Gathering.

Evaluates drafted pools (typically 40-45 cards), determines the optimal 2-color
archetype (with optional light splash), solves the 23-card non-land selection
using knapsack optimization balancing win-rates and curve targets, and calculates
an exact 17-land mana base based on colored mana pips and early-turn requirements.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

# MTG Color Constants
COLORS: Tuple[str, ...] = ("W", "U", "B", "R", "G")

COLOR_NAMES: Dict[str, str] = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green",
    "C": "Colorless",
}

COLOR_PAIRS: Dict[Tuple[str, str], str] = {
    ("W", "U"): "Azorius",
    ("U", "B"): "Dimir",
    ("B", "R"): "Rakdos",
    ("R", "G"): "Gruul",
    ("G", "W"): "Selesnya",
    ("W", "B"): "Orzhov",
    ("U", "R"): "Izzet",
    ("B", "G"): "Golgari",
    ("R", "W"): "Boros",
    ("G", "U"): "Simic",
}

BASIC_LAND_NAMES: Dict[str, str] = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
    "C": "Wastes",
}

LAND_TO_COLOR: Dict[str, str] = {
    "Plains": "W",
    "Island": "U",
    "Swamp": "B",
    "Mountain": "R",
    "Forest": "G",
    "Wastes": "C",
}

# Target curve definitions: (min_target, max_target)
TARGET_CURVE: Dict[str, Tuple[int, int]] = {
    "1": (0, 2),    # CMC <= 1
    "2": (5, 7),    # CMC == 2
    "3": (4, 6),    # CMC == 3
    "4": (3, 5),    # CMC == 4
    "5+": (2, 3),   # CMC >= 5
}

MIN_CREATURES: int = 13


@dataclass
class Card:
    """Internal normalized representation of a Magic card."""
    id: str
    name: str
    mana_cost: str = ""
    cmc: float = 0.0
    type_line: str = ""
    colors: List[str] = field(default_factory=list)
    color_identity: List[str] = field(default_factory=list)
    power: Optional[str] = None
    toughness: Optional[str] = None
    rarity: str = "common"
    oracle_text: str = ""
    gih_wr: Optional[float] = None
    grp_id: Optional[int] = None
    set: str = ""
    collector_number: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_creature(self) -> bool:
        return "Creature" in self.type_line

    @property
    def is_land(self) -> bool:
        return "Land" in self.type_line

    @property
    def cmc_bucket(self) -> str:
        c = int(math.floor(self.cmc))
        if c <= 1:
            return "1"
        elif c == 2:
            return "2"
        elif c == 3:
            return "3"
        elif c == 4:
            return "4"
        else:
            return "5+"

    @property
    def parsed_pips(self) -> Dict[str, float]:
        return parse_mana_pips(self.mana_cost)


def parse_mana_pips(mana_cost: str) -> Dict[str, float]:
    """Parse mana symbols from a mana_cost string (e.g. '{1}{W}{U}', '{B/G}').

    Returns a dictionary of color -> pip count.
    """
    pips: Dict[str, float] = {c: 0.0 for c in COLORS}
    if not mana_cost:
        return pips

    symbols = re.findall(r"\{([^}]+)\}", mana_cost)
    for sym in symbols:
        sym = sym.upper()
        if sym in pips:
            pips[sym] += 1.0
        elif "/" in sym:
            parts = sym.split("/")
            colored_parts = [p for p in parts if p in pips]
            if colored_parts:
                share = 1.0 / len(colored_parts)
                for cp in colored_parts:
                    pips[cp] += share
    return pips


def get_card_colors(mana_cost: str, colors_list: Optional[List[str]] = None) -> Set[str]:
    """Extract colored identity / colors from mana cost and explicit colors list."""
    colors = set(colors_list) if colors_list else set()
    pips = parse_mana_pips(mana_cost)
    for c, val in pips.items():
        if val > 0:
            colors.add(c)
    return colors


def is_card_castable(card: Card, allowed_colors: Set[str]) -> bool:
    """Check if card can be cast using only sources in allowed_colors."""
    if not card.mana_cost:
        # Colorless or lands
        return True

    symbols = re.findall(r"\{([^}]+)\}", card.mana_cost)
    for sym in symbols:
        sym = sym.upper()
        if sym in COLORS:
            if sym not in allowed_colors:
                return False
        elif "/" in sym:
            parts = sym.split("/")
            colored_parts = [p for p in parts if p in COLORS]
            if colored_parts:
                # Can be paid if at least one colored half is in allowed_colors
                if not any(cp in allowed_colors for cp in colored_parts):
                    return False
    return True


def is_splash_candidate(card: Card, main_colors: Set[str], splash_color: str) -> bool:
    """Determine whether a card qualifies for a light splash.

    In Limited MTG:
    - Never splash 1-drops or 2-drops (too hard to cast on curve).
    - Never splash double pips (e.g. {B}{B} or {1}{G}{G}).
    - Must require exactly 1 pip of the splash color and 0 pips of any other off-color.
    """
    if card.cmc < 3.0:
        return False

    pips = card.parsed_pips
    splash_pips = pips.get(splash_color, 0.0)
    if splash_pips != 1.0:
        return False

    for color, count in pips.items():
        if color != splash_color and color not in main_colors and count > 0:
            return False

    return True


def evaluate_card_score(card: Card) -> float:
    """Estimate the baseline standalone value of a card in limited draft."""
    if card.gih_wr is not None:
        return float(card.gih_wr) * 100.0

    rarity_scores = {
        "mythic": 62.0,
        "rare": 58.0,
        "uncommon": 54.5,
        "common": 51.5,
    }
    score = rarity_scores.get(card.rarity.lower(), 51.0)

    # Creature stat evaluation
    if card.is_creature:
        try:
            p = float(card.power) if card.power is not None and str(card.power).isdigit() else 0.0
            t = float(card.toughness) if card.toughness is not None and str(card.toughness).isdigit() else 0.0
            stat_sum = p + t
            expected_stats = max(2.0, card.cmc * 2.0)
            score += (stat_sum - expected_stats) * 1.5
        except (ValueError, TypeError):
            pass

    # Keyword bonuses
    text = (card.oracle_text or "").lower()
    if "flying" in text:
        score += 3.0
    if "deathtouch" in text:
        score += 2.5
    if "lifelink" in text:
        score += 2.0
    if "ward" in text or "hexproof" in text:
        score += 2.0
    if "flash" in text:
        score += 1.5
    if "vigilance" in text:
        score += 1.0

    # Removal / Interaction / Card Advantage heuristics
    if any(k in text for k in ("destroy target", "exile target", "deal", "damage to any target")):
        score += 5.0
    elif "counter target" in text or "return target" in text:
        score += 3.0

    if any(k in text for k in ("draw a card", "draw two", "draws")):
        score += 4.0

    return score


class DeckOptimizer:
    """Post-draft MTG deck builder optimizing 40-card decks from drafted pools."""

    def __init__(self, card_db: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.card_db: Dict[str, Dict[str, Any]] = {}
        self.grp_to_card: Dict[int, Dict[str, Any]] = {}
        if card_db is not None:
            self._ingest_card_db(card_db)
        else:
            self._load_default_card_databases()

    def _ingest_card_db(self, db_dict: Dict[str, Dict[str, Any]]) -> None:
        for k, v in db_dict.items():
            self.card_db[k] = v
            self.card_db[k.lower()] = v
            if "//" in k:
                front = k.split(" // ")[0].strip()
                self.card_db[front] = v
                self.card_db[front.lower()] = v
            grp = v.get("grpId") or v.get("grp_id")
            if grp is not None:
                try:
                    self.grp_to_card[int(grp)] = v
                except (ValueError, TypeError):
                    pass

    def _load_default_card_databases(self) -> None:
        """Find and load cards_data.json and missing_cards.json if available."""
        search_paths = [
            Path.cwd(),
            Path(__file__).resolve().parents[2],
            Path(__file__).resolve().parent,
        ]
        all_cards: List[Dict[str, Any]] = []

        for p in search_paths:
            cdata_path = p / "cards_data.json"
            if cdata_path.exists():
                try:
                    with open(cdata_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "data" in data:
                            all_cards.extend(data["data"])
                        elif isinstance(data, list):
                            all_cards.extend(data)
                except Exception:
                    pass

            mdata_path = p / "missing_cards.json"
            if mdata_path.exists():
                try:
                    with open(mdata_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            all_cards.extend(data)
                except Exception:
                    pass

            if all_cards:
                break

        for c in all_cards:
            name = c.get("name", "")
            if name:
                self.card_db[name] = c
                self.card_db[name.lower()] = c
                if "//" in name:
                    front = name.split(" // ")[0].strip()
                    self.card_db[front] = c
                    self.card_db[front.lower()] = c
            grp = c.get("grpId") or c.get("grp_id")
            if grp is not None:
                try:
                    self.grp_to_card[int(grp)] = c
                except (ValueError, TypeError):
                    pass

        # Check SQLite data/cards.db
        for p in search_paths:
            db_path = p / "data" / "cards.db"
            if db_path.exists():
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT grp_id, name, mana_cost, cmc, type_line, colors, rarity FROM cards")
                    for row in cursor.fetchall():
                        gid, name, mana_cost, cmc, type_line, colors, rarity = row
                        card_info = {
                            "grpId": gid,
                            "name": name,
                            "mana_cost": mana_cost or "",
                            "cmc": float(cmc or 0.0),
                            "type_line": type_line or "",
                            "colors": colors.split(",") if colors else [],
                            "rarity": rarity or "common",
                        }
                        self.grp_to_card[int(gid)] = card_info
                        self.card_db[name] = card_info
                    conn.close()
                except Exception:
                    pass

    def normalize_card(self, item: Any, index: int = 0) -> Card:
        """Converts raw inputs (dict, str, int grpId, tuple) into a standard Card object."""
        if isinstance(item, Card):
            return item

        card_dict: Dict[str, Any] = {}
        raw_input: Dict[str, Any] = {}

        if isinstance(item, int):
            card_dict = copy.deepcopy(self.grp_to_card.get(item, {}))
            if not card_dict:
                card_dict = {"grpId": item, "name": f"Card {item}"}
            raw_input = dict(card_dict)
        elif isinstance(item, str):
            name = item.strip()
            card_dict = copy.deepcopy(self.card_db.get(name) or self.card_db.get(name.lower()) or {})
            if not card_dict:
                card_dict = {"name": name}
            raw_input = {"name": name}
        elif isinstance(item, dict):
            raw_input = dict(item)
            grp = item.get("grpId") or item.get("grp_id")
            name = item.get("name", "")
            base_db = {}
            if grp is not None and int(grp) in self.grp_to_card:
                base_db = copy.deepcopy(self.grp_to_card[int(grp)])
            elif name:
                base_db = copy.deepcopy(self.card_db.get(name) or self.card_db.get(name.lower()) or {})
            base_db.update(item)
            card_dict = base_db
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            _, val = item
            if isinstance(val, (int, str, dict)):
                return self.normalize_card(val, index)

        cid = card_dict.get("id") or f"card_{index}_{card_dict.get('name', 'unknown')}"
        name = card_dict.get("name", "Unknown Card")
        mana_cost = card_dict.get("mana_cost", "")
        cmc = float(card_dict.get("cmc", 0.0))
        type_line = card_dict.get("type_line", "")
        colors = list(card_dict.get("colors", []))
        color_identity = list(card_dict.get("color_identity", []))
        power = card_dict.get("power")
        toughness = card_dict.get("toughness")
        rarity = card_dict.get("rarity", "common")
        oracle_text = card_dict.get("oracle_text", "")
        gih_wr = card_dict.get("gih_wr") or card_dict.get("win_rate")
        grp_id = card_dict.get("grpId") or card_dict.get("grp_id")
        c_set = card_dict.get("set", "")
        collector_number = card_dict.get("collector_number", "")

        return Card(
            id=cid,
            name=name,
            mana_cost=mana_cost,
            cmc=cmc,
            type_line=type_line,
            colors=colors,
            color_identity=color_identity,
            power=power,
            toughness=toughness,
            rarity=rarity,
            oracle_text=oracle_text,
            gih_wr=float(gih_wr) if gih_wr is not None else None,
            grp_id=int(grp_id) if grp_id is not None else None,
            set=c_set,
            collector_number=collector_number,
            raw_data=card_dict if card_dict else raw_input,
        )

    def normalize_pool(self, raw_pool: Sequence[Any]) -> List[Card]:
        """Expands raw pool input into an individual list of Card instances."""
        cards: List[Card] = []
        idx = 0
        for entry in raw_pool:
            if isinstance(entry, (tuple, list)) and len(entry) == 2:
                count, item = entry
                for _ in range(int(count)):
                    cards.append(self.normalize_card(item, idx))
                    idx += 1
            elif isinstance(entry, dict) and "count" in entry:
                count = int(entry["count"])
                card_data = {k: v for k, v in entry.items() if k != "count"}
                for _ in range(count):
                    cards.append(self.normalize_card(card_data, idx))
                    idx += 1
            elif isinstance(entry, dict) and "quantity" in entry:
                count = int(entry["quantity"])
                card_data = {k: v for k, v in entry.items() if k != "quantity"}
                for _ in range(count):
                    cards.append(self.normalize_card(card_data, idx))
                    idx += 1
            else:
                cards.append(self.normalize_card(entry, idx))
                idx += 1
        return cards

    def _score_deck_selection(
        self,
        deck: List[Card],
        target_count: int,
        splash_color: Optional[str] = None,
    ) -> float:
        """Evaluates a selection of non-land cards against win rate, curve, and creature floor."""
        if not deck:
            return -10000.0

        # Baseline value sum
        total_val = sum(evaluate_card_score(c) for c in deck)

        # Count curve buckets
        curve_counts: Dict[str, int] = {k: 0 for k in TARGET_CURVE}
        creatures = 0
        splash_cards = 0

        for c in deck:
            curve_counts[c.cmc_bucket] += 1
            if c.is_creature:
                creatures += 1
            if splash_color and splash_color in c.parsed_pips and c.parsed_pips[splash_color] > 0:
                splash_cards += 1

        curve_penalty = 0.0

        # CMC <= 1: target (0, 2)
        c1 = curve_counts["1"]
        if c1 > 2:
            curve_penalty += (c1 - 2) * 10.0

        # CMC 2: target (5, 7) - essential for limited tempo
        c2 = curve_counts["2"]
        if c2 < 5:
            curve_penalty += (5 - c2) * 15.0
        elif c2 > 7:
            curve_penalty += (c2 - 7) * 6.0

        # CMC 3: target (4, 6)
        c3 = curve_counts["3"]
        if c3 < 4:
            curve_penalty += (4 - c3) * 9.0
        elif c3 > 6:
            curve_penalty += (c3 - 6) * 7.0

        # CMC 4: target (3, 5)
        c4 = curve_counts["4"]
        if c4 < 3:
            curve_penalty += (3 - c4) * 7.0
        elif c4 > 5:
            curve_penalty += (c4 - 5) * 8.0

        # CMC >= 5: target (2, 3) - high CMC clutter heavily penalized
        c5 = curve_counts["5+"]
        if c5 < 2:
            curve_penalty += (2 - c5) * 5.0
        elif c5 > 3:
            curve_penalty += (c5 - 3) * 18.0

        # Creature count penalty / bonus (min 13)
        creature_penalty = 0.0
        if creatures < MIN_CREATURES:
            creature_penalty += (MIN_CREATURES - creatures) * 22.0
        elif 13 <= creatures <= 17:
            creature_penalty -= 5.0
        elif creatures > 18:
            creature_penalty += (creatures - 18) * 6.0

        # Splash penalty (consistency cost)
        splash_penalty = 0.0
        if splash_cards > 0:
            splash_penalty += splash_cards * 4.0
            if splash_cards > 3:
                splash_penalty += (splash_cards - 3) * 25.0

        # Size penalty if deck cannot reach target_count
        size_penalty = 0.0
        if len(deck) != target_count:
            size_penalty += abs(target_count - len(deck)) * 50.0

        return total_val - curve_penalty - creature_penalty - splash_penalty - size_penalty

    def solve_knapsack(
        self,
        candidate_cards: List[Card],
        target_count: int = 23,
        splash_color: Optional[str] = None,
    ) -> List[Card]:
        """Selects the best `target_count` non-land cards maximizing win-rate and curve balance.

        Employs seeded greedy initialization followed by multi-pass k-swap local search.
        """
        n = len(candidate_cards)
        if n <= target_count:
            return list(candidate_cards)

        seeds: List[List[Card]] = []

        # Deterministic sorting with tie-breaking
        by_quality = sorted(
            candidate_cards,
            key=lambda c: (evaluate_card_score(c), -c.cmc, c.name, c.id),
            reverse=True,
        )
        seeds.append(by_quality[:target_count])

        # Seed 2: Curve-balanced seed
        curve_seed: List[Card] = []
        buckets: Dict[str, List[Card]] = {k: [] for k in TARGET_CURVE}
        for c in by_quality:
            buckets[c.cmc_bucket].append(c)

        target_mins = {"1": 1, "2": 5, "3": 4, "4": 3, "5+": 2}
        for b_name, count in target_mins.items():
            curve_seed.extend(buckets[b_name][:count])

        remaining_candidates = [c for c in by_quality if c not in curve_seed]
        needed = target_count - len(curve_seed)
        if needed > 0:
            curve_seed.extend(remaining_candidates[:needed])
        elif needed < 0:
            curve_seed = curve_seed[:target_count]
        seeds.append(curve_seed)

        # Seed 3: Creature-floor prioritized seed
        creatures = [c for c in by_quality if c.is_creature]
        creature_seed = list(creatures[:max(MIN_CREATURES, 14)])
        rem = [c for c in by_quality if c not in creature_seed]
        creature_seed.extend(rem[: target_count - len(creature_seed)])
        seeds.append(creature_seed[:target_count])

        # Optimize each seed via hill climbing (1-swap neighborhood)
        best_overall_deck: List[Card] = seeds[0]
        best_overall_score = self._score_deck_selection(best_overall_deck, target_count, splash_color)

        for seed in seeds:
            current_selected = list(seed)
            current_unselected = [c for c in candidate_cards if c not in current_selected]
            current_score = self._score_deck_selection(current_selected, target_count, splash_color)

            improved = True
            iterations = 0
            while improved and iterations < 50:
                improved = False
                iterations += 1
                best_swap: Optional[Tuple[int, int, float]] = None
                best_gain = 0.0

                for i, in_card in enumerate(current_selected):
                    for j, out_card in enumerate(current_unselected):
                        trial = list(current_selected)
                        trial[i] = out_card
                        sc = self._score_deck_selection(trial, target_count, splash_color)
                        gain = sc - current_score
                        if gain > best_gain + 1e-4:
                            best_gain = gain
                            best_swap = (i, j, sc)

                if best_swap:
                    i, j, sc = best_swap
                    in_c = current_selected[i]
                    out_c = current_unselected[j]
                    current_selected[i] = out_c
                    current_unselected[j] = in_c
                    current_score = sc
                    improved = True

            if current_score > best_overall_score + 1e-4:
                best_overall_score = current_score
                best_overall_deck = current_selected

        return best_overall_deck

    def solve_mana_split(
        self,
        maindeck_spells: List[Card],
        primary_colors: Sequence[str],
        splash_color: Optional[str] = None,
        total_lands: int = 17,
        nonbasic_lands: Optional[List[Card]] = None,
    ) -> Dict[str, int]:
        """Calculates the exact basic mana split based on pips and early-turn needs.

        Guaranteed to sum to exactly `total_lands - len(nonbasic_lands)`.
        Uses weighted early-turn requirements and the Largest Remainder Method (Hamilton quota).
        """
        land_split: Dict[str, int] = {BASIC_LAND_NAMES[c]: 0 for c in COLORS}
        if total_lands <= 0:
            return land_split

        drafted_nonbasics_count = len(nonbasic_lands) if nonbasic_lands else 0
        basic_lands_needed = max(0, total_lands - drafted_nonbasics_count)

        if basic_lands_needed == 0:
            return land_split

        active_primary = [c for c in primary_colors if c in COLORS]
        if not active_primary:
            active_primary = ["U", "B"]

        # Calculate weighted colored demand
        weighted_demand: Dict[str, float] = {c: 0.0 for c in COLORS}
        for spell in maindeck_spells:
            pips = spell.parsed_pips
            cmc = spell.cmc
            # Early turn weights: turn 1 & 2 pips are critical
            if cmc <= 1:
                mult = 2.4
            elif cmc == 2:
                mult = 1.8
            elif cmc == 3:
                mult = 1.3
            else:
                mult = 1.0

            for color, pip_count in pips.items():
                if pip_count > 0:
                    intensity = 1.3 if pip_count >= 2.0 else 1.0
                    weighted_demand[color] += pip_count * mult * intensity

        # Case 1: Monocolor deck
        if len(active_primary) == 1 and not splash_color:
            land_split[BASIC_LAND_NAMES[active_primary[0]]] = basic_lands_needed
            return land_split

        # Case 2: Allocate splash lands first
        splash_lands_alloc = 0
        if splash_color and splash_color in COLORS and splash_color not in active_primary:
            splash_spells_count = sum(
                1 for s in maindeck_spells if splash_color in s.parsed_pips and s.parsed_pips[splash_color] > 0
            )
            if splash_spells_count >= 1:
                splash_lands_alloc = 2 if splash_spells_count <= 2 else 3
                splash_lands_alloc = min(splash_lands_alloc, basic_lands_needed - 2 * len(active_primary))
                land_split[BASIC_LAND_NAMES[splash_color]] = splash_lands_alloc

        remaining_lands = basic_lands_needed - splash_lands_alloc

        # Case 3: Distribute remaining lands between primary colors
        demands = [weighted_demand.get(c, 0.0) for c in active_primary]
        total_primary_demand = sum(demands)

        if total_primary_demand <= 0.0:
            base = remaining_lands // len(active_primary)
            rem = remaining_lands % len(active_primary)
            for idx, c in enumerate(active_primary):
                land_split[BASIC_LAND_NAMES[c]] = base + (1 if idx < rem else 0)
            return land_split

        # Hamilton quota / Largest Remainder Method
        quotas: List[float] = [(d / total_primary_demand) * remaining_lands for d in demands]
        floors: List[int] = [int(math.floor(q)) for q in quotas]

        # Enforce minimum land floor for active colors in 2-color limited
        min_floor = 5 if len(active_primary) == 2 and remaining_lands >= 12 else 1
        for idx in range(len(floors)):
            floors[idx] = max(floors[idx], min_floor)

        current_sum = sum(floors)
        if current_sum < remaining_lands:
            remainders = [(quotas[i] - int(math.floor(quotas[i])), i) for i in range(len(quotas))]
            remainders.sort(key=lambda x: (x[0], -quotas[x[1]]), reverse=True)
            diff = remaining_lands - current_sum
            for _, i in remainders[:diff]:
                floors[i] += 1
        elif current_sum > remaining_lands:
            diff = current_sum - remaining_lands
            for _ in range(diff):
                max_idx = max(range(len(floors)), key=lambda i: floors[i])
                floors[max_idx] -= 1

        for idx, c in enumerate(active_primary):
            land_split[BASIC_LAND_NAMES[c]] = floors[idx]

        return land_split

    def evaluate_pair(
        self,
        c1: str,
        c2: str,
        non_lands: List[Card],
        target_spells: int = 23,
        splash_color: Optional[str] = None,
    ) -> Tuple[float, List[Card]]:
        """Evaluates a single color pair configuration and returns its score and selected deck."""
        main_colors = {c1, c2}
        candidates: List[Card] = []

        for card in non_lands:
            if is_card_castable(card, main_colors):
                candidates.append(card)
            elif splash_color and is_splash_candidate(card, main_colors, splash_color):
                candidates.append(card)

        selected = self.solve_knapsack(candidates, target_count=target_spells, splash_color=splash_color)
        score = self._score_deck_selection(selected, target_spells, splash_color)
        return score, selected

    def evaluate_all_configurations(
        self,
        non_lands: List[Card],
        target_spells: int = 23,
        allow_splash: bool = True,
    ) -> List[Dict[str, Any]]:
        """Evaluates all 10 two-color pairs (and monocolor, plus potential splashes)."""
        configs: List[Dict[str, Any]] = []

        # Monocolor evaluations (for pools heavily skewed into one color)
        for c in COLORS:
            mono_candidates = [card for card in non_lands if is_card_castable(card, {c})]
            if len(mono_candidates) >= target_spells:
                selected = self.solve_knapsack(mono_candidates, target_spells)
                # Monocolor consistency bonus (zero chance of color screw)
                score = self._score_deck_selection(selected, target_spells) + 5.0
                configs.append({
                    "colors": (c,),
                    "pair_name": f"Mono-{COLOR_NAMES.get(c, c)}",
                    "splash": None,
                    "score": score,
                    "deck": selected,
                })

        # 2-color pair evaluations
        for (c1, c2), pair_name in COLOR_PAIRS.items():
            score_pure, deck_pure = self.evaluate_pair(c1, c2, non_lands, target_spells, splash_color=None)
            c1_count = sum(1 for card in deck_pure if c1 in card.colors)
            c2_count = sum(1 for card in deck_pure if c2 in card.colors)
            # Only consider a 2-color archetype valid if it actually plays both colors
            if c1_count > 0 and c2_count > 0:
                configs.append({
                    "colors": (c1, c2),
                    "pair_name": pair_name,
                    "splash": None,
                    "score": score_pure,
                    "deck": deck_pure,
                })

            # Light splash builds
            if allow_splash:
                for c3 in COLORS:
                    if c3 != c1 and c3 != c2:
                        has_splash_cards = any(
                            is_splash_candidate(card, {c1, c2}, c3) and evaluate_card_score(card) >= 54.0
                            for card in non_lands
                        )
                        if has_splash_cards:
                            score_splash, deck_splash = self.evaluate_pair(
                                c1, c2, non_lands, target_spells, splash_color=c3
                            )
                            uses_splash = any(c3 in c.parsed_pips and c.parsed_pips[c3] > 0 for c in deck_splash)
                            if uses_splash:
                                configs.append({
                                    "colors": (c1, c2),
                                    "pair_name": f"{pair_name} Splash {COLOR_NAMES.get(c3, c3)}",
                                    "splash": c3,
                                    "score": score_splash,
                                    "deck": deck_splash,
                                })

        configs.sort(key=lambda x: (x["score"], x["pair_name"]), reverse=True)
        return configs

    def format_arena_decklist(
        self,
        maindeck_spells: List[Card],
        basic_lands: Dict[str, int],
        sideboard: List[Card],
        nonbasic_lands: Optional[List[Card]] = None,
    ) -> str:
        """Formats the deck and sideboard for MTG Arena direct text import."""
        lines: List[str] = ["Deck"]

        spell_counts: Counter[str] = Counter()
        spell_meta: Dict[str, Card] = {}
        for s in maindeck_spells:
            spell_counts[s.name] += 1
            spell_meta[s.name] = s

        sorted_spells = sorted(spell_counts.keys(), key=lambda n: (spell_meta[n].cmc, n))
        for name in sorted_spells:
            count = spell_counts[name]
            meta = spell_meta[name]
            if meta.set and meta.collector_number:
                lines.append(f"{count} {name} ({meta.set.upper()}) {meta.collector_number}")
            else:
                lines.append(f"{count} {name}")

        if nonbasic_lands:
            nb_counts: Counter[str] = Counter()
            nb_meta: Dict[str, Card] = {}
            for l in nonbasic_lands:
                nb_counts[l.name] += 1
                nb_meta[l.name] = l
            for name in sorted(nb_counts.keys()):
                meta = nb_meta[name]
                if meta.set and meta.collector_number:
                    lines.append(f"{nb_counts[name]} {name} ({meta.set.upper()}) {meta.collector_number}")
                else:
                    lines.append(f"{nb_counts[name]} {name}")

        for land_name, count in sorted(basic_lands.items()):
            if count > 0:
                lines.append(f"{count} {land_name}")

        lines.append("")
        lines.append("Sideboard")
        sb_counts: Counter[str] = Counter()
        sb_meta: Dict[str, Card] = {}
        for s in sideboard:
            sb_counts[s.name] += 1
            sb_meta[s.name] = s

        for name in sorted(sb_counts.keys(), key=lambda n: (sb_meta[n].cmc, n)):
            count = sb_counts[name]
            meta = sb_meta[name]
            if meta.set and meta.collector_number:
                lines.append(f"{count} {name} ({meta.set.upper()}) {meta.collector_number}")
            else:
                lines.append(f"{count} {name}")

        return "\n".join(lines)

    def optimize(
        self,
        pool: Sequence[Any],
        target_spells: int = 23,
        target_lands: int = 17,
        allow_splash: bool = True,
    ) -> Dict[str, Any]:
        """Runs the complete post-draft optimization pipeline.

        Returns structured dict with maindeck (23 spells + 17 lands), sideboard, stats,
        and arena_decklist_text formatted for MTGA import.
        """
        all_pool_cards = self.normalize_pool(pool)
        if not all_pool_cards:
            return {
                "deck_name": "Empty Deck",
                "colors": [],
                "splash_color": None,
                "maindeck": [],
                "maindeck_spells": [],
                "maindeck_lands": [],
                "sideboard": [],
                "stats": {
                    "total_cards": 0,
                    "spells_count": 0,
                    "lands_count": 0,
                    "creatures_count": 0,
                    "noncreatures_count": 0,
                    "creature_ratio": 0.0,
                    "curve": {k: 0 for k in TARGET_CURVE},
                    "color_pips": {c: 0 for c in COLORS},
                    "mana_split": {},
                    "score": 0.0,
                },
                "arena_decklist_text": "Deck\n\nSideboard\n",
            }

        # Separate drafted nonbasic lands from spells
        drafted_non_lands: List[Card] = []
        drafted_lands: List[Card] = []
        for card in all_pool_cards:
            if card.is_land and card.name not in BASIC_LAND_NAMES.values():
                drafted_lands.append(card)
            else:
                drafted_non_lands.append(card)

        eff_target_spells = min(target_spells, len(drafted_non_lands))

        # Evaluate all color pair options
        configs = self.evaluate_all_configurations(
            drafted_non_lands,
            target_spells=eff_target_spells,
            allow_splash=allow_splash,
        )

        best_config = configs[0] if configs else {
            "colors": ("U", "B"),
            "pair_name": "Dimir",
            "splash": None,
            "score": 0.0,
            "deck": drafted_non_lands[:eff_target_spells],
        }

        selected_spells: List[Card] = list(best_config["deck"])
        primary_colors: Tuple[str, ...] = best_config["colors"]
        splash_color: Optional[str] = best_config["splash"]

        # If selected_spells is short of eff_target_spells (e.g. extreme 5-color soup), backfill from pool
        if len(selected_spells) < eff_target_spells:
            selected_ids = {c.id for c in selected_spells}
            pool_remaining = [c for c in drafted_non_lands if c.id not in selected_ids]
            pool_remaining.sort(key=lambda c: (c.gih_wr, -c.cmc), reverse=True)
            needed = eff_target_spells - len(selected_spells)
            selected_spells.extend(pool_remaining[:needed])

        # Check usable nonbasic lands drafted in pool
        usable_nonbasic_lands: List[Card] = []
        for land in drafted_lands:
            text = (land.oracle_text or "").upper()
            if any(f"{{{c}}}" in text for c in primary_colors) or (splash_color and f"{{{splash_color}}}" in text):
                usable_nonbasic_lands.append(land)

        # Solve mana split
        basic_mana_split = self.solve_mana_split(
            maindeck_spells=selected_spells,
            primary_colors=primary_colors,
            splash_color=splash_color,
            total_lands=target_lands,
            nonbasic_lands=usable_nonbasic_lands,
        )

        # Build individual land card dicts for the 17 lands
        maindeck_lands_data: List[Dict[str, Any]] = []
        for l in usable_nonbasic_lands:
            maindeck_lands_data.append(l.raw_data or {"name": l.name, "is_basic": False, "type_line": "Land"})

        for land_name, count in sorted(basic_mana_split.items()):
            color = LAND_TO_COLOR.get(land_name, "C")
            for _ in range(count):
                maindeck_lands_data.append({
                    "name": land_name,
                    "type_line": f"Basic Land — {land_name}",
                    "mana_cost": "",
                    "cmc": 0.0,
                    "colors": [],
                    "color_identity": [color] if color != "C" else [],
                    "rarity": "common",
                    "is_basic": True,
                })

        # Ensure exact 40-card invariant for any drafted pool with >= 40 cards
        if len(all_pool_cards) >= 40:
            current_total = len(selected_spells) + len(maindeck_lands_data)
            if current_total < 40:
                shortfall = 40 - current_total
                primary_c = primary_colors[0] if primary_colors else "U"
                primary_land = BASIC_LAND_NAMES.get(primary_c, "Island")
                for _ in range(shortfall):
                    maindeck_lands_data.append({
                        "name": primary_land,
                        "type_line": f"Basic Land — {primary_land}",
                        "mana_cost": "",
                        "cmc": 0.0,
                        "colors": [],
                        "color_identity": [primary_c],
                        "rarity": "common",
                        "is_basic": True,
                    })
                basic_mana_split[primary_land] = basic_mana_split.get(primary_land, 0) + shortfall

        # Assemble sideboard
        selected_ids = {c.id for c in selected_spells}
        usable_land_ids = {l.id for l in usable_nonbasic_lands}
        sideboard: List[Card] = []
        for c in all_pool_cards:
            if c.id not in selected_ids and c.id not in usable_land_ids:
                sideboard.append(c)

        # Stats calculation
        curve_stats: Dict[str, int] = {k: 0 for k in TARGET_CURVE}
        pip_stats: Dict[str, float] = {c: 0.0 for c in COLORS}
        creatures_count = 0

        for spell in selected_spells:
            curve_stats[spell.cmc_bucket] += 1
            if spell.is_creature:
                creatures_count += 1
            pips = spell.parsed_pips
            for c, val in pips.items():
                pip_stats[c] += val

        spells_count = len(selected_spells)
        lands_count = len(maindeck_lands_data)
        nonbasic_count = len(usable_nonbasic_lands)
        creature_ratio = round(creatures_count / max(1, spells_count), 4)
        active_lands_dict = {k: v for k, v in basic_mana_split.items() if v > 0}

        maindeck_spells_data = [
            s.raw_data if s.raw_data else {
                "name": s.name,
                "cmc": s.cmc,
                "mana_cost": s.mana_cost,
                "type_line": s.type_line,
                "colors": s.colors,
                "rarity": s.rarity,
            }
            for s in selected_spells
        ]

        arena_decklist_text = self.format_arena_decklist(
            maindeck_spells=selected_spells,
            basic_lands=active_lands_dict,
            sideboard=sideboard,
            nonbasic_lands=usable_nonbasic_lands,
        )

        return {
            "deck_name": best_config["pair_name"],
            "colors": list(primary_colors),
            "splash_color": splash_color,
            "maindeck": maindeck_spells_data + maindeck_lands_data,
            "maindeck_spells": maindeck_spells_data,
            "maindeck_lands": maindeck_lands_data,
            "sideboard": [sb.raw_data or {"name": sb.name} for sb in sideboard],
            "stats": {
                "total_cards": spells_count + lands_count,
                "spells_count": spells_count,
                "lands_count": lands_count,
                "nonbasic_lands_count": nonbasic_count,
                "creatures_count": creatures_count,
                "noncreatures_count": spells_count - creatures_count,
                "creature_ratio": creature_ratio,
                "curve": curve_stats,
                "color_pips": {k: int(round(v)) for k, v in pip_stats.items()},
                "mana_split": active_lands_dict,
                "score": round(best_config["score"], 2),
            },
            "arena_decklist_text": arena_decklist_text,
        }


def optimize_deck(
    pool: Sequence[Any],
    target_spells: int = 23,
    target_lands: int = 17,
    allow_splash: bool = True,
    card_db: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Convenience top-level entry point for post-draft deck optimization."""
    optimizer = DeckOptimizer(card_db=card_db)
    return optimizer.optimize(
        pool=pool,
        target_spells=target_spells,
        target_lands=target_lands,
        allow_splash=allow_splash,
    )
