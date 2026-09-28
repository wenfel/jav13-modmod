# Weapon similarity analysis report

Branch: `feature/weapon-similarity-analysis`  
Base: `country-filter`

This report records the first validation pass for a firearm replacement metric intended
to choose tactically similar weapons after country / historical filters remove an item.

## 1. Clean analysis population

The authoritative data comes from `Weapons.xml`, `Items.xml`, `AmmoStrings.xml`,
`Item_Settings.ini`, and `Ja2_Options.INI`, with the relevant formulas mirrored from
`Tactical/Weapons.cpp`, `Tactical/Points.cpp`, and `Tactical/Items.cpp`.

The cleaned snapshot contains **314 conventional firearms**.

Six `IC_GUN` records were excluded from the statistical population because their
mechanics are not ordinary firearm mechanics: creature spit attacks, tank cannon, and
fire extinguisher. They should not influence firearm scaling, PCA, clustering, or
replacement distances.

The checked-in configuration represented by the snapshot has:

- `NCTH = FALSE`
- `OVERHEATING = FALSE`
- gun damage modifier = 1.0
- gun range modifier = 1.0

The default replacement profile therefore uses OCTH-relevant accuracy/fire-mode
variables and does not allow inactive NCTH or overheating variables to affect distance.
The analysis script can explicitly switch profiles for sensitivity testing.

## 2. Engine-specific correction: fan-the-hammer

A naive `ubShotsPerBurst > 0` test incorrectly classifies some revolvers as native
burst-fire weapons.

`IsGunBurstCapable()` in `Tactical/Weapons.cpp` checks
`fBurstOnlyByFanTheHammer` and makes that burst capability conditional on Gunslinger,
alternate weapon hold, and the other fan-the-hammer requirements.

The dataset now separates:

- native `has_burst`
- `has_trait_gated_burst`

There are **13 trait-gated fan-the-hammer firearms** in the current data. Trait-gated
burst size/penalty is not included in the baseline replacement vector.

This correction materially improves filter coverage for revolvers.

## 3. Statistical representation

The default active OCTH profile currently uses these continuous axes:

- damage
- effective range
- reference AP per shot
- ready AP
- reload AP
- magazine capacity
- weight
- item size
- reliability
- repair ease
- native burst size
- native burst penalty
- autofire shots per 5 AP
- autofire penalty
- OCTH accuracy

Raw values are transformed with robust scaling:

```text
z = (x - median(x)) / IQR(x)
```

If a conditional column has zero IQR, the implementation falls back to standard
deviation; a constant column becomes inert.

For replacement selection the scaled axes receive explicit gameplay weights and use
weighted Euclidean distance:

```text
distance(A, B) = sqrt(sum_j w_j * (z_Aj - z_Bj)^2)
```

For PCA and k-means the weights are **not** applied. This is deliberate: exploratory
statistics should describe the structure of the dataset rather than rediscover the
subjective replacement weights.

## 4. Correlation structure

Strong correlations in the active profile include:

| Feature A | Feature B | Pearson r |
| --- | --- | ---: |
| burst size | burst penalty | 0.938 |
| autofire shots / 5 AP | autofire penalty | 0.911 |
| ready AP | item size | 0.827 |
| ready AP | weight | 0.824 |
| damage | reference shot AP | 0.748 |
| range | ready AP | 0.741 |
| range | weight | 0.739 |
| range | OCTH accuracy | 0.730 |
| item size | OCTH accuracy | 0.708 |
| damage | range | 0.704 |

This is not merely a statistical nuisance. It describes how the XML balance is built:
larger/longer-ranged guns tend to be heavier, slower to ready, and more accurate, while
automatic-fire speed is intentionally coupled to control penalties.

It also explains why blindly counting every raw XML column as an independent dimension
would double-count several gameplay concepts.

## 5. PCA

PCA was run on robust-scaled, unweighted active-profile data.

| Component | Variance | Cumulative | Strongest interpretation |
| --- | ---: | ---: | --- |
| PC1 | 35.0% | 35.0% | physical scale / reach / firing tempo |
| PC2 | 22.7% | 57.8% | magazine capacity and sustained-fire role |
| PC3 | 15.0% | 72.7% | burst-fire behavior |
| PC4 | 6.4% | 79.1% | repairability / reliability |
| PC5 | 5.0% | 84.2% | size / reliability / automatic-fire mix |
| PC6 | 3.4% | 87.6% | shot tempo versus range / automatic fire |

PC1 loads most heavily on weight, range, item size, reference shot AP and magazine
capacity. PC2 is dominated by magazine capacity. PC3 is dominated by burst size and
burst penalty.

The first three components explain roughly **72.7%** of the variance. Six components
explain roughly **87.6%**.

This means the arsenal has substantial lower-dimensional structure, but not enough to
justify replacing the runtime metric with only two or three PCA coordinates. PCA is
valuable for diagnosis and visualization, not as the final substitution rule.

## 6. K-means

Silhouette results for the active profile:

| k | Silhouette |
| ---: | ---: |
| 2 | 0.199 |
| 3 | 0.276 |
| 4 | 0.306 |
| 5 | **0.338** |
| 6 | 0.334 |
| 7 | 0.315 |
| 8 | 0.324 |
| 9 | 0.282 |
| 10 | 0.292 |
| 11 | 0.265 |
| 12 | 0.293 |

