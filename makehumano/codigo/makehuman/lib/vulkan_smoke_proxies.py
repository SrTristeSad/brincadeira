"""Exercitar proxies oficiais no carregador original e sua ligação a morphs."""
from pathlib import Path
import numpy as np


def validar_proxies(app, directory):
    import mh
    from core import G
    from getpath import getSysDataPath
    from humanmodifier import ModifierAction
    from proxychooser import ProxyAction
    from image import Image

    library = app.modules['3_libraries_eye_chooser'].taskview
    human = app.selectedHuman
    original_proxy = human.eyesProxy
    original_file = original_proxy.file if original_proxy else None
    original_eye_material = original_proxy.object.material.clone() if original_proxy else None
    original_material = human.material.clone()
    original_coords = human.meshData.coord.copy()
    modifier = human.getModifier('head/head-scale-vert-decr|incr')
    original_value = modifier.getValue()
    undo, redo = list(app.undoStack), list(app.redoStack)
    high = getSysDataPath('eyes/high-poly/high-poly.mhclo')
    low = getSysDataPath('eyes/low-poly/low-poly.mhclo')
    directory = Path(directory)

    def selection():
        proxy = human.eyesProxy
        if proxy is None or len(library.getSelection()) != 1 or proxy is not library.getSelection()[0]:
            raise RuntimeError('Biblioteca de olhos e Human discordam sobre o proxy selecionado')
        mesh = proxy.object.getSeedMesh()
        np.testing.assert_allclose(mesh.coord, proxy.getCoords(), atol=2e-5)
        return proxy, mesh

    def capture():
        proxy, mesh = selection()
        image = G.canvas._cena.capturar_framebuffer([proxy.object.mesh.object3d], G.cameras,
            512, 512, incluir_alfa=True, cor_fundo=(0, 0, 0, 0))
        if not np.any(image[:, :, 3]):
            raise RuntimeError('Vulkan não desenhou os olhos oficiais')
        return image

    try:
        library.selectProxy(high)
        high_proxy, high_mesh = selection()
        high_uuid = high_proxy.getUuid()
        high_count = len(high_mesh.coord)
        high_image = capture()
        app.do(ProxyAction('Smoke olhos oficiais', library, high, low))
        low_proxy, low_mesh = selection()
        low_uuid = low_proxy.getUuid()
        low_count = len(low_mesh.coord)
        if low_uuid == high_uuid or low_count >= high_count:
            raise RuntimeError('Troca de resolução não carregou os dois assets oficiais distintos')
        app.undo()
        if selection()[0].getUuid() != high_uuid:
            raise RuntimeError('Undo não restaurou os olhos de alta resolução')
        app.redo()
        if selection()[0].getUuid() != low_uuid:
            raise RuntimeError('Redo não restaurou os olhos de baixa resolução')
        before = selection()[1].coord.copy()
        value = -.8 if original_value > .2 else .8
        app.do(ModifierAction(modifier, original_value, value, lambda: None))
        after = selection()[1].coord.copy()
        if np.allclose(before, after, atol=1e-5):
            raise RuntimeError('Proxy de olhos não acompanhou o morph original da cabeça')
        deformed_image = capture()
        app.undo()
        np.testing.assert_allclose(selection()[1].coord, before, atol=2e-5)
        app.redo()
        np.testing.assert_allclose(selection()[1].coord, after, atol=2e-5)
        model = directory/'personagem-com-proxy.mhm'
        human.save(str(model))
        if low_uuid not in model.read_text(encoding='utf-8'):
            raise RuntimeError('MHM não gravou o UUID do proxy oficial')
        library.selectProxy(high)
        modifier.setValue(original_value)
        human.applyAllTargets()
        human.load(str(model), strict=True)
        if selection()[0].getUuid() != low_uuid:
            raise RuntimeError('MHM não recarregou os olhos oficiais selecionados')
        np.testing.assert_allclose(selection()[1].coord, after, atol=2e-5)
        if not np.array_equal(deformed_image, capture()):
            raise RuntimeError('Salvar/reabrir MHM alterou a imagem do proxy')
        Image(data=high_image).save(str(directory/'proxy-eyes-high.png'))
        Image(data=deformed_image).save(str(directory/'proxy-eyes-deformed.png'))
        result = dict(original_loader=True, high_vertices=high_count, low_vertices=low_count,
            selection_undo_redo=True, morph_binding=True, morph_undo_redo=True,
            mhm_uuid_roundtrip=True, image_roundtrip=True)
    finally:
        modifier.setValue(original_value)
        human.applyAllTargets()
        library.selectProxy(original_file)
        if original_eye_material is not None:
            human.eyesProxy.object.material = original_eye_material
        human.material = original_material
        app.undoStack[:] = undo
        app.redoStack[:] = redo
        app.syncUndoRedo()
    np.testing.assert_allclose(human.meshData.coord, original_coords, atol=2e-5)
    if original_file is not None:
        selection()
    return result
