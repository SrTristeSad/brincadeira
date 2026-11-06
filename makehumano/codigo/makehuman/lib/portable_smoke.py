"""Verificações opt-in da aplicação original, em perfil temporário da CI."""
import importlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


def check_original_tools(app, report_path):
    import numpy as np

    report = Path(report_path)
    human = app.selectedHuman
    required = ("0_modeling_0_modifiers", "3_libraries_material_chooser",
                "9_export_obj", "9_export_fbx", "9_export_collada", "9_export_stl")
    missing = [name for name in required if not app.modules.get(name)]
    if missing:
        raise RuntimeError("Plugins essenciais não carregados: " + ", ".join(missing))

    modifier = human.getModifier("macrodetails/Age")
    previous_value = modifier.getValue()
    previous_coords = human.meshData.coord.copy()
    previous_undo = list(app.undoStack)
    previous_redo = list(app.redoStack)
    try:
        from humanmodifier import ModifierAction
        value = 0.3 if abs(previous_value - 0.3) > 0.01 else 0.7
        action = ModifierAction(modifier, previous_value, value, lambda: None)
        app.do(action)
        if not app.undoStack or app.undoStack[-1] is not action:
            raise RuntimeError("Ação de modelagem não entrou no histórico original")
        changed_coords = human.meshData.coord.copy()
        if np.allclose(changed_coords, previous_coords):
            raise RuntimeError("O modificador de idade não alterou a malha original")
        app.undo()
        np.testing.assert_allclose(human.meshData.coord, previous_coords, atol=1e-5)
        if not app.redoStack or app.redoStack[-1] is not action:
            raise RuntimeError("Undo não preservou a ação para refazer")
        app.redo()
        np.testing.assert_allclose(human.meshData.coord, changed_coords, atol=1e-5)
        model = report.parent / "personagem-portátil.mhm"
        human.save(str(model))
        modifier.setValue(previous_value)
        human.applyAllTargets()
        human.load(str(model), strict=True)
        np.testing.assert_allclose(human.meshData.coord, changed_coords, atol=1e-5)

        # Chamar o mesmo exportador usado pelo plugin original, sem criar
        # formato paralelo nem substituir a interface do exportador.
        plugin = app.modules["9_export_obj"]
        config = plugin.ObjConfig()
        config.setHuman(human)
        output = report.parent / "personagem-portátil.obj"
        importlib.import_module("9_export_obj.mh2obj").exportObj(str(output), config)
        text = output.read_text(encoding="utf-8")
        if not any(line.startswith("v ") for line in text.splitlines()):
            raise RuntimeError("OBJ não contém vértices")
        if not any(line.startswith("f ") for line in text.splitlines()):
            raise RuntimeError("OBJ não contém faces")
        # Exportar os formatos principais, não apenas importar seus módulos.
        fbx_plugin = app.modules["9_export_fbx"]
        fbx_config = fbx_plugin.FbxConfig()
        fbx_config.setHuman(human)
        fbx_path = report.parent / "personagem-portátil.fbx"
        importlib.import_module("9_export_fbx.mh2fbx").exportFbx(str(fbx_path), fbx_config)
        if not fbx_path.read_bytes().startswith(b"Kaydara FBX Binary  \x00\x1a\x00"):
            raise RuntimeError("FBX binário não contém cabeçalho válido")

        dae_plugin = app.modules["9_export_collada"]
        dae_config = dae_plugin.DaeConfig()
        dae_config.setHuman(human)
        dae_path = report.parent / "personagem-portátil.dae"
        importlib.import_module("9_export_collada.mh2collada").exportCollada(str(dae_path), dae_config)
        document = ET.parse(dae_path)
        ns = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
        if not document.findall(".//c:geometry/c:mesh", ns):
            raise RuntimeError("Collada não contém geometria")

        stl_plugin = app.modules["9_export_stl"]
        stl_config = stl_plugin.STLConfig()
        stl_config.setHuman(human)
        stl_path = report.parent / "personagem-portátil.stl"
        importlib.import_module("9_export_stl.mh2stl").exportStlBinary(str(stl_path), stl_config)
        stl = stl_path.read_bytes()
        triangles = struct.unpack_from("<I", stl, 80)[0]
        if not triangles or len(stl) != 84 + 50 * triangles:
            raise RuntimeError("STL binário contém contagem de triângulos inválida")

        # Chama o exportador original: não basta testar renderSkin isolado.
        uv_path = report.parent / "uv-map.png"
        app.modules["9_export_uvmap"].ExporterUV().export(human, lambda ext: str(uv_path))
        from image import Image
        uv_pixels = Image(path=str(uv_path)).data
        if uv_pixels.shape != (2048, 2048, 3):
            raise RuntimeError("Exportador UV não produziu PNG RGB 2048x2048")
        if not np.any(np.all(uv_pixels == 255, axis=2)) or not np.any(np.all(uv_pixels == 0, axis=2)):
            raise RuntimeError("Exportador UV não desenhou arestas brancas sobre fundo preto")

        import mh
        solid_before = human.isSolid()
        try:
            human.setSolid(True)
            solid_image = mh.renderToBuffer(320, 240).data.copy()
            human.setSolid(False)
            wire_image = mh.renderToBuffer(320, 240).data.copy()
            from image import Image
            Image(data=solid_image).save(str(report.parent / "viewport-solid.png"))
            Image(data=wire_image).save(str(report.parent / "viewport-wireframe.png"))
            dark_solid = np.count_nonzero(np.all(solid_image[:, :, :3] < 12, axis=2))
            dark_wire = np.count_nonzero(np.all(wire_image[:, :, :3] < 12, axis=2))
            if np.array_equal(solid_image, wire_image) or dark_wire <= dark_solid:
                raise RuntimeError("Modo wireframe original não desenhou arestas pretas")
        finally:
            human.setSolid(solid_before)

        from vulkan_smoke_rig import validar_rig_pose
        rig_pose = validar_rig_pose(app, report.parent)
        report.write_text(json.dumps({
            "modifier": modifier.fullName,
            "mhm_roundtrip": True,
            "modifier_undo_redo": True,
            "wireframe": True,
            "rig_pose": rig_pose,
            "exports": ["obj", "fbx-binary", "collada", "stl-binary", "uv-png"],
            "plugins": sorted(name for name, module in app.modules.items() if module),
        }, indent=2), encoding="utf-8")
    finally:
        modifier.setValue(previous_value)
        human.applyAllTargets()
        app.undoStack[:] = previous_undo
        app.redoStack[:] = previous_redo
        app.syncUndoRedo()
