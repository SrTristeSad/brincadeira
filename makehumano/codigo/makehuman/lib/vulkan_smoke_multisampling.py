"""Verificar MSAA e alpha-to-coverage no renderer original, por pixels."""
from pathlib import Path
from types import SimpleNamespace
import numpy as np


def validar_multisampling(cena, cameras, mundo, marker):
    from image import Image
    candidates = [obj for obj in mundo if obj.visibility and obj.solid and len(obj.primitives) > 100]
    if not candidates:
        raise RuntimeError("MSAA: personagem original ausente")
    body = max(candidates, key=lambda obj: len(obj.primitives))
    camera = cameras[body.cameraMode]
    _, view = camera.getMatrices(0)
    modelview = np.asarray(view) @ np.asarray(camera.getModelMatrix(body))
    center = np.mean(body.verts, axis=0)
    size = float(np.ptp(body.verts[:, 1])) * .25
    offsets = size * np.array([[-1., -.8, 0.], [.93, -.69, 0.], [-.37, .91, 0.]])

    class Material:
        shader = None
        shaderParameters = {}
        shaderConfig = {"normal": False, "bump": False, "diffuse": False,
                        "spec": False, "transparency": False, "ambientOcclusion": False}
        normalMapTexture = None
        transparent = False
        alphaToCoverage = True
        opacity = 1.
        diffuseColor = SimpleNamespace(values=(1., 1., 1.))
        specularColor = SimpleNamespace(values=(0., 0., 0.))
        emissiveColor = SimpleNamespace(values=(0., 0., 0.))
        shininess = 0.

    class Triangle:
        material = Material()
        verts = center + np.linalg.solve(modelview[:3, :3], offsets.T).T
        norms = np.tile([0., 0., 1.], (3, 1))
        UVs = np.zeros((3, 2), np.float32)
        color = np.full((3, 4), 255, np.uint8)
        primitives = np.array([[0, 1, 2]], np.uint32)
        nTransparentPrimitives = 0
        cull = 0
        isTextured = False
        texture = None
        shadeless = True
        depthless = False

        def __getattr__(self, name):
            return getattr(body, name)

    obj = Triangle()
    previous = cena.amostras

    def render():
        return cena.capturar_framebuffer([obj], cameras, 96, 96,
                                         incluir_alfa=True, cor_fundo=(0, 0, 0, 0))

    def partial(pixels):
        return int(np.count_nonzero((pixels[:, :, 3] > 0) & (pixels[:, :, 3] < 255)))

    try:
        cena.configurar_multisampling(False)
        single = render()
        cena.configurar_multisampling(True)
        msaa = render()
        if not np.any(single[:, :, 3]) or partial(msaa) <= partial(single):
            raise RuntimeError("MSAA não suavizou a cobertura das bordas diagonais")
        obj.material.transparent = True
        obj.material.opacity = .5
        obj.material.alphaToCoverage = False
        blend = render()
        obj.material.alphaToCoverage = True
        coverage = render()
        if np.array_equal(blend, coverage) or not np.any(coverage[:, :, :3]):
            raise RuntimeError("Alpha to Coverage não alterou a transparência multisample")
        obj.material.opacity = 0.
        if np.any(render()):
            raise RuntimeError("Alpha to Coverage não descartou alfa zero")
        obj.material.opacity = 1.
        obj.material.transparent = False
        cena.configurar_multisampling(False)
        if not np.array_equal(single, render()):
            raise RuntimeError("Desligar MSAA não restaurou o render original")
        path = Path(marker).parent
        for name, pixels in (("msaa-off", single), ("msaa-4x", msaa),
                             ("alpha-to-coverage", coverage), ("alpha-blend-msaa", blend)):
            Image(data=pixels).save(str(path / (name + ".png")))
    finally:
        cena.configurar_multisampling(previous > 1)
