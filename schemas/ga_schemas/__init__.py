"""Provisional ``v0`` data contract for graduation-arena (pydantic source of truth).

See ``ga_schemas.models`` for the models and ``ga_schemas.export`` for the
JSON Schema export / drift check. Part of issue #4 (the v0 contract).
"""

from __future__ import annotations

from .models import (
    Evaluator,
    EvaluatorRole,
    EvaluatorStats,
    Grade,
    Level,
    ParsedThesis,
    RawThesis,
)

__all__ = [
    "Evaluator",
    "EvaluatorRole",
    "EvaluatorStats",
    "Grade",
    "Level",
    "ParsedThesis",
    "RawThesis",
]
