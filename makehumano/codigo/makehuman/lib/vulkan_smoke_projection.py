"""Exercitar o contrato original de projeção/pintura de textura via mh."""
from pathlib import Path
import numpy as np


def validar_projecao(marker):
    import mh
    from image import Image
    from vulkan_texture import Texture
    vertices = np.array([[.25, .25], [.75, .25], [.75, .75], [.25, .75]], np.float32)
    background = Image(data=np.tile(np.array([0, 0, 255, 255], np.uint8), (32, 32, 1)))
    original = background.data.copy()
    source = np.zeros((8, 8, 4), np.uint8)
    source[:, :4] = [255, 0, 0, 255]
    source[:, 4:] = [0, 255, 0, 255]
    uv3 = np.tile([0., 0., 1.], (4, 1)).astype(np.float32)
    matrix = np.eye(4, dtype=np.float32)
    matrix[0] = [0., 0., .75, 0.]
    matrix[1] = [0., 0., 0., .5]
    projected = mh.renderSkin(background, 4, vertices, texture=Image(data=source),
                              UVs=uv3, textureMatrix=matrix)
    if not np.array_equal(background.data, original):
        raise RuntimeError("renderSkin modificou a Image de entrada, contrariando o contrato original")
    if not np.array_equal(projected.data[16, 16], [0, 255, 0]):
        raise RuntimeError("Projeção ignorou Z ou a matriz das coordenadas de textura")
    if not np.array_equal(projected.data[0, 0], [0, 0, 255]):
        raise RuntimeError("Projeção apagou a imagem fora da região pintada")
    uv4 = np.concatenate((uv3 * 2., np.full((4, 1), 2., np.float32)), axis=1)
    homogeneous = mh.renderSkin(background, 4, vertices, texture=Image(data=source),
                                UVs=uv4, textureMatrix=matrix)
    if not np.array_equal(projected.data, homogeneous.data):
        raise RuntimeError("Projeção não preservou coordenadas homogêneas equivalentes")
    projective_source = np.zeros((4, 256, 4), np.uint8)
    projective_source[:, :154] = [255, 0, 0, 255]
    projective_source[:, 154:] = [0, 255, 0, 255]
    uv_projective = np.array([[0., .5, 0., 1.], [2., 1., 0., 2.],
                              [2., 1., 0., 2.], [0., .5, 0., 1.]], np.float32)
    perspective = mh.renderSkin(background, 4, vertices,
                                texture=Image(data=projective_source), UVs=uv_projective)
    if not np.array_equal(perspective.data[16, 16], [0, 255, 0]):
        raise RuntimeError("Projeção dividiu por Q antes da interpolação dos fragmentos")

    destination = Texture(image=background)
    colors = np.tile(np.array([255, 0, 0, 128], np.uint8), (4, 1))
    mh.renderSkin(destination, 4, vertices, color=colors)
    first = destination.data.copy()
    if not np.all(np.abs(first[16, 16].astype(int) - [128, 0, 127, 255]) <= 1):
        raise RuntimeError(f"Pintura não compôs alfa sobre a textura existente: {first[16, 16].tolist()}")
    model = np.eye(4, dtype=np.float32)
    model[0, 3] = .5
    colors[:] = [0, 255, 0, 255]
    result = mh.renderSkin(destination, 4, vertices, color=colors, objectMatrix=model)
    if not np.array_equal(first[:, :23], destination.data[:, :23]):
        raise RuntimeError("Segundo passe apagou a pintura anterior")
    if not np.array_equal(destination.data[16, 28], [0, 255, 0, 255]):
        raise RuntimeError("Matriz de objeto não deslocou a região pintada")
    # LA deve armazenar luminância e alfa, não os dois primeiros canais RGB.
    la = Texture(size=(8, 8), components=2)
    mh.renderSkin(la, 4, vertices, index=np.empty((0, 4), np.uint32),
                  clearColor=(1., 0., 0., .25))
    if not np.all(np.abs(la.data.astype(int) - [85, 64]) <= 1):
        raise RuntimeError("Destino luminância/alfa perdeu seus canais")
    path = Path(marker).parent
    projected.save(str(path / "projection-3d.png"))
    perspective.save(str(path / "projection-perspective.png"))
    result.save(str(path / "projection-accumulated.png"))


def validar_projecao_original(cena, cameras, mundo, directory):
    """Chama a ferramenta original com a malha real, sem fallback CPU."""
    from core import G
    from image import Image
    from projection import mapImageGL
    from vulkan_texture import reloadTexture
    human = G.app.selectedHuman
    # O setter original copia campos para o Material existente; guardar a
    # referência não preservaria o estado que será alterado pelo teste.
    original_material = human.material.clone()
    material = original_material.clone()
    path = Path(directory)
    destination = path / "projection-working-copy.png"
    Image(data=np.full((512, 512, 4), 255, np.uint8)).save(str(destination))
    original_bytes = destination.read_bytes()
    source = np.full((8, 8, 4), 255, np.uint8)
    source[:, :4] = [255, 0, 0, 255]
    source[:, 4:] = [0, 0, 255, 255]
    source = Image(data=source)
    material.shader = None
    material.autoBlendSkin = False
    material.diffuseColor = (1., 1., 1.)
    material.diffuseTexture = str(destination)
    material.shadeless = True
    material.displacementMapTexture = None
    material.displacementMapIntensity = 0.
    material.configureShading(diffuse=True, displacement=True)

    def viewport():
        return cena.capturar_framebuffer(mundo, cameras, 160, 120,
                                         incluir_alfa=True, cor_fundo=(0, 0, 0, 0))

    original_viewport = viewport()
    try:
        human.material = material
        material = human.material
        mesh = human.meshData
        if mesh.object3d.textureTex is None:
            raise RuntimeError("A ferramenta original não obteve a Texture do personagem")
        before = viewport()
        projected = mapImageGL(source, mesh, (0., 0.), (float(G.windowWidth), float(G.windowHeight)))
        painted = viewport()
        if np.array_equal(before, painted):
            raise RuntimeError("Viewport ignorou a pintura da ferramenta original em memória")
        if destination.read_bytes() != original_bytes:
            raise RuntimeError("Projeção sobrescreveu o arquivo de origem da textura")
        reloadTexture(str(destination))
        if not np.array_equal(before, viewport()):
            raise RuntimeError("Recarregar textura não descartou a cópia pintada em memória")
        material.displacementMapTexture = Image(data=np.full((4, 4, 4), 255, np.uint8))
        material.displacementMapIntensity = .5
        displaced = mapImageGL(source, mesh, (0., 0.), (float(G.windowWidth), float(G.windowHeight)))
        if np.array_equal(projected.data, displaced.data):
            raise RuntimeError("Projeção original ignorou as coordenadas deslocadas")
        projected.save(str(path / "projection-original.png"))
        displaced.save(str(path / "projection-displaced.png"))
        Image(data=painted).save(str(path / "projection-painted-viewport.png"))
    finally:
        human.material = original_material
        reloadTexture(str(destination))
        cena.invalidar_texturas()
    if not np.array_equal(original_viewport, viewport()):
        raise RuntimeError("Teste de projeção não restaurou a aparência original do personagem")
