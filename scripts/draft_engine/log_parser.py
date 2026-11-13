"""MTG Arena Draft Log Watcher and Parser.

Provides robust real-time watching and parsing of Magic: The Gathering Arena
Player.log streams and payloads, specifically tracking:
- Draft.DraftStatus (bot/quick drafts)
- Event.GetCombinedRequest (premier/traditional/cube drafts & event status)
- GrpId card resolution against canonical card database (SQLite data/cards.db)
- Live and mock draft simulation for offline test automation and verification.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger(__name__)

# Standard MTG Arena log identifiers
DRAFT_STATUS_EVENT = "Draft.DraftStatus"
GET_COMBINED_REQUEST_EVENT = "Event.GetCombinedRequest"
BOT_DRAFT_MODULE = "BotDraft"
DRAFT_MODULE = "Draft"

# Regex patterns for MTGA log line prefixes
_UNITY_LOGGER_PREFIX_RE = re.compile(
    r"^\[UnityCrossThreadLogger\](?:[^:<=>\n]+:\s*)?(?:[<=]{2,3}>\s*)?([A-Za-z0-9_.]+)(?:\(\d+\))?\s*(.*)$"
)
_ARROW_PREFIX_RE = re.compile(r"^(?:[<=]{2,3}>\s*)([A-Za-z0-9_.]+)(?:\(\d+\))?\s*(.*)$")


def _find_workspace_root() -> Path:
    """Locate the root directory of the workspace."""
    current = Path(__file__).resolve().parent
    while current.parent != current:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd()


WORKSPACE_ROOT = _find_workspace_root()
DEFAULT_DB_PATH = WORKSPACE_ROOT / "data" / "cards.db"


@dataclass
class DraftState:
    """Represents the parsed snapshot of a draft step from MTGA logs."""

    event_type: str
    pack_number: int  # 0 or 1-indexed as reported by payload
    pick_number: int  # 0 or 1-indexed as reported by payload
    pack_card_ids: List[int] = field(default_factory=list)
    drafted_pool: List[int] = field(default_factory=list)
    draft_status: str = "PickNext"
    event_name: Optional[str] = None
    course_id: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    resolved_pack_names: List[str] = field(default_factory=list)
    resolved_pool_names: List[str] = field(default_factory=list)

    @property
    def pack_num_1_indexed(self) -> int:
        """Normalized 1-indexed pack number (Pack 1, 2, or 3)."""
        if len(self.drafted_pool) >= 28:
            return 3
        elif len(self.drafted_pool) >= 14:
            return 2
        elif self.pack_number == 0:
            return 1
        elif self.pack_number in (1, 2):
            return self.pack_number + 1
        return self.pack_number

    @property
    def pick_num_1_indexed(self) -> int:
        """Normalized 1-indexed pick number (Pick 1 to 14/15)."""
        if self.drafted_pool:
            return (len(self.drafted_pool) % 14) + 1
        if 0 <= self.pick_number <= 14:
            return self.pick_number + 1
        return self.pick_number

    @property
    def is_completed(self) -> bool:
        """True if the draft phase is finalized."""
        return self.draft_status.lower() == "completed" or (
            len(self.pack_card_ids) == 0 and len(self.drafted_pool) > 0
        )

    def to_scoring_context(self) -> Dict[str, Any]:
        """Convenience structure ready for consumption by scoring_engine."""
        return {
            "pack_num": self.pack_num_1_indexed,
            "pick_num": self.pick_num_1_indexed,
            "pack_card_ids": list(self.pack_card_ids),
            "drafted_pool_ids": list(self.drafted_pool),
            "pack_card_names": list(self.resolved_pack_names),
            "drafted_pool_names": list(self.resolved_pool_names),
            "event_name": self.event_name,
            "draft_status": self.draft_status,
        }


class CardResolver:
    """Resolves MTG Arena card IDs (grpId) to canonical card names and metadata

    via SQLite data/cards.db with in-memory caching and mock fallback support.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        else:
            self.db_path = Path(db_path)

        self._name_cache: Dict[int, str] = {}
        self._card_cache: Dict[int, Dict[str, Any]] = {}
        self._memory_overrides: Dict[int, Dict[str, Any]] = {}
        self._schema_inspected = False
        self._id_col: Optional[str] = None
        self._name_col: Optional[str] = None
        self._has_cards_table = False

    def register_card(
        self,
        grp_id: int,
        name: str,
        mana_cost: str = "",
        cmc: float = 0.0,
        type_line: str = "",
        colors: Optional[List[str]] = None,
        rarity: str = "common",
        **kwargs: Any,
    ) -> None:
        """Explicitly register a card mapping in-memory for testing or overrides."""
        card_dict: Dict[str, Any] = {
            "grpId": int(grp_id),
            "id": int(grp_id),
            "name": str(name),
            "mana_cost": str(mana_cost),
            "cmc": float(cmc),
            "type_line": str(type_line),
            "colors": list(colors or []),
            "rarity": str(rarity),
            **kwargs,
        }
        self._memory_overrides[int(grp_id)] = card_dict
        self._name_cache[int(grp_id)] = str(name)
        self._card_cache[int(grp_id)] = card_dict

    def register_cards(self, cards: Sequence[Dict[str, Any]]) -> None:
        """Register multiple cards in-memory."""
        for c in cards:
            gid = c.get("grpId") or c.get("id") or c.get("arena_id")
            name = c.get("name")
            if gid is not None and name:
                self.register_card(grp_id=int(gid), name=str(name), **c)

    def _inspect_schema(self, conn: sqlite3.Connection) -> None:
        """Inspect table schema in SQLite database to dynamically bind columns."""
        if self._schema_inspected:
            return
        self._schema_inspected = True
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND (name='cards' OR name='Cards')"
            )
            row = cursor.fetchone()
            if not row:
                self._has_cards_table = False
                return

            table_name = row[0]
            self._has_cards_table = True
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [r[1] for r in cursor.fetchall()]

            # Determine ID column priority
            for col in ("grpId", "grpid", "arena_id", "id"):
                if col in columns:
                    self._id_col = col
                    break
            if not self._id_col and columns:
                self._id_col = columns[0]

            # Determine name column priority
            for col in ("name", "card_name", "canonical_name", "name_lower"):
                if col in columns:
                    self._name_col = col
                    break
            if not self._name_col and len(columns) > 1:
                self._name_col = columns[1]

        except Exception as e:
            logger.debug(f"Schema inspection failed: {e}")
            self._has_cards_table = False

    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Obtain a SQLite connection if the file exists."""
        if not self.db_path.exists():
            return None
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.OperationalError:
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                return conn
            except Exception as e:
                logger.debug(f"Failed to connect to SQLite at {self.db_path}: {e}")
                return None

    def resolve_name(self, grp_id: Union[int, str]) -> str:
        """Resolve a grpId to its canonical card name string."""
        try:
            gid = int(grp_id)
        except (ValueError, TypeError):
            return f"Unknown Card ({grp_id})"

        if gid in self._name_cache:
            return self._name_cache[gid]

        if gid in self._memory_overrides:
            name = self._memory_overrides[gid]["name"]
            self._name_cache[gid] = name
            return name

        conn = self._get_connection()
        if conn is not None:
            try:
                self._inspect_schema(conn)
                if self._has_cards_table and self._id_col and self._name_col:
                    cursor = conn.cursor()
                    query = f"SELECT {self._name_col} FROM cards WHERE {self._id_col} = ? LIMIT 1"
                    cursor.execute(query, (gid,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        name = str(row[0])
                        self._name_cache[gid] = name
                        return name
            except Exception as e:
                logger.debug(f"Error querying cards.db for {gid}: {e}")
            finally:
                conn.close()

        fallback = f"Unknown Card ({gid})"
        self._name_cache[gid] = fallback
        return fallback

    def resolve_card(self, grp_id: Union[int, str]) -> Dict[str, Any]:
        """Resolve a grpId to a complete card dictionary."""
        try:
            gid = int(grp_id)
        except (ValueError, TypeError):
            gid = -1

        if gid in self._card_cache:
            return dict(self._card_cache[gid])

        if gid in self._memory_overrides:
            res = dict(self._memory_overrides[gid])
            self._card_cache[gid] = res
            return res

        conn = self._get_connection()
        if conn is not None:
            try:
                self._inspect_schema(conn)
                if self._has_cards_table and self._id_col:
                    cursor = conn.cursor()
                    query = f"SELECT * FROM cards WHERE {self._id_col} = ? LIMIT 1"
                    cursor.execute(query, (gid,))
                    row = cursor.fetchone()
                    if row:
                        d = dict(row)
                        # Normalize common fields
                        colors = d.get("colors")
                        if isinstance(colors, str):
                            try:
                                d["colors"] = json.loads(colors)
                            except Exception:
                                d["colors"] = [c for c in colors if c in "WUBRG"]
                        d["grpId"] = gid
                        d["id"] = gid
                        if "name" not in d and self._name_col and self._name_col in d:
                            d["name"] = d[self._name_col]
                        self._card_cache[gid] = d
                        self._name_cache[gid] = str(d.get("name", f"Unknown Card ({gid})"))
                        return d
            except Exception as e:
                logger.debug(f"Error fetching card dict for {gid}: {e}")
            finally:
                conn.close()

        # Fallback card representation
        name = self.resolve_name(gid)
        fallback = {
            "grpId": gid,
            "id": gid,
            "name": name,
            "mana_cost": "",
            "cmc": 0.0,
            "type_line": "",
            "colors": [],
            "color_identity": [],
            "rarity": "common",
        }
        self._card_cache[gid] = fallback
        return fallback

    def resolve_pack_names(self, pack_card_ids: Sequence[Union[int, str]]) -> List[str]:
        """Resolve all cards in a pack to canonical names."""
        return [self.resolve_name(cid) for cid in pack_card_ids]

    def resolve_pack_cards(self, pack_card_ids: Sequence[Union[int, str]]) -> List[Dict[str, Any]]:
        """Resolve all cards in a pack to full card dictionaries."""
        return [self.resolve_card(cid) for cid in pack_card_ids]

    def resolve_pool_names(self, pool_card_ids: Sequence[Union[int, str]]) -> List[str]:
        """Resolve all cards in drafted pool to canonical names."""
        return [self.resolve_name(cid) for cid in pool_card_ids]

    def resolve_pool_cards(self, pool_card_ids: Sequence[Union[int, str]]) -> List[Dict[str, Any]]:
        """Resolve all cards in drafted pool to full card dictionaries."""
        return [self.resolve_card(cid) for cid in pool_card_ids]


def _decode_json_payload(data: Any) -> Optional[Dict[str, Any]]:
    """Recursively extracts and decodes JSON from strings or dict structures."""
    if isinstance(data, dict):
        # Look for nested escaped JSON in common wrapper keys
        for key in ("Payload", "payload", "params", "request", "result"):
            val = data.get(key)
            if isinstance(val, str) and val.strip().startswith(("{", "[")):
                decoded = _decode_json_payload(val)
                if isinstance(decoded, dict):
                    # Combine outer metadata with inner decoded payload
                    merged = dict(data)
                    merged.update(decoded)
                    return merged
        return data

    if isinstance(data, str):
        cleaned = data.strip()
        if not cleaned:
            return None
        # Attempt direct JSON load
        try:
            parsed = json.loads(cleaned)
            return _decode_json_payload(parsed)
        except json.JSONDecodeError:
            # Fallback: locate JSON object slice between first '{' and last '}'
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and start < end:
                try:
                    parsed = json.loads(cleaned[start : end + 1])
                    return _decode_json_payload(parsed)
                except json.JSONDecodeError:
                    return None
            return None

    return None


def _to_int_list(items: Any) -> List[int]:
    """Safely sanitize an arbitrary collection into a list of integers."""
    if not items:
        return []
    if not isinstance(items, (list, tuple, set)):
        return []

    result: List[int] = []
    for item in items:
        if isinstance(item, dict):
            cid = item.get("cardId") or item.get("grpId") or item.get("id")
            if cid is not None:
                try:
                    result.append(int(cid))
                except (ValueError, TypeError):
                    pass
        elif item is not None:
            try:
                result.append(int(item))
            except (ValueError, TypeError):
                pass
    return result


class ArenaLogParser:
    """Parser for MTG Arena Player.log lines, raw JSON strings, and dict payloads."""

    def __init__(
        self,
        resolver: Optional[CardResolver] = None,
        db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.resolver = resolver or CardResolver(db_path=db_path)

    def is_draft_event(self, text_or_dict: Union[str, Dict[str, Any]]) -> bool:
        """Determines if the payload represents Draft.DraftStatus or Event.GetCombinedRequest."""
        if isinstance(text_or_dict, dict):
            # Check explicit method/request keys
            for k in ("method", "request", "EventName", "eventName"):
                val = str(text_or_dict.get(k) or "")
                if (
                    DRAFT_STATUS_EVENT in val
                    or GET_COMBINED_REQUEST_EVENT in val
                    or val in (BOT_DRAFT_MODULE, DRAFT_MODULE)
                ):
                    return True

            # Check module or payload fields
            if text_or_dict.get("CurrentModule") in (BOT_DRAFT_MODULE, DRAFT_MODULE):
                return True
            if "DraftPack" in text_or_dict or "DraftStatus" in text_or_dict:
                return True
            if "Courses" in text_or_dict:
                return True
            # Inspect nested string payload
            for k in ("Payload", "payload"):
                sub = text_or_dict.get(k)
                if isinstance(sub, str) and (
                    "DraftPack" in sub or "DraftStatus" in sub or "Courses" in sub
                ):
                    return True
            return False

        if isinstance(text_or_dict, str):
            s = text_or_dict
            return (
                DRAFT_STATUS_EVENT in s
                or GET_COMBINED_REQUEST_EVENT in s
                or "DraftPack" in s
                or "DraftStatus" in s
                or "BotDraft" in s
            )

        return False

    def parse_payload(
        self,
        payload: Dict[str, Any],
        event_hint: Optional[str] = None,
    ) -> Optional[DraftState]:
        """Parse a decoded dictionary into a structured DraftState."""
        decoded = _decode_json_payload(payload)
        if not decoded:
            return None

        # Determine event type
        event_type = event_hint or DRAFT_STATUS_EVENT
        method_field = str(
            decoded.get("method")
            or decoded.get("request")
            or decoded.get("EventName")
            or decoded.get("eventName")
            or ""
        )

        if GET_COMBINED_REQUEST_EVENT in method_field or "Courses" in decoded:
            event_type = GET_COMBINED_REQUEST_EVENT
        elif DRAFT_STATUS_EVENT in method_field or "DraftStatus" in decoded or "DraftPack" in decoded:
            event_type = DRAFT_STATUS_EVENT

        if event_type == GET_COMBINED_REQUEST_EVENT:
            return self._parse_combined_request(decoded)
        else:
            return self._parse_draft_status(decoded, event_type)

    def _parse_draft_status(
        self,
        data: Dict[str, Any],
        event_type: str = DRAFT_STATUS_EVENT,
    ) -> Optional[DraftState]:
        """Extract draft state from a Draft.DraftStatus payload."""
        # Check if we have draft-specific keys
        has_draft_data = any(
            k in data for k in ("DraftPack", "draftPack", "DraftStatus", "draftStatus", "PackNumber", "PickNumber", "PickedCards")
        )
        if not has_draft_data and data.get("CurrentModule") not in (BOT_DRAFT_MODULE, DRAFT_MODULE):
            return None

        status = str(
            data.get("DraftStatus")
            or data.get("draftStatus")
            or data.get("Status")
            or "PickNext"
        )
        event_name = (
            data.get("EventName")
            or data.get("eventName")
            or data.get("InternalEventName")
        )
        course_id = data.get("CourseId") or data.get("DraftId")

        # Extract pack and pick numbers
        raw_pack = data.get("PackNumber")
        if raw_pack is None:
            raw_pack = data.get("pack_number", data.get("packNumber", data.get("pack_num", data.get("pack", 0))))
        try:
            pack_number = int(raw_pack)
        except (ValueError, TypeError):
            pack_number = 0

        raw_pick = data.get("PickNumber")
        if raw_pick is None:
            raw_pick = data.get("pick_number", data.get("pickNumber", data.get("pick_num", data.get("pick", 0))))
        try:
            pick_number = int(raw_pick)
        except (ValueError, TypeError):
            pick_number = 0

        # Extract current pack cards
        raw_pack_cards = (
            data.get("DraftPack")
            or data.get("draftPack")
            or data.get("PackCards")
            or data.get("Cards")
            or data.get("pack_cards")
            or []
        )
        pack_card_ids = _to_int_list(raw_pack_cards)

        # Extract drafted pool
        raw_picked = (
            data.get("PickedCards")
            or data.get("picked_cards")
            or data.get("CardPool")
            or data.get("card_pool")
            or data.get("DraftedCards")
            or []
        )
        drafted_pool = _to_int_list(raw_picked)

        # Resolve card names
        resolved_pack_names = self.resolver.resolve_pack_names(pack_card_ids)
        resolved_pool_names = self.resolver.resolve_pool_names(drafted_pool)

        return DraftState(
            event_type=event_type,
            pack_number=pack_number,
            pick_number=pick_number,
            pack_card_ids=pack_card_ids,
            drafted_pool=drafted_pool,
            draft_status=status,
            event_name=str(event_name) if event_name else None,
            course_id=str(course_id) if course_id else None,
            raw_payload=data,
            resolved_pack_names=resolved_pack_names,
            resolved_pool_names=resolved_pool_names,
        )

    def _parse_combined_request(self, data: Dict[str, Any]) -> Optional[DraftState]:
        """Extract draft state from an Event.GetCombinedRequest payload."""
        courses = data.get("Courses")
        if not courses or not isinstance(courses, list):
            # Fallback if payload is formatted directly as course dict
            if "DraftPack" in data or "CardPool" in data or "CourseDeck" in data:
                courses = [data]
            else:
                return None

        # Find draft course (prefer active draft with DraftPack or CardPool)
        target_course: Optional[Dict[str, Any]] = None
        for course in courses:
            if not isinstance(course, dict):
                continue
            ename = str(course.get("InternalEventName") or "").lower()
            mod = str(course.get("CurrentModule") or "").lower()
            if "draft" in ename or "draft" in mod or "DraftPack" in course or "CardPool" in course:
                target_course = course
                break

        if not target_course and courses:
            target_course = courses[0] if isinstance(courses[0], dict) else None

        if not target_course:
            return None

        event_name = target_course.get("InternalEventName")
        course_id = target_course.get("CourseId")

        # Extract pack & pick
        progress = target_course.get("DraftProgress") or {}
        raw_pack = (
            target_course.get("PackNumber")
            or progress.get("PackNumber")
            or target_course.get("pack_number")
            or 0
        )
        raw_pick = (
            target_course.get("PickNumber")
            or progress.get("PickNumber")
            or target_course.get("pick_number")
            or 0
        )

        try:
            pack_number = int(raw_pack)
        except (ValueError, TypeError):
            pack_number = 0

        try:
            pick_number = int(raw_pick)
        except (ValueError, TypeError):
            pick_number = 0

        # Pack cards
        raw_pack_cards = (
            target_course.get("DraftPack")
            or progress.get("DraftPack")
            or target_course.get("Cards")
            or []
        )
        pack_card_ids = _to_int_list(raw_pack_cards)

        # Card pool
        raw_pool = target_course.get("CardPool") or progress.get("CardPool") or []
        if not raw_pool:
            deck_info = target_course.get("CourseDeck") or {}
            main_deck = deck_info.get("MainDeck") or []
            sideboard = deck_info.get("Sideboard") or []
            combined_deck = list(main_deck) + list(sideboard)
            raw_pool = combined_deck

        drafted_pool = _to_int_list(raw_pool)

        status = str(
            target_course.get("DraftStatus")
            or ("Completed" if not pack_card_ids and drafted_pool else "PickNext")
        )

        resolved_pack_names = self.resolver.resolve_pack_names(pack_card_ids)
        resolved_pool_names = self.resolver.resolve_pool_names(drafted_pool)

        return DraftState(
            event_type=GET_COMBINED_REQUEST_EVENT,
            pack_number=pack_number,
            pick_number=pick_number,
            pack_card_ids=pack_card_ids,
            drafted_pool=drafted_pool,
            draft_status=status,
            event_name=str(event_name) if event_name else None,
            course_id=str(course_id) if course_id else None,
            raw_payload=target_course,
            resolved_pack_names=resolved_pack_names,
            resolved_pool_names=resolved_pool_names,
        )

    def parse_line(self, line: str) -> Optional[DraftState]:
        """Parse a single raw log string line."""
        if not line or not line.strip():
            return None

        stripped = line.strip()

        # Check UnityCrossThreadLogger prefix
        event_hint: Optional[str] = None
        json_content = stripped

        match = _UNITY_LOGGER_PREFIX_RE.match(stripped)
        if match:
            event_hint = match.group(1).strip()
            json_content = match.group(2).strip()
        else:
            match_arrow = _ARROW_PREFIX_RE.match(stripped)
            if match_arrow:
                event_hint = match_arrow.group(1).strip()
                json_content = match_arrow.group(2).strip()

        # Filter out lines that clearly do not relate to draft
        if event_hint and not self.is_draft_event(event_hint) and not self.is_draft_event(json_content):
            return None

        decoded = _decode_json_payload(json_content)
        if decoded:
            return self.parse_payload(decoded, event_hint=event_hint)

        # Try parsing the whole stripped string if prefix matching missed
        fallback_decoded = _decode_json_payload(stripped)
        if fallback_decoded and self.is_draft_event(fallback_decoded):
            return self.parse_payload(fallback_decoded, event_hint=event_hint)

        return None

    def parse_raw(self, raw_input: Union[str, Dict[str, Any]]) -> Optional[DraftState]:
        """Unified entrypoint handling raw line strings, JSON strings, or dict payloads."""
        if isinstance(raw_input, dict):
            return self.parse_payload(raw_input)
        if isinstance(raw_input, str):
            return self.parse_line(raw_input)
        return None

    def parse_log_text(self, text: str) -> List[DraftState]:
        """Parse a complete multi-line log string, returning all discovered DraftStates."""
        events: List[DraftState] = []
        for line in text.splitlines():
            state = self.parse_line(line)
            if state:
                events.append(state)
        return events

    def parse_file(self, file_path: Union[str, Path]) -> List[DraftState]:
        """Parse an entire Player.log file on disk."""
        path = Path(file_path)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return self.parse_log_text(f.read())
        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            return []


class DraftLogWatcher:
    """Watches and tails MTG Arena Player.log in real-time, accumulating state."""

    def __init__(
        self,
        log_path: Union[str, Path],
        parser: Optional[ArenaLogParser] = None,
        auto_seek_end: bool = False,
    ) -> None:
        self.log_path = Path(log_path)
        self.parser = parser or ArenaLogParser()
        self._last_position = 0
        self._last_inode: Optional[int] = None
        self.current_state: Optional[DraftState] = None
        self.draft_history: List[DraftState] = []
        self.accumulated_pool: List[int] = []

        if self.log_path.exists():
            stat = self.log_path.stat()
            self._last_inode = getattr(stat, "st_ino", None)
            if auto_seek_end:
                self._last_position = stat.st_size

    def reset(self) -> None:
        """Reset watcher state and position back to beginning of log."""
        self._last_position = 0
        self.current_state = None
        self.draft_history.clear()
        self.accumulated_pool.clear()

    def check_for_updates(self) -> List[DraftState]:
        """Read any new lines appended to the log file since the last check."""
        if not self.log_path.exists():
            return []

        stat = self.log_path.stat()
        current_inode = getattr(stat, "st_ino", None)
        current_size = stat.st_size

        # Detect inode change (log rotation) or file size shrinkage (in-place truncation)
        if self._last_inode is not None and current_inode != self._last_inode:
            self._last_position = 0
            self._last_inode = current_inode
        elif current_size < self._last_position:
            self._last_position = 0

        if self._last_inode is None and current_inode is not None:
            self._last_inode = current_inode

        new_states: List[DraftState] = []
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._last_position)
                for line in f:
                    state = self.parser.parse_line(line)
                    if state:
                        self.current_state = state
                        self.draft_history.append(state)
                        # Merge newly reported cards into pool
                        for cid in state.drafted_pool:
                            if cid not in self.accumulated_pool:
                                self.accumulated_pool.append(cid)
                        new_states.append(state)
                self._last_position = f.tell()
        except Exception as e:
            logger.debug(f"Error checking log updates: {e}")

        return new_states

    def tail(
        self,
        poll_interval: float = 0.5,
        max_iterations: Optional[int] = None,
    ) -> Generator[DraftState, None, None]:
        """Yield draft states as they appear in the log file."""
        iterations = 0
        while max_iterations is None or iterations < max_iterations:
            updates = self.check_for_updates()
            for state in updates:
                yield state
            iterations += 1
            time.sleep(poll_interval)


class MockDraftGenerator:
    """Generates realistic MTG Arena Player.log events and simulated draft sessions

    for testing and local development without requiring the MTGA client.
    """

    def __init__(
        self,
        card_pool: Optional[Sequence[int]] = None,
        resolver: Optional[CardResolver] = None,
    ) -> None:
        self.resolver = resolver or CardResolver()
        if card_pool:
            self.card_pool = [int(x) for x in card_pool]
        else:
            self.card_pool = self._load_default_card_pool()

    def _load_default_card_pool(self) -> List[int]:
        """Extract available card IDs from data/cards.db or build default pool."""
        conn = self.resolver._get_connection()
        if conn is not None:
            try:
                self.resolver._inspect_schema(conn)
                if self.resolver._has_cards_table and self.resolver._id_col:
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT {self.resolver._id_col} FROM cards LIMIT 200")
                    rows = cursor.fetchall()
                    if rows:
                        return [int(r[0]) for r in rows if r[0] is not None]
            except Exception:
                pass
            finally:
                conn.close()

        # Synthetic fallback IDs if DB is empty
        return list(range(1001, 1150))

    def create_draft_status_payload(
        self,
        pack_number: int,
        pick_number: int,
        draft_pack: Sequence[int],
        picked_cards: Sequence[int],
        draft_status: str = "PickNext",
        event_name: str = "QuickDraft_MOCK",
        num_cards_to_pick: int = 1,
    ) -> Dict[str, Any]:
        """Generate a realistic BotDraft Draft.DraftStatus payload dictionary."""
        inner_payload = {
            "Result": "Success",
            "EventName": str(event_name),
            "DraftStatus": str(draft_status),
            "PackNumber": int(pack_number),
            "PickNumber": int(pick_number),
            "NumCardsToPick": int(num_cards_to_pick),
            "DraftPack": [str(cid) for cid in draft_pack],
            "PickedCards": [str(cid) for cid in picked_cards],
        }

        # Return MTGA outer envelope with serialized JSON Payload
        return {
            "CurrentModule": BOT_DRAFT_MODULE,
            "Payload": json.dumps(inner_payload),
        }

    def create_combined_request_payload(
        self,
        pack_number: int,
        pick_number: int,
        draft_pack: Sequence[int],
        picked_cards: Sequence[int],
        draft_status: str = "PickNext",
        event_name: str = "PremierDraft_MOCK",
        course_id: str = "mock-course-uuid-1234",
    ) -> Dict[str, Any]:
        """Generate a realistic Event.GetCombinedRequest payload dictionary."""
        course_dict = {
            "CourseId": str(course_id),
            "InternalEventName": str(event_name),
            "CurrentModule": DRAFT_MODULE,
            "DraftStatus": str(draft_status),
            "PackNumber": int(pack_number),
            "PickNumber": int(pick_number),
            "DraftPack": [int(cid) for cid in draft_pack],
            "CardPool": [int(cid) for cid in picked_cards],
            "CourseDeck": {
                "MainDeck": [{"cardId": int(cid), "quantity": 1} for cid in picked_cards[:23]],
                "Sideboard": [{"cardId": int(cid), "quantity": 1} for cid in picked_cards[23:]],
            },
        }
        return {
            "id": 1,
            "jsonrpc": "2.0",
            "method": GET_COMBINED_REQUEST_EVENT,
            "payload": json.dumps({"Courses": [course_dict]}),
        }

    def format_log_line(
        self,
        payload: Dict[str, Any],
        event_type: str = DRAFT_STATUS_EVENT,
        timestamp: Optional[str] = None,
    ) -> str:
        """Format a payload dictionary into a standard UnityCrossThreadLogger log line."""
        ts = timestamp or "11/12/2026 8:30:00 PM"
        payload_str = json.dumps(payload)
        return f"[UnityCrossThreadLogger]{ts}: <== {event_type} {payload_str}"

    def simulate_draft(
        self,
        packs: int = 3,
        picks_per_pack: int = 14,
        strategy: str = "first",  # 'first', 'random'
        event_type: str = DRAFT_STATUS_EVENT,
        event_name: str = "QuickDraft_MOCK",
    ) -> List[Dict[str, Any]]:
        """Simulate a complete 3-pack draft session, returning sequential event payloads."""
        import random

        pool = list(self.card_pool)
        if len(pool) < packs * picks_per_pack:
            # Replicate pool if insufficient unique cards
            multiplier = (packs * picks_per_pack // len(pool)) + 2
            pool = (pool * multiplier)[: packs * picks_per_pack * 2]

        events: List[Dict[str, Any]] = []
        accumulated_picks: List[int] = []

        for p_idx in range(packs):
            # Form initial booster pack
            pack_cards = pool[p_idx * picks_per_pack : (p_idx + 1) * picks_per_pack]
            remaining = list(pack_cards)

            for pick_idx in range(picks_per_pack):
                # Build payload
                if event_type == GET_COMBINED_REQUEST_EVENT:
                    payload = self.create_combined_request_payload(
                        pack_number=p_idx,
                        pick_number=pick_idx,
                        draft_pack=remaining,
                        picked_cards=accumulated_picks,
                        draft_status="PickNext",
                        event_name=event_name,
                    )
                else:
                    payload = self.create_draft_status_payload(
                        pack_number=p_idx,
                        pick_number=pick_idx,
                        draft_pack=remaining,
                        picked_cards=accumulated_picks,
                        draft_status="PickNext",
                        event_name=event_name,
                    )
                events.append(payload)

                # Make pick
                if strategy == "random" and remaining:
                    chosen = random.choice(remaining)
                else:
                    chosen = remaining[0] if remaining else 0

                if chosen in remaining:
                    remaining.remove(chosen)
                accumulated_picks.append(chosen)

        # Final completed payload
        if event_type == GET_COMBINED_REQUEST_EVENT:
            completed_payload = self.create_combined_request_payload(
                pack_number=packs - 1,
                pick_number=picks_per_pack - 1,
                draft_pack=[],
                picked_cards=accumulated_picks,
                draft_status="Completed",
                event_name=event_name,
            )
        else:
            completed_payload = self.create_draft_status_payload(
                pack_number=packs - 1,
                pick_number=picks_per_pack - 1,
                draft_pack=[],
                picked_cards=accumulated_picks,
                draft_status="Completed",
                event_name=event_name,
            )
        events.append(completed_payload)
        return events

    def write_mock_log(
        self,
        output_path: Union[str, Path],
        packs: int = 3,
        picks_per_pack: int = 14,
        event_type: str = DRAFT_STATUS_EVENT,
        include_noise: bool = True,
        event_name: str = "QuickDraft_MOCK",
    ) -> List[Dict[str, Any]]:
        """Simulate and write a mock Player.log file to disk with optional noise lines."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        payloads = self.simulate_draft(
            packs=packs,
            picks_per_pack=picks_per_pack,
            event_type=event_type,
            event_name=event_name,
        )

        lines: List[str] = []
        if include_noise:
            lines.append("[UnityCrossThreadLogger]11/12/2026 8:00:00 PM: Client.Connected")
            lines.append("[UnityCrossThreadLogger]11/12/2026 8:01:00 PM: Event.GetActiveEventsV2 {}")
            lines.append("General log trace: Audio system initialized.")

        for p in payloads:
            lines.append(self.format_log_line(p, event_type=event_type))
            if include_noise:
                lines.append("[UnityCrossThreadLogger]Heartbeat ping ack.")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return payloads
