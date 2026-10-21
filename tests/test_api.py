"""Tests for the Loreweaver FastAPI endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["total_cards"] >= 30000


def test_recommendations_endpoint_colorless():
    response = client.get("/api/recommendations?commander=Kozilek,%20the%20Great%20Distortion&spice=50")
    assert response.status_code == 200
    lanes = response.json()
    assert len(lanes) > 0

    lane_titles = [lane["title"] for lane in lanes]
    assert "Ramp Spells" in lane_titles or "Thematic Synergy" in lane_titles

    for lane in lanes:
        assert "title" in lane
        assert "cards" in lane
        for card in lane["cards"]:
            assert "name" in card
            assert "type_line" in card


def test_recommendations_endpoint_spice_shift():
    # Test low spice (staples) vs high spice (deep cuts)
    res_low = client.get("/api/recommendations?commander=Belbe,%20Corrupted%20Observer&spice=10")
    res_high = client.get("/api/recommendations?commander=Belbe,%20Corrupted%20Observer&spice=90")

    assert res_low.status_code == 200
    assert res_high.status_code == 200

    cards_low = [c["name"] for lane in res_low.json() for c in lane["cards"]]
    cards_high = [c["name"] for lane in res_high.json() for c in lane["cards"]]

    # They should not be identical
    assert cards_low != cards_high


def test_analyze_deck_endpoint_belbe():
    belbe_deck_path = REPO_ROOT / "analysis" / "golden_decks" / "belbe.txt"
    with open(belbe_deck_path) as f:
        deck_text = f.read()

    response = client.post(
        "/api/analyze",
        json={"commander": "Belbe, Corrupted Observer", "decklist": deck_text, "spice": 50}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["commander"] == "Belbe, Corrupted Observer"
    assert data["deck_stats"]["card_count"] == 100
    assert "Colorless Big-Mana" in data["resource_profile"]["engine_type"]
    assert len(data["cuts"]) > 0

    cut_names = [c["card"] for c in data["cuts"]]
    assert "Triskaidekaphobia" in cut_names
    assert "Portal to Phyrexia" not in cut_names
    assert "Portal to Phyrexia" in data["protected_pillars"]
