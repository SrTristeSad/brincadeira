"""Canvas Vulkan definitivo da janela Qt original do MakeHuman.

Reutiliza os handlers de eventos originais e o QRenderWidget. Não cria
contexto OpenGL; framebuffers offscreen e operações de captura usam wgpu.
Shaders GLSL personalizados continuam pendentes de migração.
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

        def atualizar_iluminacao(self, cena):
            """Recebe a cena de luzes original sem invocar o antigo glmodule."""
            self._cena_luzes = cena
            if self._cena is not None:
                self._cena.atualizar_iluminacao(cena)
            self.request_redraw()

        def _garantir_cena(self):
            """Inicializa uma única instância GPU para viewport e offscreen."""
            if self._cena is None:
                self._cena = CenaVulkan(self)
                self._cena.atualizar_iluminacao(
                    getattr(self, "_cena_luzes", None)
                    or getattr(self.app, "scene", None)
                )
                self.app.logger_redraw.info(
                    "Canvas Vulkan ORIGINAL: %s", self._cena.adapter.info,
                )
            return self._cena

        def renderToBuffer(self, width, height, productionRender=True):
            """Substitui mh.renderToBuffer por renderização real no Vulkan."""
            from image import Image
            width, height = int(width), int(height)
            if width <= 0 or height <= 0:
                raise RuntimeError("Resolução de produção inválida")
            cena = self._garantir_cena()
            pixels = cena.capturar_framebuffer(
                G.world, G.cameras, width, height,
                productionRender=productionRender,
                cor_fundo=(0.5, 0.5, 0.5, 1.0),
            )
            return Image(data=pixels)

        def renderAlphaMask(self, width, height, productionRender=True):
            """Máscara em escala de cinza obtida do alfa real da GPU."""
            from image import Image
            from vulkan_offscreen import mascarar_alfa_rgba
            width, height = int(width), int(height)
            if width <= 0 or height <= 0:
                raise RuntimeError("Resolução da máscara inválida")
            cena = self._garantir_cena()
            pixels = cena.capturar_framebuffer(
                G.world, G.cameras, width, height,
                incluir_alfa=True,
                productionRender=productionRender,
                cor_fundo=(0.5, 0.5, 0.5, 0.0),
            )
            return Image(data=mascarar_alfa_rgba(pixels))

        def renderSkin(self, dst, vertsPerPrimitive, verts, index=None,
                       objectMatrix=None, texture=None, UVs=None,
                       textureMatrix=None, color=None, clearColor=None):
            """Rasteriza skins e mapas UV originais diretamente em Vulkan."""
            from vulkan_skin import render_skin
            return render_skin(
                self._garantir_cena(), dst, vertsPerPrimitive, verts,
                index=index, objectMatrix=objectMatrix, texture=texture,
                UVs=UVs, textureMatrix=textureMatrix, color=color,
                clearColor=clearColor,
            )

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
            self._garantir_cena()
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
                    # Exercita resolução diferente da viewport para validar
                    # projeção offscreen sem alterar as câmeras da GUI.
                    pixels = self._cena.capturar_framebuffer(
                        G.world, G.cameras, 320, 240,
                    )
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
                render_marker = os.environ.get("MAKEHUMANO_VULKAN_RENDER_FILE")
                if render_marker and not os.path.exists(render_marker):
                    # Exercita a mesma API pública usada pelo renderer original.
                    import mh
                    rgb = mh.renderToBuffer(160, 120)
                    alfa = mh.renderAlphaMask(160, 120)
                    if rgb.data.shape != (120, 160, 3):
                        raise RuntimeError("renderToBuffer Vulkan: tamanho incorreto")
                    if alfa.data.shape != (120, 160, 3):
                        raise RuntimeError("renderAlphaMask Vulkan: tamanho incorreto")
                    if (alfa.data[:, :, 0] != alfa.data[:, :, 1]).any() or (
                        alfa.data[:, :, 0] != alfa.data[:, :, 2]
                    ).any():
                        raise RuntimeError("Máscara alfa Vulkan não é cinza")
                    with open(render_marker, "w", encoding="utf-8") as saida:
                        saida.write(
                            "vulkan-render:160x120:"
                            + str(int(alfa.data.min())) + "-"
                            + str(int(alfa.data.max())) + "\n"
                        )
                    print(
                        "MAKEHUMANO_VULKAN: renderToBuffer e renderAlphaMask OK",
                        flush=True,
                    )
                skin_marker = os.environ.get("MAKEHUMANO_VULKAN_SKIN_FILE")
                if skin_marker and not os.path.exists(skin_marker):
                    import mh
                    import numpy as np
                    vertices = np.array(
                        [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]], np.float32,
                    )
                    cores = np.array([[255, 40, 20, 255]] * 3, np.uint8)
                    img = mh.renderSkin(
                        (96, 96), 3, vertices, color=cores,
                        clearColor=(0, 0, 0, 0),
                    )
                    if img.data.shape != (96, 96, 3) or img.data.max() == 0:
                        raise RuntimeError("renderSkin Vulkan não desenhou UVs")
                    with open(skin_marker, "w", encoding="utf-8") as saida:
                        saida.write("vulkan-skin:96x96\n")
                    print("MAKEHUMANO_VULKAN: renderSkin UV OK", flush=True)
                xray_marker = os.environ.get("MAKEHUMANO_VULKAN_XRAY_FILE")
                if xray_marker and not os.path.exists(xray_marker):
                    # Renderizar o shader xray com um wrapper local: o material
                    # e a malha do usuário NÃO são modificados pelo smoke.
                    candidatos = [
                        objeto for objeto in G.world
                        if objeto.visibility and objeto.solid
                        and len(objeto.primitives) > 100
                    ]
                    if candidatos:
                        base = max(candidatos, key=lambda o: len(o.primitives))

                        class MaterialXraySmoke:
                            shader = "data/shaders/glsl/xray"
                            shaderParameters = {
                                "edgefalloff": 1.0, "intensity": 0.7,
                            }
                            shaderConfig = {
                                "diffuse": False, "vertexColors": False,
                            }
                            transparent = True

                            def __init__(self, original):
                                self.original = original

                            def __getattr__(self, nome):
                                return getattr(self.original, nome)

                        class ObjetoXraySmoke:
                            def __init__(self, original):
                                self.original = original
                                self.material = MaterialXraySmoke(
                                    original.material,
                                )

                            def __getattr__(self, nome):
                                return getattr(self.original, nome)

                        pixels = self._cena.capturar_framebuffer(
                            [ObjetoXraySmoke(base)], G.cameras,
                            160, 120, incluir_alfa=True,
                            cor_fundo=(0, 0, 0, 0),
                        )
                        if pixels.shape != (120, 160, 4):
                            raise RuntimeError("Shader xray: tamanho RGBA inválido")
                        import numpy as np
                        cobertura = np.count_nonzero(pixels[:, :, 3])
                        if not cobertura:
                            raise RuntimeError("Shader xray não gerou cobertura")
                        with open(xray_marker, "w", encoding="utf-8") as saida:
                            saida.write(
                                "vulkan-xray:160x120:"
                                + str(int(cobertura)) + "\n"
                            )
                        print(
                            "MAKEHUMANO_VULKAN: xray WGSL, pixels="
                            + str(cobertura), flush=True,
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
