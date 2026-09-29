# Weapon similarity manual benchmark

This benchmark records qualitative review cases for the offline replacement model.
It is calibration evidence, not runtime behavior and not a list of mandatory replacements.

Snapshot/model basis:
- schema v5 effective-intrinsic features
- active OCTH profile
- tactical-role hard constraint
- audited capability-preserving replacement-family priority is evaluated before semantic tier
- same-calibre may win a <=5% near-tie inside the same family-priority + tier group
- country/year/SciFi/historical filters remain external eligibility constraints

Status vocabulary:
- **anchor**: ranking is tactically sensible and useful as a calibration anchor
- **review-tier**: a conceptually relevant family member loses because semantic tier ordering has priority
- **review-weight**: candidates are semantically admissible, but sparse intrinsic bonuses or numeric distance need calibration review
- **role-fixed**: the old result was conceptually wrong; the tactical-role gate now prevents it
- **special-pair**: a dedicated special-purpose family is correctly isolated from conventional firearms
- **policy-anchor**: the case directly validates the finalized family/calibre selection policy

## 40 unrestricted benchmark cases

| # | Target | Best permitted candidate | Tier | Distance | Percentile | Status | Review note |
|---:|---|---|---:|---:|---:|---|---|
| 1 | Glock 17 | Glock 19 | 0 | 0.534 | 90.1 | anchor | Correct family counterpart; percentile is high because the pistol neighborhood is very dense. |
| 2 | Glock 19 | Glock 17 | 0 | 0.534 | 90.1 | anchor | Reciprocal family anchor. |
| 3 | AK-74 | AKS-74 | 0 | 0.066 | 4.3 | anchor | Extremely close expected variant. |
| 4 | AKS-74 | AK-74 | 0 | 0.066 | 4.3 | anchor | Reciprocal expected variant. |
| 5 | AK-47 | AKS-47 | 0 | 0.032 | 2.2 | anchor | Extremely close expected variant. |
| 6 | AKS-47 | AK-47 | 0 | 0.032 | 2.2 | anchor | Reciprocal expected variant. |
| 7 | AKM | AKMS | 0 | 0.181 | 10.9 | anchor | Close expected variant. |
| 8 | AKMS | AKM | 0 | 0.181 | 10.9 | anchor | Reciprocal expected variant. |
| 9 | SVD | SVDS | 0 | 0.367 | 10.3 | anchor | Expected sniper-family pair. |
| 10 | SVDS | SVD | 0 | 0.367 | 10.3 | anchor | Reciprocal expected pair. |
| 11 | G36C | AK-108 | 0 | 1.206 | 93.5 | policy-anchor | G36C requires burst+auto. The audited G36-rifle family does not get priority because its other rifle variants lack burst; family never overrides a required fire mode. |
| 12 | G36 RAS | G36K RAS | 0 | 0.333 | 22.8 | anchor | Expected family pair. |
| 13 | G36K RAS | G36 RAS | 0 | 0.333 | 22.8 | anchor | Reciprocal expected pair. |
| 14 | G36 | G36K | 0 | 0.395 | 31.5 | anchor | Expected family pair after intrinsic modifiers. |
| 15 | G36K | G36 | 0 | 0.395 | 31.5 | anchor | Reciprocal expected pair. |
| 16 | MG36 RAS | MG36 | 0 | 1.204 | 65.0 | anchor | Mechanics-scale calibration restores the expected same-family nearest neighbor. |
| 17 | MG36 | MG36 RAS | 0 | 1.204 | 65.0 | anchor | Reciprocal family anchor after correcting sparse AimBonus scaling. |
| 18 | P90 | Magpul PDR-D | 0 | 1.339 | 88.2 | review-weight | Semantically plausible compact PDW/SMG result; AR57 variants are nearby but cross the type boundary. |
| 19 | OICW | AK-108 | 0 | 2.484 | 100.0 | review-weight | Still a genuine outlier after mechanics-scale calibration; its AP/laser/scope package remains unusually strong. |
| 20 | OTs 39 | L2A3 | 0 | 1.412 | 94.1 | policy-anchor | Same-calibre Type 85 is mechanically more than 5% farther, so calibre does not override the closer tactical match. |
| 21 | Rocket Rifle | A. R. Rifle | 0 | 5.704 | unknown | special-pair | Correctly isolated to the Rocket family; conventional rifles are no longer candidates. |
| 22 | A. R. Rifle | Rocket Rifle | 5 | 5.704 | unknown | special-pair | Same special family; tier 5 reflects loss of the target's burst capability. |
| 23 | CAWS | Jackhammer | 0 | 1.967 | 94.7 | review-weight | Correct automatic-shotgun neighborhood after fixing C++ autofire integer semantics. |
| 24 | Jackhammer | CAWS | 0 | 1.967 | 94.7 | review-weight | Reciprocal automatic-shotgun case. |
| 25 | USAS-12 | CAWS | 0 | 2.097 | 100.0 | policy-anchor | Jackhammer shares 12 gauge but is >5% farther, so the bounded calibre preference correctly leaves CAWS first. |
| 26 | SPAS-15 | Saiga 12K | 0 | 0.484 | 31.6 | anchor | Good conventional semi-auto shotgun anchor. |
| 27 | Sawed-Off | Super-Shorty | 0 | 1.176 | 78.9 | anchor | Correct one-handed short-shotgun counterpart. |
| 28 | Super-Shorty | Sawed-Off | 0 | 1.176 | 78.9 | anchor | Reciprocal short-shotgun anchor. |
| 29 | Dart Gun | none | — | — | unknown | role-fixed | Dedicated dart role; no conventional pistol fallback is allowed. |
| 30 | Pepper Spray | none | — | — | unknown | role-fixed | Dedicated chemical-sprayer role; no conventional pistol fallback is allowed. |
| 31 | Flamethrower | none | — | — | unknown | role-fixed | Dedicated flame-projector role; no conventional rifle fallback is allowed. |
| 32 | Hand Mortar | none | — | — | unknown | role-fixed | Dedicated hand-mortar role; no conventional shotgun fallback is allowed. |
| 33 | G11 | AN-94 | 0 | 1.767 | 96.7 | review-weight | Semantically plausible advanced assault-rifle substitute, but numerically far. |
| 34 | VSS | VSk-94 | 0 | 0.666 | 43.6 | anchor | Good suppressed 9x39 sniper-role anchor. |
| 35 | MP5SD5 | SAF Silenciada | 0 | 0.769 | 44.1 | anchor | Good suppressed-SMG anchor. |
| 36 | AS Val | Vikhr | 0 | 1.086 | 92.4 | anchor | Plausible 9x39 automatic-weapon pairing despite a relatively dense assault-rifle cohort. |
| 37 | DSR-1 | AWM | 0 | 0.897 | 59.0 | anchor | Plausible magnum precision-rifle pairing. |
| 38 | PKM | Pecheneg | 0 | 0.233 | 10.0 | anchor | Excellent expected LMG family/role match. |
| 39 | S&O Shorty | SSG-P1 | 0 | 0.859 | 53.8 | anchor | Plausible compact precision-rifle neighborhood. |
| 40 | AR57 16" | AR57 11" | 2 | 0.483 | 43.5 | policy-anchor | Explicit AR57 family priority bridges the adjacent AR/SMG type boundary because calibre, handedness and all required fire modes are preserved. |

