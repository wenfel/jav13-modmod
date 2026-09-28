#!/usr/bin/env python3
"""Extract JA2 1.13 weapon data into a reproducible statistical feature table.

This is an offline analysis tool. It does not change game XML or runtime behavior.
"""

from __future__ import annotations

import argparse
import configparser
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

IC_GUN = 0x00000002
IC_LAUNCHER = 0x00000010

WEAPON_TYPE_NAMES = {
    0: "not_gun",
    1: "pistol",
    2: "machine_pistol",
    3: "smg",
    4: "rifle",
    5: "sniper_rifle",
    6: "assault_rifle",
    7: "lmg",
    8: "shotgun",
}

TYPE_SUFFIX = {
    1: "PISTOL",
    2: "MP",
    3: "SMG",
    4: "RIFLE",
    5: "SNIPER",
    6: "AR",
    7: "LMG",
    8: "SHOTGUN",
}

WEAPON_CLASS_NAMES = {
    0: "none",
    1: "handgun",
    2: "smg",
    3: "rifle",
    4: "mg",
    5: "shotgun",
    6: "knife",
    7: "monster",
}

NUMERIC_WEAPON_FIELDS = (
    "ubWeaponClass",
    "ubWeaponType",
    "ubCalibre",
    "ubReadyTime",
    "ubShotsPer4Turns",
    "ubShotsPerBurst",
    "ubBurstPenalty",
    "ubBulletSpeed",
    "ubImpact",
    "ubDeadliness",
    "bAccuracy",
    "ubMagSize",
    "usRange",
    "usReloadDelay",
    "bBurstAP",
    "bAutofireShotsPerFiveAP",
    "APsToReload",
    "AutoPenalty",
    "APsToReloadManually",
    "nAccuracy",
    "bRecoilX",
    "bRecoilY",
    "ubAimLevels",
    "ubRecoilDelay",
    "Handling",
    "usOverheatingJamThreshold",
    "usOverheatingDamageThreshold",
    "usOverheatingSingleShotTemperature",
    "HeavyGun",
    "NoSemiAuto",
    "EasyUnjam",
)

NUMERIC_ITEM_FIELDS = (
    "usItemClass",
    "ubClassIndex",
    "ubWeight",
    "ItemSize",
    "usPrice",
    "ubCoolness",
    "bReliability",
    "bRepairEase",
    "TwoHanded",
    "SciFi",
    "WeaponOriginFlags",
    "WeaponHistoricalStatusFlags",
    "ProductionYearStart",
    "ProductionYearEnd",
    "BR_ROF",
    "RangeBonus",
    "PercentRangeBonus",
    "DamageBonus",
    "MagSizeBonus",
    "PercentAPReduction",
    "PercentBurstFireAPReduction",
    "PercentAutofireAPReduction",
    "PercentReadyTimeAPReduction",
    "PercentReloadTimeAPReduction",
    "AutoFireToHitBonus",
    "BurstSizeBonus",
    "BurstToHitBonus",
    "RecoilModifierX",
    "RecoilModifierY",
    "PercentRecoilModifier",
    "PercentAccuracyModifier",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (default: inferred from this script)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("weapon_features.json"),
    )
    p.add_argument("--reference-full-ap", type=int, default=80)
    p.add_argument("--reference-aim-skill", type=int, default=80)
    return p.parse_args()


