"""Canvas Vulkan definitivo da janela Qt original do MakeHuman.

Reutiliza os handlers de eventos originais e o QRenderWidget. Não cria
contexto OpenGL; framebuffers offscreen e operações de captura usam wgpu.
Shaders GLSL personalizados continuam pendentes de migração.
"""

import os

from PyQt5 import QtCore, QtWidgets
from core import G
import events3d


def salvar_frame_smoke(marker, name, pixels):
    """Conservar capturas reais da GPU junto aos logs opcionais da CI."""
    from image import Image
    Image(data=pixels).save(os.path.join(os.path.dirname(marker), name + ".png"))


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
            self._erro_inicializacao = None
            self._pronto = False
            # O contexto nativo pode criar a instância global wgpu antes
            # do primeiro request_adapter. O runtime deve existir ANTES.
            from vulkan_runtime import preparar_runtime_vulkan
            preparar_runtime_vulkan()
            if os.environ.get("MAKEHUMANO_VULKAN_DEBUG") == "1":
                import wgpu
                wgpu.logger.setLevel("DEBUG")
            from vulkan_runtime import preparar_instancia_vulkan
            preparar_instancia_vulkan()
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
            if self._erro_inicializacao is not None:
                return
            try:
                self._garantir_cena()
            except Exception as error:
                import sys
                self._erro_inicializacao = error
                sys.excepthook(*sys.exc_info())

                def informar_falha():
                    if not os.environ.get("MAKEHUMANO_SMOKE_READY_FILE"):
                        QtWidgets.QMessageBox.critical(
                            self, "MakeHumano — falha ao iniciar Vulkan",
                            "Não foi possível inicializar a renderização Vulkan.\n\n"
                            + str(self._erro_inicializacao)
                            + "\n\nConsulte MakeHumano-erro.txt e o log de inicialização.",
                        )
                    QtWidgets.QApplication.exit(1)

                QtCore.QTimer.singleShot(0, informar_falha)
                return
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
            if (self._cena.objetos_desenhados
                    and getattr(self.app, "_startup_complete", False)):
                # Capturar somente a cena final, após plugins, iluminação
                # e morph targets; quadros durante a carga não são referência.
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
                    from vulkan_smoke_projection import validar_projecao
                    validar_projecao(skin_marker)
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
                        salvar_frame_smoke(xray_marker, "xray", pixels)
                        with open(xray_marker, "w", encoding="utf-8") as saida:
                            saida.write(
                                "vulkan-xray:160x120:"
                                + str(int(cobertura)) + "\n"
                            )
                        print(
                            "MAKEHUMANO_VULKAN: xray WGSL, pixels="
                            + str(cobertura), flush=True,
                        )
                skin_shader_marker = os.environ.get(
                    "MAKEHUMANO_VULKAN_SKIN_SHADER_FILE"
                )
                if skin_shader_marker and not os.path.exists(skin_shader_marker):
                    # Shader de pele GLSL (não confundir com mh.renderSkin UV).
                    # Compara duas gradientMaps na mesma malha MakeHuman.
                    import numpy as np
                    from image import Image
                    from types import SimpleNamespace

                    candidatos = [
                        obj for obj in G.world
                        if obj.visibility and obj.solid
                        and len(obj.primitives) > 100
                    ]
                    if not candidatos:
                        raise RuntimeError(
                            "Skin shader: nenhuma malha original disponível"
                        )
                    corpo = max(candidatos, key=lambda o: len(o.primitives))
                    oclusao = Image(data=np.full(
                        (8, 8, 4), 255, dtype=np.uint8,
                    ))
                    vermelho = Image(data=np.tile(
                        np.array([255, 30, 30, 255], dtype=np.uint8),
                        (1, 16, 1),
                    ))
                    azul = Image(data=np.tile(
                        np.array([30, 30, 255, 255], dtype=np.uint8),
                        (1, 16, 1),
                    ))

                    class MaterialSkinShaderSmoke:
                        shader = "data/shaders/glsl/skin"
                        shaderConfig = {
                            "diffuse": True, "ambientOcclusion": True,
                        }

                        def __init__(self, original, gradiente):
                            self.original = original
                            self.shaderParameters = {
                                "ambientOcclusionMap": oclusao,
                                "gradientMap": gradiente,
                            }

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    class ObjetoSkinShaderSmoke:
                        def __init__(self, original, gradiente):
                            self.original = original
                            self.material = MaterialSkinShaderSmoke(
                                original.material, gradiente,
                            )

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    iluminacao_anterior = self._cena._cena_luzes
                    self._cena.atualizar_iluminacao(
                        SimpleNamespace(
                            environment=SimpleNamespace(
                                ambience=(0.1, 0.1, 0.1),
                            ),
                            lights=[SimpleNamespace(
                                position=(100.0, 200.0, 200.0),
                                color=(1.0, 1.0, 1.0),
                            )],
                        ),
                    )
                    try:
                        vermelho_rgba = self._cena.capturar_framebuffer(
                            [ObjetoSkinShaderSmoke(corpo, vermelho)],
                            G.cameras, 160, 120, incluir_alfa=True,
                            cor_fundo=(0, 0, 0, 0),
                        )
                        azul_rgba = self._cena.capturar_framebuffer(
                            [ObjetoSkinShaderSmoke(corpo, azul)],
                            G.cameras, 160, 120, incluir_alfa=True,
                            cor_fundo=(0, 0, 0, 0),
                        )
                    finally:
                        self._cena.atualizar_iluminacao(iluminacao_anterior)

                    if vermelho_rgba.shape != (120, 160, 4):
                        raise RuntimeError("Skin shader: RGBA inválido")
                    visiveis = (
                        (vermelho_rgba[:, :, 3] > 0)
                        & (azul_rgba[:, :, 3] > 0)
                    )
                    diferentes = int(np.count_nonzero(
                        visiveis & np.any(
                            vermelho_rgba[:, :, :3] != azul_rgba[:, :, :3],
                            axis=2,
                        )
                    ))
                    if not diferentes:
                        raise RuntimeError(
                            "Skin shader: gradientes não modificaram as cores"
                        )
                    salvar_frame_smoke(skin_shader_marker, "skin-red", vermelho_rgba)
                    salvar_frame_smoke(skin_shader_marker, "skin-blue", azul_rgba)
                    with open(skin_shader_marker, "w", encoding="utf-8") as f:
                        f.write(
                            "vulkan-skin-shader:160x120:"
                            + str(diferentes) + "\n"
                        )
                    print(
                        "MAKEHUMANO_VULKAN: skin shader WGSL pixels="
                        + str(diferentes), flush=True,
                    )
                recorte_marker = os.environ.get(
                    "MAKEHUMANO_VULKAN_RECORTE_FILE"
                )
                if recorte_marker and not os.path.exists(recorte_marker):
                    # Teste funcional: uma camada de alpha zero à frente
                    # não pode ocultar a malha opaca posicionada atrás.
                    import numpy as np
                    from types import SimpleNamespace
                    from image import Image

                    candidatos = [
                        obj for obj in G.world
                        if obj.visibility and obj.solid
                        and len(obj.primitives) > 100
                    ]
                    if not candidatos:
                        raise RuntimeError("Recorte alfa: malha ausente")
                    corpo = max(candidatos, key=lambda o: len(o.primitives))
                    camera = G.cameras[corpo.cameraMode]
                    if not getattr(camera, "updated", True):
                        camera.updateCamera()
                        camera.updated = True
                    _, view = camera.getMatrices(0)
                    view = np.asarray(view, dtype=np.float64)
                    modelo = np.asarray(
                        camera.getModelMatrix(corpo), dtype=np.float64,
                    )
                    eixo_camera = view[:3, :3] @ modelo[:3, :3]
                    deslocamento = np.linalg.solve(
                        eixo_camera, np.array([0.0, 0.0, 0.2]),
                    )

                    def objeto_transformado(delta):
                        base = np.asarray(
                            corpo.object.transform, dtype=np.float32,
                        ).copy()
                        mov = np.eye(4, dtype=np.float32)
                        mov[:3, 3] = delta
                        return SimpleNamespace(
                            transform=base @ mov,
                            lockRotation=corpo.object.lockRotation,
                        )

                    transparente = Image(
                        data=np.zeros((4, 4, 4), dtype=np.uint8),
                    )
                    vermelho = Image(data=np.tile(
                        np.array([255, 0, 0, 255], dtype=np.uint8),
                        (4, 4, 1),
                    ))
                    verde = Image(data=np.tile(
                        np.array([0, 255, 0, 255], dtype=np.uint8),
                        (4, 4, 1),
                    ))

                    class MaterialRecorteSmoke:
                        shader = None
                        shaderParameters = {}
                        shaderConfig = {"normal": False}
                        normalMapTexture = None
                        transparent = False
                        opacity = 1.0

                        def __init__(self, material):
                            self.original = material

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    class ObjetoRecorteSmoke:
                        shadeless = True
                        isTextured = True
                        cull = 0
                        depthless = False
                        visibility = True

                        def __init__(self, imagem, delta, cortado, ordem):
                            self.original = corpo
                            self.texture = imagem
                            self.material = MaterialRecorteSmoke(corpo.material)
                            self.object = objeto_transformado(delta)
                            self.nTransparentPrimitives = int(cortado)
                            self.priority = ordem

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    atras = ObjetoRecorteSmoke(
                        verde, -deslocamento, False, 1,
                    )
                    frente_vazio = ObjetoRecorteSmoke(
                        transparente, deslocamento, True, 0,
                    )
                    frente_opaco = ObjetoRecorteSmoke(
                        vermelho, deslocamento, False, 0,
                    )

                    def capturar_recorte(objetos):
                        return self._cena.capturar_framebuffer(
                            objetos, G.cameras, 160, 120,
                            incluir_alfa=True, cor_fundo=(0, 0, 0, 0),
                        )

                    apenas_atras = capturar_recorte([atras])
                    com_vazio = capturar_recorte([frente_vazio, atras])
                    com_frente = capturar_recorte([frente_opaco, atras])
                    if not np.any(apenas_atras[:, :, 3] > 0):
                        raise RuntimeError("Recorte alfa: fundo invisível")
                    if not np.array_equal(apenas_atras, com_vazio):
                        raise RuntimeError(
                            "Recorte alfa: camada vazia alterou o fundo"
                        )
                    diferencas = int(np.count_nonzero(np.any(
                        apenas_atras[:, :, :3] != com_frente[:, :, :3],
                        axis=2,
                    )))
                    if not diferencas:
                        raise RuntimeError(
                            "Recorte alfa: camada opaca não alterou a imagem"
                        )
                    # Camadas com o mesmo priority devem ter resultado
                    # idêntico independentemente da ordem de entrada.
                    # Fundo opaco + duas texturas com alpha parcial, com
                    # distâncias diferentes da câmera original.
                    vermelho_meio = Image(data=np.tile(
                        np.array([255, 20, 20, 128], dtype=np.uint8),
                        (4, 4, 1),
                    ))
                    azul_meio = Image(data=np.tile(
                        np.array([20, 20, 255, 128], dtype=np.uint8),
                        (4, 4, 1),
                    ))
                    base_opaca = ObjetoRecorteSmoke(
                        verde, -2.0 * deslocamento, False, 0,
                    )
                    camada_longe = ObjetoRecorteSmoke(
                        vermelho_meio, -deslocamento, True, 0,
                    )
                    camada_perto = ObjetoRecorteSmoke(
                        azul_meio, deslocamento, True, 0,
                    )
                    composicao_1 = capturar_recorte([
                        camada_perto, camada_longe, base_opaca,
                    ])
                    composicao_2 = capturar_recorte([
                        base_opaca, camada_longe, camada_perto,
                    ])
                    if not np.array_equal(composicao_1, composicao_2):
                        raise RuntimeError(
                            "Mistura alpha depende da ordem de G.world"
                        )
                    if np.array_equal(
                        composicao_1, capturar_recorte([base_opaca])
                    ):
                        raise RuntimeError(
                            "Camadas translúcidas não alteraram o fundo"
                        )
                    # Duas camadas da mesma malha: a ordem dos triângulos
                    # de entrada também não pode alterar a composição alpha.
                    class MalhaCamadasSmoke(ObjetoRecorteSmoke):
                        isTextured = False

                        def __init__(self, inverter):
                            super().__init__(None, np.zeros(3), True, 0)
                            self.verts = np.concatenate((
                                corpo.verts - deslocamento,
                                corpo.verts + deslocamento,
                            ))
                            n = len(corpo.verts)
                            self.norms = np.concatenate((corpo.norms, corpo.norms))
                            self.UVs = np.concatenate((corpo.UVs, corpo.UVs))
                            self.color = np.concatenate((
                                np.tile([255, 20, 20, 128], (n, 1)),
                                np.tile([20, 20, 255, 128], (n, 1)),
                            )).astype(np.uint8)
                            self.primitives = np.concatenate((
                                corpo.primitives, corpo.primitives + n,
                            ))
                            if inverter:
                                self.primitives = self.primitives[::-1].copy()
                            self.nTransparentPrimitives = len(self.primitives)

                    mesma_malha_1 = capturar_recorte([MalhaCamadasSmoke(False)])
                    mesma_malha_2 = capturar_recorte([MalhaCamadasSmoke(True)])
                    if not np.array_equal(mesma_malha_1, mesma_malha_2):
                        raise RuntimeError("Alpha dentro da malha depende da ordem dos triângulos")
                    if not np.any(mesma_malha_1[:, :, 3] > 0):
                        raise RuntimeError("Malha de teste alpha não desenhou pixels")
                    salvar_frame_smoke(recorte_marker, "transparent-triangles", mesma_malha_1)
                    salvar_frame_smoke(recorte_marker, "transparent-triangles-reversed", mesma_malha_2)
                    with open(recorte_marker, "w", encoding="utf-8") as f:
                        f.write(
                            "vulkan-recorte:160x120:"
                            + str(diferencas) + ":camadas-ok\n"
                        )
                    print(
                        "MAKEHUMANO_VULKAN: alpha test e camadas RGB, pixels="
                        + str(diferencas), flush=True,
                    )
                normal_marker = os.environ.get(
                    "MAKEHUMANO_VULKAN_NORMALMAP_FILE"
                )
                if normal_marker and not os.path.exists(normal_marker):
                    # Compara duas normais amostradas na MESMA malha.
                    # A iluminação artificial é limitada ao teste e
                    # restaurada, sem alterar a cena real do MakeHuman.
                    import numpy as np
                    from types import SimpleNamespace
                    from image import Image

                    candidatos = [
                        obj for obj in G.world
                        if obj.visibility and obj.solid
                        and len(obj.primitives) > 100
                    ]
                    if not candidatos:
                        raise RuntimeError(
                            "Normalmap: nenhuma malha original disponível"
                        )
                    corpo = max(candidatos, key=lambda o: len(o.primitives))
                    mapa_flat = Image(data=np.tile(
                        np.array([128, 128, 255, 255], dtype=np.uint8),
                        (8, 8, 1),
                    ))
                    mapa_inclinado = Image(data=np.tile(
                        np.array([255, 128, 128, 255], dtype=np.uint8),
                        (8, 8, 1),
                    ))

                    class MaterialNormalSmoke:
                        shader = "data/shaders/glsl/normalmap"
                        shaderConfig = {"normal": True, "diffuse": True}

                        def __init__(self, original, imagem):
                            self.original = original
                            self.normalMapTexture = imagem
                            self.shaderParameters = {
                                "normalmapTexture": imagem,
                            }

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    class ObjetoNormalSmoke:
                        def __init__(self, original, imagem):
                            self.original = original
                            self.material = MaterialNormalSmoke(
                                original.material, imagem,
                            )

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    iluminacao_anterior = self._cena._cena_luzes
                    self._cena.atualizar_iluminacao(
                        SimpleNamespace(
                            environment=SimpleNamespace(
                                ambience=(0.1, 0.1, 0.1),
                            ),
                            lights=[SimpleNamespace(
                                position=(100.0, 200.0, 200.0),
                                color=(1.0, 1.0, 1.0),
                            )],
                        )
                    )
                    try:
                        flat = self._cena.capturar_framebuffer(
                            [ObjetoNormalSmoke(corpo, mapa_flat)],
                            G.cameras, 160, 120, incluir_alfa=True,
                            cor_fundo=(0, 0, 0, 0),
                        )
                        inclinado = self._cena.capturar_framebuffer(
                            [ObjetoNormalSmoke(corpo, mapa_inclinado)],
                            G.cameras, 160, 120, incluir_alfa=True,
                            cor_fundo=(0, 0, 0, 0),
                        )
                    finally:
                        self._cena.atualizar_iluminacao(iluminacao_anterior)

                    if flat.shape != (120, 160, 4):
                        raise RuntimeError("Normalmap: RGBA com tamanho errado")
                    visiveis = (flat[:, :, 3] > 0) & (
                        inclinado[:, :, 3] > 0
                    )
                    diferentes = int(np.count_nonzero(
                        visiveis & np.any(
                            flat[:, :, :3] != inclinado[:, :, :3],
                            axis=2,
                        )
                    ))
                    if not diferentes:
                        raise RuntimeError(
                            "Normalmap: mudar a normal não alterou as cores"
                        )
                    # A cena original separa Light.color de Light.specular.
                    # Sem difusa/ambiente, uma luz especular branca ainda
                    # precisa produzir reflexos; preta deve apagá-los.
                    def reflexo_da_cena(cor_especular):
                        self._cena.atualizar_iluminacao(SimpleNamespace(
                            environment=SimpleNamespace(ambience=(0.0, 0.0, 0.0)),
                            lights=[SimpleNamespace(
                                position=np.linalg.inv(np.asarray(view))[:3, 3],
                                color=(0.0, 0.0, 0.0), specular=cor_especular,
                            )],
                        ))
                        return self._cena.capturar_framebuffer(
                            [ObjetoNormalSmoke(corpo, mapa_flat)], G.cameras,
                            160, 120, incluir_alfa=True, cor_fundo=(0, 0, 0, 0),
                        )

                    # Usar a mesma view real que a cena, sem mover a câmera.
                    _, view = G.cameras[corpo.cameraMode].getMatrices(0)
                    try:
                        reflexo_branco = reflexo_da_cena((1.0, 1.0, 1.0))
                        reflexo_preto = reflexo_da_cena((0.0, 0.0, 0.0))
                    finally:
                        self._cena.atualizar_iluminacao(iluminacao_anterior)
                    if np.array_equal(reflexo_branco, reflexo_preto):
                        raise RuntimeError("Light.specular não altera reflexos do shader normalmap")
                    salvar_frame_smoke(normal_marker, "normalmap-flat", flat)
                    salvar_frame_smoke(normal_marker, "normalmap-tilted", inclinado)
                    salvar_frame_smoke(normal_marker, "specular-white", reflexo_branco)
                    salvar_frame_smoke(normal_marker, "specular-black", reflexo_preto)
                    with open(normal_marker, "w", encoding="utf-8") as saida:
                        saida.write(
                            "vulkan-normalmap:160x120:"
                            + str(diferentes) + "\n"
                        )
                    print(
                        "MAKEHUMANO_VULKAN: normalmap WGSL pixels="
                        + str(diferentes), flush=True,
                    )
                estilos_marker = os.environ.get(
                    "MAKEHUMANO_VULKAN_ESTILOS_FILE"
                )
                if estilos_marker and not os.path.exists(estilos_marker):
                    # Exercita Phong e Toon em uma malha real, preservando
                    # inteiramente a geometria e os materiais do usuário.
                    import numpy as np
                    candidatos = [
                        obj for obj in G.world
                        if obj.visibility and obj.solid
                        and len(obj.primitives) > 100
                    ]
                    if not candidatos:
                        raise RuntimeError(
                            "Phong/Toon: nenhuma malha original para teste"
                        )
                    corpo = max(
                        candidatos, key=lambda obj: len(obj.primitives),
                    )

                    class MaterialEstiloSmoke:
                        def __init__(self, original, estilo):
                            self.original = original
                            self.shader = "data/shaders/glsl/" + estilo
                            self.shaderParameters = (
                                {
                                    "silhouetteThreshold": 0.6,
                                    "shininess": 20,
                                    "ambientIntensity": 0.1,
                                    "specularIntensity": 0.15,
                                    "diffuseIntensity": 0.4,
                                    "specular_th": 0.3,
                                    "diffuse_th": 0.5,
                                } if estilo == "toon" else {}
                            )
                            self.shaderConfig = {
                                "diffuse": True, "normal": False,
                            }

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    class ObjetoEstiloSmoke:
                        def __init__(self, original, estilo):
                            self.original = original
                            self.material = MaterialEstiloSmoke(
                                original.material, estilo,
                            )

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    def renderizar_estilo(nome):
                        return self._cena.capturar_framebuffer(
                            [ObjetoEstiloSmoke(corpo, nome)], G.cameras,
                            160, 120, incluir_alfa=True,
                            cor_fundo=(0, 0, 0, 0),
                        )

                    phong_rgba = renderizar_estilo("phong")
                    toon_rgba = renderizar_estilo("toon")
                    if (phong_rgba.shape != (120, 160, 4)
                            or toon_rgba.shape != (120, 160, 4)):
                        raise RuntimeError("Phong/Toon: tamanho RGBA inválido")
                    intersecao = (
                        (phong_rgba[:, :, 3] > 0)
                        & (toon_rgba[:, :, 3] > 0)
                    )
                    diferencas = int(np.count_nonzero(
                        intersecao
                        & np.any(
                            phong_rgba[:, :, :3] != toon_rgba[:, :, :3],
                            axis=2,
                        )
                    ))
                    if not diferencas:
                        raise RuntimeError(
                            "Phong/Toon: shaders não diferenciaram os pixels"
                        )
                    salvar_frame_smoke(estilos_marker, "phong", phong_rgba)
                    salvar_frame_smoke(estilos_marker, "toon", toon_rgba)
                    with open(estilos_marker, "w", encoding="utf-8") as saida:
                        saida.write(
                            "vulkan-phong-toon:160x120:"
                            + str(diferencas) + "\n"
                        )
                    print(
                        "MAKEHUMANO_VULKAN: Phong e Toon WGSL, diferenças="
                        + str(diferencas), flush=True,
                    )
                litsphere_marker = os.environ.get(
                    "MAKEHUMANO_VULKAN_LITSPHERE_FILE"
                )
                if litsphere_marker and not os.path.exists(litsphere_marker):
                    # Verifica o port do material de pele numa malha original,
                    # sem alterar o material ou os dados do personagem.
                    import mh
                    import numpy as np
                    from image import Image
                    candidatos = [
                        obj for obj in G.world
                        if obj.visibility and obj.solid
                        and len(obj.primitives) > 100
                    ]
                    if not candidatos:
                        raise RuntimeError(
                            "LitSphere: nenhuma malha original para o smoke"
                        )
                    corpo = max(
                        candidatos, key=lambda obj: len(obj.primitives),
                    )
                    imagem_pele = Image(
                        mh.getSysDataPath("litspheres/skinmat_caucasian.png")
                    )
                    imagem_pele_alternativa = Image(
                        mh.getSysDataPath("litspheres/skinmat_african.png")
                    )

                    class MaterialLitSphereSmoke:
                        shader = "data/shaders/glsl/litsphere"
                        shaderConfig = {
                            "diffuse": False, "vertexColors": False,
                            "normal": False,
                        }

                        def __init__(self, original, imagem):
                            self.original = original
                            self.shaderParameters = {
                                "litsphereTexture": imagem,
                                "AdditiveShading": 0.0,
                            }

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    class ObjetoLitSphereSmoke:
                        def __init__(self, original, imagem):
                            self.original = original
                            self.material = MaterialLitSphereSmoke(
                                original.material, imagem,
                            )

                        def __getattr__(self, nome):
                            return getattr(self.original, nome)

                    rgba = self._cena.capturar_framebuffer(
                        [ObjetoLitSphereSmoke(corpo, imagem_pele)], G.cameras,
                        160, 120, incluir_alfa=True,
                        cor_fundo=(0, 0, 0, 0),
                    )
                    if rgba.shape != (120, 160, 4):
                        raise RuntimeError("LitSphere: buffer RGBA inválido")
                    cobertura = int(np.count_nonzero(rgba[:, :, 3]))
                    if not cobertura:
                        raise RuntimeError(
                            "LitSphere: nenhum pixel de pele renderizado"
                        )
                    alternativo = self._cena.capturar_framebuffer(
                        [
                            ObjetoLitSphereSmoke(
                                corpo, imagem_pele_alternativa,
                            )
                        ],
                        G.cameras, 160, 120, incluir_alfa=True,
                        cor_fundo=(0, 0, 0, 0),
                    )
                    mascara = (rgba[:, :, 3] > 0) & (
                        alternativo[:, :, 3] > 0
                    )
                    diferentes = int(np.count_nonzero(
                        mascara & np.any(
                            rgba[:, :, :3] != alternativo[:, :, :3],
                            axis=2,
                        )
                    ))
                    if not diferentes:
                        raise RuntimeError(
                            "LitSphere: trocar a textura não mudou os pixels"
                        )
                    salvar_frame_smoke(litsphere_marker, "litsphere", rgba)
                    with open(litsphere_marker, "w", encoding="utf-8") as saida:
                        saida.write(
                            "vulkan-litsphere:160x120:"
                            + str(cobertura) + ":"
                            + str(diferentes) + "\n"
                        )
                    print(
                        "MAKEHUMANO_VULKAN: LitSphere WGSL cobertura="
                        + str(cobertura) + ", cores diferentes="
                        + str(diferentes), flush=True,
                    )
                maps_marker = os.environ.get("MAKEHUMANO_VULKAN_MATERIAL_MAPS_FILE")
                if maps_marker and not os.path.exists(maps_marker):
                    from vulkan_smoke_materials import validar_mapas
                    validar_mapas(self._cena, G.cameras, G.world, maps_marker)
                lights_marker = os.environ.get("MAKEHUMANO_VULKAN_LIGHT_CONTROLS_FILE")
                if lights_marker and not os.path.exists(lights_marker):
                    from vulkan_smoke_lighting import validar_luzes
                    from vulkan_smoke_multisampling import validar_multisampling
                    validar_multisampling(self._cena, G.cameras, G.world, lights_marker)
                    validar_luzes(self._cena, G.cameras, G.world, self.app, lights_marker)
                caminho = os.environ.get("MAKEHUMANO_VULKAN_FRAME_FILE")
                if caminho and not os.path.exists(caminho):
                    from pathlib import Path
                    from vulkan_smoke_shadows import validar_sombras
                    validar_sombras(self._cena, G.cameras, G.world, Path(caminho).parent)
                    from vulkan_smoke_displacement import validar_displacement
                    validar_displacement(self._cena, G.cameras, G.world,
                                         str(Path(caminho).parent / "displacement.json"))
                    with open(caminho, "w", encoding="utf-8") as saida:
                        saida.write(
                            "vulkan-makehuman-original:"
                            + str(self._cena.objetos_desenhados) + "\n"
                        )

    CanvasVulkan.__name__ = "CanvasVulkan"
    return CanvasVulkan
