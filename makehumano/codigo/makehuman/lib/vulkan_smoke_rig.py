"""Exercitar rig/pose oficiais nos plugins e exportadores originais."""
import importlib
from pathlib import Path
import numpy as np


def validar_rig_pose(app, directory):
    import mh
    from getpath import getSysDataPath
    from image import Image

    directory = Path(directory)
    human = app.selectedHuman
    rig_module = app.modules.get("3_libraries_skeleton")
    pose_module = app.modules.get("3_libraries_pose")
    if not rig_module or not pose_module:
        raise RuntimeError("Plugins originais de rig e pose não foram carregados")
    rig_library = rig_module.maintask
    pose_library = pose_module.taskview
    base = human.getBaseSkeleton()
    if base is None or base.getBoneCount() < 1:
        raise RuntimeError("Esqueleto de referência original ausente")
    original_rig = rig_library.selectedRig
    original_pose = pose_library.currentPose
    original_active = human.getActiveAnimation()
    original_time = human.getTime()
    original_posed = human._posed
    original_animations = [human.getAnimation(name) for name in human.getAnimations()]
    previous_undo, previous_redo = list(app.undoStack), list(app.redoStack)
    rig_path = getSysDataPath("rigs/default.mhskel")
    pose_path = getSysDataPath("poses/tpose.bvh")
    try:
        action = rig_module.skeletonlibrary.SkeletonAction("Smoke rig", rig_library, original_rig, rig_path)
        app.do(action)
        bones = human.getSkeleton().getBoneCount()
        if bones != base.getBoneCount():
            raise RuntimeError("Rig oficial não preservou os ossos de referência")
        app.undo()
        if original_rig is None and human.getSkeleton() is not None:
            raise RuntimeError("Undo do rig não limpou o esqueleto selecionado")
        app.redo()
        weights = human.getVertexWeights(human.getSkeleton())
        totals = np.zeros(len(human.meshData.coord), np.float64)
        for indices, values in weights.data.values():
            if not np.isfinite(values).all() or np.any(values < 0):
                raise RuntimeError("Rig contém pesos inválidos")
            np.add.at(totals, indices, values)
        if not np.any(totals > 0):
            raise RuntimeError("Rig não possui pesos para deformar o personagem")
        np.testing.assert_allclose(totals[totals > 0], 1., atol=1e-4)
        rest = human.meshData.coord.copy()
        rest_image = mh.renderToBuffer(160, 120).data.copy()
        pose_action = pose_module.PoseAction("Smoke pose", pose_library, original_pose, pose_path)
        app.do(pose_action)
        posed = human.meshData.coord.copy()
        if not human.isPosed() or np.allclose(posed, rest):
            raise RuntimeError("Pose oficial não deformou a geometria original")
        posed_image = mh.renderToBuffer(160, 120).data.copy()
        if np.array_equal(rest_image, posed_image):
            raise RuntimeError("Vulkan não exibiu a deformação da pose")
        app.undo()
        np.testing.assert_allclose(human.meshData.coord, rest, atol=1e-4)
        app.redo()
        np.testing.assert_allclose(human.meshData.coord, posed, atol=1e-4)
        # Track temporário de dois quadros, composto apenas do repouso e da
        # pose oficial. Exercita reprodução/skinning sem criar assets novos.
        from animation import AnimationTrack
        official_animation = human.getActiveAnimation()
        pose_data = official_animation.getAtFramePos(0, noBake=True).copy()
        identity = np.tile(np.eye(4, dtype=np.float32)[:3], (len(pose_data), 1, 1))
        playback = AnimationTrack("makehumano-smoke-playback", np.concatenate((identity, pose_data)), 2, 24.)
        playback.setLooping(False)
        human.addAnimation(playback)
        human.setActiveAnimation(playback.name)
        human.setToFrame(0)
        np.testing.assert_allclose(human.meshData.coord, rest, atol=1e-4)
        human.setToFrame(1)
        np.testing.assert_allclose(human.meshData.coord, posed, atol=1e-4)
        human.setToTime(5.)
        np.testing.assert_allclose(human.meshData.coord, posed, atol=1e-4)
        # O exportador BVH original deve ignorar o cache de skinning gerado
        # pela viewport e preservar as poses locais dos dois quadros.
        import bvh
        from types import SimpleNamespace
        bvh_exporter = app.modules["9_export_bvh"].ExporterBVH()
        bvh_exporter.feetOnGround = SimpleNamespace(selected=False)
        bvh_exporter.taskview = SimpleNamespace(getScale=lambda: (1., "decimeter"))
        bvh_path = directory / "personagem-animado.bvh"
        bvh_exporter.export(human, lambda ext: str(bvh_path))
        exported_bvh = bvh.load(str(bvh_path), convertFromZUp=False)
        reloaded_track = exported_bvh.createAnimationTrack(human.getSkeleton().getJointNames())
        if reloaded_track.nFrames != 2 or not np.isclose(reloaded_track.frameRate, 24., rtol=1e-5):
            raise RuntimeError("BVH não preservou quadros e taxa da animação")
        for frame in range(2):
            np.testing.assert_allclose(reloaded_track.getAtFramePos(frame, noBake=True),
                                       playback.getAtFramePos(frame, noBake=True), atol=1e-4)
        bvh_validation = {"frames": 2, "bones": bones, "local_pose_roundtrip": True}
        human.setActiveAnimation(official_animation.name)
        human.setToFrame(0)
        model = directory / "personagem-com-rig.mhm"
        human.save(str(model))
        text = model.read_text(encoding="utf-8")
        if "skeleton default.mhskel" not in text or "pose tpose.bvh" not in text:
            raise RuntimeError("MHM não preservou referências ao rig e à pose oficiais")
        pose_library.loadPose(None)
        rig_library.chooseSkeleton(None)
        human.load(str(model), strict=True)
        if human.getSkeleton() is None or not human.isPosed():
            raise RuntimeError("MHM não restaurou rig e pose")
        np.testing.assert_allclose(human.meshData.coord, posed, atol=1e-4)

        # Exporta o rig em repouso: não afirma suporte a animação FBX.
        pose_library.loadPose(None)
        np.testing.assert_allclose(human.meshData.coord, rest, atol=1e-4)
        fbx_config = app.modules["9_export_fbx"].FbxConfig()
        fbx_config.setHuman(human)
        fbx_path = directory / "personagem-com-rig.fbx"
        importlib.import_module("9_export_fbx.mh2fbx").exportFbx(str(fbx_path), fbx_config)
        from portable_rig_validation import validar_fbx_rig, validar_collada_rig
        fbx_validation = validar_fbx_rig(fbx_path, bones)
        dae_config = app.modules["9_export_collada"].DaeConfig()
        dae_config.setHuman(human)
        dae_path = directory / "personagem-com-rig.dae"
        importlib.import_module("9_export_collada.mh2collada").exportCollada(str(dae_path), dae_config)
        dae_validation = validar_collada_rig(dae_path, bones)
        Image(data=rest_image).save(str(directory / "rig-rest.png"))
        Image(data=posed_image).save(str(directory / "rig-tpose.png"))
        return {"bones": bones, "weighted_vertices": int(np.count_nonzero(totals)),
                "pose_deforms_mesh": True, "rig_pose_undo_redo": True,
                "animation_playback": True, "non_looping_holds_last": True,
                "mhm_rig_pose_roundtrip": True, "skinned_exports": ["fbx-binary", "collada"],
                "bvh_validation": bvh_validation,
                "fbx_validation": fbx_validation, "collada_validation": dae_validation}
    finally:
        pose_library.loadPose(None)
        rig_library.chooseSkeleton(original_rig)
        human.removeAnimations(update=False)
        for anim in original_animations:
            human.addAnimation(anim)
        if original_pose:
            pose_library.loadPose(original_pose)
        human.setActiveAnimation(original_active.name if original_active else None)
        human.setToTime(original_time, update=False)
        human.setPosed(original_posed)
        app.undoStack[:] = previous_undo
        app.redoStack[:] = previous_redo
        app.syncUndoRedo()