## Additional calibre-policy probes

| Target | Selected candidate | Tier | Distance | Percentile | Status | Review note |
|---|---|---:|---:|---:|---|---|
| Thompson M1928 | Thompson M1A1 | 0 | 1.214 | 79.4 | policy-anchor | The .45-family candidate is only ~2.2% farther than the raw mechanical best, so the bounded same-calibre preference resolves the near-tie in the tactically sensible direction. |
| Hartford 6 | Desert Eagle .357 | 0 | 0.484 | 83.1 | policy-anchor | Same .357 chambering wins a very close mechanical tie without changing semantic tier. |
| AUG HBAR | RPK-74 | 0 | 0.794 | 40.0 | policy-anchor | No audited AUG replacement-family tag is asserted, and same-calibre alternatives are not within 5%; the policy does not infer family from a display name or force 5.56 logistics over a clearly closer match. |

## Country-filter probes

These cases test the same model after external origin eligibility is applied.

| Pool | Target | Selected replacement | Tier | Distance | Review |
|---|---|---|---:|---:|---|
| USA only | Glock 17 | SIG P226R | 0 | 1.010 | Semantically valid pistol fallback, but stretched relative to the dense pistol cohort. |
| USA only | AK-74 | M468 | 0 | 1.200 | Same-type/full-auto substitute; useful calibration case. |
| USA only | SVD | SR-25 | 0 | 1.093 | Plausible semiautomatic precision-rifle fallback. |
| USA only | G36C | OICW | 0 | 2.549 | Semantic tier is valid; OICW remains unusual but is no longer inflated by sparse-bonus scaling. |
| Soviet/Russia | G36C | AK-108 | 0 | 1.206 | Plausible full-capability assault-rifle fallback. |
| Soviet/Russia | CAWS | Saiga 12K | 5 | 3.041 | Same shotgun type but fire-mode downgrade; no false cross-role substitute. |
| Soviet/Russia | G11 | AN-94 | 0 | 1.767 | Plausible advanced-AR fallback, still numerically far. |
| German lineage | AK-74 | G36 RAS | 0 | 0.590 | Good same-type automatic-rifle fallback. |
| German lineage | M14 | G3A3 | 0 | 0.874 | Plausible 7.62 battle-rifle fallback. |
| Any of the three lineage pools | Rocket Rifle / A. R. Rifle | none | — | — | Both Rocket-role weapons are filtered out, so ordinary rifles are intentionally rejected. |
| Any of the three lineage pools | Dart Gun / Flamethrower / Hand Mortar / Pepper Spray | none | — | — | Singleton special roles are intentionally unresolved when filtered out. |

The USA, Soviet/Russia and German-lineage stress tests therefore each have six unresolved
special-role targets. This is an improvement over false 100% coverage.

## Calibration conclusions from this pass

1. The semantic-role gate fixes the clearest categorical failures without touching weights.
2. Obvious AK, SVD/SVDS, G36 RAS/K, PKM/Pecheneg, VSS/VSk-94, suppressed-SMG and short-shotgun anchors behave sensibly.
3. Sparse OCTH bonus normalization restores MG36 pairing and prevents integrated optics from becoming artificial multi-standard-deviation outliers.
4. Cross-type family policy is now explicit rather than heuristic: only asserted benchmark families can receive priority, and only with same calibre/handedness plus strict fire-mode preservation. AR57 is the positive case; G36C is the deliberate non-promotion case.
5. Calibre is a bounded logistics near-tie, not a default hard constraint or a distance coordinate. It may accept at most 5% more mechanical distance inside the same family-priority + semantic-tier group; `--same-calibre` remains the hard mode.
6. Automatic shotguns remain sparse/far even after correcting their autofire AP arithmetic; their category is mechanically correct, so any further adjustment should be evidence-based.
7. Distance percentile is diagnostic rather than a pass/fail rule. Special-role cohorts with fewer than five tier-0 references report `unknown`.

No nominal weight changes are made by this policy pass. The numerical calibration remains the 10-point minimum replacement-distance scale for sparse OCTH to-hit/aim bonus axes.
