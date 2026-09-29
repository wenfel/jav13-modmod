# Weapon similarity analysis report

Branch: `feature/weapon-similarity-analysis`  
Base: `country-filter`

This report records the current validation state of the offline firearm-similarity
analysis used to design replacements after origin/year/status filters remove an item.

It is not a full tactical simulator. It deliberately separates source data, weapon-only
base values, intrinsic item modifiers, and context that remains outside the model.

## 1. Corrected source baseline

A review of the original PR #3 metadata population found two manifest/XML mismatches:

- uiIndex 1 Glock 17 had accidentally received S&O Shorty's Germany / 1998-2002 data
- uiIndex 779 S&O Shorty remained origin/year zeroed

That defect was fixed separately in PR #6 and merged into `country-filter` at:

`09a5f4a990febea69f69adde6bb95b6f5eb5b2ca`

The full 347-row weapon-origin manifest was compared with the corrected `Items.xml`
for production start, production end, and origin mask. Mismatches after the hotfix: **0**.

PR #5's analysis branch then merged that corrected base before regenerating its snapshot.

The checked-in snapshot now contains:

- Glock 17: Austria, production years 0-0
- S&O Shorty: Germany, production years 1998-2002

## 2. Reproducible source fingerprints

`weapon_features.json` records SHA-256 fingerprints for every source file that currently
affects generated features:

| Source | SHA-256 |
| --- | --- |
| `Items.xml` | `3617fb507f03f3da8c342d5644b5ae64509678523b09775a19942fb6dace0906` |
| `Weapons.xml` | `52d759787c975137cafb0fc270420f7d42d40c0017a89adf61bf45e64342b87c` |
| `AmmoStrings.xml` | `b80d0f9aa16d2491d45092e9310e0134d9ace9c0b6caa1d47eb7f7c0d46d5090` |
| `Item_Settings.ini` | `237533ccb45f42ac6a4ecb26052d18a91248f1de925e1dd6c7275675f454f4cf` |
| `Ja2_Options.INI` | `5a947e94009f766c1bda652f728d4ce971e4a62ccee3225fb8e5e902f20ff07b` |
| `APBPConstants.ini` | `952ad289f72bec60e21cf3f78b925a11474f1c2abb08adc12539ba4286bc41ed` |

A new CI job runs the standard-library extractor and compares the parsed regenerated JSON
with the checked-in snapshot. Changes to inputs or extraction rules can therefore no
longer leave a silently stale snapshot.

## 3. Analysis population

The snapshot contains **314 conventional firearm records**.

Six `IC_GUN` records with weapon type 0 are excluded because their mechanics are not
ordinary firearm mechanics:

- Queen Spit
- Infant Spit
- Young Male Spit
- Old Male Spit
- Cannon
- Extinguisher

This explains the difference from the 347 gun/launcher origin-manifest population.

There are still a few special-purpose objects encoded with ordinary weapon types, such
as Pepper Spray, Flamethrower and Hand Mortar. They are retained for now and explicitly
treated as benchmark cases for future semantic classification rather than being removed
ad hoc.

## 4. Feature layers

Each weapon now has three conceptually distinct layers.

### Raw

`raw.weapon` and `raw.item` retain XML values without pretending they are final
tactical quantities.

### Base features

`base_features` contain weapon values after global / weapon-type INI baseline modifiers,
but before the item's own intrinsic modifiers.

Examples:

- `ubShotsPer4Turns` plus type INI modifier
- `ubImpact` plus configured gun/type damage baseline
- `usRange` plus configured gun/type range baseline
- reference AP/shot using `BaseAPsToShootOrStabNoModifier` semantics
- burst AP using `CalcAPsToBurstNoModifier` semantics

### Effective intrinsic features

`effective_intrinsic_features` start from the base layer and additionally apply the
weapon item's own modifiers at **100% item status**, while excluding:

- ammunition modifiers
- attachments
- soldier traits
- stance
- target state/range-dependent full CTH calculation
- item-condition degradation
- transient scope/attachment choices

Replacement distance defaults to this layer.

This is the intended meaning of "intrinsic": the weapon as defined by its own
`Weapons.xml` + `Items.xml` data, not a complete combat situation.

The analysis CLI can switch back to the base layer with:

`--feature-layer base`

## 5. Intrinsic modifier audit

