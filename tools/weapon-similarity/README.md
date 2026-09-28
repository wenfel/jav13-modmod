# Weapon similarity analysis

This directory is an offline analysis layer for designing weapon substitutions after
country / historical filtering removes an item.

It does **not** implement runtime filtering or replacement in C++.

## Why Python first

The game remains authoritative. Python is used because exploratory statistics are much
easier to inspect and change with NumPy / pandas / scikit-learn than inside the JA2
runtime. Once the feature set and distance rule are stable, the small deterministic
scoring rule can be ported back to C++.

The extractor mirrors only weapon-intrinsic or deterministic engine-side calculations.
It deliberately does not try to reproduce the complete CTH calculation: CTH also depends
on the soldier, target, stance, visibility, traits, optics, ammunition, attachments and
game options.

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
  - global gun range/damage/autofire settings

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

The output contains raw XML values and separately named derived values. Derived values
are scenario-specific where necessary. In particular, `reference_shot_ap` uses a
reference soldier with 80 full AP and 80 aim skill by default, matching the explanatory
example in `BaseAPsToShootOrStab`.

## Statistical workflow

Install the optional analysis dependencies:

```bash
python -m pip install -r tools/weapon-similarity/requirements.txt
```

Inspect PCA:

```bash
python tools/weapon-similarity/analyze_weapon_space.py \
  tools/weapon-similarity/weapon_features.json pca
```

Find tactically similar replacements for uiIndex 25:

```bash
python tools/weapon-similarity/analyze_weapon_space.py \
  tools/weapon-similarity/weapon_features.json neighbors --index 25
```

Explore k-means clusters:

```bash
python tools/weapon-similarity/analyze_weapon_space.py \
  tools/weapon-similarity/weapon_features.json kmeans --k 8
```

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

## Initial hard constraints

These are deliberately conservative and can be relaxed later:

- firearm item class
- same `ubWeaponType` by default
- preserve two-handedness
- preserve heavy-gun status
- preserve the target weapon's required fire modes
- optional same-calibre constraint

Country, production-year, SciFi and historical-status metadata are eligibility
constraints, not similarity features.

## Initial distance axes

The default nearest-neighbour score uses a relatively small set of interpretable axes:

- damage
- effective range
- reference AP per shot
- ready AP
- reload AP
- OCTH and NCTH accuracy
- handling
- magazine capacity
- recoil magnitude
- heat endurance
- weight
- reliability

The script standardizes these columns before weighting them. This prevents range (hundreds
of units) from numerically dominating reliability (roughly -4..+5) merely because of
units.

The weights are provisional. They are meant to be inspected against real replacement
pairs before any C++ implementation is frozen.
