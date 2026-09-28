#!/usr/bin/env python3
"""Regenerate weapon_features.json and fail if the checked snapshot is stale."""

from __future__ import annotations

import difflib
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    extractor = Path(__file__).with_name("extract_weapon_features.py")
    expected = Path(__file__).with_name("weapon_features.json")

    with tempfile.TemporaryDirectory() as tmpdir:
        generated = Path(tmpdir) / "weapon_features.json"
        subprocess.run(
            [
                sys.executable,
                str(extractor),
                "--repo-root",
                str(repo),
                "--output",
                str(generated),
            ],
            check=True,
        )

        expected_bytes = expected.read_bytes()
        generated_bytes = generated.read_bytes()
        if expected_bytes == generated_bytes:
            print("weapon feature snapshot is up to date")
            return 0

        print(
            "weapon feature snapshot is stale; regenerate with "
            "tools/weapon-similarity/extract_weapon_features.py",
            file=sys.stderr,
        )

        old = expected.read_text(encoding="utf-8").splitlines()
        new = generated.read_text(encoding="utf-8").splitlines()
        diff = difflib.unified_diff(
            old,
            new,
            fromfile=str(expected.relative_to(repo)),
            tofile="regenerated weapon_features.json",
            lineterm="",
        )
        for line_number, line in enumerate(diff):
            if line_number >= 200:
                print("... diff truncated ...", file=sys.stderr)
                break
            print(line, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
