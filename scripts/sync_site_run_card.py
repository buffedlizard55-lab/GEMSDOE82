#!/usr/bin/env python3
"""Copy the canonical registry run card into the static Pages artifact."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "registry" / "run_card.json"
DESTINATION = ROOT / "docs" / "data" / "run_card.json"


def sync_run_card(source: Path = SOURCE, destination: Path = DESTINATION) -> Path:
    """Validate JSON and write an exact-content site copy; return its path."""
    payload = Path(source).read_bytes()
    json.loads(payload)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


def main() -> int:
    target = sync_run_card()
    print(f"Synchronized run card: {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
