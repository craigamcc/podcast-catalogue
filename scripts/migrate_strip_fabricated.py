#!/usr/bin/env python3
"""Strip fabricated applePodcastPage links from a catalogue JSONL file.

The deleted inject_referrals.py script once overwrote applePodcastPage for
every show: real-looking links for 5 hardcoded shows, synthesized
podcasts.apple.com/au/search?term=... URLs for the rest, presented as fact.
This migration nulls any applePodcastPage matching that search-URL pattern.

Idempotent: running it twice changes nothing the second time. Writes
atomically (tmp + os.replace). See PRODUCTION_PLAN.md Phase 3.3.

Usage: python scripts/migrate_strip_fabricated.py <catalogue.jsonl>
"""
from __future__ import annotations

import json
import os
import sys

FABRICATED_PATTERN = "podcasts.apple.com/au/search?term="


def migrate(path: str) -> tuple[int, int]:
    """Returns (total_records, records_cleaned)."""
    total = 0
    cleaned = 0
    tmp_path = path + ".tmp"

    with open(path, "r", encoding="utf-8") as src, open(tmp_path, "w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            record = json.loads(line)
            total += 1
            link = record.get("applePodcastPage")
            if isinstance(link, str) and FABRICATED_PATTERN in link:
                record["applePodcastPage"] = None
                cleaned += 1
            dst.write(json.dumps(record, ensure_ascii=False) + "\n")

    if cleaned:
        os.replace(tmp_path, path)
    else:
        os.remove(tmp_path)
    return total, cleaned


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"Error: {path} not found")
        return 1
    total, cleaned = migrate(path)
    print(f"{path}: {total} records scanned, {cleaned} fabricated applePodcastPage link(s) nulled.")
    if cleaned == 0:
        print("File was already clean — nothing changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
