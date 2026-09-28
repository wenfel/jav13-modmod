#!/usr/bin/env python3
"""Explore JA2 weapon space and find constrained nearest-neighbour replacements."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

DEFAULT_FEATURES = [
    "damage",
    "range",
    "reference_shot_ap",
    "ready_ap",
    "reload_ap",
    "octh_accuracy",
    "ncth_accuracy",
    "handling",
    "magazine_capacity",
    "recoil_magnitude",
    "heat_shots_to_jam_threshold",
    "weight",
    "reliability",
]

DEFAULT_WEIGHTS = {
    "damage": 1.25,
    "range": 1.25,
    "reference_shot_ap": 1.40,
    "ready_ap": 0.75,
    "reload_ap": 0.60,
    "octh_accuracy": 0.70,
    "ncth_accuracy": 0.90,
    "handling": 0.90,
    "magazine_capacity": 0.65,
    "recoil_magnitude": 0.80,
    "heat_shots_to_jam_threshold": 0.35,
    "weight": 0.55,
    "reliability": 0.45,
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("dataset", type=Path)
    sub = p.add_subparsers(dest="command", required=True)

    pca = sub.add_parser("pca")
    pca.add_argument("--components", type=int, default=4)

    km = sub.add_parser("kmeans")
    km.add_argument("--k", type=int, default=8)
    km.add_argument("--seed", type=int, default=1)

    nn = sub.add_parser("neighbors")
    nn.add_argument("--index", type=int, required=True)
    nn.add_argument("--limit", type=int, default=10)
    nn.add_argument(
        "--relax-type",
        action="store_true",
        help="allow other weapon types; firearm/two-hand/heavy/fire-mode constraints remain",
    )
    nn.add_argument(
        "--same-calibre",
        action="store_true",
        help="require the same calibre",
    )
    nn.add_argument(
        "--ignore-two-handed",
        action="store_true",
        help="do not require the same one/two-handed state",
    )

    return p.parse_args()


def load_frame(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for w in data["weapons"]:
        if not w.get("is_firearm"):
            continue
        row = {
            "uiIndex": w["uiIndex"],
            "name": w["name"],
            "weapon_type": w["weapon_type"],
            "weapon_type_name": w["weapon_type_name"],
            "weapon_class": w["weapon_class"],
            "calibre": w["calibre"],
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
        row.update(w["features"])
        rows.append(row)
    return pd.DataFrame(rows)


def robust_scale(df: pd.DataFrame, features: Iterable[str]) -> tuple[np.ndarray, pd.Series, pd.Series]:
    cols = list(features)
    x = df[cols].astype(float)
    med = x.median(axis=0)
    q1 = x.quantile(0.25)
    q3 = x.quantile(0.75)
    iqr = q3 - q1

    # Some conditional features can have IQR=0. Fall back to MAD-like standard
    # deviation only for those columns; if still zero, use 1 to make the column inert.
    sd = x.std(axis=0, ddof=1).replace(0.0, np.nan)
    scale = iqr.where(iqr != 0.0, sd).fillna(1.0)
    z = (x - med) / scale
    return z.to_numpy(dtype=float), med, scale


def weighted_matrix(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    features = [f for f in DEFAULT_FEATURES if f in df.columns]
    z, _, _ = robust_scale(df, features)
    weights = np.array([DEFAULT_WEIGHTS.get(f, 1.0) for f in features], dtype=float)
    return z * np.sqrt(weights), features


def constraint_mask(df: pd.DataFrame, target: pd.Series, args: argparse.Namespace) -> pd.Series:
    mask = df["uiIndex"] != target["uiIndex"]

    if not args.relax_type:
        mask &= df["weapon_type"] == target["weapon_type"]

    if not args.ignore_two_handed:
        mask &= df["two_handed"] == target["two_handed"]

    mask &= df["heavy_gun"] == target["heavy_gun"]

    # Candidate may have extra fire modes, but it must not lose a mode the removed weapon had.
    if bool(target["has_semi_auto"]):
        mask &= df["has_semi_auto"]
    if bool(target["has_burst"]):
        mask &= df["has_burst"]
    if bool(target["has_autofire"]):
        mask &= df["has_autofire"]

    if args.same_calibre:
        mask &= df["calibre"] == target["calibre"]

    return mask


def cmd_neighbors(df: pd.DataFrame, args: argparse.Namespace) -> int:
    hit = df.index[df["uiIndex"] == args.index].tolist()
    if not hit:
        raise SystemExit(f"uiIndex {args.index} is not a firearm in this dataset")

    target_pos = hit[0]
    target = df.loc[target_pos]
    matrix, features = weighted_matrix(df)

    mask = constraint_mask(df, target, args).to_numpy()
    delta = matrix - matrix[target_pos]
    distance = np.sqrt(np.sum(delta * delta, axis=1))

    out = df.loc[mask, [
        "uiIndex",
        "name",
        "weapon_type_name",
        "calibre_name",
        "two_handed",
        "has_burst",
        "has_autofire",
    ]].copy()
    out["distance"] = distance[mask]
    out = out.sort_values(["distance", "uiIndex"]).head(args.limit)

    print(
        f"target {int(target.uiIndex)}: {target['name']} "
        f"({target['weapon_type_name']}, {target['calibre_name']})"
    )
    print(f"metric: robust-scaled weighted Euclidean on {', '.join(features)}")
    print(out.to_string(index=False))

    # Explain the closest result in raw feature differences.
    if not out.empty:
        best_index = int(out.iloc[0]["uiIndex"])
        best = df.loc[df["uiIndex"] == best_index].iloc[0]
        print("\nclosest-candidate feature differences:")
        details = []
        for f in features:
            details.append(
                {
                    "feature": f,
                    "target": float(target[f]),
                    "candidate": float(best[f]),
                    "delta": float(best[f] - target[f]),
                    "weight": DEFAULT_WEIGHTS.get(f, 1.0),
                }
            )
        print(pd.DataFrame(details).to_string(index=False))

    return 0


def cmd_pca(df: pd.DataFrame, args: argparse.Namespace) -> int:
    matrix, features = weighted_matrix(df)
    n_components = min(args.components, len(features), len(df))
    pca = PCA(n_components=n_components)
    scores = pca.fit_transform(matrix)

    print("features:", ", ".join(features))
    print("explained variance ratio:")
    cumulative = 0.0
    for i, ratio in enumerate(pca.explained_variance_ratio_, start=1):
        cumulative += float(ratio)
        print(f"  PC{i}: {ratio:.4f}  cumulative={cumulative:.4f}")

    print("\ncomponent loadings (absolute magnitude shows contribution):")
    loadings = pd.DataFrame(
        pca.components_.T,
        index=features,
        columns=[f"PC{i}" for i in range(1, n_components + 1)],
    )
    print(loadings.to_string(float_format=lambda x: f"{x: .3f}"))

    if scores.shape[1] >= 2:
        projected = df[["uiIndex", "name", "weapon_type_name"]].copy()
        projected["PC1"] = scores[:, 0]
        projected["PC2"] = scores[:, 1]
        print("\nfirst two PCA coordinates:")
        print(projected.to_string(index=False))

    return 0


def cmd_kmeans(df: pd.DataFrame, args: argparse.Namespace) -> int:
    matrix, features = weighted_matrix(df)
    km = KMeans(n_clusters=args.k, random_state=args.seed, n_init="auto")
    labels = km.fit_predict(matrix)

    out = df[["uiIndex", "name", "weapon_type_name", "calibre_name"]].copy()
    out["cluster"] = labels
    out = out.sort_values(["cluster", "weapon_type_name", "uiIndex"])

    print("features:", ", ".join(features))
    print(out.to_string(index=False))
    print("\ncluster composition by weapon type:")
    composition = pd.crosstab(out["cluster"], out["weapon_type_name"])
    print(composition.to_string())
    return 0


def main() -> int:
    args = parse_args()
    df = load_frame(args.dataset)

    if args.command == "neighbors":
        return cmd_neighbors(df, args)
    if args.command == "pca":
        return cmd_pca(df, args)
    if args.command == "kmeans":
        return cmd_kmeans(df, args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
