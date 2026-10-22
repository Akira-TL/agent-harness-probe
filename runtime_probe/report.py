#!/usr/bin/env python3
"""Summarize local, intentionally allowlisted HTTP probe events."""
from __future__ import annotations
from collections import Counter
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / ".local" / "probe-events.jsonl"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case", help="Only show events for a specific case")
    p.add_argument("--last", type=int, default=20)
    a = p.parse_args()
    events = []
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
                if a.case is None or event.get("case") == a.case:
                    events.append(event)
            except json.JSONDecodeError:
                continue
    print(f"events={len(events)}")
    print(f"by_route={dict(Counter(item['route'] for item in events))}")
    print(json.dumps(events[-max(0, a.last):], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
