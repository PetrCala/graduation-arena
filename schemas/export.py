"""Export JSON Schema from the pydantic models and validate the example fixtures.

Running ``python schemas/export.py`` (re)generates the JSON Schema files under
``schemas/json/`` and validates every fixture under ``data/fixtures/`` against the
corresponding pydantic model. It exits non-zero if any fixture fails to validate,
so it doubles as a check.

Part of the provisional ``v0`` data contract (issue #4). See ``schemas/models.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from models import EvaluatorStats, ParsedThesis, RawThesis

# Repo-relative locations.
SCHEMAS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCHEMAS_DIR.parent
JSON_DIR = SCHEMAS_DIR / "json"
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


def export_schemas() -> None:
    """Write ``<name>.schema.json`` for each model into ``schemas/json/``."""
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        schema = model.model_json_schema()
        out = JSON_DIR / f"{name}.schema.json"
        out.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"  wrote {out.relative_to(REPO_ROOT)}")


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


def main() -> int:
    print("Exporting JSON Schema:")
    export_schemas()
    print("Validating fixtures:")
    failures = validate_fixtures()
    if failures:
        print(f"\nFAILED: {failures} fixture(s) did not validate.")
        return 1
    print("\nOK: schemas exported and all fixtures valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