def element_dict(elem: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for child in elem:
        # BarrelConfiguration may repeat. It is not required by the current metric.
        if child.tag not in out:
            out[child.tag] = (child.text or "").strip()
    return out


def parse_number(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(int(value, 0))
    except ValueError:
        return float(value)


def parse_int(value: str | None, default: int = 0) -> int:
    return int(parse_number(value, float(default)))


def load_ini(path: Path) -> dict[str, str]:
    # JA2 INIs contain comments and historical formatting that are easier to handle
    # as simple key/value data than with strict ConfigParser semantics.
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#", "[")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(";", 1)[0].strip()
        values[key.strip().upper()] = value
    return values


def ini_float(values: dict[str, str], key: str, default: float = 1.0) -> float:
    try:
        return float(values.get(key.upper(), default))
    except ValueError:
        return default


def round_cpp_nearest(top: int, bottom: int) -> int:
    """Mirror the positive integer rounding in BaseAPsToShootOrStab."""
    if bottom <= 0:
        return -1
    return (top + bottom // 2) // bottom


def reference_shot_ap(
    shots_per_4_turns: float,
    full_ap: int,
    aim_skill: int,
) -> int:
    # Tactical/Points.cpp, BaseAPsToShootOrStabNoModifier:
    # Top = 8 * bAPs * 100
    # Bottom = (100 + bAimSkill) * rof
    # result = (Top + Bottom / 2) / Bottom
    bottom = int((100 + aim_skill) * shots_per_4_turns)
    return round_cpp_nearest(8 * full_ap * 100, bottom)


def read_ammo_names(path: Path) -> dict[int, str]:
    root = ET.parse(path).getroot()
    result: dict[int, str] = {}
    for elem in root.findall("AMMO"):
        d = element_dict(elem)
        idx = parse_int(d.get("uiIndex"))
        result[idx] = d.get("AmmoCaliber", str(idx))
    return result


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()

    weapons_path = repo / "gamedir/Data-1.13/TableData/Items/Weapons.xml"
    items_path = repo / "gamedir/Data-1.13/TableData/Items/Items.xml"
    ammo_path = repo / "gamedir/Data-1.13/TableData/Items/AmmoStrings.xml"
    item_settings_path = repo / "gamedir/Data-1.13/Item_Settings.ini"
    options_path = repo / "gamedir/Data-1.13/Ja2_Options.INI"

    weapon_root = ET.parse(weapons_path).getroot()
    item_root = ET.parse(items_path).getroot()

    weapon_rows = {
        parse_int(d.get("uiIndex")): d
        for d in (element_dict(e) for e in weapon_root.findall("WEAPON"))
    }
    item_rows = {
        parse_int(d.get("uiIndex")): d
        for d in (element_dict(e) for e in item_root.findall("ITEM"))
    }
    ammo_names = read_ammo_names(ammo_path)
    item_settings = load_ini(item_settings_path)
    options = load_ini(options_path)

    global_damage_mod = ini_float(options, "GUN_DAMAGE_MODIFIER", 100.0) / 100.0
    global_range_mod = ini_float(options, "GUN_RANGE_MODIFIER", 100.0) / 100.0
    global_auto_bonus = ini_float(options, "AUTOFIRE_BULLETS_PER_5AP_MODIFIER", 0.0)

    rows: list[dict[str, Any]] = []

    for ui_index, w in sorted(weapon_rows.items()):
        item = item_rows.get(ui_index)
        if item is None:
            continue

        item_class = parse_int(item.get("usItemClass"))
        is_firearm = bool(item_class & IC_GUN)
        is_launcher = bool(item_class & IC_LAUNCHER)
        weapon_type = parse_int(w.get("ubWeaponType"))
        weapon_class = parse_int(w.get("ubWeaponClass"))
        calibre = parse_int(w.get("ubCalibre"))

        suffix = TYPE_SUFFIX.get(weapon_type)
        if is_firearm and suffix:
            range_type_mod = ini_float(item_settings, f"RANGE_{suffix}_MODIFIER", 1.0)
            damage_type_mod = ini_float(item_settings, f"DAMAGE_{suffix}_MODIFIER", 1.0)
            sp4t_mod = ini_float(item_settings, f"SP4T_{suffix}_MODIFIER", 1.0)
            reload_mod = ini_float(item_settings, f"AP_RELOAD_{suffix}_MODIFIER", 1.0)
            handling_mod = ini_float(item_settings, f"HANDLING_{suffix}_MODIFIER", 1.0)
            recoil_x_mod = ini_float(item_settings, f"RECOILX_{suffix}_MODIFIER", 1.0)
            recoil_y_mod = ini_float(item_settings, f"RECOILY_{suffix}_MODIFIER", 1.0)
            af_mod = ini_float(item_settings, f"AF_SP5AP_{suffix}_MODIFIER", 1.0)
        else:
            range_type_mod = damage_type_mod = sp4t_mod = reload_mod = 1.0
            handling_mod = recoil_x_mod = recoil_y_mod = af_mod = 1.0

        raw_sp4t = parse_number(w.get("ubShotsPer4Turns"))
        effective_sp4t = raw_sp4t * sp4t_mod
        raw_range = parse_number(w.get("usRange"))
        raw_damage = parse_number(w.get("ubImpact"))
        raw_recoil_x = parse_number(w.get("bRecoilX"))
        raw_recoil_y = parse_number(w.get("bRecoilY"))
        effective_recoil_x = raw_recoil_x * recoil_x_mod
        effective_recoil_y = raw_recoil_y * recoil_y_mod
        heat_per_shot = parse_number(w.get("usOverheatingSingleShotTemperature"))
        jam_threshold = parse_number(w.get("usOverheatingJamThreshold"))
        damage_threshold = parse_number(w.get("usOverheatingDamageThreshold"))

        raw_weapon = {
            field: parse_number(w.get(field))
            for field in NUMERIC_WEAPON_FIELDS
        }
        raw_item = {
            field: parse_number(item.get(field))
            for field in NUMERIC_ITEM_FIELDS
        }

        shots_per_burst = parse_int(w.get("ubShotsPerBurst"))
        auto_per_5ap = parse_number(w.get("bAutofireShotsPerFiveAP"))
        effective_auto = 0.0
        if auto_per_5ap > 0:
            effective_auto = max(1.0, auto_per_5ap * af_mod + global_auto_bonus)

        row = {
            "uiIndex": ui_index,
            "name": item.get("szItemName") or w.get("szWeaponName") or str(ui_index),
            "long_name": item.get("szLongItemName") or item.get("szItemName") or "",
            "is_firearm": is_firearm,
            "is_launcher": is_launcher,
            "weapon_class": weapon_class,
            "weapon_class_name": WEAPON_CLASS_NAMES.get(weapon_class, f"class_{weapon_class}"),
            "weapon_type": weapon_type,
            "weapon_type_name": WEAPON_TYPE_NAMES.get(weapon_type, f"type_{weapon_type}"),
            "calibre": calibre,
            "calibre_name": ammo_names.get(calibre, str(calibre)),
            "two_handed": bool(parse_int(item.get("TwoHanded"))),
            "heavy_gun": bool(parse_int(w.get("HeavyGun"))),
            "has_semi_auto": not bool(parse_int(w.get("NoSemiAuto"))),
            "has_burst": shots_per_burst > 0,
            "has_autofire": auto_per_5ap > 0,
            "origin_flags": parse_int(item.get("WeaponOriginFlags")),
            "historical_status_flags": parse_int(item.get("WeaponHistoricalStatusFlags")),
            "production_year_start": parse_int(item.get("ProductionYearStart")),
            "production_year_end": parse_int(item.get("ProductionYearEnd")),
            "scifi": bool(parse_int(item.get("SciFi"))),
            "raw": {
                "weapon": raw_weapon,
                "item": raw_item,
            },
            "features": {
                # Deterministic baseline values with no ammo/attachment/status bonuses.
                "damage": raw_damage * global_damage_mod * damage_type_mod,
                "range": raw_range * global_range_mod * range_type_mod,
                "shots_per_4_turns": effective_sp4t,
                "reference_shot_ap": reference_shot_ap(
                    effective_sp4t,
                    args.reference_full_ap,
                    args.reference_aim_skill,
                ),
                "ready_ap": parse_number(w.get("ubReadyTime")),
                "reload_ap": parse_number(w.get("APsToReload")) * reload_mod,
                "octh_accuracy": parse_number(w.get("bAccuracy")),
                "ncth_accuracy": parse_number(w.get("nAccuracy")),
                "aim_levels": parse_number(w.get("ubAimLevels")),
                "handling": parse_number(w.get("Handling")) * handling_mod,
                "magazine_capacity": parse_number(w.get("ubMagSize")),
                "burst_size": float(shots_per_burst),
                "burst_penalty": parse_number(w.get("ubBurstPenalty")),
                "autofire_shots_per_5ap": effective_auto,
                "autofire_penalty": parse_number(w.get("AutoPenalty")),
                "recoil_x": effective_recoil_x,
                "recoil_y": effective_recoil_y,
                "recoil_magnitude": math.hypot(effective_recoil_x, effective_recoil_y),
                "heat_shots_to_jam_threshold": (
                    jam_threshold / heat_per_shot if heat_per_shot > 0 else 0.0
                ),
                "heat_shots_to_damage_threshold": (
                    damage_threshold / heat_per_shot if heat_per_shot > 0 else 0.0
                ),
                "weight": parse_number(item.get("ubWeight")),
                "item_size": parse_number(item.get("ItemSize")),
                "reliability": parse_number(item.get("bReliability")),
                "repair_ease": parse_number(item.get("bRepairEase")),
                "coolness": parse_number(item.get("ubCoolness")),
            },
        }
        rows.append(row)

    payload = {
        "schema_version": 1,
        "source": {
            "weapons_xml": str(weapons_path.relative_to(repo)),
            "items_xml": str(items_path.relative_to(repo)),
            "ammo_strings_xml": str(ammo_path.relative_to(repo)),
            "item_settings_ini": str(item_settings_path.relative_to(repo)),
            "ja2_options_ini": str(options_path.relative_to(repo)),
        },
        "reference_scenario": {
            "full_ap": args.reference_full_ap,
            "aim_skill": args.reference_aim_skill,
            "attachments": "none",
            "ammo_modifiers": "none",
            "weapon_status": "baseline",
        },
        "counts": {
            "weapon_rows": len(rows),
            "firearms": sum(1 for r in rows if r["is_firearm"]),
            "launchers": sum(1 for r in rows if r["is_launcher"]),
        },
        "weapons": rows,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {len(rows)} weapon records "
        f"({payload['counts']['firearms']} firearms) to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
