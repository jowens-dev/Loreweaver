#!/usr/bin/env python3
"""Draftweaver Real-Time MTG Arena Draft Watcher & Live Decision Engine.

Watches MTG Arena's Player.log in real-time, automatically detects when you open
a booster pack in Quick Draft, Premier Draft, or Traditional Draft, and outputs
instantaneous data-driven pick recommendations (1-55 score, tier, insights).
"""

import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.draft_engine import (
    ArenaLogParser,
    CardResolver,
    DraftLogWatcher,
    DraftScoringEngine,
    DraftState,
    optimize_deck,
)


def get_default_arena_log_path() -> Path:
    """Detect default Player.log path on macOS or Windows."""
    home = Path.home()
    if sys.platform == "darwin":
        mac_path = home / "Library" / "Logs" / "Wizards Of The Coast" / "MTGA" / "Player.log"
        if mac_path.exists():
            return mac_path
    elif sys.platform == "win32":
        win_path = home / "AppData" / "LocalLow" / "Wizards Of The Coast" / "MTGA" / "Player.log"
        if win_path.exists():
            return win_path

    # Fallback search
    candidates = [
        home / "Library" / "Logs" / "Wizards Of The Coast" / "MTGA" / "Player.log",
        home / "AppData" / "LocalLow" / "Wizards Of The Coast" / "MTGA" / "Player.log",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def format_tier_badge(tier: str) -> str:
    """ANSI color-coded tier badge."""
    colors = {
        "S": "\033[93m\033[1m[ S ]\033[0m",   # Bright Yellow / Gold
        "A": "\033[92m\033[1m[ A ]\033[0m",   # Green
        "B": "\033[96m\033[1m[ B ]\033[0m",   # Cyan
        "C": "\033[94m[ C ]\033[0m",          # Blue
        "D": "\033[95m[ D ]\033[0m",          # Magenta
        "F": "\033[90m[ F ]\033[0m",          # Grey
    }
    return colors.get(tier, f"[{tier}]")


class LiveDraftAssistant:
    """Manages real-time draft state and prints instant decisions."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or get_default_arena_log_path()
        self.resolver = CardResolver()
        self.parser = ArenaLogParser(resolver=self.resolver)
        self.engine = DraftScoringEngine()
        self.last_pack_key = None

    def on_pack_event(self, state: DraftState) -> None:
        """Triggered immediately when MTG Arena deals a new booster pack."""
        if state.is_completed:
            self._handle_draft_completed(state)
            return

        pack_key = (state.pack_num_1_indexed, state.pick_num_1_indexed, tuple(state.pack_card_ids))
        if pack_key == self.last_pack_key:
            return
        self.last_pack_key = pack_key

        candidates = self.resolver.resolve_pack_cards(state.pack_card_ids)
        picked = self.resolver.resolve_pool_cards(state.drafted_pool)

        scored = self.engine.score_candidates(
            candidates,
            picked,
            pack_num=state.pack_num_1_indexed,
            pick_num=state.pick_num_1_indexed,
        )

        print("\n" + "=" * 70)
        print(f"🎯 \033[1mPACK {state.pack_num_1_indexed}, PICK {state.pick_num_1_indexed}\033[0m ({len(candidates)} cards remaining)")
        if picked:
            # Show current leading color archetype
            from scripts.draft_engine.scoring_engine import calculate_bayesian_archetype_probabilities, ARCHETYPE_NAMES
            probs = calculate_bayesian_archetype_probabilities(picked)
            best_arch, best_prob = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[0]
            arch_name = ARCHETYPE_NAMES.get(best_arch, best_arch)
            print(f"📊 Leading Archetype: \033[36m{arch_name}\033[0m ({best_arch}: {best_prob*100:.0f}% confidence) | Pool: {len(picked)} cards")
        print("=" * 70)

        for rank, card in enumerate(scored, 1):
            tier_badge = format_tier_badge(card.get("tier", "C"))
            score = card.get("composite_rating", 0.0)
            name = card.get("name", "Unknown")
            cmc = card.get("cmc", 0.0)
            colors = "".join(card.get("colors") or []) or "C"
            insights = card.get("insights", [])
            insight_str = f" — \033[90m{insights[0]}\033[0m" if insights else ""

            prefix = "\033[1m⭐ #1 PICK:\033[0m " if rank == 1 else f"   #{rank:2d}       "
            print(f"{prefix}{tier_badge} \033[1m{score:4.1f}\033[0m | {name:<26} ({colors}, {cmc:.0f} CMC){insight_str}")

        print("-" * 70)

    def _handle_draft_completed(self, state: DraftState) -> None:
        """Triggered when the draft finishes; builds the 40-card deck automatically."""
        print("\n" + "🎉 " * 15)
        print("🎉 \033[1;92mDRAFT COMPLETED! BUILDING OPTIMAL 40-CARD DECK...\033[0m 🎉")
        print("🎉 " * 15 + "\n")

        picked_cards = self.resolver.resolve_pool_cards(state.drafted_pool)
        deck_result = optimize_deck(picked_cards, target_spells=23, target_lands=17)

        stats = deck_result.get("stats", {})
        print(f"🏆 Recommended Build: \033[1;36m{deck_result.get('deck_name', 'Optimal Deck')}\033[0m")
        print(f"📈 Curve: {stats.get('curve', {})}")
        print(f"⚔️  Creatures: {stats.get('creatures_count', 0)} / {stats.get('spells_count', 23)} spells")
        print(f"🏔️  Mana Split: {stats.get('mana_split', {})}\n")
        print("📋 MTG Arena Importable Decklist:")
        print("-" * 40)
        print(deck_result.get("arena_decklist_text", ""))
        print("-" * 40)

    def start(self) -> None:
        """Start live watching."""
        print("\n" + "=" * 70)
        print("🔮 \033[1mDRAFTWEAVER LIVE ASSISTANT READY\033[0m")
        print(f"📁 Monitoring MTGA Log: {self.log_path}")
        print("✨ Start a draft in MTG Arena (Quick, Premier, or Traditional) to begin.")
        print("=" * 70 + "\n")

        watcher = DraftLogWatcher(
            log_path=self.log_path,
            callback=self.on_pack_event,
            parser=self.parser,
            poll_interval=0.25,
        )
        watcher.watch()


if __name__ == "__main__":
    assistant = LiveDraftAssistant()
    assistant.start()
