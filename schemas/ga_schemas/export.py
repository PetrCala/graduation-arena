"""Export JSON Schema from the pydantic models, and check the contract for drift.

Two modes:

* ``python -m ga_schemas.export`` — (re)generates the JSON Schema files under
  ``schemas/json/`` from the pydantic models and validates every fixture under
  ``data/fixtures/`` against the corresponding model.
* ``python -m ga_schemas.export --check`` — generates nothing; instead it *verifies*
  the contract is internally consistent and exits non-zero if not:
    1. committed ``schemas/json/`` matches what the models would generate (stale-schema guard),
    2. every fixture validates,
    3. the hand-authored ``schemas/ts/types.ts`` agrees with the schema on field names,
       optionality, and enum members (TS<->schema drift guard).

The TS check is intentionally structural, not a full type-equality check: it catches the
common drift (a field added/renamed/removed, a required<->optional flip, an enum member
added/removed) without the noisy generator ``v0`` deliberately avoids. Full type-level
generation is deferred to K1.

Part of the provisional ``v0`` data contract (issue #4). See ``ga_schemas.models``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from .models import EvaluatorStats, ParsedThesis, RawThesis

# Repo-relative locations. This module lives at schemas/ga_schemas/export.py.
PKG_DIR = Path(__file__).resolve().parent
SCHEMAS_DIR = PKG_DIR.parent
REPO_ROOT = SCHEMAS_DIR.parent
JSON_DIR = SCHEMAS_DIR / "json"
TS_DIR = SCHEMAS_DIR / "ts"
FIXTURES_DIR = REPO_ROOT / "data" / "fixtures"

# Models to export, mapped to their JSON Schema filename stem.
MODELS: dict[str, Type[BaseModel]] = {
    "raw_thesis": RawThesis,
    "parsed_thesis": ParsedThesis,
    "evaluator_stats": EvaluatorStats,
}

# Fixtures to validate: filename -> model.
FIXTURES: dict[str, Type[BaseModel]] = {
    "parsed_thesis.example.json": ParsedThesis,
    "evaluator_stats.example.json": EvaluatorStats,
}

# TS interface name -> JSON Schema object that defines its fields. A tuple of
# (model stem, $defs key); a key of ``None`` means the schema's root object.
TS_OBJECTS: dict[str, tuple[str, str | None]] = {
    "Evaluator": ("parsed_thesis", "Evaluator"),
    "RawThesis": ("raw_thesis", None),
    "ParsedThesis": ("parsed_thesis", None),
    "EvaluatorStats": ("evaluator_stats", None),
}

# TS string-literal union alias -> JSON Schema enum ($defs key).
TS_ENUMS: dict[str, str] = {
    "Level": "Level",
    "EvaluatorRole": "EvaluatorRole",
}


def build_schemas() -> dict[str, dict]:
    """Generate the JSON Schema for every model from the pydantic source of truth."""
    return {name: model.model_json_schema() for name, model in MODELS.items()}


def _dump(schema: dict) -> str:
    """Serialise a schema exactly as it is written to disk."""
    return json.dumps(schema, indent=2) + "\n"


def write_schemas(schemas: dict[str, dict]) -> None:
    """Write ``<name>.schema.json`` for each model into ``schemas/json/``."""
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas.items():
        out = JSON_DIR / f"{name}.schema.json"
        out.write_text(_dump(schema), encoding="utf-8")
        print(f"  wrote {out.relative_to(REPO_ROOT)}")


def check_schemas_fresh(schemas: dict[str, dict]) -> int:
    """Fail if any committed JSON Schema differs from what the models generate."""
    failures = 0
    for name, schema in schemas.items():
        out = JSON_DIR / f"{name}.schema.json"
        if not out.exists():
            print(f"  MISSING {out.relative_to(REPO_ROOT)} (run export to generate)")
            failures += 1
            continue
        committed = json.loads(out.read_text(encoding="utf-8"))
        if committed == schema:
            print(f"  fresh   {out.relative_to(REPO_ROOT)}")
        else:
            print(f"  STALE   {out.relative_to(REPO_ROOT)} (models changed; re-run export)")
            failures += 1
    return failures


def validate_fixtures() -> int:
    """Validate each example fixture against its model. Returns a failure count."""
    failures = 0
    for filename, model in FIXTURES.items():
        path = FIXTURES_DIR / filename
        if not path.exists():
            print(f"  MISSING {path.relative_to(REPO_ROOT)}")
            failures += 1
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            model.model_validate(data)
        except Exception as exc:  # noqa: BLE001 - surface any validation error
            print(f"  INVALID {path.relative_to(REPO_ROOT)}: {exc}")
            failures += 1
        else:
            print(f"  ok      {path.relative_to(REPO_ROOT)} -> {model.__name__}")
    return failures


def _resolve_object(schemas: dict[str, dict], stem: str, defs_key: str | None) -> dict:
    """Return the schema object for a model (root) or one of its ``$defs`` entries."""
    schema = schemas[stem]
    if defs_key is None:
        return schema
    return schema["$defs"][defs_key]


def _ts_interfaces(text: str) -> dict[str, dict[str, bool]]:
    """Map each ``export interface`` to ``{field_name: is_optional}``.

    Interfaces in ``types.ts`` are flat (no inline nested objects), so the body is
    everything up to the first ``}``.
    """
    interfaces: dict[str, dict[str, bool]] = {}
    for match in re.finditer(r"export interface (\w+)\s*\{([^}]*)\}", text):
        name, body = match.group(1), match.group(2)
        fields: dict[str, bool] = {}
        for line in body.splitlines():
            field = re.match(r"\s*(\w+)(\??)\s*:", line)
            if field:
                fields[field.group(1)] = bool(field.group(2))
        interfaces[name] = fields
    return interfaces


def _ts_string_unions(text: str) -> dict[str, set[str]]:
    """Map each ``export type X = "a" | "b";`` alias to its set of string literals."""
    unions: dict[str, set[str]] = {}
    for match in re.finditer(r"export type (\w+)\s*=\s*([^;]+);", text):
        name, rhs = match.group(1), match.group(2)
        literals = set(re.findall(r'"([^"]+)"', rhs))
        if literals:
            unions[name] = literals
    return unions


def check_ts(schemas: dict[str, dict]) -> int:
    """Fail if ``types.ts`` disagrees with the schema on fields, optionality, or enums."""
    types_path = TS_DIR / "types.ts"
    if not types_path.exists():
        print(f"  MISSING {types_path.relative_to(REPO_ROOT)}")
        return 1

    text = types_path.read_text(encoding="utf-8")
    interfaces = _ts_interfaces(text)
    unions = _ts_string_unions(text)
    failures = 0

    for ts_name, (stem, defs_key) in TS_OBJECTS.items():
        obj = _resolve_object(schemas, stem, defs_key)
        schema_fields = set(obj.get("properties", {}))
        required = set(obj.get("required", []))
        ts_fields = interfaces.get(ts_name)
        if ts_fields is None:
            print(f"  TS MISS interface {ts_name} not found in types.ts")
            failures += 1
            continue

        if set(ts_fields) != schema_fields:
            only_ts = set(ts_fields) - schema_fields
            only_schema = schema_fields - set(ts_fields)
            print(f"  TS DRIFT {ts_name} fields differ: +ts={sorted(only_ts)} "
                  f"+schema={sorted(only_schema)}")
            failures += 1
            continue

        field_failures = 0
        for field, optional in ts_fields.items():
            schema_optional = field not in required
            if optional != schema_optional:
                print(f"  TS DRIFT {ts_name}.{field}: ts optional={optional} "
                      f"schema optional={schema_optional}")
                field_failures += 1
        failures += field_failures
        if field_failures == 0:
            print(f"  ts ok   {ts_name}")

    for ts_name, defs_key in TS_ENUMS.items():
        enum_def = None
        for schema in schemas.values():
            enum_def = schema.get("$defs", {}).get(defs_key)
            if enum_def is not None:
                break
        if enum_def is None:
            print(f"  TS MISS enum {defs_key} not found in any schema")
            failures += 1
            continue
        schema_members = set(enum_def.get("enum", []))
        ts_members = unions.get(ts_name)
        if ts_members is None:
            print(f"  TS MISS type alias {ts_name} not found in types.ts")
            failures += 1
        elif ts_members != schema_members:
            print(f"  TS DRIFT {ts_name} members differ: ts={sorted(ts_members)} "
                  f"schema={sorted(schema_members)}")
            failures += 1
        else:
            print(f"  ts ok   {ts_name} (enum)")

    return failures


def run_export() -> int:
    """Write schemas and validate fixtures (the generate-artifacts path)."""
    print("Exporting JSON Schema:")
    write_schemas(build_schemas())
    print("Validating fixtures:")
    failures = validate_fixtures()
    if failures:
        print(f"\nFAILED: {failures} fixture(s) did not validate.")
        return 1
    print("\nOK: schemas exported and all fixtures valid.")
    return 0


def run_check() -> int:
    """Verify schemas are fresh, fixtures valid, and TS in sync (the CI path)."""
    schemas = build_schemas()
    print("Checking committed JSON Schema is fresh:")
    failures = check_schemas_fresh(schemas)
    print("Validating fixtures:")
    failures += validate_fixtures()
    print("Checking TS types match the schema:")
    failures += check_ts(schemas)
    if failures:
        print(f"\nFAILED: {failures} contract check(s) failed.")
        return 1
    print("\nOK: schemas fresh, fixtures valid, TS in sync.")
    return 0


def main(argv: list[str]) -> int:
    if "--check" in argv:
        return run_check()
    return run_export()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
