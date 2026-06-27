"""Provisional ``v0`` data contract for graduation-arena (DRAFT).

This module is the **single source of truth** for the data contract shared between
the pipeline (producer) and the web app (consumer). JSON Schema (``schemas/json/``)
and TypeScript types (``schemas/ts/``) are *generated* from these pydantic models so
the two sides cannot drift. See ``../docs/app-architecture.md`` and the README.

Status: ``v0`` — deliberately loose. The exact fields firm up later, once real source
fixtures exist (A1) and the legal verdict on naming vs. anonymising evaluators lands.
Anything unconfirmed is marked with a ``TODO`` comment. Keep uncertain fields loose.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums / small value types
# ---------------------------------------------------------------------------


class Level(str, Enum):
    """Thesis level."""

    bachelor = "bachelor"
    master = "master"


class EvaluatorRole(str, Enum):
    """Role an evaluator plays for a given thesis."""

    supervisor = "supervisor"
    opponent = "opponent"


# GRADE SCALE NOTE:
# Czech university theses are typically graded on a 1-4 integer scale, where
# 1 = excellent ("výborně") ... 4 = fail ("nevyhověl"). We use that as the
# provisional default below.
#
# TODO(v0): The exact IES scale is UNCONFIRMED. IES may use a different mapping
# (e.g. letter grades A-F, or a points-based scheme), and individual defenses may
# carry per-criterion sub-scores (e.g. content / contribution / methodology /
# literature / presentation). Both are unconfirmed pending real fixtures (A1).
# The grade type is kept as a plain ``int`` (validated to the 1-4 range) so it is
# trivial to widen or swap for an Enum / Decimal once the real scale is known.
GRADE_MIN = 1
GRADE_MAX = 4

# A grade is modelled as a bare ``int`` for v0 so downstream code does not bake in
# a scale that may change. The range constraint is applied at the field level.
Grade = int


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class Evaluator(BaseModel):
    """A person who evaluates a thesis (supervisor or opponent).

    ``v0`` — loose. ``id`` and ``role`` are optional because raw sources may not
    expose a stable identifier, and an ``Evaluator`` may be referenced outside the
    context of a single role (e.g. in aggregated stats).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Full display name of the evaluator.")
    # TODO(v0): id scheme unconfirmed. Likely a slug derived from the name, or an
    # IES/university person id if one is exposed by the source. May become required
    # once a stable identifier is chosen.
    id: Optional[str] = Field(
        default=None,
        description="Stable identifier for the evaluator, if known. Scheme TBD.",
    )
    # TODO(v0): how the image is sourced/stored is the subject of B4b (#37). Photos are
    # served from the Firebase Hosting deploy, so this is typically a site-relative path
    # (e.g. "/images/evaluators/<id>.webp"); an absolute URL is also valid. Optional and
    # often absent — many evaluators (external opponents especially) have no photo.
    image_url: Optional[str] = Field(
        default=None,
        description="Profile image reference (site-relative path or absolute URL), if any.",
    )
    role: Optional[EvaluatorRole] = Field(
        default=None,
        description="Role for the referencing thesis, if applicable.",
    )


# ---------------------------------------------------------------------------
# RawThesis — as scraped, intentionally minimal & loose
# ---------------------------------------------------------------------------


class RawThesis(BaseModel):
    """A raw scraped thesis record, before parsing/normalisation.

    ``v0`` — intentionally minimal. We only commit to the provenance fields needed
    to fetch, dedupe, and re-parse a record; everything else lives untyped in
    ``raw_fields`` until the parser shape is known.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(
        ...,
        description="Identifier of the record in the source system (e.g. a thesis id).",
    )
    source_url: str = Field(..., description="URL the record was fetched from.")
    fetched_at: datetime = Field(
        ...,
        description="UTC timestamp when the record was fetched.",
    )
    # TODO(v0): shape of the raw payload is unconfirmed until the scraper (A1) lands.
    # Free-form holder for whatever the scraper captured (HTML fragments, extracted
    # key/value pairs, PDF text, etc.). Keep untyped on purpose for v0.
    raw_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form bag of raw scraped fields. Untyped for v0.",
    )


# ---------------------------------------------------------------------------
# ParsedThesis — normalised
# ---------------------------------------------------------------------------


class ParsedThesis(BaseModel):
    """A normalised thesis record produced by the parser.

    ``v0`` — the core fields the web app needs for the supervisor + opponent lookup,
    plus light metadata. Some fields are optional because not every source record
    will expose them.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable id for the thesis (carried from RawThesis).")
    title: str = Field(..., description="Thesis title.")
    author: str = Field(..., description="Thesis author (student) full name.")
    year: int = Field(..., description="Year of defense / submission.")
    level: Level = Field(..., description="bachelor or master.")
    # TODO(v0): language codes unconfirmed; likely ISO 639-1 ("cs"/"en") but the
    # source's representation is not yet known.
    language: Optional[str] = Field(
        default=None,
        description="Language of the thesis (e.g. 'cs', 'en'). Optional for v0.",
    )
    supervisor: Evaluator = Field(..., description="The thesis supervisor.")
    # TODO(v0): a thesis may in principle have more than one opponent; v0 models a
    # single opponent. Revisit if multi-opponent records appear in real fixtures.
    opponent: Evaluator = Field(..., description="The thesis opponent.")
    # TODO(v0): grade scale unconfirmed — see GRADE SCALE NOTE above. Optional
    # because some records (e.g. not-yet-defended) may lack a grade.
    defense_grade: Optional[Grade] = Field(
        default=None,
        ge=GRADE_MIN,
        le=GRADE_MAX,
        description="Overall defense grade on the provisional 1-4 scale (1 = best).",
    )
    abstract: Optional[str] = Field(default=None, description="Thesis abstract.")
    source_url: str = Field(..., description="URL of the source record.")


# ---------------------------------------------------------------------------
# EvaluatorStats — aggregated per evaluator
# ---------------------------------------------------------------------------


class EvaluatorStats(BaseModel):
    """Per-evaluator aggregated grade statistics — the artifact the web app serves.

    ``v0`` — grade distribution (counts) and probabilities (normalised) are keyed by
    the string form of the grade so the JSON is self-describing and the grade type
    can change without reshaping the contract.
    """

    model_config = ConfigDict(extra="forbid")

    evaluator: Evaluator = Field(..., description="The evaluator these stats describe.")
    total_theses: int = Field(
        ...,
        ge=0,
        description="Total number of theses this evaluator evaluated in the dataset.",
    )
    # TODO(v0): grade keys are the string form of the provisional 1-4 grade. The
    # key space follows whatever the final grade scale becomes (see GRADE SCALE NOTE).
    grade_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Count of theses per grade, keyed by grade as a string.",
    )
    # TODO(v0): probabilities should sum to ~1 across grades (allowing float error).
    # Not enforced as a validator in v0 to keep the draft loose; the aggregator is
    # responsible for normalising. Revisit whether to validate the sum.
    grade_probabilities: dict[str, float] = Field(
        default_factory=dict,
        description="Probability of each grade (counts normalised to ~1.0).",
    )
    # TODO(v0): optional breakdowns are best-effort and their inner shape mirrors
    # grade_distribution. Keys are the role/level value (e.g. 'supervisor', 'master').
    by_role: Optional[dict[str, dict[str, int]]] = Field(
        default=None,
        description="Optional grade distribution broken down by evaluator role.",
    )
    by_level: Optional[dict[str, dict[str, int]]] = Field(
        default=None,
        description="Optional grade distribution broken down by thesis level.",
    )
    last_updated: date = Field(
        ...,
        description="Date these aggregates were last recomputed.",
    )
