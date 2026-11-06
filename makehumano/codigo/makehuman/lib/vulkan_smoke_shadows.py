"""Sombras Vulkan em duas superfícies, usando câmera e controles originais."""
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np


def validar_sombras(cena, cameras, mundo, directory):
    from image import Image
    from scene import Light
    body = max((o for o in mundo if o.visibility and o.solid), key=lambda o: len(o.primitives))
    camera = cameras[body.cameraMode]
    _, view = camera.getMatrices(0)
    model = np.asarray(camera.getModelMatrix(body))
    view = np.asarray(view)
    basis = np.linalg.inv((view @ model)[:3, :3])
    center = np.mean(body.verts, axis=0)
    scale = float(np.ptp(body.verts[:, 1]))*.2
    normal = basis @ [0., 0., 1.]
    normal /= np.linalg.norm(normal)

    class Object:
        hasUVs = False
        UVs = None
        norms = np.tile(normal, (4, 1)).astype(np.float32)
        color = np.full((4, 4), 255, np.uint8)
        primitives = np.array([[0, 1, 2, 3]], np.uint32)
        nTransparentPrimitives = 0
        isTextured = False
        texture = None
        shadeless = False
        depthless = False
        cull = 0

        def __getattr__(self, name):
            return getattr(body, name)

    def material(cast, receive):
        return SimpleNamespace(shader=None, shaderParameters={}, shaderConfig={},
            castShadows=cast, receiveShadows=receive, transparent=False, opacity=1.,
            diffuseColor=SimpleNamespace(values=(.7, .7, .7)), shininess=0.,
            specularColor=SimpleNamespace(values=(0., 0., 0.)),
            emissiveColor=SimpleNamespace(values=(0., 0., 0.)))

    def quad(radius, z):
        offsets = scale*np.array([[-radius, -radius, z], [radius, -radius, z],
                                  [radius, radius, z], [-radius, radius, z]])
        return np.asarray(center + offsets @ basis.T, np.float32)

    receiver, blocker = Object(), Object()
    receiver.material = material(False, True)
    blocker.material = material(False, False)
    receiver.verts = quad(1.5, 0.)
    blocker.verts = quad(.28, 1.)
    original_receiver = receiver.verts.copy()
    light = Light()
    world_center = model[:3, :3] @ center + model[:3, 3]
    light.position = tuple(world_center + np.linalg.solve(view[:3, :3], scale*np.array([2., 0., 4.])))
    light.focus = tuple(world_center)
    light.color = (1., 1., 1.)
    light.specular = (0., 0., 0.)
    light.fov = 180.
    light.attenuation = 0.
    scene = SimpleNamespace(environment=SimpleNamespace(ambience=(.1, .1, .1)), lights=[light])
    previous = cena._cena_luzes

    def render(objects=None, production=False):
        return cena.capturar_framebuffer([receiver, blocker] if objects is None else objects,
            cameras, 160, 120, incluir_alfa=True, productionRender=production, cor_fundo=(0, 0, 0, 0))

    try:
        cena.atualizar_iluminacao(scene)
        off = render()
        blocker.material.castShadows = True
        on = render()
        dark = np.sum(off[:, :, :3].astype(int)-on[:, :, :3].astype(int), axis=2) > 60
        if np.count_nonzero(dark) < 10:
            raise RuntimeError('Sombras: oclusor não escureceu a superfície receptora')
        if not np.array_equal(off[:, :, 3], on[:, :, 3]):
            raise RuntimeError('Sombras alteraram a cobertura alpha')
        receiver.material.receiveShadows = False
        if not np.array_equal(off, render()):
            raise RuntimeError('receiveShadows=False não restaurou a iluminação')
        receiver.material.receiveShadows = True
        blocker.visibility = False
        visible_receiver = render([receiver])
        blocker.visibility = True
        blocker.verts = quad(.28, -1.)
        if not np.array_equal(visible_receiver, render()):
            raise RuntimeError('Oclusor atrás do receptor bloqueou luz incorretamente')
        blocker.verts = quad(.28, 1.)
        blocker.excludeFromProduction = True
        if not np.array_equal(visible_receiver, render(production=True)):
            raise RuntimeError('Objeto excluído da produção ainda projetou sombra')
        blocker.excludeFromProduction = False
        light.areaLights = 8
        light.areaLightSize = scale*2.
        soft = render()
        blocker.material.castShadows = False
        area_off = render()
        light.color = (0., 0., 0.)
        ambient = render()
        direct = np.sum(area_off[:, :, :3].astype(float)-ambient[:, :, :3], axis=2)
        shadowed = np.sum(soft[:, :, :3].astype(float)-ambient[:, :, :3], axis=2)
        partial = (direct > 80) & (shadowed > .15*direct) & (shadowed < .85*direct)
        if np.count_nonzero(partial) < 10:
            raise RuntimeError('Luz de área não produziu penumbra')
        if not np.array_equal(original_receiver, receiver.verts):
            raise RuntimeError('Sombras alteraram a malha receptora')
        path = Path(directory)
        for name, image in [('shadow-off', off), ('shadow-point', on), ('shadow-area', soft)]:
            Image(data=image).save(str(path / (name+'.png')))
        (path/'shadows.json').write_text(json.dumps(dict(point=True, area_penumbra=True,
            cast_receive=True, behind_receiver=True, production_exclusion=True,
            mesh_preserved=True, partial_pixels=int(np.count_nonzero(partial)))), encoding='utf-8')
    finally:
        cena.atualizar_iluminacao(previous)
