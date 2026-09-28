#!/usr/bin/env python3
"""Extract JA2 1.13 weapon data into a reproducible statistical feature table.

This is an offline analysis tool. It does not change game XML or runtime behavior.
"""

from __future__ import annotations

import argparse
import hashlib
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
    "fBurstOnlyByFanTheHammer",
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
    "ToHitBonus",
    "AimBonus",
    "MinRangeForAimBonus",
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
    if value is None or value == "":
        return default
    text = value.strip()
    try:
        return int(text, 0)
    except ValueError:
        return int(float(text))


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


def ini_bool(values: dict[str, str], key: str, default: bool = False) -> bool:
    value = values.get(key.upper())
    if value is None:
        return default
    normalized = value.strip().upper()
    if normalized in {"TRUE", "1", "YES", "ON"}:
        return True
    if normalized in {"FALSE", "0", "NO", "OFF"}:
        return False
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
    percent_ap_reduction: int = 0,
) -> int:
    """Mirror BaseAPsToShootOrStab(NoModifier) for a reference soldier."""
    bottom = int((100 + aim_skill) * shots_per_4_turns)
    reduction = max(0, min(100, percent_ap_reduction))
    return round_cpp_nearest(8 * full_ap * (100 - reduction), bottom)


def reference_burst_ap(
    burst_ap: float,
    burst_ap_modifier: float,
    full_ap: int,
    ap_maximum: int,
    percent_ap_reduction: int = 0,
    percent_burst_reduction: int = 0,
) -> int:
    """Mirror CalcAPsToBurst for an unmodified 100%-status weapon object."""
    modified = int(burst_ap * burst_ap_modifier)
    if modified <= 0 or ap_maximum <= 0:
        return 0

    aps = (modified * full_ap + (ap_maximum - 1)) // ap_maximum
    aps = aps * max(0, 100 - percent_ap_reduction) // 100
    aps = max(aps, (modified + 1) // 2)
    aps = aps * max(0, 100 - percent_burst_reduction) // 100
    return max(0, min(ap_maximum, aps))


def reference_autofire_ap(
    shots_per_5_ap: float,
    volley_rounds: int,
    full_ap: int,
    ap_maximum: int,
    autofire_shots_ap_value: int,
    percent_ap_reduction: int = 0,
    percent_autofire_reduction: int = 0,
) -> int:
    """Mirror CalcAPsToAutofire surcharge for a fixed-size reference volley."""
    if shots_per_5_ap <= 0 or volley_rounds <= 1 or ap_maximum <= 0:
        return 0

    extra_rounds = volley_rounds - 1
    numerator = autofire_shots_ap_value * extra_rounds * full_ap
    base_aps = int(
        (numerator / shots_per_5_ap + (ap_maximum - 1)) / ap_maximum
    )

    aps = base_aps * max(0, 100 - percent_ap_reduction) // 100
    aps = max(aps, (base_aps + 1) // 2)
    aps = aps * max(0, 100 - percent_autofire_reduction) // 100
    return max(0, min(255, aps))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    apbp_path = repo / "gamedir/Data-1.13/APBPConstants.ini"

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
    apbp = load_ini(apbp_path)

    global_damage_mod = ini_float(options, "GUN_DAMAGE_MODIFIER", 100.0) / 100.0
    global_range_mod = ini_float(options, "GUN_RANGE_MODIFIER", 100.0) / 100.0
    global_auto_bonus = ini_float(options, "AUTOFIRE_BULLETS_PER_5AP_MODIFIER", 0.0)
    ap_maximum = int(ini_float(apbp, "AP_MAXIMUM", 100.0))
    autofire_shots_ap_value = int(
        ini_float(apbp, "AUTOFIRE_SHOTS_AP_VALUE", 20.0)
    )

    rows: list[dict[str, Any]] = []

    for ui_index, w in sorted(weapon_rows.items()):
        item = item_rows.get(ui_index)
        if item is None:
            continue

        item_class = parse_int(item.get("usItemClass"))
        is_firearm = bool(item_class & IC_GUN)
        is_launcher = bool(item_class & IC_LAUNCHER)

        # The present metric is calibrated for firearms only. Launchers, melee
        # attacks and monster/utility weapon records have different mechanics
        # and should receive separate feature models rather than being forced
        # into the same Euclidean space.
        if not is_firearm:
            continue

        weapon_type = parse_int(w.get("ubWeaponType"))
        weapon_class = parse_int(w.get("ubWeaponClass"))
        calibre = parse_int(w.get("ubCalibre"))

        suffix = TYPE_SUFFIX.get(weapon_type)
        if suffix is None:
            continue

        if is_firearm and suffix:
            range_type_mod = ini_float(item_settings, f"RANGE_{suffix}_MODIFIER", 1.0)
            damage_type_mod = ini_float(item_settings, f"DAMAGE_{suffix}_MODIFIER", 1.0)
            sp4t_mod = ini_float(item_settings, f"SP4T_{suffix}_MODIFIER", 1.0)
            reload_mod = ini_float(item_settings, f"AP_RELOAD_{suffix}_MODIFIER", 1.0)
            handling_mod = ini_float(item_settings, f"HANDLING_{suffix}_MODIFIER", 1.0)
            recoil_x_mod = ini_float(item_settings, f"RECOILX_{suffix}_MODIFIER", 1.0)
            recoil_y_mod = ini_float(item_settings, f"RECOILY_{suffix}_MODIFIER", 1.0)
            af_mod = ini_float(item_settings, f"AF_SP5AP_{suffix}_MODIFIER", 1.0)
            burst_ap_mod = ini_float(item_settings, f"BURST_AP_{suffix}_MODIFIER", 1.0)
        else:
            range_type_mod = damage_type_mod = sp4t_mod = reload_mod = 1.0
            handling_mod = recoil_x_mod = recoil_y_mod = af_mod = 1.0
            burst_ap_mod = 1.0

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
            field: (
                str(parse_int(item.get(field)))
                if field == "WeaponOriginFlags"
                else parse_int(item.get(field))
                if field in {
                    "usItemClass",
                    "WeaponHistoricalStatusFlags",
                    "ProductionYearStart",
                    "ProductionYearEnd",
                }
                else parse_number(item.get(field))
            )
            for field in NUMERIC_ITEM_FIELDS
        }

        shots_per_burst = parse_int(w.get("ubShotsPerBurst"))
        fan_the_hammer_burst = bool(parse_int(w.get("fBurstOnlyByFanTheHammer")))
        native_burst = shots_per_burst > 0 and not fan_the_hammer_burst
        auto_per_5ap = parse_number(w.get("bAutofireShotsPerFiveAP"))
        effective_auto = 0.0
        if auto_per_5ap > 0:
            effective_auto = max(1.0, auto_per_5ap * af_mod + global_auto_bonus)

        percent_ap = parse_int(item.get("PercentAPReduction"))
        percent_ready = parse_int(item.get("PercentReadyTimeAPReduction"))
        percent_reload = parse_int(item.get("PercentReloadTimeAPReduction"))
        percent_burst_ap = parse_int(item.get("PercentBurstFireAPReduction"))
        percent_autofire_ap = parse_int(item.get("PercentAutofireAPReduction"))
        burst_to_hit = parse_int(item.get("BurstToHitBonus"))
        auto_to_hit = parse_int(item.get("AutoFireToHitBonus"))
        item_burst_size = parse_int(item.get("BurstSizeBonus"))
        item_mag_size = parse_int(item.get("MagSizeBonus"))
        item_rate_bonus = parse_number(item.get("RateOfFireBonus"))
        item_to_hit = parse_number(item.get("ToHitBonus"))
        item_aim_bonus = parse_number(item.get("AimBonus"))

        base_burst_size = float(shots_per_burst if native_burst else 0)
        effective_burst_size = (
            base_burst_size + item_burst_size if native_burst else 0.0
        )
        base_burst_penalty = (
            parse_number(w.get("ubBurstPenalty")) if native_burst else 0.0
        )
        effective_burst_penalty = (
            max(0.0, base_burst_penalty - burst_to_hit) if native_burst else 0.0
        )
        base_auto_penalty = parse_number(w.get("AutoPenalty"))
        effective_auto_penalty = (
            max(0.0, base_auto_penalty - auto_to_hit)
            if auto_per_5ap > 0
            else 0.0
        )

        base_shot_ap = reference_shot_ap(
            effective_sp4t,
            args.reference_full_ap,
            args.reference_aim_skill,
        )
        intrinsic_shot_ap = reference_shot_ap(
            effective_sp4t + item_rate_bonus,
            args.reference_full_ap,
            args.reference_aim_skill,
            percent_ap,
        )

        base_ready_ap = parse_int(w.get("ubReadyTime"))
        intrinsic_ready_ap = (
            base_ready_ap * max(0, 100 - percent_ready) // 100
        )

        base_reload_ap = parse_number(w.get("APsToReload")) * reload_mod
        intrinsic_reload_ap = (
            base_reload_ap * max(0, 100 - percent_reload) / 100.0
        )

        base_burst_ap = (
            reference_burst_ap(
                parse_number(w.get("bBurstAP")),
                burst_ap_mod,
                args.reference_full_ap,
                ap_maximum,
            )
            if native_burst
            else 0
        )
        intrinsic_burst_ap = (
            reference_burst_ap(
                parse_number(w.get("bBurstAP")),
                burst_ap_mod,
                args.reference_full_ap,
                ap_maximum,
                percent_ap,
                percent_burst_ap,
            )
            if native_burst
            else 0
        )

        base_autofire_ap_5_rounds = (
            reference_autofire_ap(
                effective_auto,
                5,
                args.reference_full_ap,
                ap_maximum,
                autofire_shots_ap_value,
            )
            if auto_per_5ap > 0
            else 0
        )
        intrinsic_autofire_ap_5_rounds = (
            reference_autofire_ap(
                effective_auto,
                5,
                args.reference_full_ap,
                ap_maximum,
                autofire_shots_ap_value,
                percent_ap,
                percent_autofire_ap,
            )
            if auto_per_5ap > 0
            else 0
        )

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
            "has_burst": native_burst,
            "has_trait_gated_burst": fan_the_hammer_burst and shots_per_burst > 0,
            "has_autofire": auto_per_5ap > 0,
            # Store UINT64 bitmasks as decimal strings in JSON so consumers
            # implemented in languages with IEEE-754 numbers do not lose bits.
            "origin_flags": str(parse_int(item.get("WeaponOriginFlags"))),
            "historical_status_flags": parse_int(item.get("WeaponHistoricalStatusFlags")),
            "production_year_start": parse_int(item.get("ProductionYearStart")),
            "production_year_end": parse_int(item.get("ProductionYearEnd")),
            "scifi": bool(parse_int(item.get("SciFi"))),
            "raw": {
                "weapon": raw_weapon,
                "item": raw_item,
            },
            "base_features": {
                # Weapon + global/type INI baseline, before inherent item modifiers.
                "damage": raw_damage * global_damage_mod * damage_type_mod,
                "range": raw_range * global_range_mod * range_type_mod,
                "shots_per_4_turns": effective_sp4t,
                "reference_shot_ap": base_shot_ap,
                "ready_ap": base_ready_ap,
                "reload_ap": base_reload_ap,
                "burst_ap": base_burst_ap,
                "autofire_ap_5_rounds": base_autofire_ap_5_rounds,
                "octh_accuracy": parse_number(w.get("bAccuracy")),
                "octh_to_hit_bonus": 0.0,
                "octh_aim_bonus": 0.0,
                "ncth_accuracy": parse_number(w.get("nAccuracy")),
                "aim_levels": parse_number(w.get("ubAimLevels")),
                "handling": parse_number(w.get("Handling")) * handling_mod,
                "magazine_capacity": parse_number(w.get("ubMagSize")),
                "burst_size": base_burst_size,
                "burst_penalty": base_burst_penalty,
                "autofire_shots_per_5ap": effective_auto,
                "autofire_penalty": (
                    base_auto_penalty if auto_per_5ap > 0 else 0.0
                ),
                "recoil_x": effective_recoil_x,
                "recoil_y": effective_recoil_y,
                "recoil_magnitude": math.hypot(
                    effective_recoil_x, effective_recoil_y
                ),
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
            "effective_intrinsic_features": {
                # Base features plus the weapon item's own 100%-status modifiers.
                # No ammo, attachments, soldier traits, stance, condition loss, etc.
                "damage": raw_damage * global_damage_mod * damage_type_mod,
                "range": raw_range * global_range_mod * range_type_mod,
                "shots_per_4_turns": effective_sp4t + item_rate_bonus,
                "reference_shot_ap": intrinsic_shot_ap,
                "ready_ap": intrinsic_ready_ap,
                "reload_ap": intrinsic_reload_ap,
                "burst_ap": intrinsic_burst_ap,
                "autofire_ap_5_rounds": intrinsic_autofire_ap_5_rounds,
                "octh_accuracy": parse_number(w.get("bAccuracy")),
                "octh_to_hit_bonus": item_to_hit,
                "octh_aim_bonus": item_aim_bonus,
                "ncth_accuracy": parse_number(w.get("nAccuracy")),
                "aim_levels": parse_number(w.get("ubAimLevels")),
                "handling": parse_number(w.get("Handling")) * handling_mod,
                "magazine_capacity": parse_number(w.get("ubMagSize")) + item_mag_size,
                "burst_size": effective_burst_size,
                "burst_penalty": effective_burst_penalty,
                "autofire_shots_per_5ap": effective_auto,
                "autofire_penalty": effective_auto_penalty,
                "recoil_x": effective_recoil_x,
                "recoil_y": effective_recoil_y,
                "recoil_magnitude": math.hypot(
                    effective_recoil_x, effective_recoil_y
                ),
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
        "schema_version": 3,
        "source": {
            "weapons_xml": str(weapons_path.relative_to(repo)),
            "items_xml": str(items_path.relative_to(repo)),
            "ammo_strings_xml": str(ammo_path.relative_to(repo)),
            "item_settings_ini": str(item_settings_path.relative_to(repo)),
            "ja2_options_ini": str(options_path.relative_to(repo)),
            "apbp_constants_ini": str(apbp_path.relative_to(repo)),
            "sha256": {
                str(items_path.relative_to(repo)): sha256_file(items_path),
                str(weapons_path.relative_to(repo)): sha256_file(weapons_path),
                str(ammo_path.relative_to(repo)): sha256_file(ammo_path),
                str(item_settings_path.relative_to(repo)): sha256_file(item_settings_path),
                str(options_path.relative_to(repo)): sha256_file(options_path),
                str(apbp_path.relative_to(repo)): sha256_file(apbp_path),
            },
        },
        "settings": {
            "ncth": ini_bool(options, "NCTH", False),
            "overheating": ini_bool(options, "OVERHEATING", False),
            "gun_damage_modifier": global_damage_mod,
            "gun_range_modifier": global_range_mod,
            "scope_modes": ini_bool(options, "USE_SCOPE_MODES", False),
            "ap_maximum": ap_maximum,
            "autofire_shots_ap_value": autofire_shots_ap_value,
        },
        "reference_scenario": {
            "full_ap": args.reference_full_ap,
            "aim_skill": args.reference_aim_skill,
            "attachments": "none",
            "ammo_modifiers": "none",
            "weapon_status": 100,
            "intrinsic_layer": (
                "weapon item at 100% status; no ammo, attachments, traits, stance, "
                "or other soldier/target context"
            ),
        },
        "counts": {
            "weapon_rows": len(rows),
            "firearms": sum(1 for r in rows if r["is_firearm"]),
            "launchers": sum(1 for r in rows if r["is_launcher"]),
        },
        "notes": {
            "origin_flags": "Decimal string to preserve the full UINT64 mask exactly in JSON.",
            "population": (
                "Conventional firearm weapon types 1..8 only; special IC_GUN records "
                "such as creature spit/tank cannon/extinguisher are excluded."
            ),
            "feature_layers": (
                "base_features are weapon + INI baseline before item modifiers; "
                "effective_intrinsic_features additionally apply the weapon item's "
                "own modifiers at 100% status."
            ),
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