The best result in this range is only about **0.34**, which is moderate/weak separation.
At k=8 the clusters still mix several XML weapon types. Examples include combined
pistol/shotgun clusters, mixed SMG/assault-rifle clusters, and separate LMG subgroups.

Conclusion: k-means is useful for exploring tactical regions, but cluster membership
should not determine replacements.

## 7. Semantic fallback tiers

The initial implementation used `weapon_class` as a broad fallback. Inspection showed
that this field is not consistent enough for that purpose:

- machine pistols split between handgun and SMG classes
- four LMGs are classed as rifles

The scorer now uses an explicit tactical adjacency graph between weapon types.

The ordered fallback tiers are:

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

Current adjacency is deliberately conservative:

- pistol <-> machine pistol
- machine pistol <-> pistol / SMG
- SMG <-> machine pistol / assault rifle
- rifle <-> sniper rifle / assault rifle
- sniper rifle <-> rifle / assault rifle
- assault rifle <-> rifle / SMG / LMG
- LMG <-> assault rifle
- shotgun remains shotgun

Tier is ordered before statistical distance. Thus a slightly more distant semantically
faithful candidate beats a numerically close but role-changing candidate.

## 8. Country-filter stress tests

These are diagnostic masks, not a statement of intended campaign composition.

### USA-only origin pool

- eligible firearms: 92
- removed weapons requiring replacement: 222
- tier 0: 200
- tier 1: 4
- tier 2: 3
- tier 4: 15
- unresolved: **0**

The tier-4 cases are mainly one-handed machine pistols. The U.S.-origin pool lacks a
matching one-handed automatic weapon for those targets, so the fallback becomes a
two-handed adjacent SMG.

Examples:

- Glock 18 -> Colt SMG, tier 4, distance ~2.29
- MP5KA4 -> KAC PDW, tier 4, distance ~1.62
- AK-74 -> M468, tier 0, distance ~1.20

### Soviet / Russia lineage pool

Mask includes Soviet Union, Russia, and Russian Empire origins.

- eligible firearms: 56
- removed weapons requiring replacement: 258
- tier 0: 237
- tier 1: 15
- tier 2: 1
- tier 3: 2
- tier 5: 3
- unresolved: **0**

The tier-5 cases are full-auto shotguns for which the eligible pool has no equivalent
automatic shotgun; a semiautomatic shotgun is therefore used as an explicit
fire-mode downgrade.

Examples:

- CAWS -> Saiga 12K, tier 5, distance ~1.96
- Sawed-Off -> MP-233B, tier 3, distance ~2.02

### German-lineage pool

Mask includes Germany, East Germany, and pre-1949 Germany.

- eligible firearms: 59
- removed weapons requiring replacement: 255
- tier 0: 250
- tier 2: 3
- tier 3: 2
- unresolved: **0**

The remaining tier-3 cases are the one-handed short shotguns. The origin pool has no
one-handed shotgun equivalent, so handedness must be relaxed.

## 9. Distance calibration

Weighted robust Euclidean distance has no natural physical unit. Therefore an absolute
cutoff such as "distance > 2 is bad" is poorly justified.

A better calibration is empirical: compare a filtered replacement's distance with the
distribution of unrestricted tier-0 nearest-neighbour distances for the same weapon
type.

Across 313 firearms with at least one tier-0 neighbour:

- median nearest distance: **0.548**
- 75th percentile: **0.911**
- 90th percentile: **1.312**
- 95th percentile: **1.794**

The distribution differs substantially by weapon type. Pistols have a median of about
0.26, while rifles and sniper rifles are much more heterogeneous.

The analysis tool now reports a type-relative distance percentile and labels it:

- <= 75th percentile: `typical`
- > 75th to 95th: `stretched`
- > 95th: `far`

This is a warning/diagnostic, not another hard eligibility rule.

## 10. Filter metadata coverage

Current conventional-firearm coverage:

- origin nonzero: **302 / 314**
- production start year nonzero: **65 / 314**
- production end year nonzero: **33 / 314**
- historical-status flags nonzero: **0 / 314**
- SciFi true: **18 / 314**

Origin-filter stress tests are therefore meaningful now.

Year-filter conclusions are still weak because most production bounds are unknown.
Historical-status filtering cannot yet be stress-tested because the new status metadata
has deliberately not been populated in `Items.xml`.

Unknown dates are treated as unknown, not as automatically unavailable.

## 11. Current recommendation

For the eventual C++ implementation:

1. filter candidate eligibility first;
2. assign the lowest available semantic fallback tier;
3. compare only candidates in that best tier using robust-scaled weighted distance;
4. expose/log both tier and distance quality;
5. never use k-means cluster membership as the replacement decision;
6. choose OCTH/NCTH/overheating feature terms from the actual game configuration;
7. keep country, year, SciFi and historical-status metadata out of the similarity vector.

Do not port the statistical exploration stack to C++. The eventual runtime code only
needs the frozen feature extraction, robust scaling constants/strategy, tier rules, and
weighted distance.

## 12. Remaining validation work before C++ port

- populate historical-status metadata, then run the coverage command with exclusion masks;
- improve production-year coverage before treating year tests as authoritative;
- manually review a benchmark set of obvious variant pairs and difficult filtered cases;
- decide policy for the 12 firearms whose origin mask is still zero;
- decide whether calibre should remain optional, be a hard constraint in some modes, or
  receive a categorical penalty;
- tune weights only after reviewing failures; prefer changing semantic constraints when
  the problem is categorical rather than numerical.
