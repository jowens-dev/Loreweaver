"""FastAPI backend service for Loreweaver deck recommendations and analysis."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure scripts directory is on Python path
SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import db  # noqa: E402
import hybrid_engine  # noqa: E402

app = FastAPI(
    title="Loreweaver API",
    description="Objective MTG Commander deck recommendations and analytics engine",
    version="1.0.0"
)

# Standardized CORS middleware (RFC-compliant wildcard without invalid credentials flag)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Heuristic classifiers for card role bucketing
RAMP_REGEX = re.compile(
    r"\badd\b.*\bmana\b|\badd\s+({[WUBRGCCX/]+}|\w+\s+mana)|search\s+your\s+library\s+for\s+a\s+.*land|create\s+.*Treasure",
    re.IGNORECASE
)
DRAW_REGEX = re.compile(
    r"\bdraw\s+(\w+|\d+)?\s*cards?\b|\bdraws\s+a\s+card\b",
    re.IGNORECASE
)
REMOVAL_REGEX = re.compile(
    r"\b(destroy|exile|counter)\b\s+target|deals?\s+(\d+|x)\s+damage\s+to\s+target|damage\s+to\s+any\s+target|counter\s+target\s+spell",
    re.IGNORECASE
)


def classify_lane(card: dict[str, Any]) -> str:
    """Classify a card into its primary operational lane."""
    raw_type = (card.get("type_line") or "").lower()
    text = card.get("oracle_text") or ""

    if "land" in raw_type:
        return "lands"
    if RAMP_REGEX.search(text):
        return "ramp"
    if DRAW_REGEX.search(text):
        return "draw"
    if REMOVAL_REGEX.search(text):
        return "removal"
    return "synergy"


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Health check endpoint confirming database status and card counts."""
    try:
        conn = db.get_connection()
        total_cards = db.get_card_count(conn)
        conn.close()
        return {
            "status": "healthy",
            "database": "connected",
            "total_cards": total_cards
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.get("/api/recommendations")
def get_recommendations(
    commander: str = Query(default="", description="Name of the commander to build around"),
    spice: int = Query(default=50, ge=0, le=100, description="Flavor spice dial (0=Staples, 50=Balanced, 100=Deep Cuts)")
) -> list[dict[str, Any]]:
    """Return categorized card recommendations matching the commander's color identity and spice level."""
    try:
        conn = db.get_connection()
    except Exception as e:
        return [{"title": "Error", "cards": [{"name": f"Database error: {e}", "mana_cost": "", "type_line": ""}]}]

    comm_card = None
    if commander.strip():
        comm_card = db.get_card_by_name(conn, commander.strip())

    # Resolve commander color identity (default to colorless if not found or empty)
    comm_identity = comm_card.get("color_identity", []) if comm_card else []
    comm_subtypes = set(s.lower() for s in (comm_card.get("subtypes") or [])) if comm_card else set()
    comm_keywords = set(k.lower() for k in (comm_card.get("keywords") or [])) if comm_card else set()

    # Query pool of legal cards in this color identity
    candidates = db.get_cards_by_identity(conn, comm_identity, limit=350)
    conn.close()

    if not candidates:
        return []

    # Score cards based on spice level and commander synergy
    scored_candidates = []
    for card in candidates:
        # Avoid recommending the commander in the 99
        if comm_card and card["name_lower"] == comm_card["name_lower"]:
            continue

        rank = card.get("edhrec_rank") or 15000
        card_subtypes = set(s.lower() for s in card.get("subtypes", []))
        card_keywords = set(k.lower() for k in card.get("keywords", []))
        oracle_lower = (card.get("oracle_text") or "").lower()

        # Check synergy match
        shared_subs = len(comm_subtypes.intersection(card_subtypes))
        shared_kws = len(comm_keywords.intersection(card_keywords))
        for kw in comm_keywords:
            if kw and kw in oracle_lower:
                shared_kws += 1

        synergy_score = (shared_subs * 4) + (shared_kws * 2)

        # Spice weighting
        if spice < 34:
            # Low Spice: Prioritize premier staples (lowest EDHREC rank)
            sort_weight = -rank + (synergy_score * 50)
        elif spice > 66:
            # High Spice: Prioritize synergistic deep cuts (high EDHREC rank + high synergy)
            is_niche = 1 if rank > 600 else 0
            sort_weight = (synergy_score * 500) + (is_niche * 300) - (rank * 0.1)
        else:
            # Balanced: Harmonize synergy with baseline playability
            sort_weight = (synergy_score * 150) - (rank * 0.5)

        lane = classify_lane(card)
        scored_candidates.append((sort_weight, lane, card))

    # Sort candidates by calculated weight descending
    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    # Bucket into swimlanes (at most 8 cards per lane)
    lane_order = ["ramp", "draw", "removal", "synergy", "lands"]
    lanes: dict[str, list[dict[str, Any]]] = {k: [] for k in lane_order}

    for _, lane, card in scored_candidates:
        target_lane = lane if lane in lanes else "synergy"
        if len(lanes[target_lane]) < 8:
            lanes[target_lane].append({
                "name": card["name"],
                "mana_cost": card.get("mana_cost") or "",
                "type_line": card.get("type_line") or "",
                "oracle_text": card.get("oracle_text") or "",
                "image_url": card.get("image_url") or "",
                "edhrec_rank": card.get("edhrec_rank"),
                "category": target_lane.capitalize()
            })

    lane_titles = {
        "ramp": "Ramp Spells",
        "draw": "Card Advantage",
        "removal": "Removal & Answers",
        "synergy": "Thematic Synergy",
        "lands": "Recommended Lands"
    }

    return [
        {"title": lane_titles[lane_key], "cards": lanes[lane_key]}
        for lane_key in lane_order
        if lanes[lane_key]
    ]


class AnalyzeRequest(BaseModel):
    commander: str = Field(default="", description="Name of the commander to build around")
    decklist: str = Field(description="Raw text decklist with quantities and card names")
    spice: int = Field(default=50, ge=0, le=100, description="Flavor spice dial (0=Staples, 50=Balanced, 100=Deep Cuts)")


@app.post("/api/analyze")
def analyze_deck_endpoint(req: AnalyzeRequest) -> dict[str, Any]:
    """Analyze a full Commander decklist: compute mana curve, resource profile, and tactical cut recommendations."""
    try:
        conn = db.get_connection()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")

    try:
        comm_card = None
        if req.commander.strip():
            canonical = db.resolve_card_name(conn, req.commander.strip())
            comm_card = db.get_card_by_name(conn, canonical)

        comm_from_deck, mainboard, unmapped = hybrid_engine.parse_decklist_text(req.decklist, conn)
        active_commander = comm_card or comm_from_deck

        analysis = hybrid_engine.analyze_deck(active_commander, mainboard, req.spice, conn)
        analysis["unmapped_cards"] = unmapped
        return analysis
    finally:
        conn.close()
