# JA2 weapon-catalog toolkit

Read-only-by-default helpers for comparing large JA2 weapon catalogues without putting whole XML files or large derived results into LLM context.

## Commands

```bash
python tools/weapon-catalog/weapon_catalog.py index \
  --items path/Items.xml --weapons path/Weapons.xml \
  --source ours --output work/ours.json

python tools/weapon-catalog/weapon_catalog.py compare \
  --base work/ours.json \
  --other brainmod=work/brainmod.json \
  --other sdo=work/sdo.json \
  --output work/compare.json

python tools/weapon-catalog/weapon_catalog.py query \
  --index work/brainmod.json --name "M16" --limit 20

python tools/weapon-catalog/weapon_catalog.py lobot \
  --filters gamedir/Base/TableData/LogicalBodyTypes/Filters.xml \
  --id 632 --donor 762

python tools/weapon-catalog/weapon_catalog.py attachments \
  --attachments gamedir/Data-1.13/TableData/Items/Attachments.xml \
  --id 632 --limit 20
```

`validate` checks XML roots, parsing, duplicate IDs, missing item records and source hashes without creating an index.

## Context-safety contract

- Large XML is parsed locally; it is never printed by the tool.
- `query`, `compare`, and `attachments` print at most 40 rows by default.
- Complete large results are written only when `--output` is supplied.
- Indexes retain source paths and SHA-256 hashes so later sessions can reuse pinned results.
- Family normalization is deliberately conservative. It collapses obvious representation/configuration states such as folded/collapsed/RAS/tactical and known SDO display-state suffixes, but does not merge model numbers, calibres, or barrel lengths.
- Exact source IDs and aliases are preserved for traceability.

## LOBOT

`lobot` reads Logical Body Types `Filters.xml` and reports exact `HANDPOS` filter memberships for candidate and donor item IDs. It also records generic weapon-class/type filters when `--include-generic` is requested. Choosing whether a donor is visually appropriate remains an LLM/human judgment.

## Tests

```bash
python tools/weapon-catalog/test_weapon_catalog.py
```

Tests use tiny synthetic XML fixtures; they do not load the production catalogues.
