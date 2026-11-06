"""Validação opt-in dos controles originais de luz usando pixels Vulkan."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np


def validar_luzes(cena, cameras, mundo, app, marker):
    from image import Image
    from scene import Light
    candidates = [obj for obj in mundo if obj.visibility and obj.solid and len(obj.primitives) > 100]
    if not candidates:
        raise RuntimeError("Iluminação: personagem original ausente")
    body = max(candidates, key=lambda obj: len(obj.primitives))

    class Material:
        shader = None
        shaderParameters = {}
        shaderConfig = {"normal": False, "diffuse": False, "spec": False, "transparency": False}
        normalMapTexture = None
        transparent = False
        opacity = 1.
        shininess = 0.
        diffuseColor = SimpleNamespace(values=(1., 1., 1.))
        specularColor = SimpleNamespace(values=(0., 0., 0.))
        emissiveColor = SimpleNamespace(values=(0., 0., 0.))

    class Object:
        material = Material()
        isTextured = False
        texture = None
        shadeless = False
        depthless = False
        nTransparentPrimitives = 0
        cull = 1
        color = np.full_like(body.color, 255)

        def __getattr__(self, name):
            return getattr(body, name)

    camera = cameras[body.cameraMode]
    _, view = camera.getMatrices(0)
    position = np.linalg.inv(np.asarray(view))[:3, 3]
    center = (np.asarray(camera.getModelMatrix(body)) @ np.append(np.mean(body.verts, axis=0), 1.))[:3]
    light = SimpleNamespace(position=position, focus=center, fov=180., attenuation=0.,
                            color=(1., 1., 1.), specular=(0., 0., 0.))
    scene = SimpleNamespace(environment=SimpleNamespace(ambience=(0., 0., 0.)), lights=[light])
    previous = cena._cena_luzes

    def render():
        return cena.capturar_framebuffer([Object()], cameras, 160, 120,
                                         incluir_alfa=True, cor_fundo=(0, 0, 0, 0))

    def energy(image):
        return int(image[:, :, :3].astype(np.uint64).sum())

    try:
        cena.atualizar_iluminacao(scene)
        point = render()
        light.attenuation = 1. / float(np.dot(position - center, position - center))
        attenuated = render()
        light.attenuation = 0.
        light.fov = 5.
        spot = render()
        light.focus = 2. * position - center
        away = render()
        if not 0 < energy(attenuated) < energy(point):
            raise RuntimeError("Atenuação não reduziu a iluminação do personagem")
        if not 0 < energy(spot) < energy(point):
            raise RuntimeError("Cone de luz não limitou a região iluminada")
        if energy(away) or not np.any(away[:, :, 3]):
            raise RuntimeError("Foco invertido não apagou apenas a iluminação")
        if any(not np.array_equal(point[:, :, 3], image[:, :, 3]) for image in (attenuated, spot, away)):
            raise RuntimeError("Controles de luz alteraram a cobertura da malha")
        light.fov = 180.
        if not np.array_equal(point, render()):
            raise RuntimeError("Luz pontual padrão deixou de ser compatível")

        light.focus = center
        light.areaLights = 8
        light.areaLightSize = 0.
        if not np.array_equal(point, render()):
            raise RuntimeError("Área de tamanho zero alterou a luz pontual")
        light.areaLightSize = float(np.linalg.norm(position-center)) * 1.2
        area = render()
        if np.array_equal(point, area) or not energy(area):
            raise RuntimeError("Tamanho da área não alterou a iluminação")
        if not np.array_equal(point[:, :, 3], area[:, :, 3]):
            raise RuntimeError("Luz de área alterou a cobertura do personagem")
        if not np.array_equal(area, render()):
            raise RuntimeError("Amostragem de área mudou entre frames idênticos")
        from vulkan_area_lights import amostrar_luzes
        expanded, _ = amostrar_luzes(scene)
        reference_scene = SimpleNamespace(environment=scene.environment, lights=[
            SimpleNamespace(position=sample.position, focus=center, fov=180., attenuation=0.,
                            color=tuple(c / len(expanded.lights) for c in light.color),
                            specular=(0., 0., 0.)) for sample in expanded.lights])
        cena.atualizar_iluminacao(reference_scene)
        reference_area = render()
        if np.max(np.abs(reference_area.astype(int)-area.astype(int))) > 1:
            raise RuntimeError("Área não equivale à soma de luzes com energia normalizada")
        cena.atualizar_iluminacao(scene)
        light.areaLights = 2
        two_samples = render()
        if np.array_equal(two_samples, area):
            raise RuntimeError("Samples não alterou a integração da área")
        # Presets que originalmente usam a primeira luz devem integrar só
        # as amostras desse emissor, sem passar a usar outros emissores.
        from getpath import getSysDataPath
        Object.material.shader = getSysDataPath("shaders/glsl/phong")
        light.areaLights = 1
        phong_point = render()
        light.areaLights = 8
        phong_area = render()
        if np.array_equal(phong_point, phong_area) or not energy(phong_area):
            raise RuntimeError("Preset Phong ignorou a área da primeira luz")
        light.areaLightSize = 0.
        if not np.array_equal(phong_point, render()):
            raise RuntimeError("Área zero mudou o preset Phong pontual")
        Object.material.shader = None

        # Exercita os eventos dos widgets originais; nenhum valor da cena
        # usada pelo usuário é modificado para esta regressão de Softness.
        item = app.modules["7_scene_editor"].LightSceneItem(SimpleNamespace(scene=app.scene), Light(), 0)
        original_attenuation = item.light.attenuation
        item.size.callEvent("onChange", [7.])
        if item.light.areaLightSize != 7. or item.light.attenuation != original_attenuation:
            raise RuntimeError("Softness alterou a atenuação em vez do tamanho da luz")
        item.att.callEvent("onChange", [.25])
        item.fov.callEvent("onChange", [30.])
        if item.light.attenuation != .25 or item.light.fov != 30.:
            raise RuntimeError("Eventos do editor de luz não atualizaram os parâmetros")
        item.soft.callEvent("onChange", True)
        if item.light.areaLights != 2:
            raise RuntimeError("Soft light não ativou as amostras da área")
        item.samples.callEvent("onChange", [8])
        if item.light.areaLights != 8:
            raise RuntimeError("Samples não atualizou a luz original")
        item.soft.callEvent("onChange", False)
        if item.light.areaLights != 1:
            raise RuntimeError("Soft light não restaurou a luz pontual")
        app._smoke_light_item = item
        path = Path(marker)
        for name, pixels in (("light-point", point), ("light-attenuated", attenuated),
                             ("light-spot", spot), ("light-spot-away", away),
                             ("light-area", area), ("light-area-two", two_samples),
                             ("light-area-phong", phong_area)):
            Image(data=pixels).save(str(path.parent / (name + ".png")))
        path.write_text(json.dumps({"attenuation": True, "focus": True, "original_widgets": True,
                                   "area": True, "normalized_energy": True, "repeatable": True}), encoding="utf-8")
    finally:
        cena.atualizar_iluminacao(previous)
