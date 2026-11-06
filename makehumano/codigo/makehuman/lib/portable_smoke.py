"""Verificações opt-in da aplicação original, em perfil temporário da CI."""
import importlib
import json
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
    try:
        modifier.setValue(0.3 if abs(previous_value - 0.3) > 0.01 else 0.7)
        human.applyAllTargets()
        changed_coords = human.meshData.coord.copy()
        if np.allclose(changed_coords, previous_coords):
            raise RuntimeError("O modificador de idade não alterou a malha original")
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
        report.write_text(json.dumps({
            "modifier": modifier.fullName,
            "mhm_roundtrip": True,
            "obj_export": True,
            "plugins": sorted(name for name, module in app.modules.items() if module),
        }, indent=2), encoding="utf-8")
    finally:
        modifier.setValue(previous_value)
        human.applyAllTargets()
