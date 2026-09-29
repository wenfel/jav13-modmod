#!/usr/bin/env python3
"""Regenerate weapon_features.json and fail if the checked snapshot is stale."""

from __future__ import annotations

import difflib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path


def first_difference(expected, generated, path="$"):
    if isinstance(expected, dict) and isinstance(generated, dict):
        expected_keys = set(expected)
        generated_keys = set(generated)
        if expected_keys != generated_keys:
            return (
                path,
                {"missing": sorted(expected_keys - generated_keys),
                 "extra": sorted(generated_keys - expected_keys)},
                "different dictionary keys",
            )
        for key in expected:
            diff = first_difference(
                expected[key],
                generated[key],
                f"{path}.{key}",
            )
            if diff is not None:
                return diff
        return None

    if isinstance(expected, list) and isinstance(generated, list):
        if len(expected) != len(generated):
            return path, len(expected), len(generated)
        for index, (left, right) in enumerate(zip(expected, generated)):
            diff = first_difference(left, right, f"{path}[{index}]")
            if diff is not None:
                return diff
        return None

    if (
        isinstance(expected, (int, float))
        and not isinstance(expected, bool)
        and isinstance(generated, (int, float))
        and not isinstance(generated, bool)
    ):
        if not math.isclose(
            float(expected),
            float(generated),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            return path, expected, generated
        return None

    if expected != generated:
        return path, expected, generated
    return None


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

        expected_data = json.loads(expected.read_text(encoding="utf-8"))
        generated_data = json.loads(generated.read_text(encoding="utf-8"))

        required_fields = {"tactical_role", "replacement_family"}
        for weapon in generated_data.get("weapons", []):
            missing = required_fields - set(weapon)
            if missing:
                print(
                    f"generated weapon {weapon.get('uiIndex')} missing semantic fields: "
                    f"{sorted(missing)}",
                    file=sys.stderr,
                )
                return 1

        diff_value = first_difference(expected_data, generated_data)
        if diff_value is None:
            print("weapon feature snapshot is up to date")
            return 0

        print(
            "weapon feature snapshot is stale; regenerate with "
            "tools/weapon-similarity/extract_weapon_features.py",
            file=sys.stderr,
        )
        diff_path, expected_value, generated_value = diff_value
        print(f"first semantic difference: {diff_path}", file=sys.stderr)
        print(f"  expected:  {expected_value!r}", file=sys.stderr)
        print(f"  generated: {generated_value!r}", file=sys.stderr)

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
