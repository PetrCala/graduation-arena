"""SQLite processing store for raw harvested thesis records."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ga_schemas.models import RawThesis


class ProcessingStore:
    """Persist raw thesis records with idempotent upserts keyed by source id."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> ProcessingStore:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_theses (
                source_id TEXT PRIMARY KEY,
                source_url TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                raw_fields_json TEXT NOT NULL
            )
            """
        )
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            self.connection.commit()
        self.connection.close()

    def upsert_raw_thesis(self, thesis: RawThesis) -> None:
        """Insert or replace one raw thesis."""
        self.connection.execute(
            """
            INSERT INTO raw_theses (source_id, source_url, fetched_at, raw_fields_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                source_url = excluded.source_url,
                fetched_at = excluded.fetched_at,
                raw_fields_json = excluded.raw_fields_json
            """,
            (
                thesis.source_id,
                thesis.source_url,
                thesis.fetched_at.isoformat(),
                json.dumps(thesis.raw_fields, ensure_ascii=False, sort_keys=True),
            ),
        )
