# Weapon similarity analysis

This directory is an offline analysis layer for designing weapon substitutions after
country / historical filtering removes an item.

It does **not** implement runtime filtering or replacement in C++.

## Why Python first

The game remains authoritative. Python is used because exploratory statistics are much
easier to inspect and change with NumPy / pandas / scikit-learn than inside the JA2
runtime. Once the feature set and distance rule are stable, the small deterministic
scoring rule can be ported back to C++.

The extractor separates raw XML, weapon-only base features, and effective intrinsic
features. "Effective intrinsic" means the weapon item at 100% status with its own
inherent item modifiers applied, but without ammunition, attachments, soldier traits,
stance, target state, or a full CTH simulation.

It deliberately does not claim to reproduce complete tactical performance. Full CTH and
several other mechanics remain contextual.

## Authoritative inputs

- `gamedir/Data-1.13/TableData/Items/Weapons.xml`
  - mechanical weapon data: damage, range, firing rate, burst/auto, recoil, accuracy,
    handling, magazine size, heat, ready/reload values
- `gamedir/Data-1.13/TableData/Items/Items.xml`
  - item data: weight, size, reliability, two-handedness, coolness, production years,
    origin flags, historical-status flags and item-level modifiers
- `gamedir/Data-1.13/TableData/Items/AmmoStrings.xml`
  - readable calibre names
- `gamedir/Data-1.13/Item_Settings.ini`
  - weapon-type multipliers used by the engine
- `gamedir/Data-1.13/Ja2_Options.INI`
  - global gun range/damage/autofire and active OCTH/NCTH/overheating settings
- `gamedir/Data-1.13/APBPConstants.ini`
  - AP scale and autofire AP constants used by reference AP calculations

Relevant engine implementation:

- `Tactical/Weapons.h`: `WEAPONTYPE`
- `Tactical/Weapons.cpp`: XML parsing, `GunRange`, `GetDamage`,
  `GetAPsToReload`, burst/autofire helpers and CTH implementations
- `Tactical/Points.cpp`: `BaseAPsToShootOrStab(NoModifier)` and
  `GetAPsToReadyWeapon`
- `Tactical/Items.cpp`: item/attachment modifiers such as range, damage,
  ready/reload and AP modifiers
- `Tactical/Item Types.h`: `INVTYPE`, origin and historical-status metadata
- `Utils/XML_Items.cpp`: Items.xml parser

## Generate a feature snapshot

From repository root:

```bash
python tools/weapon-similarity/extract_weapon_features.py \
  --output tools/weapon-similarity/weapon_features.json
```

The output contains:

- `raw`: XML values
- `base_features`: weapon + configured global/type baseline, before item modifiers
- `effective_intrinsic_features`: base plus the weapon item's own modifiers at 100%
  status

Replacement analysis defaults to `effective_intrinsic_features`. Use
`--feature-layer base` on analysis commands to inspect the pre-item-modifier baseline.

Reference AP quantities use an 80-full-AP / 80-aim-skill reference soldier by default.
The snapshot also records SHA-256 fingerprints for every source file above.

Check that the committed snapshot can be exactly regenerated:

```bash
python tools/weapon-similarity/check_weapon_features.py
```

CI runs the same regeneration check without requiring NumPy, pandas, or scikit-learn.

## Statistical workflow

Install the optional analysis dependencies:

```bash
python -m pip install -r tools/weapon-similarity/requirements.txt
```

Run the complete diagnostic pass:

```bash
python tools/weapon-similarity/analyze_weapon_space.py \
  tools/weapon-similarity/weapon_features.json diagnostics
```

Inspect PCA:

```bash
python tools/weapon-similarity/analyze_weapon_space.py \
  tools/weapon-similarity/weapon_features.json pca
```

Find replacements for uiIndex 25 using the current game mechanics profile:

```bash
python tools/weapon-similarity/analyze_weapon_space.py \
  tools/weapon-similarity/weapon_features.json neighbors --index 25
```

Restrict candidates to a country/origin mask:

```bash
python tools/weapon-similarity/analyze_weapon_space.py \
  tools/weapon-similarity/weapon_features.json neighbors \
  --index 25 --allowed-origin-mask 0x1
```

Evaluate an entire filter configuration rather than one target:

```bash
python tools/weapon-similarity/analyze_weapon_space.py \
  tools/weapon-similarity/weapon_features.json coverage \
  --allowed-origin-mask 0x1
```

The `coverage` command reports the first fallback tier used for every removed weapon,
distance-quality bands, the most stretched substitutions, and unresolved targets.

Explore k-means clusters:

```bash
python tools/weapon-similarity/analyze_weapon_space.py \
  tools/weapon-similarity/weapon_features.json kmeans --k 8
```

See `ANALYSIS_REPORT.md` for the current validation results and country-filter stress
tests.

## Interpretation

For replacement, clustering is secondary. The primary operation should be:

1. Apply eligibility filters first: the candidate must survive the country/year/status
   filter and satisfy hard gameplay constraints.
2. Compute distance only among eligible candidates.
3. Use a standardized, weighted distance on tactical features.
4. Return the nearest candidate, with an explicit distance and per-feature differences.