For the 314-firearm population, current nonzero inherent modifiers relevant to this
analysis are:

| Modifier | Firearms |
| --- | ---: |
| `PercentAPReduction` | 5 |
| `PercentReadyTimeAPReduction` | 3 |
| `AutoFireToHitBonus` | 23 |
| `BurstToHitBonus` | 23 |
| `ToHitBonus` | 8 |
| `AimBonus` | 4 |

The current data has no nonzero firearm values for the other audited flat/percent range,
damage, magazine, ROF, reload-AP, burst/autofire-AP, recoil, or accuracy item modifiers.

Thirty firearms differ between the base and effective-intrinsic feature layers.

Observed differences in the current data:

- reference shot AP: 5 weapons
- 5-round autofire AP surcharge: 5
- ready AP: 3
- burst AP: 2
- burst penalty: 4
- autofire penalty: 18
- OCTH intrinsic to-hit bonus: 8
- OCTH intrinsic aim bonus: 4

## 6. Concrete modifier examples

The three AR57 variants have an inherent 30% ready-time AP reduction:

| Weapon | Base ready AP | Effective intrinsic ready AP |
| --- | ---: | ---: |
| AR57 16" | 13 | 9 |
| AR57 11" | 9 | 6 |
| AR57 6"-S | 11 | 7 |

The five weapons with 20% intrinsic general AP reduction now receive it in reference
single-shot and autofire economy. Example P90:

- reference AP/shot: 18 -> 15
- reference 5-round autofire surcharge: 16 -> 12
- autofire penalty: 7 -> 2 because of its built-in `AutoFireToHitBonus=5`

Burst AP is now an explicit rapid-fire feature. It mirrors the configured
`CalcAPsToBurst` arithmetic for the reference soldier and includes inherent general /
burst AP reductions where present.

A reference 5-round autofire AP surcharge is likewise included so that general AP
reduction is not captured for single shots while silently omitted from automatic fire.

The formula audit also found a C++ integer-width detail in
`GetAutofireShotsPerFiveAPs()`: the weapon-type multiplier is assigned back to a
`UINT8` before the global flat modifier is added. With the configured shotgun multiplier
of 1.3, this means CAWS and Jackhammer remain at 1 shot / 5 AP rather than 1.3, and
USAS-12 remains at 2 rather than 2.6. Their corrected reference 5-round autofire
surcharges are 64, 64, and 32 AP respectively.

## 7. OCTH/NCTH boundary

The checked-in configuration is:

- `NCTH = FALSE`
- `OVERHEATING = FALSE`
- `USE_SCOPE_MODES = TRUE`
- `AP_MAXIMUM = 100`
- `AUTOFIRE_SHOTS_AP_VALUE = 20`
- `AUTOFIRE_TOHIT_BONUS_MULTIPLIER = 5`

The default similarity profile therefore uses OCTH-relevant dimensions and excludes
NCTH/heat dimensions from distance.

The optional NCTH profile is not yet a complete effective-intrinsic model. `Items.xml`
contains nonzero stance-specific NCTH modifier blocks (for example `PercentHandling`,
`PercentMaxCounterForce`, `PercentCounterForceAccuracy`, and `AimLevels`). Because
the current intrinsic definition deliberately excludes stance, those modifiers are not
yet folded into a single NCTH distance vector. This does not affect the active OCTH
profile, but NCTH calibration should not be treated as finished.

OCTH's intrinsic terms are intentionally not collapsed into one invented "accuracy"
score:

- `bAccuracy`
- item `ToHitBonus`
- item `AimBonus`
- effective burst penalty
- effective autofire penalty

These enter the engine through different formulas and some are contextual. The snapshot
preserves them as separate axes; it does **not** claim to reproduce final chance-to-hit.

## 8. Fan-the-hammer correction

A naive `ubShotsPerBurst > 0` test incorrectly classifies some revolvers as native
burst weapons.

`IsGunBurstCapable()` checks `fBurstOnlyByFanTheHammer` and makes that capability
conditional on Gunslinger / alternate-hold requirements.

The dataset therefore separates:

- native `has_burst`
- `has_trait_gated_burst`

There are **13 trait-gated fan-the-hammer firearms**. Their trait-only burst data does not
enter the baseline replacement role.

## 9. Statistical representation

Continuous replacement axes use robust scaling:

