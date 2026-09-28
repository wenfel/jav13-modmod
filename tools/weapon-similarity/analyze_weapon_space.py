#!/usr/bin/env python3
"""Explore JA2 firearm space and rank filter-safe replacement candidates.

The analysis layer deliberately separates:
1. eligibility (country/year/status/SciFi filters),
2. semantic fallback tiers (weapon type/class and capabilities), and
3. statistical distance inside an eligible tier.

PCA/k-means use unweighted robust-scaled data so exploratory structure is not
biased by the subjective replacement weights. Nearest-neighbour scoring uses
explicit weights and only mechanics that are active in the selected profile.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score


CORE_WEIGHTS = {
    "damage": 1.25,
    "range": 1.25,
    "reference_shot_ap": 1.40,
    "ready_ap": 0.75,
    "reload_ap": 0.60,
    "magazine_capacity": 0.65,
    "weight": 0.55,
    "item_size": 0.30,
    "reliability": 0.45,
    "repair_ease": 0.25,
}

RAPID_FIRE_WEIGHTS = {
    "burst_size": 0.35,
    "burst_penalty": 0.60,
    "autofire_shots_per_5ap": 0.60,
    "autofire_penalty": 0.70,
}

OCTH_WEIGHTS = {
    "octh_accuracy": 0.90,
}

NCTH_WEIGHTS = {
    "ncth_accuracy": 0.90,
    "handling": 0.80,
    "aim_levels": 0.35,
    "recoil_magnitude": 0.80,
}

OVERHEAT_WEIGHTS = {
    "heat_shots_to_jam_threshold": 0.35,
}


def add_profile_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cth-system",
        choices=("active", "octh", "ncth", "both"),
        default="active",
        help="mechanics used in the metric; active reads the dataset's Ja2_Options.INI",
    )
    parser.add_argument(
        "--overheating",
        choices=("active", "on", "off"),
        default="active",
        help="whether heat endurance is part of the metric",
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("dataset", type=Path)
    sub = p.add_subparsers(dest="command", required=True)

    pca = sub.add_parser("pca")
    pca.add_argument("--components", type=int, default=6)
    add_profile_args(pca)

    km = sub.add_parser("kmeans")
    km.add_argument("--k", type=int, default=8)
    km.add_argument("--seed", type=int, default=1)
    add_profile_args(km)

    diag = sub.add_parser("diagnostics")
    diag.add_argument("--k-min", type=int, default=2)
    diag.add_argument("--k-max", type=int, default=12)
    diag.add_argument("--seed", type=int, default=1)
    add_profile_args(diag)

    nn = sub.add_parser("neighbors")
    nn.add_argument("--index", type=int, required=True)
    nn.add_argument("--limit", type=int, default=10)
    nn.add_argument("--max-tier", type=int, choices=(0, 1, 2), default=2)
    nn.add_argument("--same-calibre", action="store_true")
    nn.add_argument(
        "--allowed-origin-mask",
        type=lambda x: int(x, 0),
        help="candidate must overlap this origin bitmask; accepts decimal or 0x...",
    )
    nn.add_argument("--allow-unknown-origin", action="store_true")
    nn.add_argument("--year", type=int)
    nn.add_argument(
        "--exclude-historical-mask",
        type=lambda x: int(x, 0),
        default=0,
        help="exclude candidates whose historical-status mask overlaps this value",
    )
    nn.add_argument("--exclude-scifi", action="store_true")
    add_profile_args(nn)

    return p.parse_args()


def load_dataset(path: Path) -> tuple[dict, pd.DataFrame]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []

    for w in payload["weapons"]:
        weapon_type = int(w["weapon_type"])
        if not 1 <= weapon_type <= 8:
            continue

        row = {
            "uiIndex": int(w["uiIndex"]),
            "name": w["name"],
            "weapon_type": weapon_type,
            "weapon_type_name": w["weapon_type_name"],
            "weapon_class": int(w["weapon_class"]),
            "weapon_class_name": w["weapon_class_name"],
            "calibre": int(w["calibre"]),
            "calibre_name": w["calibre_name"],
            "two_handed": bool(w["two_handed"]),
            "heavy_gun": bool(w["heavy_gun"]),
            "has_semi_auto": bool(w["has_semi_auto"]),
            "has_burst": bool(w["has_burst"]),
            "has_autofire": bool(w["has_autofire"]),
            "origin_flags": int(w["origin_flags"]),
            "historical_status_flags": int(w["historical_status_flags"]),
            "production_year_start": int(w["production_year_start"]),
            "production_year_end": int(w["production_year_end"]),
            "scifi": bool(w["scifi"]),
        }
        row.update({k: float(v) for k, v in w["features"].items()})
        rows.append(row)

    return payload, pd.DataFrame(rows)


def resolve_profile(
    payload: dict,
    cth_system: str,
    overheating: str,
) -> dict[str, float]:
    weights = dict(CORE_WEIGHTS)
    weights.update(RAPID_FIRE_WEIGHTS)

    active_ncth = bool(payload.get("settings", {}).get("ncth", False))
    if cth_system == "active":
        cth_system = "ncth" if active_ncth else "octh"

    if cth_system in ("octh", "both"):
        weights.update(OCTH_WEIGHTS)
    if cth_system in ("ncth", "both"):
        weights.update(NCTH_WEIGHTS)

    active_overheat = bool(payload.get("settings", {}).get("overheating", False))
    if overheating == "active":
        use_overheat = active_overheat
    else:
        use_overheat = overheating == "on"

    if use_overheat:
        weights.update(OVERHEAT_WEIGHTS)

    return weights


def robust_scale(
    df: pd.DataFrame,
    features: Iterable[str],
) -> tuple[np.ndarray, pd.Series, pd.Series]:
    cols = list(features)
    x = df[cols].astype(float)
    med = x.median(axis=0)
    iqr = x.quantile(0.75) - x.quantile(0.25)

    # Conditional fire-mode columns can have IQR == 0. Fall back to standard
    # deviation only for such columns; if still constant, make it inert.
    sd = x.std(axis=0, ddof=1).replace(0.0, np.nan)
    scale = iqr.where(iqr != 0.0, sd).fillna(1.0)
    z = (x - med) / scale
    return z.to_numpy(dtype=float), med, scale


def analysis_matrix(
    df: pd.DataFrame,
    feature_weights: dict[str, float],
) -> tuple[np.ndarray, list[str]]:
    """Unweighted matrix for PCA/clustering."""
    features = [f for f in feature_weights if f in df.columns]
    z, _, _ = robust_scale(df, features)
    return z, features


def distance_matrix(
    df: pd.DataFrame,
    feature_weights: dict[str, float],
) -> tuple[np.ndarray, list[str], pd.Series]:
    """Weighted matrix for replacement distance."""
    features = [f for f in feature_weights if f in df.columns]
    z, _, scale = robust_scale(df, features)
    weights = np.array([feature_weights[f] for f in features], dtype=float)
    return z * np.sqrt(weights), features, scale


def candidate_tier(target: pd.Series, candidate: pd.Series) -> int | None:
    """Return semantic fallback tier, or None if the candidate is unsuitable.

    Tier 0: same weapon type and preserves every fire mode the target has.
    Tier 1: same weapon type and preserves broad rapid-fire capability.
    Tier 2: same broad weapon class and preserves broad rapid-fire capability.

    Extra capabilities on the candidate are allowed.
    """
    if bool(candidate["two_handed"]) != bool(target["two_handed"]):
        return None
    if bool(candidate["heavy_gun"]) != bool(target["heavy_gun"]):
        return None

    strict_modes = (
        (not bool(target["has_semi_auto"]) or bool(candidate["has_semi_auto"]))
        and (not bool(target["has_burst"]) or bool(candidate["has_burst"]))
        and (not bool(target["has_autofire"]) or bool(candidate["has_autofire"]))
    )

    if (
        int(candidate["weapon_type"]) == int(target["weapon_type"])
        and strict_modes
    ):
        return 0

    target_rapid = bool(target["has_burst"]) or bool(target["has_autofire"])
    candidate_rapid = bool(candidate["has_burst"]) or bool(candidate["has_autofire"])
    capability_ok = (
        (not bool(target["has_semi_auto"]) or bool(candidate["has_semi_auto"]))
        and (not target_rapid or candidate_rapid)
    )

    if (
        int(candidate["weapon_type"]) == int(target["weapon_type"])
        and capability_ok
    ):
        return 1

    if (
        int(candidate["weapon_class"]) == int(target["weapon_class"])
        and capability_ok
    ):
        return 2

    return None


def candidate_is_eligible(row: pd.Series, args: argparse.Namespace) -> bool:
    if args.same_calibre and int(row["calibre"]) != int(args._target_calibre):
        return False

    if args.allowed_origin_mask is not None:
        origin = int(row["origin_flags"])
        if origin == 0:
            if not args.allow_unknown_origin:
                return False
        elif origin & int(args.allowed_origin_mask) == 0:
            return False

    if args.year is not None:
        start = int(row["production_year_start"])
        end = int(row["production_year_end"])
        # Unknown boundaries do not by themselves make a candidate unavailable.
        if start > 0 and args.year < start:
            return False
        if end > 0 and args.year > end:
            return False

    if (
        int(args.exclude_historical_mask)
        and int(row["historical_status_flags"]) & int(args.exclude_historical_mask)
    ):
        return False

    if args.exclude_scifi and bool(row["scifi"]):
        return False

    return True


def cmd_neighbors(
    payload: dict,
    df: pd.DataFrame,
    args: argparse.Namespace,
) -> int:
    hit = df.index[df["uiIndex"] == args.index].tolist()
    if not hit:
        raise SystemExit(f"uiIndex {args.index} is not in the firearm dataset")

    target_pos = hit[0]
    target = df.loc[target_pos]
    args._target_calibre = int(target["calibre"])

    weights = resolve_profile(payload, args.cth_system, args.overheating)
    matrix, features, scale = distance_matrix(df, weights)

    records = []
    for pos, candidate in df.iterrows():
        if pos == target_pos:
            continue

        tier = candidate_tier(target, candidate)
        if tier is None or tier > args.max_tier:
            continue
        if not candidate_is_eligible(candidate, args):
            continue

        delta = matrix[pos] - matrix[target_pos]
        distance = float(np.sqrt(np.dot(delta, delta)))
        records.append(
            {
                "tier": tier,
                "uiIndex": int(candidate["uiIndex"]),
                "name": candidate["name"],
                "weapon_type": candidate["weapon_type_name"],
                "calibre": candidate["calibre_name"],
                "distance": distance,
            }
        )

    records.sort(key=lambda r: (r["tier"], r["distance"], r["uiIndex"]))
    result = pd.DataFrame(records[: args.limit])

    print(
        f"target {int(target.uiIndex)}: {target['name']} "
        f"({target['weapon_type_name']}, {target['calibre_name']})"
    )
    print("tier 0=same type/exact required modes; 1=same type/capability; 2=same class/capability")
    print("metric features:", ", ".join(features))
    if result.empty:
        print("no eligible candidates")
        return 0

    print(result.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    best_tier = int(result.iloc[0]["tier"])
    best_index = int(result.iloc[0]["uiIndex"])
    best = df.loc[df["uiIndex"] == best_index].iloc[0]

    print(f"\nclosest candidate in best available tier ({best_tier}) feature differences:")
    details = []
    for feature in features:
        details.append(
            {
                "feature": feature,
                "target": float(target[feature]),
                "candidate": float(best[feature]),
                "delta": float(best[feature] - target[feature]),
                "robust_scale": float(scale[feature]),
                "weight": float(weights[feature]),
            }
        )
    print(pd.DataFrame(details).to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    return 0


def cmd_pca(
    payload: dict,
    df: pd.DataFrame,
    args: argparse.Namespace,
) -> int:
    weights = resolve_profile(payload, args.cth_system, args.overheating)
    matrix, features = analysis_matrix(df, weights)
    n_components = min(args.components, len(features), len(df))

    pca = PCA(n_components=n_components)
    scores = pca.fit_transform(matrix)

    print("PCA uses robust scaling but no replacement weights.")
    print("features:", ", ".join(features))
    print("explained variance ratio:")
    cumulative = 0.0
    for i, ratio in enumerate(pca.explained_variance_ratio_, start=1):
        cumulative += float(ratio)
        print(f"  PC{i}: {ratio:.4f}  cumulative={cumulative:.4f}")

    loadings = pd.DataFrame(
        pca.components_.T,
        index=features,
        columns=[f"PC{i}" for i in range(1, n_components + 1)],
    )
    print("\ncomponent loadings:")
    print(loadings.to_string(float_format=lambda x: f"{x: .3f}"))

    if scores.shape[1] >= 2:
        projected = df[["uiIndex", "name", "weapon_type_name"]].copy()
        projected["PC1"] = scores[:, 0]
        projected["PC2"] = scores[:, 1]
        print("\nfirst two PCA coordinates:")
        print(projected.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    return 0


def cmd_kmeans(
    payload: dict,
    df: pd.DataFrame,
    args: argparse.Namespace,
) -> int:
    weights = resolve_profile(payload, args.cth_system, args.overheating)
    matrix, features = analysis_matrix(df, weights)

    km = KMeans(n_clusters=args.k, random_state=args.seed, n_init=20)
    labels = km.fit_predict(matrix)
    sil = silhouette_score(matrix, labels) if 1 < args.k < len(df) else float("nan")

    out = df[["uiIndex", "name", "weapon_type_name", "calibre_name"]].copy()
    out["cluster"] = labels
    out = out.sort_values(["cluster", "weapon_type_name", "uiIndex"])

    print("k-means uses robust scaling but no replacement weights.")
    print("features:", ", ".join(features))
    print(f"k={args.k} silhouette={sil:.4f} inertia={km.inertia_:.2f}")
    print(out.to_string(index=False))

    print("\ncluster composition by weapon type:")
    print(pd.crosstab(out["cluster"], out["weapon_type_name"]).to_string())
    return 0


def candidate_count_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, target in df.iterrows():
        counts = {0: 0, 1: 0, 2: 0}
        for _, candidate in df.iterrows():
            if int(candidate["uiIndex"]) == int(target["uiIndex"]):
                continue
            tier = candidate_tier(target, candidate)
            if tier is not None:
                counts[tier] += 1
        rows.append(
            {
                "uiIndex": int(target["uiIndex"]),
                "name": target["name"],
                "tier0": counts[0],
                "tier1": counts[1],
                "tier2": counts[2],
                "through_tier1": counts[0] + counts[1],
                "through_tier2": counts[0] + counts[1] + counts[2],
            }
        )
    return pd.DataFrame(rows)


def cmd_diagnostics(
    payload: dict,
    df: pd.DataFrame,
    args: argparse.Namespace,
) -> int:
    weights = resolve_profile(payload, args.cth_system, args.overheating)
    matrix, features = analysis_matrix(df, weights)

    print(f"weapons={len(df)}")
    print("active exploratory features:", ", ".join(features))
    print("dataset settings:", json.dumps(payload.get("settings", {}), sort_keys=True))

    corr = df[features].corr(numeric_only=True)
    pairs = []
    for i, left in enumerate(features):
        for right in features[i + 1 :]:
            value = float(corr.loc[left, right])
            pairs.append((abs(value), value, left, right))
    pairs.sort(reverse=True)

    print("\ntop absolute Pearson correlations:")
    for _, value, left, right in pairs[:20]:
        print(f"  {left:32s} {right:32s} r={value: .3f}")

    n_components = min(8, len(features), len(df))
    pca = PCA(n_components=n_components).fit(matrix)
    print("\nPCA explained variance (unweighted robust-scaled data):")
    cumulative = 0.0
    for i, ratio in enumerate(pca.explained_variance_ratio_, start=1):
        cumulative += float(ratio)
        print(f"  PC{i}: {ratio:.4f} cumulative={cumulative:.4f}")

    print("\nPCA strongest loadings:")
    for i, component in enumerate(pca.components_, start=1):
        order = np.argsort(np.abs(component))[::-1][:6]
        text = ", ".join(f"{features[j]}={component[j]:+.3f}" for j in order)
        print(f"  PC{i}: {text}")

    print("\nk-means silhouette diagnostics:")
    for k in range(args.k_min, args.k_max + 1):
        if k >= len(df):
            break
        km = KMeans(n_clusters=k, random_state=args.seed, n_init=20)
        labels = km.fit_predict(matrix)
        score = silhouette_score(matrix, labels)
        print(f"  k={k:2d} silhouette={score:.4f} inertia={km.inertia_:.2f}")

    counts = candidate_count_summary(df)
    print("\ncandidate coverage before country/year filtering:")
    for col in ("tier0", "through_tier1", "through_tier2"):
        s = counts[col]
        print(
            f"  {col:14s} min={int(s.min())} p10={s.quantile(.10):.1f} "
            f"median={s.median():.1f} p90={s.quantile(.90):.1f} "
            f"zero={int((s == 0).sum())}"
        )

    print("\nsparse tier-0 cases:")
    sparse = counts.sort_values(["tier0", "uiIndex"]).head(20)
    print(sparse.to_string(index=False))

    origin_nonzero = int((df["origin_flags"] != 0).sum())
    year_start = int((df["production_year_start"] != 0).sum())
    year_end = int((df["production_year_end"] != 0).sum())
    historical_nonzero = int((df["historical_status_flags"] != 0).sum())
    print("\nfilter metadata coverage:")
    print(f"  origin nonzero: {origin_nonzero}/{len(df)}")
    print(f"  production start nonzero: {year_start}/{len(df)}")
    print(f"  production end nonzero: {year_end}/{len(df)}")
    print(f"  historical status nonzero: {historical_nonzero}/{len(df)}")
    print(f"  SciFi true: {int(df['scifi'].sum())}/{len(df)}")
    return 0


def main() -> int:
    args = parse_args()
    payload, df = load_dataset(args.dataset)

    if args.command == "neighbors":
        return cmd_neighbors(payload, df, args)
    if args.command == "pca":
        return cmd_pca(payload, df, args)
    if args.command == "kmeans":
        return cmd_kmeans(payload, df, args)
    if args.command == "diagnostics":
        return cmd_diagnostics(payload, df, args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
