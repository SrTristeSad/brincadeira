"""Canvas Vulkan PILOTO para a janela Qt ORIGINAL do MakeHuman.

Somente ativado via MAKEHUMANO_VULKAN_PILOT=1 durante a migração.
Reutiliza, sem alterar, os handlers de mouse e teclado do Canvas original.
Não importa OpenGL e não solicita contexto QOpenGLWidget.
Ainda não substitui renderização offscreen independente nem shaders legados.
"""

import os

from PyQt5 import QtCore, QtWidgets
from core import G
import events3d


def criar_canvas_vulkan(canvas_original):
    """Adapta os eventos originais mantendo o restante da GUI intocado."""
    # Evita que a seleção automática de wgpu faça fallback ao OpenGL.
    os.environ["WGPU_BACKEND_TYPE"] = "Vulkan"
    from rendercanvas.qt import QRenderWidget
    from vulkan_scene import CenaVulkan

    class CanvasVulkan(QRenderWidget):
        # Os eventos existentes são deliberadamente reaproveitados, não
        # redesenhados. makeCurrent() não cria contexto OpenGL.
        getMousePos = canvas_original.getMousePos
        mousePressEvent = canvas_original.mousePressEvent
        mouseReleaseEvent = canvas_original.mouseReleaseEvent
        mouseUpDownEvent = canvas_original.mouseUpDownEvent
        wheelEvent = canvas_original.wheelEvent
        mouseMoveEvent = canvas_original.mouseMoveEvent
        handleMouse = canvas_original.handleMouse

        def __init__(self, parent, app):
            self.app = app
            self.blockRedraw = False
            self._cena = None
            self._pronto = False
            super().__init__(parent, update_mode="ondemand")
            G.canvas = self
            self.setFocusPolicy(QtCore.Qt.TabFocus)
            self.setFocus()
            self.setMouseTracking(True)
            # QRenderWidget apresenta por bitmap no Qt; forçar
            # WA_NativeWindow aqui interfere com esse mecanismo.
            self.setAttribute(QtCore.Qt.WA_KeyCompression, False)
            self.setMinimumHeight(5)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored
            )
            # RenderCanvas descarta _draw_and_present() enquanto ainda não
            # existe um canvas_context. A cena GPU (adapter/device/pipeline)
            # pode ser criada depois, mas o contexto precisa existir AGORA.
            # Caso contrário, o primeiro callback nunca será invocado.
            self.get_wgpu_context()
            self._pronto = True
            print(
                "MAKEHUMANO_VULKAN: Canvas Qt original conectado",
                flush=True,
            )
            self.request_redraw()

        def makeCurrent(self):
            """Compatibilidade de chamada com handlers Qt, sem contexto GL."""
            pass

        def showEvent(self, event):
            super().showEvent(event)
            print(
                "MAKEHUMANO_VULKAN: showEvent, tamanho="
                + str((self.width(), self.height()))
                + ", fisico=" + str(self.get_physical_size()),
                flush=True,
            )
            self.request_redraw()
            # A viewport pode ser mostrada antes da carga da cena.
            QtCore.QTimer.singleShot(300, self.request_redraw)

        def getPickedColor(self, x=None, y=None):
            """Compatibilidade com mh.getPickedColor, sem tocar em OpenGL."""
            from vulkan_picking import selecionar_cor
            if x is None or y is None:
                pos = self.getMousePos()
                if pos is None:
                    return (0, 0, 0)
                x, y = pos
            return selecionar_cor(
                G.world, G.cameras, x, y,
                G.windowWidth, G.windowHeight,
            )

        def grabScreen(self, x, y, width, height, filename=None,
                       productionRender=False):
            """Captura a viewport já apresentada, sem glReadPixels.

            A API de produção pede outro passe de renderização; não a
            substituímos por uma imagem da janela de forma silenciosa.
            """
            if productionRender:
                raise NotImplementedError(
                    "Captura de produção em Vulkan requer render offscreen"
                )
            if width <= 0 or height <= 0:
                raise RuntimeError("width or height is 0")
            if not self.isVisible():
                raise RuntimeError("Canvas Vulkan não está visível")
            from image import Image
            from vulkan_capture import recortar_captura_rgb
            import numpy as np

            imagem = self.grab().toImage()
            if imagem.isNull():
                raise RuntimeError("Captura Qt da viewport Vulkan indisponível")
            imagem = imagem.convertToFormat(imagem.Format_RGB888)
            # QLabel/QWidget pode devolver pixels físicos em HiDPI.
            # As coordenadas do MakeHuman são as dimensões lógicas do canvas.
            if (imagem.width(), imagem.height()) != (self.width(), self.height()):
                imagem = imagem.scaled(self.width(), self.height())
            largura, altura = imagem.width(), imagem.height()
            stride = imagem.bytesPerLine()
            bruto = imagem.bits().asstring(imagem.byteCount())
            pixels = np.frombuffer(bruto, dtype=np.uint8).reshape(altura, stride)
            pixels = pixels[:, :largura * 3].reshape(altura, largura, 3)
            recorte = recortar_captura_rgb(pixels, x, y, width, height)
            resultado = Image(data=recorte)
            if filename is not None:
                resultado.save(filename)
            return resultado

        def invalidar_texturas(self, caminho=None):
            """Expõe a recarga de texturas à API original do MakeHuman."""
            if self._cena is not None:
                self._cena.invalidar_texturas(caminho)
            self.request_redraw()

        def request_redraw(self):
            # Não sobrescrever QWidget.update(): rendercanvas chama update()
            # internamente para apresentar os quadros. Interceptar update()
            # aqui impediria que o evento de pintura chegasse ao Qt.
            if getattr(self, "_pronto", False):
                self.request_draw(self._desenhar)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            largura, altura = max(1, self.width()), max(1, self.height())
            G.windowWidth = largura
            G.windowHeight = altura
            if getattr(G, "app", None) is not None:
                G.app.callEvent(
                    "onResizedCallback",
                    events3d.ResizeEvent(largura, altura, False),
                )
            self.request_redraw()

        def _desenhar(self):
            if self.blockRedraw:
                return
            if self._cena is None:
                print("MAKEHUMANO_VULKAN: inicializando GPU", flush=True)
                self._cena = CenaVulkan(self)
                self.app.logger_redraw.info(
                    "Canvas Vulkan PILOTO na interface original: %s",
                    self._cena.adapter.info,
                )
            try:
                self._cena.desenhar(
                    G.world, G.cameras, cor_fundo=G.clearColor,
                )
            except Exception:
                import traceback
                traceback.print_exc()
                raise
            if self._cena.frames == 1:
                print(
                    "MAKEHUMANO_VULKAN: primeiro quadro, objetos="
                    + str(self._cena.objetos_desenhados),
                    flush=True,
                )
            if self._cena.objetos_desenhados:
                # Exercita o picking da janela original em smoke (sem
                # glReadPixels); o valor RGB mantém contrato de FaceGroups.
                picking = os.environ.get("MAKEHUMANO_VULKAN_PICK_FILE")
                if picking and not os.path.exists(picking):
                    px = max(0, G.windowWidth // 2)
                    py = max(0, G.windowHeight // 2)
                    cor = self.getPickedColor(px, py)
                    if len(cor) != 3 or not all(
                        isinstance(c, int) and 0 <= c <= 255 for c in cor
                    ):
                        raise RuntimeError(
                            "Seleção Vulkan retornou cor RGB inválida"
                        )
                    with open(picking, "w", encoding="utf-8") as saida:
                        saida.write(",".join(str(v) for v in cor) + "\n")
                    print(
                        "MAKEHUMANO_VULKAN: picking original RGB="
                        + str(cor), flush=True,
                    )
                offscreen = os.environ.get("MAKEHUMANO_VULKAN_OFFSCREEN_FILE")
                if offscreen and not os.path.exists(offscreen):
                    pixels = self._cena.capturar_framebuffer(G.world, G.cameras)
                    if (pixels.ndim != 3 or pixels.shape[2] != 3
                            or pixels.dtype.name != "uint8"
                            or pixels.shape[0] < 1 or pixels.shape[1] < 1):
                        raise RuntimeError("Framebuffer Vulkan retornou RGB inválido")
                    with open(offscreen, "w", encoding="utf-8") as saida:
                        saida.write(
                            "vulkan-offscreen:"
                            + str(pixels.shape[1]) + "x"
                            + str(pixels.shape[0]) + "\n"
                        )
                    print(
                        "MAKEHUMANO_VULKAN: framebuffer offscreen RGB="
                        + str(pixels.shape), flush=True,
                    )
                caminho = os.environ.get("MAKEHUMANO_VULKAN_FRAME_FILE")
                if caminho and not os.path.exists(caminho):
                    with open(caminho, "w", encoding="utf-8") as saida:
                        saida.write(
                            "vulkan-makehuman-original:"
                            + str(self._cena.objetos_desenhados) + "\n"
                        )

    CanvasVulkan.__name__ = "CanvasVulkan"
    return CanvasVulkan