```text
z = (x - median(x)) / IQR(x)
```

When a conditional column has zero IQR, the implementation falls back to its sample
standard deviation; a constant column becomes inert.

Replacement distance then uses an explicit weighted Euclidean metric:

```text
distance(A, B) = sqrt(sum_j w_j * (z_Aj - z_Bj)^2)
```

PCA and k-means use robust-scaled **unweighted** data so exploratory structure is not
forced to reproduce subjective replacement weights.

## 10. Effective-intrinsic correlation structure

Strong correlations under the active OCTH profile include:

| Feature A | Feature B | Pearson r |
| --- | --- | ---: |
| burst AP | burst size | 0.980 |
| burst size | burst penalty | 0.932 |
| burst AP | burst penalty | 0.927 |
| 5-round autofire AP | autofire penalty | 0.907 |
| autofire shots / 5 AP | autofire penalty | 0.899 |
| ready AP | item size | 0.825 |
| ready AP | weight | 0.825 |
| 5-round autofire AP | autofire shots / 5 AP | 0.737 |
| damage | reference shot AP | 0.745 |
| range | ready AP | 0.743 |
| range | weight | 0.739 |
| range | OCTH accuracy | 0.730 |

The correlations are expected: the XML balance deliberately couples firing speed with
control costs and larger weapons with range, weight and ready cost.

## 11. PCA after intrinsic-modifier correction

PCA on robust-scaled, unweighted effective-intrinsic active-profile data:

| Component | Variance | Cumulative | Dominant structure |
| --- | ---: | ---: | --- |
| PC1 | 27.8% | 27.8% | physical scale / range / capacity |
| PC2 | 21.2% | 49.0% | burst behavior versus long-range/slow-fire role |
| PC3 | 15.6% | 64.6% | magazine capacity versus burst behavior |
| PC4 | 8.4% | 73.0% | built-in OCTH to-hit / aim bonuses |
| PC5 | 5.7% | 78.7% | reliability/repair and intrinsic aiming |
| PC6 | 4.7% | 83.3% | automatic-fire economy/control mix |

The first three components now explain about **64.6%** rather than the earlier 72.7%.
That change is expected: adding real burst-AP and intrinsic-control/sight dimensions
creates additional independent variance.

Eight components explain about **89.8%**.

PCA remains a diagnostic/visualization technique, not the runtime replacement rule.

## 12. K-means after intrinsic-modifier correction

K-means remains an exploratory diagnostic only.

The effective-intrinsic model adds sparse built-in optics/control dimensions. That means
low-k solutions can isolate a few unusual weapons and produce superficially improved
silhouette values without discovering useful replacement classes. This is particularly
visible around OICW / Rocket Rifle / other intrinsic-bonus outliers.

Therefore the report no longer treats a single "best k" as a design result. Use the
checked-in `diagnostics` / `kmeans` commands with the desired feature layer and profile
to inspect cluster composition. The important stable conclusion is unchanged: cluster
membership must not determine replacement; semantic tier + local nearest-neighbour
distance does.

## 13. Semantic fallback tiers

Eligibility is evaluated before similarity.

Country/year/SciFi/historical metadata are filters, not distance dimensions.

Within the surviving pool, candidates are ordered by semantic fallback tier before
statistical distance:

0. same type, same handedness, preserve every required fire mode
1. same type, same handedness, preserve broad rapid-fire capability
2. adjacent type, same handedness, preserve broad rapid-fire capability
3. same type, relax handedness, preserve broad rapid-fire capability
4. adjacent type, relax handedness, preserve broad rapid-fire capability
5. same type, same handedness, allow fire-mode downgrade
6. adjacent type, same handedness, allow fire-mode downgrade
7. same type, relax handedness, allow fire-mode downgrade
8. adjacent type, relax handedness, allow fire-mode downgrade

Heavy-gun status is never relaxed.

The explicit adjacency graph is used instead of `weapon_class`, because the XML class
field is inconsistent for machine pistols and several LMGs.

## 14. Special-purpose tactical roles and country-filter stress tests

The benchmark review found a categorical failure that weights cannot solve: Pepper Spray,
Flamethrower, Hand Mortar and Dart Gun were being compared with ordinary weapons solely
because their XML weapon types are pistol, rifle or shotgun. The Rocket Rifle family had
the same problem when country filtering removed both family members.

