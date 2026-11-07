"""Diagnóstico isolado de codificação UNORM/sRGB na rota Vulkan do MakeHumano.

Não altera a CenaVulkan nem o formato da renderização de produção.
O sucesso deste experimento NÃO equivale a paridade visual OpenGL × Vulkan.
"""
import argparse
import json
import sys
from pathlib import Path


def _amostra_clear(device, wgpu, formato):
    """Limpa uma textura 4x4 com linear 0,5 e lê o primeiro pixel RGBA."""
    largura, altura, stride = 4, 4, 256
    textura = device.create_texture(
        size=(largura, altura, 1),
        dimension="2d",
        format=formato,
        usage=wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.COPY_SRC,
    )
    buffer = device.create_buffer(
        size=stride * altura,
        usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
    )
    encoder = device.create_command_encoder()
    passagem = encoder.begin_render_pass(
        color_attachments=[wgpu.RenderPassColorAttachment(
            view=textura.create_view(),
            load_op="clear",
            store_op="store",
            clear_value=(0.5, 0.5, 0.5, 1.0),
        )],
    )
    passagem.end()
    encoder.copy_texture_to_buffer(
        wgpu.TexelCopyTextureInfo(texture=textura, mip_level=0, origin=(0, 0, 0)),
        wgpu.TexelCopyBufferInfo(
            buffer=buffer, offset=0, bytes_per_row=stride, rows_per_image=altura,
        ),
        (largura, altura, 1),
    )
    device.queue.submit([encoder.finish()])
    buffer.map_sync(wgpu.MapMode.READ)
    try:
        dados = bytes(buffer.read_mapped(copy=True))
    finally:
        buffer.unmap()
    primeiro = list(dados[:4])
    if formato.startswith("bgra"):
        primeiro = [primeiro[2], primeiro[1], primeiro[0], primeiro[3]]
    return primeiro


def diagnosticar():
    # A instância é restringida a Vulkan antes de pedir adaptador/contexto.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo" / "makehuman" / "lib"))
    from vulkan_runtime import preparar_instancia_vulkan
    preparar_instancia_vulkan()
    import wgpu
    from PyQt5 import QtWidgets
    from rendercanvas.qt import QRenderWidget

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    canvas = QRenderWidget(update_mode="ondemand")
    canvas.resize(64, 64)
    canvas.show()
    app.processEvents()
    try:
        contexto = canvas.get_wgpu_context()
        adapter = wgpu.gpu.request_adapter_sync(
            power_preference="high-performance", canvas=canvas,
        )
        if adapter is None:
            raise RuntimeError("Nenhum adaptador Vulkan disponível")
        if "vulkan" not in str(adapter.info).lower():
            raise RuntimeError("Adaptador não Vulkan: " + str(adapter.info))
        preferido = str(contexto.get_preferred_format(adapter))
        device = adapter.request_device_sync()
        formatos = list(dict.fromkeys((
            "rgba8unorm", "rgba8unorm-srgb", preferido,
        )))
        amostras = {formato: _amostra_clear(device, wgpu, formato)
                    for formato in formatos}
        linear = amostras["rgba8unorm"]
        srgb = amostras["rgba8unorm-srgb"]
        if not all(abs(v - 128) <= 1 for v in linear[:3]):
            raise RuntimeError("Clear UNORM linear 0,5 diferente de 128: " + str(linear))
        if not all(abs(v - 188) <= 1 for v in srgb[:3]):
            raise RuntimeError("Clear sRGB linear 0,5 diferente de 188: " + str(srgb))
        return {
            "estado": "DIAGNOSTICO_ISOLADO",
            "adaptador": str(adapter.info),
            "formato_preferido_qt": preferido,
            "formato_preferido_e_srgb": preferido.endswith("-srgb"),
            "cor_linear_de_entrada": [0.5, 0.5, 0.5, 1.0],
            "amostras_rgba_8bit": amostras,
            "conversao_de_clear_observada": True,
            "nota": "Não testa o shader Phong, a cena real ou o original OpenGL.",
        }
    finally:
        canvas.close()
        app.processEvents()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Arquivo de saída para evidências")
    args = parser.parse_args()
    resultado = diagnosticar()
    texto = json.dumps(resultado, ensure_ascii=False, indent=2) + "\n"
    print(texto, end="", flush=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
