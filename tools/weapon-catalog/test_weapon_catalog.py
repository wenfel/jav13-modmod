import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import weapon_catalog as wc

ITEMS = """<?xml version="1.0"?><ITEMLIST>
<ITEM><uiIndex>1</uiIndex><szItemName>AK-74M</szItemName><szLongItemName>AK-74M</szLongItemName><usItemClass>2</usItemClass><ubClassIndex>1</ubClassIndex><ItemSize>22</ItemSize><TwoHanded>1</TwoHanded></ITEM>
<ITEM><uiIndex>2</uiIndex><szItemName>AK-74M folded</szItemName><szLongItemName>AK-74M - folded</szLongItemName><usItemClass>2</usItemClass><ubClassIndex>2</ubClassIndex><ItemSize>18</ItemSize><TwoHanded>1</TwoHanded></ITEM>
<ITEM><uiIndex>3</uiIndex><szItemName>M16A2</szItemName><szLongItemName>Colt M16A2</szLongItemName><usItemClass>2</usItemClass><ubClassIndex>3</ubClassIndex><ItemSize>25</ItemSize><TwoHanded>1</TwoHanded></ITEM>
</ITEMLIST>"""

WEAPONS = """<?xml version="1.0"?><WEAPONLIST>
<WEAPON><uiIndex>0</uiIndex><szWeaponName>Nothing</szWeaponName></WEAPON>
<WEAPON><uiIndex>1</uiIndex><szWeaponName>AK-74M</szWeaponName><ubWeaponClass>3</ubWeaponClass><ubWeaponType>6</ubWeaponType><ubCalibre>7</ubCalibre><ubMagSize>30</ubMagSize></WEAPON>
<WEAPON><uiIndex>2</uiIndex><szWeaponName>AK-74M - folded</szWeaponName><ubWeaponClass>3</ubWeaponClass><ubWeaponType>6</ubWeaponType><ubCalibre>7</ubCalibre><ubMagSize>30</ubMagSize></WEAPON>
<WEAPON><uiIndex>3</uiIndex><szWeaponName>M16A2</szWeaponName><ubWeaponClass>3</ubWeaponClass><ubWeaponType>6</ubWeaponType><ubCalibre>8</ubCalibre><ubMagSize>30</ubMagSize></WEAPON>
</WEAPONLIST>"""

LOBOT = """<?xml version="1.0"?><Filters>
<Filter name="HasM16InHand"><AND><HANDPOS op="in">3, 99</HANDPOS></AND></Filter>
<Filter name="HasARInHand"><WEAPON_CLASS>RIFLECLASS</WEAPON_CLASS></Filter>
</Filters>"""

ATTACHMENTS = """<?xml version="1.0"?><ATTACHMENTLIST>
<ATTACHMENT><attachmentIndex>37</attachmentIndex><itemIndex>3</itemIndex><APCost>20</APCost></ATTACHMENT>
<ATTACHMENT><attachmentIndex>38</attachmentIndex><itemIndex>3</itemIndex><APCost>10</APCost><NASOnly>1</NASOnly></ATTACHMENT>
<ATTACHMENT><attachmentIndex>37</attachmentIndex><itemIndex>1</itemIndex><APCost>20</APCost></ATTACHMENT>
</ATTACHMENTLIST>"""


class WeaponCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "Items.xml").write_text(ITEMS, encoding="utf-8")
        (self.root / "Weapons.xml").write_text(WEAPONS, encoding="utf-8")
        (self.root / "Filters.xml").write_text(LOBOT, encoding="utf-8")
        (self.root / "Attachments.xml").write_text(ATTACHMENTS, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_family_normalization_is_conservative(self):
        self.assertEqual(wc.family_key("AK-74M - folded"), wc.family_key("AK-74M"))
        self.assertEqual(wc.family_key("AK-74M III/)-|"), wc.family_key("AK-74M"))
        self.assertNotEqual(wc.family_key("M16A1"), wc.family_key("M16A2"))
        self.assertNotEqual(wc.family_key('HK 416 10"'), wc.family_key('HK 416 16"'))
        self.assertNotEqual(wc.family_key("Model III"), wc.family_key("Model"))
        self.assertNotEqual(wc.family_key("Browning Hi-Power Mk III"), wc.family_key("Browning Hi-Power Mk"))

    def test_index_and_query(self):
        data = wc.build_index(self.root / "Items.xml", self.root / "Weapons.xml", "test")
        self.assertEqual(data["stats"]["weapon_records"], 3)
        self.assertEqual(len({r["family_keys"][0] for r in data["weapons"]}), 2)
        rows = wc.query_rows(data, [], "m16", None, False)
        self.assertEqual([r["id"] for r in rows], [3])

    def test_compare_collapses_folded_variant(self):
        base = wc.build_index(self.root / "Items.xml", self.root / "Weapons.xml", "base")
        other = json.loads(json.dumps(base))
        other["source"] = "other"
        other["weapons"].append({
            "id": 4, "canonical_name": "STEN Mk.II", "family_name": "STEN Mk.II",
            "identity_keys": [wc.identity_key("STEN Mk.II")], "family_keys": [wc.family_key("STEN Mk.II")],
            "aliases": ["STEN Mk.II"], "item_class": 2, "class_index": 4,
            "weapon_class": 2, "weapon_type": 3, "calibre": 2, "mag_size": 32,
            "item_size": 18, "two_handed": 1,
        })
        result = wc.compare_indexes(base, [("other", other)])
        self.assertEqual(result["comparisons"]["other"]["missing_unique_families"], 1)
        self.assertEqual(result["comparisons"]["other"]["missing"][0]["canonical_name"], "STEN Mk.II")

    def test_compare_does_not_merge_shared_short_alias(self):
        base = wc.build_index(self.root / "Items.xml", self.root / "Weapons.xml", "base")
        other = json.loads(json.dumps(base))
        base["weapons"] = [{
            "id": 10, "canonical_name": "HK 416 10 inch", "family_name": "HK 416 10 inch",
            "canonical_family_key": wc.family_key("HK 416 10 inch"),
            "identity_keys": [wc.identity_key("HK 416 10 inch"), wc.identity_key("HK 416")],
            "family_keys": [wc.family_key("HK 416 10 inch"), wc.family_key("HK 416")],
            "aliases": ["HK 416 10 inch", "HK 416"], "calibre": 5,
        }]
        other["weapons"] = [{
            "id": 11, "canonical_name": "HK 416 16 inch", "family_name": "HK 416 16 inch",
            "canonical_family_key": wc.family_key("HK 416 16 inch"),
            "identity_keys": [wc.identity_key("HK 416 16 inch"), wc.identity_key("HK 416")],
            "family_keys": [wc.family_key("HK 416 16 inch"), wc.family_key("HK 416")],
            "aliases": ["HK 416 16 inch", "HK 416"], "calibre": 5,
        }]
        result = wc.compare_indexes(base, [("other", other)])
        self.assertEqual(result["comparisons"]["other"]["overlapping_records"], 0)
        self.assertEqual(result["comparisons"]["other"]["missing_unique_signatures"], 1)

    def test_compare_keeps_calibre_variants_distinct(self):
        base = {"source": "base", "weapons": [{
            "id": 20, "canonical_name": "Example Carbine", "canonical_family_key": wc.family_key("Example Carbine"),
            "calibre": 1,
        }]}
        other = {"source": "other", "weapons": [{
            "id": 21, "canonical_name": "Example Carbine", "canonical_family_key": wc.family_key("Example Carbine"),
            "calibre": 2,
        }]}
        result = wc.compare_indexes(base, [("other", other)])
        self.assertEqual(result["comparisons"]["other"]["overlapping_records"], 0)
        self.assertEqual(result["comparisons"]["other"]["missing_unique_signatures"], 1)

    def test_generic_descriptive_alias_is_not_equivalence(self):
        base = {"source": "base", "weapons": [{
            "id": 30, "canonical_name": "Model Alpha", "canonical_family_key": wc.family_key("Model Alpha"),
            "family_keys": [wc.family_key("Model Alpha"), wc.family_key("Assault Rifle")],
            "calibre": 3,
        }]}
        other = {"source": "other", "weapons": [{
            "id": 31, "canonical_name": "Model Beta", "canonical_family_key": wc.family_key("Model Beta"),
            "family_keys": [wc.family_key("Model Beta"), wc.family_key("Assault Rifle")],
            "calibre": 3,
        }]}
        result = wc.compare_indexes(base, [("other", other)])
        self.assertEqual(result["comparisons"]["other"]["overlapping_records"], 0)

    def test_stdout_limit_is_clamped(self):
        self.assertEqual(wc.stdout_limit(100000), wc.HARD_STDOUT_LIMIT)
        self.assertEqual(wc.stdout_limit("100000"), wc.HARD_STDOUT_LIMIT)
        self.assertEqual(wc.stdout_limit(-1), 0)
        args = wc.parser().parse_args([
            "attachments", "--attachments", "x.xml", "--limit", "100000"
        ])
        self.assertEqual(args.limit, wc.HARD_STDOUT_LIMIT)

    def test_validate_and_index_fail_on_invalid_ids(self):
        bad_items = ITEMS.replace(
            "</ITEMLIST>",
            "<ITEM><uiIndex>not-an-id</uiIndex><szItemName>Broken</szItemName></ITEM></ITEMLIST>",
        )
        bad_weapons = WEAPONS.replace(
            "</WEAPONLIST>",
            "<WEAPON><uiIndex>not-an-id</uiIndex><szWeaponName>Broken</szWeaponName></WEAPON></WEAPONLIST>",
        )
        cases = [
            ("bad-items", bad_items, WEAPONS),
            ("bad-weapons", ITEMS, bad_weapons),
        ]
        for label, items_xml, weapons_xml in cases:
            with self.subTest(label=label):
                items_path = self.root / f"{label}-Items.xml"
                weapons_path = self.root / f"{label}-Weapons.xml"
                output_path = self.root / f"{label}-index.json"
                items_path.write_text(items_xml, encoding="utf-8")
                weapons_path.write_text(weapons_xml, encoding="utf-8")
                validate_args = type("Args", (), {
                    "items": str(items_path), "weapons": str(weapons_path),
                    "source": label, "output": None,
                })()
                index_args = type("Args", (), {
                    "items": str(items_path), "weapons": str(weapons_path),
                    "source": label, "output": str(output_path),
                })()
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(wc.cmd_validate(validate_args), 2)
                    self.assertEqual(wc.cmd_index(index_args), 2)

    def test_validate_and_index_fail_on_missing_item_record(self):
        orphan_weapons = WEAPONS.replace(
            "</WEAPONLIST>",
            "<WEAPON><uiIndex>99</uiIndex><szWeaponName>Orphan Carbine</szWeaponName>"
            "<ubWeaponClass>3</ubWeaponClass><ubWeaponType>6</ubWeaponType>"
            "<ubCalibre>8</ubCalibre><ubMagSize>30</ubMagSize></WEAPON></WEAPONLIST>",
        )
        weapons_path = self.root / "Orphan-Weapons.xml"
        output_path = self.root / "orphan-index.json"
        weapons_path.write_text(orphan_weapons, encoding="utf-8")
        validate_args = type("Args", (), {
            "items": str(self.root / "Items.xml"), "weapons": str(weapons_path),
            "source": "orphan", "output": None,
        })()
        index_args = type("Args", (), {
            "items": str(self.root / "Items.xml"), "weapons": str(weapons_path),
            "source": "orphan", "output": str(output_path),
        })()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(wc.cmd_validate(validate_args), 2)
            self.assertEqual(wc.cmd_index(index_args), 2)

    def test_validate_and_lobot_are_bounded(self):
        validate_args = type("Args", (), {
            "items": str(self.root / "Items.xml"), "weapons": str(self.root / "Weapons.xml"),
            "source": "test", "output": None,
        })()
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(wc.cmd_validate(validate_args), 0)
        self.assertLessEqual(len(buf.getvalue().splitlines()), 5)

        lobot_args = type("Args", (), {
            "filters": str(self.root / "Filters.xml"), "id": [3], "donor": [99],
            "include_generic": True, "limit": 100000, "output": None,
        })()
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(wc.cmd_lobot(lobot_args), 0)
        lines = buf.getvalue().splitlines()
        self.assertLessEqual(len(lines), wc.HARD_STDOUT_LIMIT + 5)
        self.assertTrue(any("generic_filters=1" in line for line in lines))

    def test_lobot_and_attachments(self):
        lobot = wc.parse_lobot_filters(self.root / "Filters.xml")
        self.assertEqual(lobot["exact_item_filters"]["3"], ["HasM16InHand"])
        self.assertIn("HasARInHand", lobot["generic_filters"])
        rows = wc.parse_attachments(self.root / "Attachments.xml")
        self.assertEqual(sum(1 for row in rows if row["item_id"] == 3), 2)


if __name__ == "__main__":
    unittest.main()
