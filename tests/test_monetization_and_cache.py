"""Tests for Cloudflare edge caching headers, TCGplayer mass entry export, and monetization integration."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from fastapi.testclient import TestClient
from api import app
import db
import deck_builder
import deck_exporter

client = TestClient(app)


def test_api_search_cache_control_headers():
    """Verify that /api/search returns 24h edge cache headers for Cloudflare and browsers."""
    response = client.get("/api/search?q=sol&commanders_only=false&limit=5")
    assert response.status_code == 200
    cache_control = response.headers.get("Cache-Control", "")
    assert "public" in cache_control
    assert "max-age=86400" in cache_control
    assert "s-maxage=86400" in cache_control
    assert "stale-while-revalidate=604800" in cache_control


def test_api_recommendations_cache_control_headers():
    """Verify that /api/recommendations returns 1h edge cache headers."""
    response = client.get("/api/recommendations?commander=Kozilek,%20the%20Great%20Distortion&spice=50")
    assert response.status_code == 200
    cache_control = response.headers.get("Cache-Control", "")
    assert "public" in cache_control
    assert "max-age=3600" in cache_control
    assert "s-maxage=3600" in cache_control


def test_api_swap_candidates_cache_control_headers():
    """Verify that /api/swap-candidates returns 1h edge cache headers."""
    response = client.get(
        "/api/swap-candidates?card_name=Sol%20Ring&commander=Belbe,%20Corrupted%20Observer&category=ramp&bracket=3"
    )
    assert response.status_code == 200
    cache_control = response.headers.get("Cache-Control", "")
    assert "public" in cache_control
    assert "max-age=3600" in cache_control
    assert "s-maxage=3600" in cache_control


def test_tcgplayer_export_exact_100_cards():
    """Verify that TCGplayer mass entry export generates exact 100 cards with clean format."""
    conn = db.get_connection()
    deck = deck_builder.build_deck(
        conn=conn,
        commander_name="Belbe, Corrupted Observer",
        bracket=3,
        budget="moderate",
        preferred_win_con="combat"
    )
    conn.close()

    assert deck["total_cards"] == 100
    assert "exports" in deck
    assert "tcgplayer" in deck["exports"]

    tcg = deck["exports"]["tcgplayer"]
    # Check format: "1 Card Name"
    lines = [line.strip() for line in tcg.splitlines() if line.strip()]
    assert len(lines) > 0
    assert "1 Belbe, Corrupted Observer" in lines

    # Verify every line matches "<count> <card_name>"
    total_count = 0
    for line in lines:
        parts = line.split(" ", 1)
        assert len(parts) == 2, f"Invalid TCGplayer format line: {line}"
        count = int(parts[0])
        assert count >= 1
        total_count += count

    assert total_count == 100, f"Expected exactly 100 cards in TCGplayer export, found {total_count}"
