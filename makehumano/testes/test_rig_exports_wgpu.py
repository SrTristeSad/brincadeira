"""Validadores independentes rejeitam exportações de skinning inválidas."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo/makehuman/lib"))
from portable_rig_validation import _array, validar_fbx_rig, validar_collada_rig


class RigExportValidation(unittest.TestCase):
    def test_uncompressed_fbx_indices(self):
        payload = struct.pack("<iii", 0, 2, 4)
        np.testing.assert_array_equal(_array(b"i"+struct.pack("<III", 3, 0, len(payload))+payload), [0, 2, 4])

    def test_compressed_fbx_weights(self):
        payload = zlib.compress(struct.pack("<dd", .25, .75))
        np.testing.assert_array_equal(_array(b"d"+struct.pack("<III", 2, 1, len(payload))+payload), [.25, .75])

    def test_fbx_array_rejects_wrong_lengths_encoding_and_element_count(self):
        for data in (b"", b"i"+struct.pack("<III", 1, 2, 4)+b"1234",
                     b"i"+struct.pack("<III", 1, 0, 3)+b"1234",
                     b"i"+struct.pack("<III", 2, 0, 4)+b"1234"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                _array(data)

    def test_fbx_rejects_missing_skeleton_and_truncated_records(self):
        header = b"Kaydara FBX Binary  \x00\x1a\x00"+struct.pack("<I", 7400)
        for data in (b"bad header", header+b"\x00"*13,
                     header+struct.pack("<IIIB", 9999, 0, 0, 1)+b"X"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/"invalid.fbx"
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    validar_fbx_rig(path, 1)

    def collada(self, weights=".25 .75", pairs="0 0 0 1", count="1", vcount="2"):
        return f'''<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema">
          <library_visual_scenes><visual_scene><node type="JOINT" id="root"/></visual_scene></library_visual_scenes>
          <library_controllers><controller><skin source="#mesh">
          <source id="joints"><IDREF_array>root</IDREF_array></source>
          <source id="weights"><float_array>{weights}</float_array></source>
          <vertex_weights count="{count}"><input semantic="JOINT" source="#joints" offset="0"/>
          <input semantic="WEIGHT" source="#weights" offset="1"/><vcount>{vcount}</vcount><v>{pairs}</v>
          </vertex_weights></skin></controller></library_controllers></COLLADA>'''

    def validate(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"test.dae"
            path.write_text(text, encoding="utf-8")
            return validar_collada_rig(path, 1)

    def test_collada_normalized_weights(self):
        self.assertEqual(self.validate(self.collada()), {"bones": 1, "skins": 1, "vertices": 1})

    def test_collada_rejects_invalid_joint_and_weight_indices(self):
        for pairs in ("1 0 0 1", "0 0 0 7", "-1 0 0 1"):
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                self.validate(self.collada(pairs=pairs))

    def test_collada_rejects_non_normalized_or_non_finite_weights(self):
        for weights in (".2 .3", "nan .5", "-.5 1.5"):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                self.validate(self.collada(weights=weights))

    def test_collada_rejects_vertex_count_and_missing_weights(self):
        for kwargs in ({"count": "2"}, {"vcount": "0", "pairs": ""}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.validate(self.collada(**kwargs))
