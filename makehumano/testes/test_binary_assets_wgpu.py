"""Dados binários originais e Unicode em NumPy moderno, sem fromstring/tostring."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / "codigo/makehuman"
for directory in (ROOT, ROOT / "lib", ROOT / "core", ROOT / "shared"):
    sys.path.insert(0, str(directory))

import files3d
import proxy
from makehuman import LicenseInfo


class BinaryAssets(unittest.TestCase):
    def test_mesh_group_names_roundtrip_utf8(self):
        names = ["torso", "coração", "cabeça", "日本語"]
        packed, offsets = files3d.packStringList(names)
        self.assertEqual(files3d.unpackStringList(packed, offsets), names)

    def test_proxy_tags_roundtrip_utf8(self):
        names = ["cabelo", "órgãos", "日本語"]
        packed, offsets = proxy._packStringList(names)
        self.assertEqual(proxy._unpackStringList(packed, offsets), names)

    def test_asset_license_roundtrip_utf8(self):
        original = LicenseInfo()
        original.author = "José — 日本語"
        restored = LicenseInfo()
        restored.fromNumpyString(original.toNumpyString())
        self.assertEqual(restored.asDict(), original.asDict())

    def test_empty_group_list_is_valid(self):
        packed, offsets = files3d.packStringList([])
        self.assertEqual(files3d.unpackStringList(packed, offsets), [])
