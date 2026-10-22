"""
SQLite persistence layer for the Observer Agent.

Schema:
  sessions         — session metadata (id, scenario, participants, created_at, finalized_at)
  turn_observations — per-turn JSON blobs
  scorecards       — final ConversationScorecard JSON
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

from .schemas import TurnObservation, ConversationScorecard

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / ".cache" / "observer.db"


def _connect(db_path: Path = _DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = _DB_PATH) -> None:
    """Create tables if they don't exist."""
    conn = _connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id      TEXT PRIMARY KEY,
                scenario        TEXT NOT NULL DEFAULT '',
                participants    TEXT NOT NULL DEFAULT '[]',
                created_at      REAL NOT NULL,
                finalized_at    REAL
            );

            CREATE TABLE IF NOT EXISTS turn_observations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                turn_index      INTEGER NOT NULL,
                speaker         TEXT NOT NULL,
                observation_json TEXT NOT NULL,
                created_at      REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE INDEX IF NOT EXISTS idx_obs_session
                ON turn_observations(session_id, turn_index);

            CREATE TABLE IF NOT EXISTS scorecards (
                session_id      TEXT PRIMARY KEY,
                scorecard_json  TEXT NOT NULL,
                created_at      REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


class ObserverStorage:
    """SQLite-backed persistence for observer data."""

    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        init_db(db_path)

    def _conn(self) -> sqlite3.Connection:
        return _connect(self._db_path)

    # ── Sessions ─────────────────────────────────────────────────────────────

    def upsert_session(
        self,
        session_id: str,
        scenario: str = "",
        participants: Optional[list[str]] = None,
    ) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO sessions (session_id, scenario, participants, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    scenario = excluded.scenario,
                    participants = excluded.participants
                """,
                (
                    session_id,
                    scenario,
                    json.dumps(sorted(participants or [])),
                    time.time(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_finalized(self, session_id: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE sessions SET finalized_at = ? WHERE session_id = ?",
                (time.time(), session_id),
            )
            conn.commit()
        finally:
            conn.close()

    def list_sessions(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT session_id, scenario, participants, created_at, finalized_at FROM sessions ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Turn observations ────────────────────────────────────────────────────

    def save_observation(self, obs: TurnObservation) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO turn_observations
                    (session_id, turn_index, speaker, observation_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    obs.session_id,
                    obs.turn_index,
                    obs.speaker,
                    obs.model_dump_json(),
                    time.time(),
                ),
            )
            conn.commit()
        except Exception as exc:
            logger.error("save_observation failed: %s", exc)
        finally:
            conn.close()

    def get_observations(self, session_id: str) -> list[TurnObservation]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT observation_json FROM turn_observations WHERE session_id = ? ORDER BY turn_index",
                (session_id,),
            ).fetchall()
            return [TurnObservation.model_validate_json(r["observation_json"]) for r in rows]
        finally:
            conn.close()

    # ── Dyad snapshots ────────────────────────────────────────────────────────

    # ── Scorecards ───────────────────────────────────────────────────────────

    def save_scorecard(self, scorecard: ConversationScorecard) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO scorecards (session_id, scorecard_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    scorecard_json = excluded.scorecard_json,
                    created_at = excluded.created_at
                """,
                (scorecard.session_id, scorecard.model_dump_json(), time.time()),
            )
            conn.commit()
        except Exception as exc:
            logger.error("save_scorecard failed: %s", exc)
        finally:
            conn.close()

    def get_scorecard(self, session_id: str) -> Optional[ConversationScorecard]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT scorecard_json FROM scorecards WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row:
                return ConversationScorecard.model_validate_json(row["scorecard_json"])
            return None
        finally:
            conn.close()
