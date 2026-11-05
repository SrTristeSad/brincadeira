"""Canvas Vulkan PILOTO para a janela Qt ORIGINAL do MakeHuman.

Somente ativado via MAKEHUMANO_VULKAN_PILOT=1 durante a migração.
Reutiliza, sem alterar, os handlers de mouse e teclado do Canvas original.
Não importa OpenGL e não solicita contexto QOpenGLWidget.
Ainda não substitui as APIs glmodule de picking, offscreen e shaders.
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
            self.setAttribute(QtCore.Qt.WA_NativeWindow)
            self.setAttribute(QtCore.Qt.WA_KeyCompression, False)
            self.setMinimumHeight(5)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored
            )
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
            print("MAKEHUMANO_VULKAN: showEvent", flush=True)
            self.request_redraw()
            # A viewport pode ser mostrada antes da carga da cena.
            QtCore.QTimer.singleShot(300, self.request_redraw)

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
                caminho = os.environ.get("MAKEHUMANO_VULKAN_FRAME_FILE")
                if caminho and not os.path.exists(caminho):
                    with open(caminho, "w", encoding="utf-8") as saida:
                        saida.write(
                            "vulkan-makehuman-original:"
                            + str(self._cena.objetos_desenhados) + "\n"
                        )

    CanvasVulkan.__name__ = "CanvasVulkan"
    return CanvasVulkan
