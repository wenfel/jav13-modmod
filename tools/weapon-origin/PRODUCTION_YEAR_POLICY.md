# Weapon production-year metadata policy

This document defines the production-year semantics used by the weapon metadata in
`tools/weapon-origin/weapon_origin_metadata.csv` and the corresponding
`ProductionYearStart` / `ProductionYearEnd` values in `Items.xml`.

The purpose is chronological equipment filtering. The values should be useful for
gameplay without claiming false historical precision.

## Coverage

The current pass covers all 347 `IC_GUN` / `IC_LAUNCHER` item rows:

- 327 rows have a nonzero start year.
- 135 rows have a finite nonzero end year.
- 20 intentionally generic, fictional, creature, or non-manufactured rows remain
  `0/0`.

The CSV is the metadata source of truth. `Items.xml` must be generated from the
CSV by a byte-preserving process; unrelated XML content must not be reformatted or
rewritten.

## Field semantics

### `ProductionYearStart`

Use the earliest defensible year in which the represented weapon or variant can
enter the historical equipment pool.

Preference order:

1. documented serial-production start;
2. documented introduction/adoption date when production start is unavailable;
3. documented prototype/build/test-series date for experimental weapons;
4. a clearly identified family/configuration proxy when the JA2 item is a
   gameplay-derived variant rather than a separately manufactured model.

A proxy is a practical dating mechanism, not a claim that an unofficial variant
had an independent production line.

### `ProductionYearEnd`

Use a finite end year only when there is a defensible stop date for the represented
model or variant.

`0` means **open-ended / no defensible finite end**. It does not mean that the
row was not researched.

Where production had gaps or multiple runs, the single start/end pair represents
the useful overall historical availability window; the schema cannot encode
discontinuous production intervals.

## Prototypes and experimental weapons

Real prototypes should be dated to their physical build, test, or program window
when ordinary serial production never occurred. This keeps them chronologically
placeable without describing them as mass-produced weapons.

## Gameplay-derived or ambiguous variants

When a JA2 item is clearly derived from a real weapon but does not correspond to
a distinct production model, a documented family/configuration date may be used.
Such dates should be treated as proxies and reviewed if a better model-specific
source becomes available.

Notable examples in this pass:

- `M82A1` uses 1986 rather than the earlier family-level 1982 date. 1982 describes
  the early M82 family; the represented M82A1 variant is dated from 1986.
- `AKMSU` uses 1988 as an existence proxy for the disputed/nonstandard weapon,
  not as a claim of official Soviet serial production.

## Intentional `0/0` exceptions

These rows do not have a defensible model-specific manufacturing history:

- `5` — .38 Special: generic gameplay revolver
- `48` — Queen Spit: creature attack
- `50` — Talon: fictional/game-specific launcher
- `55` — Rocket Rifle: fictional
- `56` — Automag III: game-specific fictional/custom variant
- `57` — Infant Spit: creature attack
- `58` — Young Male Spit: creature attack
- `59` — Old Male Spit: creature attack
- `60` — Cannon: generic tank cannon
- `61` — Dart Gun: generic weapon
- `63` — Flamethrower: generic weapon
- `65` — A. R. Rifle: fictional auto rocket rifle
- `66` — Hartford 6: game-specific custom variant
- `711` — Sawed-Off: generic sawed-off shotgun
- `893` — M29 SATAN: fictional
- `901` — Commando Mortar: generic weapon
- `1352` — Hand Mortar: generic weapon
- `1581` — Rifle Grenade Device: generic device
- `1627` — Pepper Spray: no specific weapon model
- `1761` — Extinguisher: not a manufactured weapon model

Do not invent dates for these rows merely to eliminate zero values.

## Integrity requirements

When production-year metadata is changed:

1. update the CSV first;
2. regenerate the XML from the CSV by `uiIndex`;
3. change only the existing `ProductionYearStart` and `ProductionYearEnd`
   values for the intended rows;
4. leave `WeaponOriginFlags` and all unrelated XML bytes unchanged;
5. verify exact target coverage and idempotence;
6. compare the generated XML against the authoritative current XML before commit.

For this population pass, 260 of the 347 weapon/launcher rows change. There are
259 start-year changes and 100 end-year changes. No origin flag or unrelated XML
content is changed.
