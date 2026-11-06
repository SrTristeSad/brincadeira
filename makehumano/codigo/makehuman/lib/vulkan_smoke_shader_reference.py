"""Referências analíticas dos arquivos GLSL oficiais, renderizadas em Vulkan.

GLSL 1.20, estado derivado: sceneColor = emission + materialAmbient*sceneAmbient.
Os vertex shaders Phong/Skin originais multiplicam sceneColor por ambient.
setSceneLighting original zera o ambiente de cada luz; normalmap usa esse
ambiente da luz, enquanto Phong/Skin usam o termo global derivado.
"""
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np


def validar_referencias_shader(cena, cameras, mundo, directory):
    from getpath import getSysDataPath
    from image import Image
    body = max((obj for obj in mundo if obj.visibility and obj.solid), key=lambda obj: len(obj.primitives))
    camera = cameras[body.cameraMode]
    _, view = camera.getMatrices(0)
    view = np.asarray(view)
    model = np.asarray(camera.getModelMatrix(body))
    center = np.mean(body.verts, axis=0)
    basis = np.linalg.inv((view@model)[:3, :3])
    size = float(np.ptp(body.verts[:, 1]))*.15
    offsets = size*np.array([[-1., -1., 0.], [1., -1., 0.], [1., 1., 0.], [-1., 1., 0.]])
    positions = np.asarray(center+offsets@basis.T, np.float32)
    normal = np.cross(positions[1]-positions[0], positions[3]-positions[0])
    normal /= np.linalg.norm(normal)
    white = Image(data=np.full((4, 4, 4), 255, np.uint8))
    black = Image(data=np.tile([0, 0, 0, 255], (4, 4, 1)).astype(np.uint8))
    grey = Image(data=np.tile([128, 128, 128, 255], (4, 4, 1)).astype(np.uint8))
    flat = Image(data=np.tile([128, 128, 255, 255], (4, 4, 1)).astype(np.uint8))
    ambient = np.array([.2, .4, .6])
    emission = np.array([.05, .1, .15])
    scene_ambient = np.array([.5, .25, .75])
    material = SimpleNamespace(shader=None, shaderParameters={},
        shaderConfig={'diffuse': True, 'normal': False, 'ambientOcclusion': True},
        ambientColor=SimpleNamespace(values=tuple(ambient)),
        diffuseColor=SimpleNamespace(values=(.9, .1, .3)),
        emissiveColor=SimpleNamespace(values=tuple(emission)),
        specularColor=SimpleNamespace(values=(0., 0., 0.)), shininess=.2,
        opacity=1., transparent=False, alphaToCoverage=False,
        castShadows=False, receiveShadows=False, normalMapTexture=None,
        aoMapTexture=None, aoMapIntensity=1.)

    class Object:
        verts = positions
        norms = np.tile(normal, (4, 1))
        UVs = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]], np.float32)
        hasUVs = True
        primitives = np.array([[0, 1, 2, 3]], np.uint32)
        color = np.full((4, 4), 255, np.uint8)
        nTransparentPrimitives = 0
        cull = 0
        texture = white
        isTextured = True
        shadeless = False
        depthless = False

        def __getattr__(self, name):
            return getattr(body, name)

    obj = Object()
    obj.material = material
    world_center = model[:3, :3]@center+model[:3, 3]
    light = SimpleNamespace(position=tuple(world_center-np.linalg.solve(view[:3, :3], [0., 0., 4.*size])),
        color=(1., 1., 1.), specular=(0., 0., 0.), fov=180., attenuation=0.)
    scene = SimpleNamespace(environment=SimpleNamespace(ambience=tuple(scene_ambient)), lights=[light])
    previous = cena._cena_luzes
    path = Path(directory)

    def render():
        return cena.capturar_framebuffer([obj], cameras, 160, 120,
            incluir_alfa=True, cor_fundo=(0, 0, 0, 0))

    def check(image, linear, label):
        expected = np.asarray(linear, float)
        if cena.formato.endswith('-srgb'):
            expected = np.where(expected <= .0031308, expected*12.92, 1.055*expected**(1./2.4)-.055)
        mask = image[:, :, 3] == 255
        if np.count_nonzero(mask) < 16:
            raise RuntimeError('Referência de shader sem cobertura interior suficiente')
        error = float(np.max(np.abs(image[:, :, :3][mask].astype(float)-expected*255.)))
        if error > 2.:
            Image(data=image).save(str(path/'shader-reference-failure.png'))
            raise RuntimeError(f'Referência {label}: erro de {error} níveis de canal')
        return error

    try:
        cena.atualizar_iluminacao(scene)
        # No direct contribution: the single light is behind the surface.
        # These formulas include the original extra ambient multiplication.
        derived = (emission+ambient*scene_ambient)*ambient
        material.shader = getSysDataPath('shaders/glsl/phong')
        phong = render()
        errors = {'phong': check(phong, derived+emission, 'Phong ambiente/emissão')}
        material.diffuseColor = SimpleNamespace(values=(.1, .9, .2))
        if not np.array_equal(phong, render()):
            raise RuntimeError('Cor difusa contaminou o termo ambiente de Phong')
        material.shader = getSysDataPath('shaders/glsl/skin')
        material.shaderParameters = {'ambientOcclusionMap': white, 'gradientMap': white}
        skin = render()
        errors['skin'] = check(skin, derived, 'Skin ambiente/emissão')
        material.diffuseColor = SimpleNamespace(values=(.9, .1, .3))
        if not np.array_equal(skin, render()):
            raise RuntimeError('Cor difusa contaminou o termo ambiente de Skin')
        material.shader = getSysDataPath('shaders/glsl/normalmap')
        material.shaderParameters = {'normalmapTexture': flat}
        normalmap = render()
        errors['normalmap'] = check(normalmap, [0., 0., 0.], 'Normalmap ambiente da luz zero')
        scene.environment.ambience = (1., 1., 1.)
        if not np.array_equal(normalmap, render()):
            raise RuntimeError('Normalmap usou ambiente global ausente no GLSL original')
        material.shader = getSysDataPath('shaders/glsl/litsphere')
        lit_rgb = np.array([64, 128, 192], float)/255.
        material.shaderParameters = {'litsphereTexture': Image(data=np.tile([64, 128, 192, 255], (4, 4, 1)).astype(np.uint8))}
        material.shaderConfig['diffuse'] = False
        lit_reference = render()
        material.aoMapTexture = white
        lit_white = render()
        if not np.array_equal(lit_reference, lit_white):
            raise RuntimeError('AO branco alterou a LitSphere sem mapa')
        errors['litsphere_white'] = check(lit_white, lit_rgb, 'LitSphere sem AO')
        material.aoMapTexture = black
        lit_black = render()
        errors['litsphere_black'] = check(lit_black, [0., 0., 0.], 'LitSphere AO preto')
        material.aoMapTexture = grey
        material.aoMapIntensity = .5
        lit_grey = render()
        errors['litsphere_grey'] = check(lit_grey, lit_rgb*(.5+.5*128./255.), 'LitSphere AO intensidade')
        material.aoMapIntensity = 0.
        if not np.array_equal(lit_reference, render()):
            raise RuntimeError('Intensidade AO zero não restaurou LitSphere')
        material.aoMapIntensity = 1.
        material.shaderConfig['ambientOcclusion'] = False
        if not np.array_equal(lit_reference, render()):
            raise RuntimeError('Desativar AO não restaurou LitSphere')
        if not all(np.array_equal(lit_reference[:, :, 3], image[:, :, 3]) for image in (lit_white, lit_black, lit_grey)):
            raise RuntimeError('Mapa AO alterou cobertura alfa de LitSphere')
        for name, image in [('reference-phong-ambient', phong), ('reference-skin-ambient', skin),
                            ('reference-normalmap-ambient', normalmap), ('reference-litsphere-ao-white', lit_white),
                            ('reference-litsphere-ao-black', lit_black), ('reference-litsphere-ao-grey', lit_grey)]:
            Image(data=image).save(str(path/(name+'.png')))
        (path/'shader-reference.json').write_text(json.dumps(dict(
            ambient_reference=True, diffuse_independent=True, zero_light_ambient=True,
            litsphere_ao=True, intensity_and_config=True, alpha_preserved=True,
            maximum_channel_errors=errors)), encoding='utf-8')
    finally:
        cena.atualizar_iluminacao(previous)
