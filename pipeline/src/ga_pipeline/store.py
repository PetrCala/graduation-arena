"""SQLite processing store for raw harvested thesis records."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from ga_schemas.models import EvaluatorStats, ParsedThesis, RawThesis


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
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS parsed_theses (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                parsed_json TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES raw_theses(source_id)
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluator_stats (
                evaluator_id TEXT PRIMARY KEY,
                stats_json TEXT NOT NULL
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

    def iter_raw_theses(self) -> Iterator[RawThesis]:
        """Yield raw thesis records from the store in deterministic order."""
        rows = self.connection.execute(
            """
            SELECT source_id, source_url, fetched_at, raw_fields_json
            FROM raw_theses
            ORDER BY source_id
            """
        )
        for source_id, source_url, fetched_at, raw_fields_json in rows:
            yield RawThesis(
                source_id=source_id,
                source_url=source_url,
                fetched_at=datetime.fromisoformat(fetched_at),
                raw_fields=json.loads(raw_fields_json),
            )

    def replace_parsed_theses(self, rows: list[tuple[str, ParsedThesis]]) -> None:
        """Replace parsed thesis output with the supplied validated records."""
        self.connection.execute("DELETE FROM parsed_theses")
        self.connection.executemany(
            """
            INSERT INTO parsed_theses (id, source_id, parsed_json)
            VALUES (?, ?, ?)
            """,
            [
                (
                    thesis.id,
                    source_id,
                    thesis.model_dump_json(exclude_none=True),
                )
                for source_id, thesis in rows
            ],
        )

    def iter_parsed_theses(self) -> Iterator[ParsedThesis]:
        """Yield parsed thesis records from the store in deterministic order."""
        rows = self.connection.execute(
            """
            SELECT parsed_json
            FROM parsed_theses
            ORDER BY id
            """
        )
        for (parsed_json,) in rows:
            yield ParsedThesis.model_validate_json(parsed_json)

    def replace_evaluator_stats(self, stats: list[EvaluatorStats]) -> None:
        """Replace public evaluator aggregate rows with validated stats."""
        self.connection.execute("DELETE FROM evaluator_stats")
        self.connection.executemany(
            """
            INSERT INTO evaluator_stats (evaluator_id, stats_json)
            VALUES (?, ?)
            """,
            [
                (
                    stat.evaluator.id or stat.evaluator.name,
                    stat.model_dump_json(exclude_none=True),
                )
                for stat in stats
            ],
        )

    def iter_evaluator_stats(self) -> Iterator[EvaluatorStats]:
        """Yield public evaluator stats from the store in deterministic order."""
        rows = self.connection.execute(
            """
            SELECT stats_json
            FROM evaluator_stats
            ORDER BY evaluator_id
            """
        )
        for (stats_json,) in rows:
            yield EvaluatorStats.model_validate_json(stats_json)
