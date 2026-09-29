#!/usr/bin/env python3
"""Read-only JA2 weapon catalogue indexing, comparison, and relationship queries."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

DEFAULT_LIMIT = 40
TOOL_VERSION = 1

MANUFACTURER_ALIASES = (
    (re.compile(r"\bheckler\s*(?:&|and)\s*koch\b", re.I), "hk"),
    (re.compile(r"\bh\s*&\s*k\b", re.I), "hk"),
    (re.compile(r"\bfabrique\s+nationale(?:\s+herstal)?\b", re.I), "fn"),
    (re.compile(r"\bfn\s+herstal\b", re.I), "fn"),
)

FAMILY_SUFFIXES = (
    re.compile(r"\s*(?:-|\(|\[)?\s*(?:folded|collapsed)\s*[\)\]]?\s*$", re.I),
    re.compile(r"\s+(?:ras|tactical)\s*$", re.I),
    re.compile(r"\s+(?:iii)(?:\s*/\s*)?\s*$", re.I),
    re.compile(r"\s*(?:iii\s*/\s*)?\)\-\|\s*$", re.I),
    re.compile(r"\s*\(<\)\s*$", re.I),
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _root(path: Path) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"XML parse failed for {path}: {exc}") from exc


def _text(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    child = node.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _int_text(node: ET.Element | None, tag: str) -> int | None:
    value = _text(node, tag)
    if not value:
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None


def clean_display_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", value).strip()


def _apply_manufacturer_aliases(value: str) -> str:
    for pattern, replacement in MANUFACTURER_ALIASES:
        value = pattern.sub(replacement, value)
    return value


def identity_key(value: str) -> str:
    value = _apply_manufacturer_aliases(clean_display_name(value).lower())
    value = value.replace("&", " and ")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value)


def family_name(value: str) -> str:
    value = clean_display_name(value)
    previous = None
    while value != previous:
        previous = value
        for pattern in FAMILY_SUFFIXES:
            value = pattern.sub("", value).strip()
    return value


def family_key(value: str) -> str:
    return identity_key(family_name(value))


def _unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = clean_display_name(value)
        if not value or value.lower() == "nothing" or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def parse_items(path: Path) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    root = _root(path)
    if root.tag.upper() not in {"ITEMLIST", "ITEMS"}:
        raise ValueError(f"unexpected Items.xml root {root.tag!r} in {path}")

    records: dict[int, dict[str, Any]] = {}
    duplicates: list[int] = []
    invalid_ids = 0
    for item in root.findall(".//ITEM"):
        idx = _int_text(item, "uiIndex")
        if idx is None:
            invalid_ids += 1
            continue
        if idx in records:
            duplicates.append(idx)
        records[idx] = {
            "short_name": _text(item, "szItemName"),
            "long_name": _text(item, "szLongItemName"),
            "br_name": _text(item, "szBRName"),
            "item_class": _int_text(item, "usItemClass"),
            "class_index": _int_text(item, "ubClassIndex"),
            "item_size": _int_text(item, "ItemSize"),
            "two_handed": _int_text(item, "TwoHanded"),
        }
    meta = {
        "root": root.tag,
        "records": len(records),
        "duplicate_ids": sorted(set(duplicates)),
        "invalid_id_records": invalid_ids,
    }
    return records, meta


def parse_weapons(path: Path) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    root = _root(path)
    if root.tag.upper() != "WEAPONLIST":
        raise ValueError(f"unexpected Weapons.xml root {root.tag!r} in {path}")

    records: dict[int, dict[str, Any]] = {}
    duplicates: list[int] = []
    invalid_ids = 0
    for weapon in root.findall(".//WEAPON"):
        idx = _int_text(weapon, "uiIndex")
        if idx is None:
            invalid_ids += 1
            continue
        if idx in records:
            duplicates.append(idx)
        records[idx] = {
            "weapon_name": _text(weapon, "szWeaponName"),
            "weapon_class": _int_text(weapon, "ubWeaponClass"),
            "weapon_type": _int_text(weapon, "ubWeaponType"),
            "calibre": _int_text(weapon, "ubCalibre"),
            "mag_size": _int_text(weapon, "ubMagSize"),
        }
    meta = {
        "root": root.tag,
        "records": len(records),
        "duplicate_ids": sorted(set(duplicates)),
        "invalid_id_records": invalid_ids,
    }
    return records, meta


def build_index(items_path: Path, weapons_path: Path, source: str) -> dict[str, Any]:
    items, item_meta = parse_items(items_path)
    weapons, weapon_meta = parse_weapons(weapons_path)
    rows: list[dict[str, Any]] = []
    missing_items: list[int] = []

    for idx, weapon in sorted(weapons.items()):
        if idx == 0:
            continue
        item = items.get(idx)
        if item is None:
            missing_items.append(idx)
            item = {}
        aliases = _unique(
            [
                str(weapon.get("weapon_name") or ""),
                str(item.get("short_name") or ""),
                str(item.get("long_name") or ""),
                str(item.get("br_name") or ""),
            ]
        )
        if not aliases:
            continue
        canonical = (
            clean_display_name(str(item.get("long_name") or ""))
            or clean_display_name(str(weapon.get("weapon_name") or ""))
            or aliases[0]
        )
        identity_keys = {identity_key(a) for a in aliases}
        family_keys = {family_key(a) for a in aliases}
        rows.append(
            {
                "id": idx,
                "canonical_name": canonical,
                "family_name": family_name(canonical),
                "identity_keys": sorted(k for k in identity_keys if k),
                "family_keys": sorted(k for k in family_keys if k),
                "aliases": aliases,
                "item_class": item.get("item_class"),
                "class_index": item.get("class_index"),
                "weapon_class": weapon.get("weapon_class"),
                "weapon_type": weapon.get("weapon_type"),
                "calibre": weapon.get("calibre"),
                "mag_size": weapon.get("mag_size"),
                "item_size": item.get("item_size"),
                "two_handed": item.get("two_handed"),
            }
        )

    family_counts = Counter((row["family_keys"] or [""])[0] for row in rows)
    return {
        "schema": "ja2-weapon-catalog-index",
        "schema_version": TOOL_VERSION,
        "source": source,
        "source_files": {
            "items": {"path": str(items_path), "sha256": sha256_file(items_path), **item_meta},
            "weapons": {"path": str(weapons_path), "sha256": sha256_file(weapons_path), **weapon_meta},
        },
        "validation": {
            "weapon_ids_missing_item_record": missing_items,
            "unique_weapon_ids": not bool(weapon_meta["duplicate_ids"]),
            "unique_item_ids": not bool(item_meta["duplicate_ids"]),
        },
        "stats": {
            "weapon_records": len(rows),
            "family_keys": len({k for row in rows for k in row["family_keys"]}),
            "duplicate_primary_family_keys": sum(1 for v in family_counts.values() if v > 1),
        },
        "weapons": rows,
    }


def load_index(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "ja2-weapon-catalog-index":
        raise ValueError(f"{path} is not a weapon-catalog index")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _row_line(row: dict[str, Any]) -> str:
    return (
        f"{row['id']:>5}  {row['canonical_name']}"
        f"  [family={row.get('family_name','')}; class={row.get('weapon_class')};"
        f" type={row.get('weapon_type')}; calibre={row.get('calibre')}]"
    )


def print_bounded(rows: list[dict[str, Any]], limit: int) -> None:
    limit = max(0, limit)
    for row in rows[:limit]:
        print(_row_line(row))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more record(s) omitted; use --output for complete data")


def query_rows(index: dict[str, Any], ids: list[int], name: str | None, family: str | None, regex: bool) -> list[dict[str, Any]]:
    rows = index["weapons"]
    idset = set(ids)
    name_re = re.compile(name, re.I) if name and regex else None
    family_re = re.compile(family, re.I) if family and regex else None
    out = []
    for row in rows:
        if idset and row["id"] not in idset:
            continue
        hay_name = " || ".join([row["canonical_name"], *row["aliases"]])
        hay_family = " || ".join([row.get("family_name", ""), *row.get("family_keys", [])])
        if name:
            if name_re:
                if not name_re.search(hay_name):
                    continue
            elif name.lower() not in hay_name.lower():
                continue
        if family:
            if family_re:
                if not family_re.search(hay_family):
                    continue
            elif family.lower() not in hay_family.lower():
                continue
        out.append(row)
    return out


def compare_indexes(base: dict[str, Any], others: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    base_family = {k for row in base["weapons"] for k in row.get("family_keys", []) if k}
    base_identity = {k for row in base["weapons"] for k in row.get("identity_keys", []) if k}
    result: dict[str, Any] = {
        "schema": "ja2-weapon-catalog-comparison",
        "schema_version": TOOL_VERSION,
        "base": base.get("source", "base"),
        "base_weapon_records": len(base["weapons"]),
        "comparisons": {},
    }
    for label, other in others:
        missing = []
        overlap = 0
        seen_family: set[str] = set()
        for row in other["weapons"]:
            families = {k for k in row.get("family_keys", []) if k}
            identities = {k for k in row.get("identity_keys", []) if k}
            if families & base_family or identities & base_identity:
                overlap += 1
                continue
            primary = next(iter(sorted(families)), f"id:{row['id']}")
            if primary in seen_family:
                continue
            seen_family.add(primary)
            missing.append(row)
        missing.sort(key=lambda r: r["canonical_name"].casefold())
        result["comparisons"][label] = {
            "source": other.get("source", label),
            "weapon_records": len(other["weapons"]),
            "overlapping_records": overlap,
            "missing_unique_families": len(missing),
            "missing": missing,
        }
    return result


def parse_lobot_filters(path: Path) -> dict[str, Any]:
    root = _root(path)
    if root.tag != "Filters":
        raise ValueError(f"unexpected LOBOT filter root {root.tag!r} in {path}")
    exact: dict[int, list[str]] = defaultdict(list)
    generic: dict[str, list[dict[str, str]]] = {}
    filter_count = 0
    for filt in root.findall(".//Filter"):
        name = filt.get("name") or ""
        if not name:
            continue
        filter_count += 1
        criteria: list[dict[str, str]] = []
        for node in filt.iter():
            if node is filt:
                continue
            tag = node.tag.upper()
            text = (node.text or "").strip()
            if tag == "HANDPOS" and text:
                for token in re.findall(r"\d+", text):
                    exact[int(token)].append(name)
            elif tag in {"WEAPON_CLASS", "WEAPON_TYPE", "WEAPON_IN_HAND", "LEFT_WEAPON_TYPE"} and text:
                criteria.append({"tag": tag, "value": text, "op": node.get("op") or "", "not": node.get("not") or ""})
        if criteria:
            generic[name] = criteria
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "filters": filter_count,
        "exact_item_filters": {str(k): sorted(set(v)) for k, v in sorted(exact.items())},
        "generic_filters": generic,
    }


def parse_attachments(path: Path) -> list[dict[str, Any]]:
    root = _root(path)
    if root.tag != "ATTACHMENTLIST":
        raise ValueError(f"unexpected Attachments.xml root {root.tag!r} in {path}")
    rows = []
    for node in root.findall(".//ATTACHMENT"):
        attachment = _int_text(node, "attachmentIndex")
        item = _int_text(node, "itemIndex")
        if attachment is None or item is None:
            continue
        rows.append(
            {
                "attachment_id": attachment,
                "item_id": item,
                "ap_cost": _int_text(node, "APCost"),
                "nas_only": _int_text(node, "NASOnly"),
            }
        )
    return rows


def cmd_index(args: argparse.Namespace) -> int:
    data = build_index(Path(args.items), Path(args.weapons), args.source)
    write_json(Path(args.output), data)
    print(f"indexed {data['stats']['weapon_records']} weapon records; {data['stats']['family_keys']} family keys; output={args.output}")
    v = data["validation"]
    print(f"validation: item_ids_unique={v['unique_item_ids']} weapon_ids_unique={v['unique_weapon_ids']} weapon_ids_missing_items={len(v['weapon_ids_missing_item_record'])}")
    return 0 if v["unique_item_ids"] and v["unique_weapon_ids"] else 2


def cmd_validate(args: argparse.Namespace) -> int:
    data = build_index(Path(args.items), Path(args.weapons), args.source)
    report = {"source": data["source"], "source_files": data["source_files"], "stats": data["stats"], "validation": data["validation"]}
    if args.output:
        write_json(Path(args.output), report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    ok = report["validation"]["unique_item_ids"] and report["validation"]["unique_weapon_ids"]
    return 0 if ok else 2


def cmd_query(args: argparse.Namespace) -> int:
    index = load_index(Path(args.index))
    rows = query_rows(index, args.id or [], args.name, args.family, args.regex)
    print(f"matches={len(rows)} source={index.get('source','')}")
    print_bounded(rows, args.limit)
    if args.output:
        write_json(Path(args.output), rows)
        print(f"full_result={args.output}")
    return 0


def _parse_other(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--other must be LABEL=INDEX.json")
    label, path = value.split("=", 1)
    if not label or not path:
        raise argparse.ArgumentTypeError("--other must be LABEL=INDEX.json")
    return label, Path(path)


def cmd_compare(args: argparse.Namespace) -> int:
    base = load_index(Path(args.base))
    others = [(label, load_index(path)) for label, path in args.other]
    result = compare_indexes(base, others)
    print(f"base={result['base']} weapon_records={result['base_weapon_records']}")
    for label, comp in result["comparisons"].items():
        print(f"{label}: records={comp['weapon_records']} overlap={comp['overlapping_records']} missing_unique_families={comp['missing_unique_families']}")
        print_bounded(comp["missing"], args.limit)
    if args.output:
        write_json(Path(args.output), result)
        print(f"full_result={args.output}")
    return 0


def cmd_lobot(args: argparse.Namespace) -> int:
    data = parse_lobot_filters(Path(args.filters))
    exact = data["exact_item_filters"]
    result: dict[str, Any] = {"filters_sha256": data["sha256"], "filter_count": data["filters"], "targets": {}}
    for idx in args.id or []:
        result["targets"][str(idx)] = exact.get(str(idx), [])
    if args.donor:
        result["donors"] = {}
        for idx in args.donor:
            result["donors"][str(idx)] = exact.get(str(idx), [])
    if args.include_generic:
        result["generic_filters"] = data["generic_filters"]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.output:
        write_json(Path(args.output), result)
    return 0


def cmd_attachments(args: argparse.Namespace) -> int:
    path = Path(args.attachments)
    rows = parse_attachments(path)
    item_ids = set(args.id or [])
    attachment_ids = set(args.attachment_id or [])
    matched = [row for row in rows if (not item_ids or row["item_id"] in item_ids) and (not attachment_ids or row["attachment_id"] in attachment_ids)]
    counts = Counter(row["item_id"] for row in matched)
    print(f"relationships={len(matched)} total_relationships={len(rows)} sha256={sha256_file(path)}")
    if item_ids:
        for idx in sorted(item_ids):
            print(f"item {idx}: {counts.get(idx, 0)} relationship(s)")
    for row in matched[: max(0, args.limit)]:
        print(f"item={row['item_id']} attachment={row['attachment_id']} ap_cost={row['ap_cost']} nas_only={row['nas_only']}")
    if len(matched) > args.limit:
        print(f"... {len(matched) - args.limit} more relationship(s) omitted; use --output for complete data")
    if args.output:
        write_json(Path(args.output), {"source": {"path": str(path), "sha256": sha256_file(path)}, "matches": matched})
        print(f"full_result={args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    ix = sub.add_parser("index", help="build a compact JSON index from Items.xml + Weapons.xml")
    ix.add_argument("--items", required=True)
    ix.add_argument("--weapons", required=True)
    ix.add_argument("--source", required=True)
    ix.add_argument("--output", required=True)
    ix.set_defaults(func=cmd_index)

    va = sub.add_parser("validate", help="validate and summarize Items.xml + Weapons.xml")
    va.add_argument("--items", required=True)
    va.add_argument("--weapons", required=True)
    va.add_argument("--source", default="catalog")
    va.add_argument("--output")
    va.set_defaults(func=cmd_validate)

    qu = sub.add_parser("query", help="bounded query against a compact index")
    qu.add_argument("--index", required=True)
    qu.add_argument("--id", action="append", type=int)
    qu.add_argument("--name")
    qu.add_argument("--family")
    qu.add_argument("--regex", action="store_true")
    qu.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    qu.add_argument("--output")
    qu.set_defaults(func=cmd_query)

    co = sub.add_parser("compare", help="compare normalized weapon families against a base index")
    co.add_argument("--base", required=True)
    co.add_argument("--other", action="append", type=_parse_other, required=True, metavar="LABEL=INDEX.json")
    co.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    co.add_argument("--output")
    co.set_defaults(func=cmd_compare)

    lo = sub.add_parser("lobot", help="inspect exact Logical Body Types HANDPOS filter membership")
    lo.add_argument("--filters", required=True)
    lo.add_argument("--id", action="append", type=int)
    lo.add_argument("--donor", action="append", type=int)
    lo.add_argument("--include-generic", action="store_true")
    lo.add_argument("--output")
    lo.set_defaults(func=cmd_lobot)

    at = sub.add_parser("attachments", help="bounded attachment-relationship query")
    at.add_argument("--attachments", required=True)
    at.add_argument("--id", action="append", type=int)
    at.add_argument("--attachment-id", action="append", type=int)
    at.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    at.add_argument("--output")
    at.set_defaults(func=cmd_attachments)

    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        return int(args.func(args))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
