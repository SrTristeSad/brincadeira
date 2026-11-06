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
    # Eventos dos controles na interface original e persistência .mhmat.
    from core import G
    from material import Material
    human = G.app.selectedHuman
    original_flags = (human.material.castShadows, human.material.receiveShadows)
    editor = G.app.getTask('Utilities', 'Material Editor')
    try:
        editor.listMaterialSettings(human)
        for widget, attribute in ((editor.castShadowsValue, 'castShadows'),
                                  (editor.receiveShadowsValue, 'receiveShadows')):
            widget.value = False
            widget.callEvent('onActivate', False)
            if getattr(human.material, attribute):
                raise RuntimeError('Controle de sombras não alterou o Material original')
        material_path = Path(directory) / 'shadow-controls.mhmat'
        human.material.toFile(str(material_path))
        loaded = Material()
        loaded.fromFile(str(material_path))
        if loaded.castShadows or loaded.receiveShadows:
            raise RuntimeError('Salvar/reabrir material perdeu controles de sombras')
    finally:
        human.material.castShadows, human.material.receiveShadows = original_flags
        editor.reloadMaterial()
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
        # Fração transmitida é medida no receptor, fora da projeção visual
        # dos cartões. A área dark foi determinada por um oclusor opaco.
        def linear_rgb(image):
            rgb = image[:, :, :3].astype(float)/255.
            if cena.formato.endswith('-srgb'):
                rgb = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
            return rgb

        def expected_fraction(fraction):
            rgb = linear_rgb(on) + fraction*(linear_rgb(off)-linear_rgb(on))
            if cena.formato.endswith('-srgb'):
                rgb = np.where(rgb <= .0031308, rgb*12.92, 1.055*rgb**(1./2.4)-.055)
            return rgb*255.

        def check_fraction(image, fraction, label):
            expected = expected_fraction(fraction)
            error = np.max(np.abs(image[:, :, :3].astype(float)[dark]-expected[dark]))
            if error > 3.:
                debug_path = Path(directory)
                np.savez_compressed(debug_path/'shadow-alpha-failure.npz', off=off, on=on,
                    actual=image, mask=dark, fraction=fraction, receiver=receiver.verts,
                    blocker=blocker.verts, model=model, view=view, light=np.asarray(light.position))
                for name, pixels in [('before', off), ('opaque', on), ('actual', image)]:
                    Image(data=pixels).save(str(debug_path/('shadow-alpha-failure-'+name+'.png')))
                delta = np.max(np.abs(image[:, :, :3].astype(float)-expected), axis=2)*dark
                y, x = np.unravel_index(np.argmax(delta), delta.shape)
                raise RuntimeError(f'Sombra {label}: erro máximo {error} em {x},{y}; '
                    f'antes={off[y,x,:3].tolist()}, opaco={on[y,x,:3].tolist()}, atual={image[y,x,:3].tolist()}')

        blocker.material.opacity = .5
        half = render()
        check_fraction(half, .5, 'opacidade 50% ou diagonal duplicada')
        blocker.material.opacity = 1.
        blocker.color = Object.color.copy()
        blocker.color[:, 3] = 128
        check_fraction(render(), 1.-128./255., 'alfa dos vértices')
        blocker.color[:, 3] = 255
        from vulkan_texture import Texture
        rgba = np.full((32, 32, 4), 255, np.uint8)
        rgba[:, :, 3] = 0
        rgba[:16, :16, 3] = 255
        texture = Texture(image=Image(data=rgba))
        blocker.texture = texture
        blocker.isTextured = True
        blocker.hasUVs = True
        blocker.UVs = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]], np.float32)
        cutout = render()
        difference = np.sum(off[:, :, :3].astype(float)-on[:, :, :3], axis=2)
        transmitted = np.sum(cutout[:, :, :3].astype(float)-on[:, :, :3], axis=2)
        if np.count_nonzero(dark & (transmitted > .9*difference)) < 5:
            raise RuntimeError('Textura recortada não deixou a luz passar pelos buracos')
        if np.count_nonzero(dark & (transmitted < .1*difference)) < 3:
            raise RuntimeError('Textura recortada não preservou a sombra da região opaca')
        # UVs independentes assimétricas verificam também a origem superior.
        from vulkan_scene import matriz_wgpu
        mvp = matriz_wgpu(camera, receiver, tamanho_origem=(G.windowWidth, G.windowHeight), tamanho_destino=(160, 120))
        for u, v, uv_fraction in ((.25, .75, 0.), (.25, .25, 1.), (.75, .75, 1.)):
            offset = scale*np.array([(4./3.)*.28*(2*u-1)-2./3., (4./3.)*.28*(2*v-1), 0.])
            point = center+basis@offset
            clip = mvp@np.array([*point, 1.])
            x, y = np.floor((clip[:2]/clip[3]*[.5, -.5]+[.5, .5])*[160, 120]).astype(int)
            expected = on[y, x, :3].astype(float)+uv_fraction*(off[y, x, :3].astype(float)-on[y, x, :3])
            if np.max(np.abs(cutout[y, x, :3].astype(float)-expected)) > 3.:
                raise RuntimeError(f'Sombra recortada ignorou UV/orientação em {u}, {v}')
        rgba[:, :, 3] = 0
        texture.loadImage(Image(data=rgba))
        check_fraction(render(), 1., 'edição alpha em memória')
        rgba[:, :, 3] = 255
        texture.loadImage(Image(data=rgba))
        check_fraction(render(), 0., 'restauração alpha opaco')
        rgba[:, :, 3] = 128
        texture.loadImage(Image(data=rgba))
        check_fraction(render(), 1.-128./255., 'alfa parcial da textura')
        blocker.texture = None
        blocker.isTextured = False
        blocker.hasUVs = False
        blocker.material.transparencyMapTexture = Image(data=np.full((4, 4, 3), 128, np.uint8))
        blocker.material.transparencyMapIntensity = 1.
        check_fraction(render(), 128./255., 'mapa de transparência')
        blocker.material.transparencyMapIntensity = 0.
        check_fraction(render(), 0., 'intensidade zero do mapa')
        blocker.material.transparencyMapIntensity = 1.
        blocker.material.shaderConfig['transparency'] = False
        check_fraction(render(), 0., 'mapa desativado')
        blocker.material.transparencyMapTexture = None
        blocker.material.shaderConfig.clear()
        blocker.material.opacity = .5
        second = Object()
        second.material = material(True, False)
        second.material.opacity = .5
        second.verts = quad(.28*2.5/3., 1.5) + basis@np.array([scale/3., 0., 0.])
        layers = render([receiver, blocker, second])
        check_fraction(layers, .25, 'duas camadas de 50%')
        reordered = render([second, blocker, receiver])
        if not np.array_equal(layers, reordered):
            raise RuntimeError('Ordem dos objetos alterou a transmissão das sombras')
        blocker.material.opacity = 1.
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
        for name, image in [('shadow-off', off), ('shadow-point', on), ('shadow-area', soft),
                            ('shadow-cutout', cutout), ('shadow-opacity', half), ('shadow-layers', layers)]:
            Image(data=image).save(str(path / (name+'.png')))
        (path/'shadows.json').write_text(json.dumps(dict(point=True, area_penumbra=True,
            cast_receive=True, original_widgets=True, mhmat_roundtrip=True,
            behind_receiver=True, production_exclusion=True,
            mesh_preserved=True, alpha_cutout=True, alpha_uv_orientation=True,
            texture_edit=True, vertex_alpha=True, opacity=True, transparency_map=True,
            layered_transmission=True, order_independent=True, partial_pixels=int(np.count_nonzero(partial)))), encoding='utf-8')
    finally:
        cena.atualizar_iluminacao(previous)
