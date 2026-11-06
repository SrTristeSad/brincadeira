"""Comparações GPU opt-in dos mapas do editor de materiais original."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np


def validar_mapas(cena, cameras, mundo, marker):
    from image import Image
    candidates = [obj for obj in mundo if obj.visibility and obj.solid and len(obj.primitives) > 100]
    if not candidates:
        raise RuntimeError("Mapas de material: personagem original ausente")
    body = max(candidates, key=lambda obj: len(obj.primitives))
    white = Image(data=np.full((4, 4, 4), 255, np.uint8))
    black = Image(data=np.tile(np.array([0, 0, 0, 255], np.uint8), (4, 4, 1)))
    grey = Image(data=np.tile(np.array([128, 128, 128, 255], np.uint8), (4, 4, 1)))

    class Material:
        shader = None
        shaderParameters = {}
        shaderConfig = {"normal": False, "diffuse": False, "spec": True, "transparency": True}
        normalMapTexture = None
        specularMapTexture = None
        transparencyMapTexture = None
        specularMapIntensity = 1.0
        transparencyMapIntensity = 1.0
        transparent = False
        opacity = 1.0
        shininess = 0.1
        diffuseColor = SimpleNamespace(values=(0., 0., 0.))
        specularColor = SimpleNamespace(values=(1., 1., 1.))
        emissiveColor = SimpleNamespace(values=(0., 0., 0.))

    class Object:
        isTextured = False
        texture = None
        shadeless = False
        depthless = False
        nTransparentPrimitives = 0
        cull = 0

        def __init__(self, material, planar=False):
            self.material = material
            self.color = np.full_like(body.color, 255)
            if planar:
                # Uma superfície isolada torna o alfa analítico: a malha
                # fechada do corpo acumularia várias faces transparentes.
                center = np.mean(body.verts, axis=0)
                modelview = np.asarray(view) @ np.asarray(camera.getModelMatrix(body))
                size = float(np.ptp(body.verts[:, 1])) * .15
                offsets = np.array([[-size, -size, 0], [size, -size, 0],
                                    [size, size, 0], [-size, size, 0]])
                self.verts = center + np.linalg.solve(modelview[:3, :3], offsets.T).T
                self.norms = np.tile([0., 0., 1.], (4, 1))
                self.UVs = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])
                self.color = np.full((4, 4), 255, np.uint8)
                self.primitives = np.array([[0, 1, 2, 3]], np.uint32)

        def __getattr__(self, name):
            return getattr(body, name)

    previous = cena._cena_luzes
    camera = cameras[body.cameraMode]
    _, view = camera.getMatrices(0)
    light = np.linalg.inv(np.asarray(view))[:3, 3]
    scene = SimpleNamespace(environment=SimpleNamespace(ambience=(0., 0., 0.)),
                            lights=[SimpleNamespace(position=light, color=(0., 0., 0.), specular=(1., 1., 1.))])
    path = Path(marker)

    def render(material, unlit=False, objects=None):
        obj = Object(material, planar=unlit)
        obj.shadeless = unlit
        return cena.capturar_framebuffer(objects or [obj], cameras, 160, 120,
                                         incluir_alfa=True, cor_fundo=(0, 0, 0, 0))

    try:
        cena.atualizar_iluminacao(scene)
        material = Material()
        reference = render(material)
        material.specularMapTexture = white
        spec_white = render(material)
        material.specularMapTexture = black
        spec_black = render(material)
        if not np.array_equal(reference, spec_white):
            raise RuntimeError("Mapa especular branco mudou o material sem mapa")
        if np.any(spec_black[:, :, :3]) or not np.any(spec_white[:, :, :3]):
            raise RuntimeError("Mapa especular preto não suprimiu apenas o brilho")
        material.specularMapIntensity = 0
        if not np.array_equal(reference, render(material)):
            raise RuntimeError("Intensidade especular zero não restaura o material")

        material = Material()
        material.diffuseColor = SimpleNamespace(values=(1., 1., 1.))
        opaque = render(material, True)
        material.transparencyMapTexture = black
        if not np.array_equal(opaque, render(material, True)):
            raise RuntimeError("Mapa de transparência preto alterou a opacidade")
        material.transparencyMapTexture = grey
        half = render(material, True)
        mask = opaque[:, :, 3] > 0
        # Cobertura alfa deve ser aproximadamente 1 - 128/255, sem gamma.
        if not np.any(mask) or not np.all(np.abs(half[mask, 3].astype(int) - 127) <= 1):
            raise RuntimeError("Mapa de transparência cinza não produziu alfa esperado")
        material.transparencyMapTexture = white
        clear = render(material, True)
        if np.any(clear):
            raise RuntimeError("Mapa branco não tornou a malha totalmente transparente")
        material.transparencyMapIntensity = 0
        if not np.array_equal(opaque, render(material, True)):
            raise RuntimeError("Intensidade de transparência zero alterou o material")
        for name, pixels in (("map-specular-white", spec_white), ("map-specular-black", spec_black),
                             ("map-transparency-none", opaque), ("map-transparency-grey", half),
                             ("map-transparency-clear", clear)):
            Image(data=pixels).save(str(path.parent / (name + ".png")))

        scene.lights[0].color = (1., 1., 1.)
        scene.lights[0].specular = (0., 0., 0.)
        material = Material()
        material.diffuseColor = SimpleNamespace(values=(1., 1., 1.))
        material.shaderConfig = {"normal": False, "bump": True, "diffuse": False,
                                 "spec": False, "transparency": False}
        baseline = render(material)
        for flat in (black, white):
            material.bumpMapTexture = flat
            if not np.array_equal(baseline, render(material)):
                raise RuntimeError("Altura constante alterou a iluminação do material")
        # Padrão de teste de altura: nunca altera os assets do personagem.
        values = np.round(127.5 + 127.5 * np.sin(np.arange(64) * np.pi / 8)).astype(np.uint8)
        pixels = np.full((64, 64, 4), 255, np.uint8)
        pixels[:, :, :3] = values[None, :, None]
        material.bumpMapTexture = Image(data=pixels)
        bumped = render(material)
        if np.array_equal(baseline, bumped):
            raise RuntimeError("Bump map não alterou a iluminação")
        if not np.array_equal(baseline[:, :, 3], bumped[:, :, 3]):
            raise RuntimeError("Bump map alterou a cobertura da geometria")
        material.bumpMapIntensity = 0.
        if not np.array_equal(baseline, render(material)):
            raise RuntimeError("Bump com intensidade zero alterou o material")
        material.bumpMapIntensity = 1.
        material.shaderConfig["bump"] = False
        if not np.array_equal(baseline, render(material)):
            raise RuntimeError("Configuração bump desligada alterou o material")
        material.shaderConfig["normal"] = True
        material.normalMapTexture = Image(data=np.tile(np.array([128, 128, 255, 255], np.uint8), (4, 4, 1)))
        normal_only = render(material)
        material.shaderConfig["bump"] = True
        if not np.array_equal(normal_only, render(material)):
            raise RuntimeError("Bump substituiu o normal map prioritário do material original")
        Image(data=baseline).save(str(path.parent / "bump-disabled.png"))
        Image(data=bumped).save(str(path.parent / "bump-enabled.png"))
        material = Material()
        material.diffuseColor = SimpleNamespace(values=(1., 1., 1.))
        material.shaderConfig = {"normal": False, "bump": False, "diffuse": False,
                                 "spec": False, "transparency": False, "ambientOcclusion": True}
        reference_ao = render(material)
        material.aoMapTexture = white
        if not np.array_equal(reference_ao, render(material)):
            raise RuntimeError("Mapa AO branco alterou o material")
        material.aoMapTexture = grey
        grey_ao = render(material)
        material.aoMapTexture = black
        black_ao = render(material)
        if np.any(black_ao[:, :, :3]) or not np.any(black_ao[:, :, 3]):
            raise RuntimeError("Mapa AO preto não suprimiu apenas a iluminação difusa")
        if not 0 < int(grey_ao[:, :, :3].sum()) < int(reference_ao[:, :, :3].sum()):
            raise RuntimeError("Mapa AO cinza não reduziu a iluminação")
        material.aoMapIntensity = 0.
        if not np.array_equal(reference_ao, render(material)):
            raise RuntimeError("Intensidade AO zero alterou o material")
        material.aoMapIntensity = 1.
        material.shaderConfig["ambientOcclusion"] = False
        if not np.array_equal(reference_ao, render(material)):
            raise RuntimeError("Mapa AO desligado alterou o material")
        Image(data=grey_ao).save(str(path.parent / "ao-grey.png"))
        Image(data=black_ao).save(str(path.parent / "ao-black.png"))
        # O preset Phong usa a mesma intensidade, conservando o brilho
        # especular separado do fator de oclusão da cor difusa.
        from getpath import getSysDataPath
        material.shader = getSysDataPath("shaders/glsl/phong")
        material.shaderConfig["ambientOcclusion"] = True
        material.aoMapTexture = None
        phong_reference = render(material)
        material.aoMapTexture = white
        if not np.array_equal(phong_reference, render(material)):
            raise RuntimeError("AO branco alterou o preset Phong")
        material.aoMapTexture = black
        phong_black = render(material)
        if np.any(phong_black[:, :, :3]) or not np.any(phong_reference[:, :, :3]):
            raise RuntimeError("AO preto não suprimiu a cor difusa do Phong")
        material.aoMapIntensity = 0.
        if not np.array_equal(phong_reference, render(material)):
            raise RuntimeError("Phong ignorou intensidade AO zero")
        Image(data=phong_reference).save(str(path.parent / "ao-phong-white.png"))
        Image(data=phong_black).save(str(path.parent / "ao-phong-black.png"))
        path.write_text(json.dumps({"specular": True, "transparency": True,
                                   "zero_intensity": True, "bump": True,
                                   "normal_precedence": True, "ao": True}), encoding="utf-8")
    finally:
        cena.atualizar_iluminacao(previous)
