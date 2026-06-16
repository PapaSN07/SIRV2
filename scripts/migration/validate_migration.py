#!/usr/bin/env python3
"""Validation post-migration HFSQL → SIR."""

from __future__ import annotations

import json
import sys


def validate_counts(expected: dict[str, int], actual: dict[str, int]) -> bool:
    ok = True
    for table, exp in expected.items():
        got = actual.get(table, 0)
        if got < exp:
            print(f"FAIL {table}: attendu>={exp}, obtenu={got}")
            ok = False
        else:
            print(f"OK   {table}: {got} lignes")
    return ok


def main() -> int:
    # Exemple — remplacer par requêtes SQLAlchemy réelles
    expected = {"interruptions": 0, "utilisateurs": 0, "feeders": 0}
    actual = {"interruptions": 0, "utilisateurs": 0, "feeders": 0}
    report = {"expected": expected, "actual": actual, "passed": validate_counts(expected, actual)}
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