Schema v4 therefore adds a derived `tactical_role` gate:

- `conventional` for ordinary firearms
- `dart_projector` for Dart Gun
- `flame_projector` for Flamethrower
- `chemical_sprayer` for Pepper Spray
- `hand_mortar` for Hand Mortar
- `rocket_rifle` for Rocket Rifle / A. R. Rifle

Tactical role is a hard semantic constraint and is never relaxed. A special-purpose
weapon with no eligible same-role candidate is reported unresolved rather than receiving
a numerically close but conceptually invalid ordinary firearm.

### USA-only origin pool

- eligible: 92
- replacements required: 222
- tier 0: 195
- tier 1: 4
- tier 2: 2
- tier 4: 15
- unresolved: **6**

### Soviet / Russia lineage pool

- eligible: 56
- replacements required: 258
- tier 0: 232
- tier 1: 15
- tier 3: 2
- tier 5: 3
- unresolved: **6**

### German-lineage pool

- eligible: 59
- replacements required: 255
- tier 0: 245
- tier 2: 2
- tier 3: 2
- unresolved: **6**

The six unresolved targets in each of these three lineage-only pools are the two Rocket
rifles plus Dart Gun, Flamethrower, Hand Mortar and Pepper Spray. None has an eligible
same-role weapon in those pools. This is intentional: semantic correctness takes
precedence over artificial 100% coverage.

## 15. Distance calibration after intrinsic correction

Across 309 weapons with an unrestricted tier-0 neighbour:

- median nearest distance: **0.555**
- 75th percentile: **0.879**
- 90th percentile: **1.343**
- 95th percentile: **1.874**

The distribution remains strongly weapon-type dependent, so the CLI reports a
type-relative distance percentile rather than relying on a universal hard cutoff.

The existing bands remain diagnostics:

- <= 75th percentile: `typical`
- >75th to 95th: `stretched`
- >95th: `far`

## 16. Intrinsic-bonus outliers

The effective layer intentionally exposes some extreme cases:

- OICW's closest unrestricted tier-0 neighbour is still very distant because OICW
  combines 20% AP reduction, `ToHitBonus=20`, and `AimBonus=15`
- OTs-39 and Rocket Rifle carry unusual built-in to-hit values
- MG36 combines AP reduction with an intrinsic aim bonus

These are not being "fixed" by lowering weights simply to compress the distribution.
They belong in the manual benchmark set, where we can decide how strongly built-in
optics/control should influence tactical equivalence.

There is a separate semantic issue around special-purpose ordinary-type records such as
Pepper Spray, Flamethrower and Hand Mortar. That is a role-classification problem, not
something weight tuning should conceal.

## 17. Filter metadata coverage

Current conventional-firearm metadata coverage remains:

- origin nonzero: **302 / 314**
- production start year nonzero: **65 / 314**
- production end year nonzero: **33 / 314**
- historical-status flags nonzero: **0 / 314**
- SciFi true: **18 / 314**

Origin stress tests are meaningful.

Production-year tests remain incomplete because most bounds are unknown.

Historical-status filtering cannot yet be stress-tested because that follow-up data
population has not been produced.

## 18. Current recommendation before a C++ port

The offline design should continue to use:

1. external eligibility filtering first;
2. the lowest available semantic fallback tier;
3. effective-intrinsic features by default;
4. robust-scaled weighted distance only inside that tier;
5. tier and distance percentile in diagnostics/logging;
6. PCA/k-means strictly for analysis;
7. explicit benchmark review before freezing weights.

The next calibration set should include both obvious variants and difficult cases:

- Glock 17 / Glock 19
- AK-74 / AKS-74
- SVD / SVDS
- G36 family and MG36
- P90
- OICW
- OTs-39
- Rocket Rifle / A. R. Rifle
- automatic shotguns
- one-handed short shotguns
- Pepper Spray
- Flamethrower
- Hand Mortar

Where a substitution is conceptually impossible, fix semantics/eligibility/tiering.
Where two semantically valid weapons are merely ranked poorly, then tune numerical
weights.

Do not port PCA, k-means or the exploratory Python stack to C++. Once calibration is
stable, the runtime port only needs the finalized intrinsic feature extraction,
normalization/scaling policy, semantic tiers, weights, and distance calculation.
