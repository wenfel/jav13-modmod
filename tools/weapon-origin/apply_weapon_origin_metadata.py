#!/usr/bin/env python3
"""Apply and validate JA2 weapon origin/production metadata without reformatting Items.xml."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

IC_GUN = 0x00000002
IC_LAUNCHER = 0x00000010
IC_BOBBY_GUN = IC_GUN | IC_LAUNCHER

REQUIRED_COLUMNS = (
    "uiIndex",
    "xml_name",
    "item_class",
    "normalized_identity",
    "production_year_start",
    "production_year_end",
    "origin_codes",
    "origin_mask_hex",
    "status",
    "confidence",
    "source_1",
    "source_2",
    "notes",
)
STATUSES = {
    "CONFIRMED",
    "PROTOTYPE",
    "FICTIONAL_SCIFI",
    "FICTIONAL_UNFLAGGED",
    "AMBIGUOUS_VARIANT",
    "RANDOM_WRAPPER",
    "MISSING_ORIGIN_BIT",
    "UNRESOLVED",
}
CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
METADATA_TAGS = ("ProductionYearStart", "ProductionYearEnd", "WeaponOriginFlags")
ITEM_RE = re.compile(r"<ITEM>(?P<body>[\s\S]*?)</ITEM>")
TAG_CACHE: dict[str, re.Pattern[str]] = {}


class MetadataError(RuntimeError):
    pass


def tag_re(tag: str) -> re.Pattern[str]:
    if tag not in TAG_CACHE:
        TAG_CACHE[tag] = re.compile(
            rf"<{re.escape(tag)}>(?P<value>[\s\S]*?)</{re.escape(tag)}>"
        )
    return TAG_CACHE[tag]


def get_tag(body: str, tag: str, *, required: bool = False) -> str:
    matches = list(tag_re(tag).finditer(body))
    if len(matches) > 1:
        raise MetadataError(f"duplicate <{tag}> tag")
    if not matches:
        if required:
            raise MetadataError(f"missing <{tag}> tag")
        return ""
    return matches[0].group("value").strip()


def parse_int(text: str, field: str, ui_index: int, maximum: int) -> int:
    try:
        value = int(text.strip(), 0)
    except ValueError as exc:
        raise MetadataError(
            f"uiIndex {ui_index}: invalid {field} value {text!r}"
        ) from exc
    if not 0 <= value <= maximum:
        raise MetadataError(
            f"uiIndex {ui_index}: {field}={value} outside 0..{maximum}"
        )
    return value


def xml_unescape(text: str) -> str:
    return (
        text.replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )


def read_items(xml_text: str) -> dict[int, dict[str, object]]:
    items: dict[int, dict[str, object]] = {}
    for match in ITEM_RE.finditer(xml_text):
        body = match.group("body")
        index_text = get_tag(body, "uiIndex", required=True)
        try:
            ui_index = int(index_text, 0)
        except ValueError as exc:
            raise MetadataError(f"invalid uiIndex {index_text!r}") from exc
        if ui_index in items:
            raise MetadataError(f"duplicate uiIndex {ui_index} in XML")
        try:
            item_class = int(get_tag(body, "usItemClass", required=True), 0)
        except ValueError as exc:
            raise MetadataError(f"uiIndex {ui_index}: invalid usItemClass") from exc
        items[ui_index] = {
            "body": body,
            "span": match.span(),
            "name": xml_unescape(get_tag(body, "szItemName", required=True)),
            "long_name": xml_unescape(get_tag(body, "szLongItemName")),
            "item_class": item_class,
        }
    if not items:
        raise MetadataError("no <ITEM> rows found")
    return items


def read_manifest(path: Path) -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing_columns:
            raise MetadataError(
                "manifest missing columns: " + ", ".join(missing_columns)
            )
        for line_number, row in enumerate(reader, start=2):
            try:
                ui_index = int(row["uiIndex"], 10)
            except ValueError as exc:
                raise MetadataError(
                    f"manifest line {line_number}: invalid uiIndex {row['uiIndex']!r}"
                ) from exc
            if ui_index in rows:
                raise MetadataError(f"duplicate manifest uiIndex {ui_index}")
            status = row["status"].strip()
            confidence = row["confidence"].strip()
            if status not in STATUSES:
                raise MetadataError(f"uiIndex {ui_index}: invalid status {status!r}")
            if confidence not in CONFIDENCE:
                raise MetadataError(
                    f"uiIndex {ui_index}: invalid confidence {confidence!r}"
                )
            start = parse_int(
                row["production_year_start"], "production_year_start", ui_index, 0xFFFF
            )
            end = parse_int(
                row["production_year_end"], "production_year_end", ui_index, 0xFFFF
            )
            mask = parse_int(
                row["origin_mask_hex"], "origin_mask_hex", ui_index, 0xFFFFFFFFFFFFFFFF
            )
            if start and end and end < start:
                raise MetadataError(
                    f"uiIndex {ui_index}: production end {end} precedes start {start}"
                )
            if confidence == "LOW" and (start or end or mask):
                raise MetadataError(
                    f"uiIndex {ui_index}: LOW-confidence rows must remain zero-valued"
                )
            row["_start"] = str(start)
            row["_end"] = str(end)
            row["_mask"] = f"0x{mask:016X}"
            rows[ui_index] = row
    return rows


def validate_coverage(
    items: dict[int, dict[str, object]], manifest: dict[int, dict[str, str]]
) -> list[int]:
    targets = sorted(
        ui_index
        for ui_index, item in items.items()
        if int(item["item_class"]) & IC_BOBBY_GUN
    )
    target_set = set(targets)
    manifest_set = set(manifest)
    missing = sorted(target_set - manifest_set)
    extra = sorted(manifest_set - target_set)
    if missing:
        raise MetadataError(
            "target firearm/launcher rows missing from manifest: "
            + ", ".join(map(str, missing))
        )
    if extra:
        raise MetadataError(
            "manifest rows are not current firearm/launcher targets: "
            + ", ".join(map(str, extra))
        )
    for ui_index in targets:
        expected = manifest[ui_index]["xml_name"]
        actual = str(items[ui_index]["name"])
        if expected != actual:
            raise MetadataError(
                f"uiIndex {ui_index}: XML name {actual!r} != manifest xml_name {expected!r}"
            )
    return targets


def canonical_values(row: dict[str, str]) -> dict[str, str]:
    return {
        "ProductionYearStart": row["_start"],
        "ProductionYearEnd": row["_end"],
        "WeaponOriginFlags": row["_mask"],
    }


def check_xml(
    items: dict[int, dict[str, object]],
    manifest: dict[int, dict[str, str]],
    targets: list[int],
) -> None:
    errors: list[str] = []
    for ui_index in targets:
        body = str(items[ui_index]["body"])
        expected = canonical_values(manifest[ui_index])
        for tag, expected_value in expected.items():
            matches = list(tag_re(tag).finditer(body))
            if len(matches) != 1:
                errors.append(
                    f"uiIndex {ui_index}: expected exactly one <{tag}>, found {len(matches)}"
                )
                continue
            actual = matches[0].group("value").strip()
            try:
                if tag == "WeaponOriginFlags":
                    actual_norm = f"0x{int(actual, 0):016X}"
                else:
                    actual_norm = str(int(actual, 0))
            except ValueError:
                errors.append(
                    f"uiIndex {ui_index}: invalid XML value for <{tag}>: {actual!r}"
                )
                continue
            if actual_norm != expected_value:
                errors.append(
                    f"uiIndex {ui_index}: <{tag}> XML={actual_norm} manifest={expected_value}"
                )
    if errors:
        preview = "\n".join(errors[:50])
        more = "" if len(errors) <= 50 else f"\n... {len(errors) - 50} more"
        raise MetadataError("manifest/XML mismatch:\n" + preview + more)


def replace_block_metadata(body: str, row: dict[str, str], eol: str) -> str:
    # Remove only complete metadata-tag lines. This avoids duplicate tags and
    # leaves every unrelated character in the ITEM block untouched.
    for tag in METADATA_TAGS:
        body = re.sub(
            rf"(?m)^[ \t]*<{tag}>[\s\S]*?</{tag}>[ \t]*(?:\r?\n)?",
            "",
            body,
            count=0,
        )

    class_match = re.search(
        r"(?m)^(?P<indent>[ \t]*)<usItemClass>[^\r\n]*</usItemClass>[ \t]*(?:\r?\n|$)",
        body,
    )
    if not class_match:
        raise MetadataError(
            f"uiIndex {row['uiIndex']}: cannot find canonical <usItemClass> line"
        )
    indent = class_match.group("indent")
    values = canonical_values(row)
    insertion = "".join(
        f"{indent}<{tag}>{values[tag]}</{tag}>{eol}" for tag in METADATA_TAGS
    )
    return body[: class_match.end()] + insertion + body[class_match.end() :]


def apply_metadata(
    xml_text: str,
    items: dict[int, dict[str, object]],
    manifest: dict[int, dict[str, str]],
    targets: list[int],
) -> str:
    eol = "\r\n" if "\r\n" in xml_text else "\n"
    replacements: list[tuple[int, int, str]] = []
    for ui_index in targets:
        item = items[ui_index]
        start, end = item["span"]  # type: ignore[misc]
        body = str(item["body"])
        new_body = replace_block_metadata(body, manifest[ui_index], eol)
        replacements.append((int(start), int(end), "<ITEM>" + new_body + "</ITEM>"))

    result = xml_text
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]

    try:
        ET.fromstring(result)
    except ET.ParseError as exc:
        raise MetadataError(f"resulting Items.xml is not well formed: {exc}") from exc
    return result


def report(manifest: dict[int, dict[str, str]], targets: list[int]) -> None:
    status_counts = Counter(manifest[i]["status"] for i in targets)
    nonzero_origin = sum(int(manifest[i]["origin_mask_hex"], 0) != 0 for i in targets)
    nonzero_start = sum(
        int(manifest[i]["production_year_start"], 0) != 0 for i in targets
    )
    nonzero_end = sum(
        int(manifest[i]["production_year_end"], 0) != 0 for i in targets
    )

    print(f"total target firearm/launcher rows: {len(targets)}")
    print(f"nonzero origin masks: {nonzero_origin}")
    print(f"nonzero production start years: {nonzero_start}")
    print(f"nonzero production end years: {nonzero_end}")
    for status in sorted(STATUSES):
        print(f"{status}: {status_counts[status]}")
    if sum(status_counts.values()) != len(targets):
        raise MetadataError("status totals do not reconcile with target-row count")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--xml",
        type=Path,
        default=repo_root / "gamedir/Data-1.13/TableData/Items/Items.xml",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("weapon_origin_metadata.csv"),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate coverage and require Items.xml to match the manifest",
    )
    args = parser.parse_args()

    xml_bytes = args.xml.read_bytes()
    xml_text = xml_bytes.decode("utf-8-sig")
    items = read_items(xml_text)
    manifest = read_manifest(args.manifest)
    targets = validate_coverage(items, manifest)

    if args.check:
        try:
            ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise MetadataError(f"Items.xml is not well formed: {exc}") from exc
        check_xml(items, manifest, targets)
        report(manifest, targets)
        print("metadata check: OK")
        return 0

    new_text = apply_metadata(xml_text, items, manifest, targets)
    if new_text == xml_text:
        print("Items.xml already matches manifest")
    else:
        args.xml.write_bytes(new_text.encode("utf-8"))
        print(f"updated {args.xml}")
    # Re-parse and verify what was actually written.
    written = args.xml.read_bytes().decode("utf-8-sig")
    written_items = read_items(written)
    written_targets = validate_coverage(written_items, manifest)
    check_xml(written_items, manifest, written_targets)
    report(manifest, written_targets)
    print("metadata apply: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MetadataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
