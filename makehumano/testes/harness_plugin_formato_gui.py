"""Plugin de teste TRANSITÓRIO: carregado somente pelo harness isolado de CI.

Este arquivo está em testes/; é copiado temporariamente à pasta de plugins
apenas durante a execução do runner. Não integra o produto final.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

from PyQt5 import QtCore
from core import G


def load(app):
    destino = os.environ.get("MAKEHUMANO_HARNESS_FORMATO_JSON")
    if not destino:
        raise RuntimeError("Harness isolado sem destino JSON")

    testes = os.environ["MAKEHUMANO_HARNESS_TESTES_DIR"]
    if testes not in sys.path:
        sys.path.insert(0, testes)
    from observar_formato_cena_vulkan import observar_captura_offscreen

    destino = Path(destino)
    provisorio = destino.with_name(destino.stem + "-observacao.json")
    png = Path(os.environ["MAKEHUMANO_HARNESS_FORMATO_PNG"])
    iniciado = False

    def medir():
        nonlocal iniciado
        if iniciado:
            return
        if not getattr(app, "_startup_complete", False):
            QtCore.QTimer.singleShot(200, medir)
            return
        iniciado = True
        try:
            import mh
            import numpy as np

            # Este é exatamente o canvas usado pelo serviço mh.renderToBuffer.
            canvas = G.canvas
            cena = canvas._garantir_cena()
            with observar_captura_offscreen(cena, provisorio):
                imagem = mh.renderToBuffer(1024, 768)

            evidencia = json.loads(provisorio.read_text(encoding="utf-8"))
            dados = np.asarray(imagem.data)
            if dados.ndim != 3 or dados.shape[:2] != (768, 1024):
                raise RuntimeError(f"Imagem inesperada: {dados.shape}")
            if dados.dtype != np.uint8 or dados.shape[2] not in (3, 4):
                raise RuntimeError(f"Formato de pixels inesperado: {dados.dtype}, {dados.shape}")

            png.parent.mkdir(parents=True, exist_ok=True)
            imagem.save(str(png))
            material = getattr(app.selectedHuman, "material", None)
            evidencia.update({
                "origem": "GUI original Vulkan / harness temporario CI",
                "pareado_com_opengl": False,
                "shader_material_observado": str(getattr(material, "shader", None)),
                "numpy": np.__version__,
                "pixel_canto_superior_esquerdo": [int(x) for x in dados[0, 0]],
                "dimensoes_imagem": [int(dados.shape[1]), int(dados.shape[0])],
                "sha256_bytes_rgb": hashlib.sha256(dados.tobytes()).hexdigest(),
                "sha256_png": hashlib.sha256(png.read_bytes()).hexdigest(),
                "arquivo_png": str(png),
            })
            # Escrever o relatório final somente quando a captura e o
            # checksum tiverem terminado; o runner espera por ESTE arquivo.
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(
                json.dumps(evidencia, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("MAKEHUMANO_HARNESS_FORMATO: " + json.dumps({
                "estado": evidencia["estado"],
                "formato_cena": evidencia["formato_cena_inicial"],
                "texturas": evidencia["texturas_offscreen_observadas"],
                "pixel_canto": evidencia["pixel_canto_superior_esquerdo"],
            }, ensure_ascii=False), flush=True)
        except BaseException as exc:
            traceback.print_exc()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps({
                "estado": "ERRO",
                "erro": f"{type(exc).__name__}: {exc}",
                "pareado_com_opengl": False,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # O carregamento de plugins ocorre ANTES de loadFinish e do primeiro
    # frame. Agendar a captura, sem adicionar widgets ou eventos à GUI.
    QtCore.QTimer.singleShot(200, medir)


def unload(app):
    pass
