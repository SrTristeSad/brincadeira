"""Exercitar rig/pose oficiais nos plugins e exportadores originais."""
import importlib
from pathlib import Path
import xml.etree.ElementTree as ET
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
        fbx = fbx_path.read_bytes()
        if not fbx.startswith(b"Kaydara FBX Binary  \x00\x1a\x00") or any(
                token not in fbx for token in (b"LimbNode", b"Deformer", b"Cluster", b"TransformLink")):
            raise RuntimeError("FBX não contém esqueleto e deformadores de skinning")
        dae_config = app.modules["9_export_collada"].DaeConfig()
        dae_config.setHuman(human)
        dae_path = directory / "personagem-com-rig.dae"
        importlib.import_module("9_export_collada.mh2collada").exportCollada(str(dae_path), dae_config)
        document = ET.parse(dae_path)
        ns = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
        if len(document.findall('.//c:node[@type="JOINT"]', ns)) < bones:
            raise RuntimeError("Collada perdeu ossos do rig")
        skins = document.findall(".//c:controller/c:skin", ns)
        if not skins:
            raise RuntimeError("Collada não contém controladores de skinning")
        for skin in skins:
            vertex_weights = skin.find("c:vertex_weights", ns)
            counts = np.fromstring(vertex_weights.find("c:vcount", ns).text, sep=" ", dtype=int)
            pairs = np.fromstring(vertex_weights.find("c:v", ns).text, sep=" ", dtype=int)
            if len(counts) != int(vertex_weights.attrib["count"]) or len(pairs) != 2*int(counts.sum()):
                raise RuntimeError("Collada contém índices/pesos incompatíveis com os vértices")
            if np.any(counts <= 0) or np.any(pairs < 0):
                raise RuntimeError("Collada contém vértices sem pesos ou índices inválidos")
        Image(data=rest_image).save(str(directory / "rig-rest.png"))
        Image(data=posed_image).save(str(directory / "rig-tpose.png"))
        return {"bones": bones, "weighted_vertices": int(np.count_nonzero(totals)),
                "pose_deforms_mesh": True, "rig_pose_undo_redo": True,
                "mhm_rig_pose_roundtrip": True, "skinned_exports": ["fbx-binary", "collada"]}
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
