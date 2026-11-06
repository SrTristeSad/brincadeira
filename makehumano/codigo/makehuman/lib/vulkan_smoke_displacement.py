"""Comparar displacement visível e picking usando a mesma geometria."""
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np


def validar_displacement(cena, cameras, mundo, marker):
    from core import G
    from image import Image
    from vulkan_picking import selecionar_cor, selecionar_profundidade
    candidates = [obj for obj in mundo if obj.visibility and obj.solid and len(obj.primitives) > 100]
    if not candidates:
        raise RuntimeError("Displacement: personagem original ausente")
    body = max(candidates, key=lambda obj: len(obj.primitives))
    camera = cameras[body.cameraMode]
    _, view = camera.getMatrices(0)
    modelview = np.asarray(view) @ np.asarray(camera.getModelMatrix(body))
    size = float(np.ptp(body.verts[:, 1])) * .12
    offsets = size*np.array([[-1., -1., -.7], [1., -1., .7],
                            [1., 1., .7], [-1., 1., -.7]])
    positions = np.mean(body.verts, axis=0) + np.linalg.solve(modelview[:3, :3], offsets.T).T
    normal = np.cross(positions[1]-positions[0], positions[2]-positions[0])
    normal /= np.linalg.norm(normal)
    white = Image(data=np.full((4, 4, 4), 255, np.uint8))
    black = Image(data=np.zeros((4, 4, 4), np.uint8))

    class Material:
        shader = None
        shaderParameters = {}
        shaderConfig = {"normal": False, "bump": False, "diffuse": False, "spec": False,
                        "ambientOcclusion": False, "transparency": False, "displacement": True}
        normalMapTexture = None
        displacementMapTexture = white
        displacementMapIntensity = 0.
        opacity = 1.
        transparent = False
        diffuseColor = SimpleNamespace(values=(1., 1., 1.))
        specularColor = SimpleNamespace(values=(0., 0., 0.))
        emissiveColor = SimpleNamespace(values=(0., 0., 0.))
        shininess = 0.

    class Object:
        material = Material()
        verts = positions
        norms = np.tile(normal, (4, 1))
        UVs = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]], np.float32)
        hasUVs = True
        color = np.full((4, 4), 255, np.uint8)
        primitives = np.array([[0, 1, 2, 3]], np.uint32)
        groups = [(0, 1)]
        pickable = True
        nTransparentPrimitives = 0
        cull = 0
        isTextured = False
        texture = None
        shadeless = True
        depthless = False

        def clrid(self, index):
            return (240, 120, 60)

        def __getattr__(self, name):
            return getattr(body, name)

    obj = Object()
    previous_coords = body.verts.copy()
    original = positions.copy()
    width, height = int(G.windowWidth), int(G.windowHeight)

    def render():
        return cena.capturar_framebuffer([obj], cameras, width, height,
                                         incluir_alfa=True, cor_fundo=(0, 0, 0, 0))

    reference = render()
    obj.material.displacementMapIntensity = 1.
    moved = render()
    candidates = np.argwhere((moved[:, :, 3] == 255) & (reference[:, :, 3] == 0))
    if not len(candidates):
        raise RuntimeError("Displacement não deslocou a silhueta visível")
    # Escolhe uma região interior nova, evitando diferenças de cobertura MSAA.
    selected = None
    for y, x in candidates[::max(1, len(candidates)//100)]:
        if selecionar_cor([obj], cameras, int(x), int(y), width, height) == obj.clrid(0):
            selected = (int(x), int(y))
            break
    if selected is None:
        raise RuntimeError("Picking não acompanhou a geometria deslocada")
    if selecionar_profundidade([obj], cameras, *selected, width, height) >= 1.:
        raise RuntimeError("Displacement não atualizou a profundidade de seleção")
    obj.material.displacementMapIntensity = 0.
    if selecionar_cor([obj], cameras, *selected, width, height) != (0, 0, 0):
        raise RuntimeError("Picking manteve a geometria deslocada após intensidade zero")
    if not np.array_equal(reference, render()):
        raise RuntimeError("Intensidade zero não restaurou o render anterior")
    obj.material.displacementMapIntensity = 1.
    obj.material.displacementMapTexture = black
    if not np.array_equal(reference, render()):
        raise RuntimeError("Mapa preto alterou a geometria")
    obj.material.displacementMapTexture = white
    obj.material.shaderConfig["displacement"] = False
    if not np.array_equal(reference, render()):
        raise RuntimeError("Displacement desligado alterou a geometria")
    obj.material.shaderConfig["displacement"] = True
    path = Path(marker)
    image_path = path.parent / "displacement-map.png"
    black.save(str(image_path))
    obj.material.displacementMapTexture = str(image_path)
    if not np.array_equal(reference, render()):
        raise RuntimeError("Mapa de arquivo preto alterou a geometria")
    white.save(str(image_path))
    if not np.array_equal(moved, render()):
        raise RuntimeError("Displacement não recarregou o arquivo modificado")
    black.save(str(image_path))
    cena.invalidar_texturas(str(image_path))
    if not np.array_equal(reference, render()):
        raise RuntimeError("Invalidação do cache não atualizou displacement")
    np.testing.assert_array_equal(positions, original)
    np.testing.assert_array_equal(body.verts, previous_coords)
    Image(data=reference).save(str(path.parent / "displacement-off.png"))
    Image(data=moved).save(str(path.parent / "displacement-on.png"))
    from vulkan_smoke_projection import validar_projecao_original
    validar_projecao_original(cena, cameras, mundo, path.parent)
    path.write_text(json.dumps({"geometry": True, "picking": True, "depth": True,
                               "file_refresh": True, "original_mesh_preserved": True,
                               "original_projection": True}), encoding="utf-8")
