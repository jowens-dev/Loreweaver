"""Tests for Creator Link Hub, PWA Manifest, URL Deep-Linking, and Mana Pool Attribution."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

import api
import db
from scripts import deck_builder, deck_exporter

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pwa_manifest_validity():
    """Verify manifest.json exists, is valid JSON, and meets PWA installability requirements."""
    manifest_path = REPO_ROOT / "web" / "public" / "manifest.json"
    assert manifest_path.exists(), "manifest.json is missing in web/public"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("name") == "Loreweaver: MTG Commander Architect"
    assert data.get("short_name") == "Loreweaver"
    assert data.get("display") == "standalone"
    assert data.get("start_url") == "/"
    assert "theme_color" in data
    assert "background_color" in data
    assert len(data.get("icons", [])) >= 2
    for icon in data["icons"]:
        assert "src" in icon
        assert "sizes" in icon
        assert "type" in icon


def test_pwa_service_worker_exists():
    """Verify sw.js exists in web/public and references shell assets."""
    sw_path = REPO_ROOT / "web" / "public" / "sw.js"
    assert sw_path.exists(), "sw.js is missing in web/public"

    content = sw_path.read_text(encoding="utf-8")
    assert "CACHE_NAME" in content
    assert "install" in content
    assert "activate" in content
    assert "fetch" in content


def test_vercel_spa_rewrites():
    """Verify vercel.json contains SPA rewrites for deep-linking (/links, /bio, /decks)."""
    vercel_path = REPO_ROOT / "web" / "vercel.json"
    assert vercel_path.exists(), "vercel.json is missing in web"

    with open(vercel_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "rewrites" in data, "vercel.json missing rewrites array"
    rewrites = data["rewrites"]
    has_catchall = any(r.get("source") == "/(.*)" and r.get("destination") == "/index.html" for r in rewrites)
    assert has_catchall, "vercel.json missing catch-all rewrite to /index.html"


def test_capacitor_config_validity():
    """Verify capacitor.config.json is valid and configured for app store packaging."""
    cap_path = REPO_ROOT / "web" / "capacitor.config.json"
    assert cap_path.exists(), "capacitor.config.json is missing in web"

    with open(cap_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("appId") == "app.loreweaver.mobile"
    assert data.get("appName") == "Loreweaver"
    assert data.get("webDir") == "dist"


def test_deep_linked_deck_synthesis():
    """Verify backend synthesizes an exact 100-card deck from deep-link parameters."""
    client = TestClient(api.app)
    # Simulate a request triggered by ?c=Belbe,%20Corrupted%20Observer&b=3&budget=ultra_budget&auto=true
    response = client.post(
        "/api/build",
        json={
            "commander": "Belbe, Corrupted Observer",
            "bracket": 3,
            "budget": "ultra_budget",
            "preferred_win_con": "combat"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_cards"] == 100
    assert "exports" in data
    assert "manapool" in data["exports"]
    assert "1 Belbe, Corrupted Observer" in data["exports"]["manapool"]


def test_video_decks_data_integrity():
    """Verify videoDecksData.js contains all 5 video backlog decks with verified 100-card exports."""
    decks_path = REPO_ROOT / "web" / "src" / "data" / "videoDecksData.js"
    assert decks_path.exists(), "videoDecksData.js is missing"

    content = decks_path.read_text(encoding="utf-8")
    assert "export const VIDEO_DECKS =" in content
    # Extract the JSON array portion
    start = content.index("[")
    end = content.rindex("]") + 1
    decks = json.loads(content[start:end])

    assert len(decks) == 5, f"Expected 5 video decks, got {len(decks)}"
    for d in decks:
        assert d.get("totalCards") == 100, f"Deck {d.get('id')} totalCards != 100"
        assert "manapoolExport" in d, f"Deck {d.get('id')} missing manapoolExport"
        assert "moxfieldExport" in d, f"Deck {d.get('id')} missing moxfieldExport"
        # Confirm card line count in export
        lines = [l for l in d["manapoolExport"].splitlines() if l.strip() and not l.startswith("//")]
        card_count = sum(int(l.split(" ", 1)[0]) for l in lines if l.split(" ", 1)[0].isdigit())
        assert card_count == 100, f"Deck {d.get('id')} parsed card count is {card_count}, expected 100"


def test_service_worker_strict_mime_type_safety():
    """Verify sw.js enforces request.mode === 'navigate' before falling back to index.html."""
    sw_path = REPO_ROOT / "web" / "public" / "sw.js"
    content = sw_path.read_text(encoding="utf-8")
    assert "event.request.mode === 'navigate'" in content, "Service worker must restrict index.html fallback to navigate requests"
    assert "Offline Asset Unavailable" in content or "408" in content, "Service worker must return non-HTML response for asset fetch failures"


def test_api_build_bracket_validation_boundary():
    """Verify /api/build enforces schema boundary checks on bracket parameter."""
    client = TestClient(api.app)
    # Bracket out-of-bounds: bracket=6 (allowed range: 1..5)
    res_high = client.post("/api/build", json={"commander": "Belbe, Corrupted Observer", "bracket": 6})
    assert res_high.status_code == 422

    # Bracket out-of-bounds: bracket=0
    res_low = client.post("/api/build", json={"commander": "Belbe, Corrupted Observer", "bracket": 0})
    assert res_low.status_code == 422


def test_manapool_mass_entry_url_preloads_deck():
    """Verify get_manapool_mass_entry_url generates a base64url encoded deck param that round-trips exactly."""
    import base64
    deck_text = "1 Belbe, Corrupted Observer\n1 Sol Ring\n1 Arcane Signet"
    url = deck_exporter.get_manapool_mass_entry_url(deck_text, ref="loreweaver")

    assert "https://manapool.com/add-deck?ref=loreweaver&deck=" in url
    encoded_part = url.split("&deck=")[1]
    # Check URL-safe characters: no '+', '/', or '='
    assert "+" not in encoded_part
    assert "/" not in encoded_part
    assert "=" not in encoded_part

    # Decode base64url
    padded = encoded_part + "=" * ((4 - len(encoded_part) % 4) % 4)
    decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
    assert decoded == deck_text