A cluster says "these weapons occupy a similar region." It does not tell us which member
is the best substitute for a specific removed weapon.

PCA is useful for learning the structure of the dataset and identifying redundant axes.
It should not automatically define the runtime score. ICA is not currently justified:
there is no strong generative assumption that JA2 weapon stats are mixtures of
statistically independent latent sources.

## Semantic fallback tiers

Eligibility and tactical similarity are separate.

Country, production-year, SciFi and historical-status metadata determine whether a
candidate may be used. They are **not** coordinates in the distance vector.

Among eligible weapons, candidates are ordered by semantic fallback tier before
statistical distance:

0. same type, same handedness, preserve every required fire mode
1. same type, same handedness, preserve broad rapid-fire capability
2. adjacent tactical type, same handedness, preserve broad rapid-fire capability
3. same type, relax handedness, preserve broad rapid-fire capability
4. adjacent tactical type, relax handedness, preserve broad rapid-fire capability
5. same type, same handedness, allow fire-mode downgrade
6. adjacent tactical type, same handedness, allow fire-mode downgrade
7. same type, relax handedness, allow fire-mode downgrade
8. adjacent tactical type, relax handedness, allow fire-mode downgrade

Tactical role and heavy-gun status are never relaxed. The role gate separates
special-purpose records that happen to use ordinary gun types: Dart Gun, Flamethrower,
Pepper Spray, Hand Mortar, and the Rocket Rifle family. The role is derived from their
distinctive calibre/ammunition identity; ordinary firearms use `conventional`.

Schema v5 also adds an explicit `replacement_family` tag for benchmark-audited cases.
It is deliberately not inferred from display names. The current asserted families are
the G36 rifle line, the MG36 pair, and the three AR57 barrel-length variants. An empty
family tag means "no family preference asserted", not "unrelated in real life".

Family affinity may bridge an adjacent weapon-type boundary, but only when the candidate
also has the same calibre and handedness and preserves every fire mode required by the
target. Family therefore does **not** compensate for lost tactical capability. This is
why AR57 16" may prefer AR57 11", while G36C does not prefer a non-burst G36 rifle merely
because the model lineage matches.

The adjacency graph is explicit in `analyze_weapon_space.py`; it is used instead of
`weapon_class` because the XML class field is not fully consistent for machine pistols
and some LMGs.

Calibre is a logistics preference, not a default hard tactical constraint. After family
priority and semantic tier are fixed, a same-calibre candidate is preferred only when
its mechanical distance is no more than **5%** worse than the mechanically closest
candidate in that same group. This bounds the cost of ammunition compatibility. Use
`--same-calibre` when the scenario requires strict ammunition compatibility.

Selection order is therefore:

1. eligibility filters;
2. hard tactical-role / heavy-gun compatibility;
3. audited capability-preserving replacement-family priority;
4. semantic fallback tier;
5. bounded same-calibre near-tie preference;
6. mechanical distance.

## Mechanics-aware distance profile

The score is configuration-aware. Core axes currently include:

- damage
- effective range
- reference AP per shot
- ready AP
- reload AP
- burst AP surcharge
- reference 5-round autofire AP surcharge
- magazine capacity
- weight and item size
- reliability and repair ease
- burst/autofire characteristics

Accuracy/control axes depend on the selected CTH system:

- OCTH: weapon accuracy, inherent item to-hit/aim bonuses, and effective
  burst/autofire penalties
- NCTH: NCTH accuracy, handling, aim levels and recoil

The optional NCTH profile currently uses the weapon-level values above but does not fold
stance-specific `Items.xml` NCTH modifiers into a single effective-intrinsic vector.
Those modifiers are deliberately stance-dependent, while this model excludes soldier
stance. Treat NCTH output as exploratory until that policy is calibrated.

Heat endurance is included only when overheating is enabled.

The checked-in snapshot currently represents `NCTH = FALSE` and
`OVERHEATING = FALSE`, so inactive NCTH/heat columns do not influence the default
replacement score.

All continuous axes use robust scaling before weighting:

```text
z = (x - median) / IQR
```

This prevents large-unit or outlier-heavy columns from dominating merely because of
their units. Zero-IQR columns fall back to sample standard deviation. Replacement
distance then applies mechanics-sized minimum scales of 10 CTH points to the sparse
OCTH `ToHitBonus` and `AimBonus` axes. This prevents a handful of built-in laser/scope
items from becoming many artificial standard deviations solely because almost every
weapon has zero in those fields. PCA and k-means keep the unmodified robust scaling.

The tool also reports a role-and-type-relative distance percentile. It compares a
filtered replacement with the unrestricted tier-0 nearest-neighbour distribution for
the same tactical role and weapon type. Cohorts with fewer than five reference weapons
report `unknown` instead of a misleading percentile:

- <= 75th percentile: `typical`
- 75th-95th: `stretched`
- > 95th: `far`

The manual benchmark and country-filter probes are recorded in
`BENCHMARK_CASES.md`. The cross-type family policy and default calibre policy are now
resolved for the active OCTH model. NCTH remains exploratory because stance-specific
intrinsic modifiers still lack a finalized aggregation policy.
