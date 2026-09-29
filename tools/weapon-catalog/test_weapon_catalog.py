import json
import tempfile
import unittest
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
        self.assertNotEqual(wc.family_key("M16A1"), wc.family_key("M16A2"))
        self.assertNotEqual(wc.family_key('HK 416 10"'), wc.family_key('HK 416 16"'))

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

    def test_lobot_and_attachments(self):
        lobot = wc.parse_lobot_filters(self.root / "Filters.xml")
        self.assertEqual(lobot["exact_item_filters"]["3"], ["HasM16InHand"])
        self.assertIn("HasARInHand", lobot["generic_filters"])
        rows = wc.parse_attachments(self.root / "Attachments.xml")
        self.assertEqual(sum(1 for row in rows if row["item_id"] == 3), 2)


if __name__ == "__main__":
    unittest.main()
