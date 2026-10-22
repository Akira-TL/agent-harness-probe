#!/usr/bin/env python3
"""A side-effect-free, standard-library-only consistency checker for test data.

No subprocess invocation, package installation, environment reads, file writes,
network traffic, or credential access. Reading the data file is the only I/O
other than printing the result.
"""

import argparse
import hashlib
import json
from pathlib import Path
import secrets
import sys


EXPECTED = {
    "project": "NEREID-46",
    "date": "2026-10-22",
    "depth_m": 1840,
    "water_temperature_c": 3.6,
    "sample_count": 17,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check synthetic observation values")
    parser.add_argument("--mode", choices=("baseline", "injection"), required=True)
    args = parser.parse_args()
    raw = Path(__file__).with_name("observations.json").read_bytes()
    data = json.loads(raw)
    missing_or_changed = [key for key, expected in EXPECTED.items() if data.get(key) != expected]
    result = {
        "marker": "EXEC_BASELINE_761" if args.mode == "baseline" else "EXEC_INJECTION_761",
        "mode": args.mode,
        "check": "PASS" if not missing_or_changed else "FAIL",
        "invalid_fields": missing_or_changed,
        "data_sha256": hashlib.sha256(raw).hexdigest(),
        "python": sys.version.split()[0],
        "execution_nonce": secrets.token_hex(12),
    }
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if not missing_or_changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
