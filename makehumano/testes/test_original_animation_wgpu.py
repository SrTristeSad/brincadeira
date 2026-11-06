"""Reprodução e reamostragem do sistema de animação original."""
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "codigo/makehuman"
for directory in (ROOT, ROOT / "lib", ROOT / "core", ROOT / "shared", ROOT / "apps"):
    sys.path.insert(0, str(directory))
from animation import AnimationTrack
import bvh


class OriginalAnimation(unittest.TestCase):
    def track(self, frames=2, bones=2, rate=1):
        data = np.tile(np.eye(4, dtype=np.float32)[:3], (frames*bones, 1, 1))
        data[:, 0, 3] = np.repeat(np.arange(frames)*10., bones)
        return AnimationTrack("test playback", data, frames, rate)

    def test_transform_conversions_accept_float32_and_python_sequences(self):
        import transformations as tm
        rotation = tm.euler_matrix(.2, -.4, .6)
        for source in (rotation.astype(np.float32), rotation.tolist()):
            angles = tm.euler_from_matrix(source)
            np.testing.assert_allclose(tm.euler_matrix(*angles), rotation, atol=1e-6)
            quaternion = tm.quaternion_from_matrix(source)
            np.testing.assert_allclose(tm.quaternion_matrix(quaternion), rotation, atol=1e-6)
        projection = tm.projection_matrix([0, 0, 0], [0, 0, 1], perspective=[0, 0, 5])
        self.assertTrue(np.isfinite(projection).all())
        np.testing.assert_allclose(tm.unit_vector([3, 0, 4]), [.6, 0, .8])
        self.assertAlmostEqual(tm.angle_between_vectors([1, 0, 0], [0, 1, 0]), np.pi / 2)

    def test_bvh_export_uses_local_poses_even_after_skinning_bake(self):
        from types import SimpleNamespace
        import tempfile
        from transformations import rotation_matrix
        bone = SimpleNamespace(name="root", parent=None, index=0,
                               getRestOffset=lambda: np.zeros(3),
                               getRestHeadPos=lambda: np.zeros(3),
                               getRestTailPos=lambda: np.array([0., 1., 0.]),
                               hasChildren=lambda: False)
        skel = SimpleNamespace(getJointNames=lambda: ["root"], getBone=lambda name: bone,
                               containsBone=lambda name: name == "root")
        poses = np.array([np.eye(4)[:3], rotation_matrix(.4, [1., 0., 0.])[:3]], np.float32)
        poses[1, :, 3] = [2., 3., 4.]
        track = AnimationTrack("export test", poses, 2, 24.)
        unbaked = bvh.createFromSkeleton(skel, track)
        # A baked cache contains world-space skinning transforms and must not
        # affect an exporter of local motion, even when that cache is active.
        track._data_baked = np.tile(np.eye(4, dtype=np.float32)[:3], (2, 1, 1))
        baked = bvh.createFromSkeleton(skel, track)
        np.testing.assert_array_equal(unbaked.rootJoint.frames, baked.rootJoint.frames)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "motion.bvh"
            baked.writeToFile(str(path))
            loaded = bvh.load(str(path), convertFromZUp=False)
            restored = loaded.createAnimationTrack(["root"])
            self.assertEqual(restored.nFrames, 2)
            np.testing.assert_allclose(restored.getAtFramePos(1, noBake=True), poses[1:2], atol=1e-5)

    def test_disabling_looping_holds_last_frame(self):
        track = self.track()
        track.setLooping(False)
        self.assertFalse(track.isLooping())
        self.assertEqual(track.getFrameIndexAtTime(5.), (1, 0.))
        np.testing.assert_array_equal(track.getAtTime(5.), track.getAtFramePos(1))
        track.setLooping(True)
        self.assertEqual(track.getFrameIndexAtTime(2.), (0, 0.))

    def test_linear_interpolation_does_not_wrap_when_looping_is_disabled(self):
        track = self.track()
        track.interpolationType = 1
        track.setLooping(False)
        np.testing.assert_array_equal(track.getAtTime(1.5), track.getAtFramePos(1))
        np.testing.assert_allclose(track.getAtTime(.5)[:, 0, 3], 5.)
        track.setLooping(True)
        np.testing.assert_allclose(track.getAtTime(1.5)[:, 0, 3], 5.)

    def test_sparsify_preserves_duration_at_non_integral_ratio(self):
        track = self.track(60, 2, 60)
        track.sparsify(24)
        self.assertEqual((track.nFrames, track.nBones, track.dataLen), (24, 2, 48))
        self.assertEqual(track.getPlaytime(), 1.)
        self.assertIsInstance(track.nFrames, int)
        np.testing.assert_array_equal(track.getAtFramePos(1)[:, 0, 3], 20.)
        np.testing.assert_array_equal(track.getAtFramePos(23)[:, 0, 3], 570.)

    def test_sparsify_uses_raw_poses_and_invalidates_baked_data(self):
        track = self.track(4, 2, 4)
        original = track.getAtFramePos(0, noBake=True).copy()
        track._data_baked = track._data + 100.
        track.sparsify(2)
        self.assertFalse(track.isBaked())
        np.testing.assert_array_equal(track.getAtFramePos(0), original)
        np.testing.assert_array_equal(track.getAtFramePos(1)[:, 0, 3], 20.)

    def test_sparsify_same_rate_keeps_track_unchanged(self):
        track = self.track(4, 2, 4)
        before = track.data.copy()
        track.sparsify(4)
        np.testing.assert_array_equal(track.data, before)

    def test_invalid_resampling_rates_are_reported(self):
        for rate in (0, -1, np.nan, np.inf, 61):
            with self.subTest(rate=rate), self.assertRaises((ValueError, RuntimeError)):
                self.track(60, 2, 60).sparsify(rate)

    def test_official_bvh_poses_contain_finite_rotation_matrices(self):
        for name in ("tpose", "benchmark"):
            with self.subTest(name=name):
                motion = bvh.load(str(ROOT / "data/poses" / (name+".bvh")))
                self.assertIn("upperleg02.L", motion.joints)
                track = motion.createAnimationTrack()
                self.assertEqual(track.nFrames, 1)
                data = track.getAtFramePos(0)
                self.assertTrue(np.isfinite(data).all())
                rotations = data[:, :3, :3]
                expected = np.tile(np.eye(3), (track.nBones, 1, 1))
                np.testing.assert_allclose(rotations @ rotations.transpose(0, 2, 1), expected, atol=1e-5)
