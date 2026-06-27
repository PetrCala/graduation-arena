"""Normalise harvested XOAI metadata into the shared parsed-thesis contract."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from ga_schemas.models import Evaluator, EvaluatorRole, Level, ParsedThesis, RawThesis

IES_DEPARTMENTS = {
    "institut ekonomickych studii",
    "institute of economic studies",
}
DEFENDED_STATUSES = {"o", "obhajeno", "defended"}
GRADE_BY_TEXT = {
    "vyborne": 1,
    "excellent": 1,
    "velmi dobre": 2,
    "very good": 2,
    "dobre": 3,
    "good": 3,
    "neprospel": 4,
    "neprospela": 4,
    "failed": 4,
}
GRADE_BY_CODE = {"a": 1, "b": 1, "c": 2, "d": 2, "e": 3, "f": 4}


class ParseSkipError(ValueError):
    """Raised when a raw record is intentionally excluded from parsed output."""


def parse_raw_thesis(thesis: RawThesis, *, require_ies: bool = True) -> ParsedThesis:
    """Convert one ``RawThesis`` into ``ParsedThesis`` or raise ``ParseSkipError``."""
    metadata = thesis.raw_fields.get("metadata", {})
    tree = XoaiTree(metadata)

    if require_ies and not _is_ies_record(tree):
        raise ParseSkipError("not an IES thesis")

    defense_status = tree.first(["uk", "thesis", "defenceStatus"])
    supervisor = _first_required(tree, ["dc", "contributor", "advisor"], "supervisor")
    opponent = _first_required(tree, ["dc", "contributor", "referee"], "opponent")
    grade = _normalise_grade(tree.values(["thesis", "grade"]))
    if grade is None and _is_defended(defense_status):
        raise ParseSkipError("defended thesis is missing a parseable grade")

    return ParsedThesis(
        id=_thesis_id(thesis.source_id),
        title=_first_required(tree, ["dc", "title"], "title"),
        author=_first_required(tree, ["dc", "creator"], "author"),
        year=_normalise_year(
            tree.first(["dcterms", "dateAccepted"])
            or tree.first(["dcterms", "created"])
            or tree.first(["dc", "date", "issued"])
        ),
        level=_normalise_level(
            tree.first(["thesis", "degree", "name"])
            or tree.first(["thesis", "degree", "level"])
            or tree.first(["dc", "type"])
        ),
        language=_normalise_language(tree.first(["dc", "language", "iso"])),
        supervisor=_evaluator(supervisor, EvaluatorRole.supervisor),
        opponent=_evaluator(opponent, EvaluatorRole.opponent),
        defense_grade=grade,
        abstract=tree.first(["dc", "description", "abstract"]),
        source_url=thesis.source_url,
    )


class XoaiTree:
    """Small helper for reading values from the nested JSON emitted by ``oai.py``."""

    def __init__(self, root: dict[str, Any]) -> None:
        self.root = root

    def first(self, path: list[str]) -> str | None:
        return next(iter(self.values(path)), None)

    def values(self, path: list[str]) -> list[str]:
        nodes = [self.root]
        for part in path:
            nodes = [
                child
                for node in nodes
                for child in node.get("children", [])
                if child.get("attrs", {}).get("name") == part
            ]
        return list(_leaf_texts(nodes))


def _leaf_texts(nodes: Iterable[dict[str, Any]]) -> Iterable[str]:
    for node in nodes:
        text = node.get("text")
        if isinstance(text, str) and text.strip():
            yield text.strip()
        yield from _leaf_texts(node.get("children", []))


def _first_required(tree: XoaiTree, path: list[str], field_name: str) -> str:
    value = tree.first(path)
    if not value:
        raise ParseSkipError(f"missing {field_name}")
    return value


def _is_ies_record(tree: XoaiTree) -> bool:
    return any(
        _fold(value) in IES_DEPARTMENTS
        for value in tree.values(["dc", "description", "department"])
    )


def _is_defended(status: str | None) -> bool:
    return status is None or _fold(status) in DEFENDED_STATUSES


def _normalise_grade(values: Iterable[str]) -> int | None:
    for value in values:
        folded = _fold(value)
        if folded in GRADE_BY_TEXT:
            return GRADE_BY_TEXT[folded]
        if folded in GRADE_BY_CODE:
            return GRADE_BY_CODE[folded]
        if folded.isdigit() and 1 <= int(folded) <= 4:
            return int(folded)
    return None


def _normalise_year(value: str | None) -> int:
    if not value:
        raise ParseSkipError("missing year")
    match = re.search(r"\d{4}", value)
    if not match:
        raise ParseSkipError("missing year")
    return int(match.group(0))


def _normalise_level(value: str | None) -> Level:
    folded = _fold(value or "")
    if "bc" in folded or "bakalar" in folded or "bachelor" in folded:
        return Level.bachelor
    if "mgr" in folded or "magistr" in folded or "diplom" in folded or "master" in folded:
        return Level.master
    raise ParseSkipError("unsupported thesis level")


def _normalise_language(value: str | None) -> str | None:
    if not value:
        return None
    folded = _fold(value).replace("_", "-")
    if folded.startswith("en") or folded == "english":
        return "en"
    if folded.startswith("cs") or folded.startswith("cz") or folded in {"czech", "cesky"}:
        return "cs"
    return folded[:2] if len(folded) >= 2 else folded


def _evaluator(name: str, role: EvaluatorRole) -> Evaluator:
    return Evaluator(name=name, id=_person_slug(name), role=role)


def _person_slug(name: str) -> str:
    stripped = re.sub(
        r"\b(doc|prof|phdr|mgr|ing|bc|phd|ph\.d|csc|ma|mba|rndr)\.?\b",
        "",
        _fold(name),
    )
    parts = [part for part in re.split(r"[^a-z0-9]+", stripped) if part]
    if "," in name:
        family, given = name.split(",", 1)
        return "-".join([*_name_parts(family), *_name_parts(given)])
    return "-".join(parts)


def _name_parts(value: str) -> list[str]:
    return [part for part in re.split(r"[^a-z0-9]+", _fold(value)) if part]


def _thesis_id(source_id: str) -> str:
    return source_id.rsplit("/", 1)[-1].rsplit(":", 1)[-1]


def _fold(value: str) -> str:
    normalised = unicodedata.normalize("NFKD", value)
    ascii_value = normalised.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_value).strip().lower()
