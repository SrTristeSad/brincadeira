"""Primeira ponte Vulkan com a CENA ORIGINAL do MakeHuman (G.world).

Não carrega um segundo personagem, não aplica alvos morfológicos próprios.
Converte o Object3D de renderização que o MakeHuman já atualiza em dados
para GPU. O piloto é incompleto: picking, transparência, render offscreen
e shaders customizados ainda precisam ser migrados antes de remover OpenGL.
"""

import os

import numpy as np


def pixels_textura_rgba(dados):
    """Converte imagem CPU original (cinza, LA, RGB ou RGBA) em RGBA."""
    pixels = np.asarray(dados)
    if pixels.dtype != np.uint8 or pixels.ndim != 3:
        raise ValueError("Imagem Vulkan exige matriz uint8 [H,W,C]")
    if pixels.shape[0] < 1 or pixels.shape[1] < 1:
        raise ValueError("Dimensões da imagem Vulkan inválidas")
    canais = pixels.shape[2]
    if canais == 1:
        cinza = np.repeat(pixels, 3, axis=2)
        pixels = np.concatenate(
            (cinza, np.full((*pixels.shape[:2], 1), 255, np.uint8)), axis=2
        )
    elif canais == 2:
        cinza = np.repeat(pixels[:, :, :1], 3, axis=2)
        pixels = np.concatenate((cinza, pixels[:, :, 1:2]), axis=2)
    elif canais == 3:
        pixels = np.concatenate(
            (pixels, np.full((*pixels.shape[:2], 1), 255, np.uint8)), axis=2
        )
    elif canais != 4:
        raise ValueError("Número de canais de textura não suportado")
    return np.ascontiguousarray(pixels)


def assinatura_textura(caminho):
    """Identifica mudanças de arquivo sem depender de OpenGL ou Qt."""
    if not caminho:
        return None
    try:
        info = os.stat(caminho)
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)



def preparar_malha_original(obj):
    """Retorna vértices float32 [n,12] e triângulos uint32 de Object3D.

    O objeto aqui é lib/object3d.Object3D (já desenhado por glmodule), não
    um novo parser de base.obj. Respeita os índices UV desenrolados e as
    máscaras de faces atualizados pelo próprio module3d.Object3D.
    """
    posicoes = np.asarray(obj.verts, dtype=np.float32)
    if posicoes.ndim != 2 or posicoes.shape[1] != 3:
        raise ValueError("Object3D original: posições inválidas")
    n = len(posicoes)
    normais = np.asarray(obj.norms, dtype=np.float32)
    if normais.shape != posicoes.shape:
        raise ValueError("Object3D original: normais inválidas")
    if obj.hasUVs:
        uvs = np.asarray(obj.UVs, dtype=np.float32)
        if uvs.shape != (n, 2):
            raise ValueError("Object3D original: coordenadas UV inválidas")
    else:
        uvs = np.zeros((n, 2), dtype=np.float32)

    cores = np.asarray(obj.color, dtype=np.uint8)
    if cores.shape != (n, 4):
        raise ValueError("Object3D original: cores RGBA inválidas")
    vertices = np.empty((n, 12), dtype=np.float32)
    vertices[:, :3] = posicoes
    vertices[:, 3:6] = normais
    vertices[:, 6:8] = uvs
    vertices[:, 8:12] = cores.astype(np.float32) / 255.0

    face = np.asarray(obj.primitives)
    # O MakeHuman cria também overlays auxiliares sem faces; eles podem
    # chegar com array vazio unidimensional. Não são erros de geometria.
    if face.size == 0:
        return (
            np.ascontiguousarray(vertices),
            np.empty(0, dtype=np.uint32),
        )
    if face.ndim != 2 or face.shape[1] not in (2, 3, 4):
        raise ValueError(
            "Object3D original: primitiva não triangular não suportada "
            + str(face.shape)
        )
    if np.any(face < 0) or np.any(face >= n):
        raise ValueError("Object3D original: índice de face fora da malha")
    face = np.asarray(face, dtype=np.uint32)
    if face.shape[1] == 4:
        # MakeHuman mantém triangulações na sequência das faces visíveis.
        indices = np.concatenate(
            (face[:, [0, 1, 2]], face[:, [0, 2, 3]]), axis=0
        )
    else:
        indices = face
    if face.shape[1] == 2:
        # O grid e outras linhas auxiliares têm pares de vértices.
        indices = indices[indices[:, 0] != indices[:, 1]]
    else:
        # Quads degenerados são usados pelo MakeHuman para representar tris.
        indices = indices[
            (indices[:, 0] != indices[:, 1])
            & (indices[:, 1] != indices[:, 2])
            & (indices[:, 0] != indices[:, 2])
        ]
    if not np.isfinite(vertices).all():
        raise ValueError("Object3D original: coordenadas não finitas")
    return (np.ascontiguousarray(vertices),
            np.ascontiguousarray(indices.reshape(-1), dtype=np.uint32))


def matriz_wgpu(camera, obj, *, tamanho_origem=None, tamanho_destino=None):
    """Converte câmera original para Vulkan, com proporção opcional offscreen.

    A matriz projetiva é ajustada para o aspecto do destino sem modificar
    G.windowWidth, G.windowHeight nem os parâmetros da câmera original.
    """
    if (tamanho_origem is None) != (tamanho_destino is None):
        raise ValueError("É preciso informar origem e destino da projeção")

    if not camera.updated:
        camera.updateCamera()
        camera.updated = True
    proj, view = camera.getMatrices(0)
    model = camera.getModelMatrix(obj)
    proj = np.asarray(proj, dtype=np.float32).copy()
    if tamanho_destino is not None:
        ow, oh = tamanho_origem
        dw, dh = tamanho_destino
        if min(ow, oh, dw, dh) <= 0:
            raise ValueError("Tamanhos de câmera offscreen inválidos")
        origem_aspect = float(ow) / float(oh)
        destino_aspect = float(dw) / float(dh)
        # MakeHuman Camera.getMatrices(0) e OrbitalCamera.getMatrices(0)
        # usam aspect somente no eixo horizontal em perspectiva/ortho.
        # Para eye=0, o ajuste da linha X preserva a direção da câmera.
        proj[0, :] *= origem_aspect / destino_aspect
    view = np.asarray(view, dtype=np.float32)
    model = np.asarray(model, dtype=np.float32)
    if any(m.shape != (4, 4) or not np.isfinite(m).all()
           for m in (proj, view, model)):
        raise ValueError("Matrizes da câmera original inválidas")
    conversao_z = np.eye(4, dtype=np.float32)
    conversao_z[2, 2] = 0.5
    conversao_z[2, 3] = 0.5
    return np.ascontiguousarray(conversao_z @ proj @ view @ model)


def parametros_material_vulkan(obj):
    """Lê as opções do material já utilizadas pelo Object3D original.

    Vetor de controle WGSL: x=sem iluminação, y=usar textura difusa.
    Mantém a cor difusa original e não instancia shaders OpenGL.
    """
    material = getattr(obj, "material", None)
    difusa = getattr(getattr(material, "diffuseColor", None), "values",
                     (1.0, 1.0, 1.0))
    rgb = np.asarray(difusa, dtype=np.float32)
    if rgb.shape != (3,) or not np.isfinite(rgb).all():
        raise ValueError("Material original: cor difusa RGB inválida")
    cor = np.array([*rgb, 1.0], dtype=np.float32)
    sem_luz = bool(getattr(obj, "shadeless",
                           getattr(material, "shadeless", False)))
    usar_textura = bool(getattr(obj, "isTextured", True))
    flags = np.array([float(sem_luz), float(usar_textura), 0.0, 0.0],
                     dtype=np.float32)
    return cor, flags


def aparencia_material_vulkan(obj):
    """Converte especular, emissão e opacidade do Material original.

    Uniforms: specular.xyz = RGB, specular.w = expoente de brilho GL;
    emissive.xyz = RGB, emissive.w = reservado. Nenhum shader GLSL importado.
    """
    material = getattr(obj, "material", None)

    def rgb_atributo(nome, padrao):
        atributo = getattr(material, nome, None)
        vetor = np.asarray(getattr(atributo, "values", atributo)
                           if atributo is not None else padrao, dtype=np.float32)
        if vetor.shape != (3,) or not np.isfinite(vetor).all():
            raise ValueError("Material original: " + nome + " inválido")
        return vetor

    especular = rgb_atributo("specularColor", (0.0, 0.0, 0.0))
    emissiva = rgb_atributo("emissiveColor", (0.0, 0.0, 0.0))
    brilho = float(getattr(material, "shininess", 0.2))
    opacidade = float(getattr(material, "opacity", 1.0))
    if not np.isfinite(brilho) or not np.isfinite(opacidade):
        raise ValueError("Material original: brilho/opacidade não finitos")
    especular_uniform = np.array(
        [*especular, 128.0 * float(np.clip(brilho, 0.0, 1.0))], np.float32,
    )
    emissiva_uniform = np.array([*emissiva, 0.0], np.float32)
    return especular_uniform, emissiva_uniform, float(np.clip(opacidade, 0.0, 1.0))


def configuracao_raster_vulkan(obj, *, linhas=False):
    """Converte as regras de face e profundidade da geometria original.

    cull: 0 = ambas as faces; >0 = remover backfaces; <0 = remover
    frontfaces. Objetos sem profundidade ignoram Z, sem gravá-lo;
    materiais transparentes deixam o depth buffer intacto.
    """
    cull = getattr(obj, "cull", 0)
    if cull is None:
        cull = 0
    modo_cull = "back" if cull > 0 else "front" if cull < 0 else "none"
    sem_profundidade = bool(getattr(obj, "depthless", False))
    material = getattr(obj, "material", None)
    opacidade = float(getattr(material, "opacity", 1.0))
    if not np.isfinite(opacidade):
        raise ValueError("Material original: opacidade não finita")
    transparente = bool(getattr(material, "transparent", False))
    escrever_profundidade = (
        not linhas and not sem_profundidade
        and not transparente and opacidade >= 1.0
    )
    comparacao = "always" if sem_profundidade else "less-equal"
    return modo_cull, escrever_profundidade, comparacao


class CenaVulkan:
    """Renderização piloto de objetos G.world na própria janela MakeHuman."""

    def __init__(self, canvas):
        import wgpu
        from PyQt5 import QtGui

        self.wgpu = wgpu
        self.QtGui = QtGui
        self.canvas = canvas
        self.adapter = wgpu.gpu.request_adapter_sync(
            power_preference="high-performance", canvas=canvas
        )
        if self.adapter is None:
            raise RuntimeError("Nenhum adaptador Vulkan disponível")
        # Sem fallback OpenGL: o piloto só opera com Vulkan.
        if "vulkan" not in str(self.adapter.info).lower():
            raise RuntimeError(
                "Backend não é Vulkan: " + str(self.adapter.info)
            )
        self.device = self.adapter.request_device_sync()
        self.contexto = canvas.get_wgpu_context()
        self.formato = self.contexto.get_preferred_format(self.adapter)
        self.contexto.configure(device=self.device, format=self.formato)
        codigo = """
struct Globals {
    mvp: mat4x4<f32>,
    modelo: mat4x4<f32>,
    cor: vec4<f32>,
    flags: vec4<f32>,
    ambiente: vec4<f32>,
    especular: vec4<f32>,
    emissiva: vec4<f32>,
    observador: vec4<f32>,
    luzes_posicao: array<vec4<f32>, 8>,
    luzes_cor: array<vec4<f32>, 8>,
};
@group(0) @binding(0) var<uniform> dados: Globals;
@group(0) @binding(1) var mapa: texture_2d<f32>;
@group(0) @binding(2) var amostra: sampler;
struct Entrada {
    @location(0) pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) uv: vec2<f32>,
    @location(3) cor: vec4<f32>,
};
struct Fragmento {
    @builtin(position) pos: vec4<f32>,
    @location(0) normal: vec3<f32>,
    @location(1) uv: vec2<f32>,
    @location(2) cor: vec4<f32>,
    @location(3) mundo: vec3<f32>,
};
@vertex fn vs_main(v: Entrada) -> Fragmento {
    var o: Fragmento;
    o.pos = dados.mvp * vec4<f32>(v.pos, 1.0);
    o.normal = normalize((dados.modelo * vec4<f32>(v.normal, 0.0)).xyz);
    o.mundo = (dados.modelo * vec4<f32>(v.pos, 1.0)).xyz;
    o.uv = v.uv;
    o.cor = v.cor;
    return o;
}
@fragment fn fs_main(i: Fragmento) -> @location(0) vec4<f32> {
    let tex = textureSample(mapa, amostra, vec2<f32>(i.uv.x, 1.0-i.uv.y));
    let usar_textura = dados.flags.y > 0.5;
    let rgb = select(vec3<f32>(1.0), tex.rgb, usar_textura);
    let alfa = select(1.0, tex.a, usar_textura);
    var iluminacao = dados.ambiente.rgb;
    var reflexo = vec3<f32>(0.0);
    let normal = normalize(i.normal);
    let direcao_visao = normalize(dados.observador.xyz - i.mundo);
    for (var j: i32 = 0; j < 8; j = j + 1) {
        if (j >= i32(dados.flags.z)) {
            break;
        }
        let deslocamento = dados.luzes_posicao[j].xyz - i.mundo;
        let direcao = normalize(deslocamento);
        let difusa = max(dot(normal, direcao), 0.0);
        iluminacao += dados.luzes_cor[j].rgb * difusa;
        if (difusa > 0.0 && dados.especular.w > 0.0) {
            let meio = normalize(direcao + direcao_visao);
            let intensidade = pow(max(dot(normal, meio), 0.0),
                                  dados.especular.w);
            reflexo += dados.luzes_cor[j].rgb * dados.especular.rgb
                     * intensidade;
        }
    }
    let luz = select(iluminacao, vec3<f32>(1.0), dados.flags.x > 0.5);
    let brilho = select(reflexo, vec3<f32>(0.0), dados.flags.x > 0.5);
    return vec4<f32>(rgb * i.cor.rgb * dados.cor.rgb * luz
                     + brilho + dados.emissiva.rgb,
                     alfa * i.cor.a * dados.cor.a);
}
"""
        shader = self.device.create_shader_module(code=codigo)
        # Preserva a cobertura alpha dos materiais (inclusive textura alpha)
        # para que a máscara de produção venha da GPU, não da captura Qt.
        blend = wgpu.BlendState(
            color=wgpu.BlendComponent(
                src_factor="src-alpha", dst_factor="one-minus-src-alpha",
            ),
            alpha=wgpu.BlendComponent(
                src_factor="one", dst_factor="one-minus-src-alpha",
            ),
        )
        self.pipeline = self.device.create_render_pipeline(
            layout=wgpu.AutoLayoutMode.auto,
            vertex=wgpu.VertexState(
                module=shader, entry_point="vs_main",
                buffers=[wgpu.VertexBufferLayout(
                    array_stride=48, step_mode="vertex",
                    attributes=[
                        wgpu.VertexAttribute(
                            format="float32x3", offset=0, shader_location=0
                        ),
                        wgpu.VertexAttribute(
                            format="float32x3", offset=12, shader_location=1
                        ),
                        wgpu.VertexAttribute(
                            format="float32x2", offset=24, shader_location=2
                        ),
                        wgpu.VertexAttribute(
                            format="float32x4", offset=32, shader_location=3
                        ),
                    ],
                )],
            ),
            primitive=wgpu.PrimitiveState(
                topology="triangle-list", cull_mode="none"
            ),
            depth_stencil=wgpu.DepthStencilState(
                format="depth24plus", depth_write_enabled=True,
                depth_compare="less-equal"
            ),
            fragment=wgpu.FragmentState(
                module=shader, entry_point="fs_main",
                targets=[wgpu.ColorTargetState(format=self.formato, blend=blend)],
            ),
        )
        # A grade de referência original (back_grid) usa GL_LINES.
        # Mantê-la com seus mesmos índices, cores e transformações.
        self.pipeline_linhas = self.device.create_render_pipeline(
            layout=wgpu.AutoLayoutMode.auto,
            vertex=wgpu.VertexState(
                module=shader, entry_point="vs_main",
                buffers=[wgpu.VertexBufferLayout(
                    array_stride=48, step_mode="vertex",
                    attributes=[
                        wgpu.VertexAttribute(
                            format="float32x3", offset=0, shader_location=0
                        ),
                        wgpu.VertexAttribute(
                            format="float32x3", offset=12, shader_location=1
                        ),
                        wgpu.VertexAttribute(
                            format="float32x2", offset=24, shader_location=2
                        ),
                        wgpu.VertexAttribute(
                            format="float32x4", offset=32, shader_location=3
                        ),
                    ],
                )],
            ),
            primitive=wgpu.PrimitiveState(
                topology="line-list", cull_mode="none"
            ),
            depth_stencil=wgpu.DepthStencilState(
                format="depth24plus", depth_write_enabled=False,
                depth_compare="less-equal"
            ),
            fragment=wgpu.FragmentState(
                module=shader, entry_point="fs_main",
                targets=[wgpu.ColorTargetState(format=self.formato, blend=blend)],
            ),
        )
        self.amostra = self.device.create_sampler(
            mag_filter="linear", min_filter="linear"
        )
        self._texturas = {}
        self._depth = None
        self._depth_size = None
        self.frames = 0
        self.objetos_desenhados = 0
        self.linhas_desenhadas = 0
        self._primitivas_pendentes = set()
        self._cena_luzes = None
        self._shader_malhas = shader
        self._blend_malhas = blend
        self._pipelines_malhas = {
            (False, "none", True, "less-equal"): self.pipeline,
            (True, "none", False, "less-equal"): self.pipeline_linhas,
        }

    def _pipeline_objeto(self, obj, linhas):
        """Cache de variantes Vulkan para culling e depth do MakeHuman."""
        wgpu = self.wgpu
        config = configuracao_raster_vulkan(obj, linhas=linhas)
        chave = (bool(linhas), *config)
        cached = self._pipelines_malhas.get(chave)
        if cached is not None:
            return cached
        modo_cull, grava_z, compara_z = config
        novo = self.device.create_render_pipeline(
            layout=wgpu.AutoLayoutMode.auto,
            vertex=wgpu.VertexState(
                module=self._shader_malhas, entry_point="vs_main",
                buffers=[wgpu.VertexBufferLayout(
                    array_stride=48, step_mode="vertex",
                    attributes=[
                        wgpu.VertexAttribute(
                            format="float32x3", offset=0, shader_location=0,
                        ),
                        wgpu.VertexAttribute(
                            format="float32x3", offset=12, shader_location=1,
                        ),
                        wgpu.VertexAttribute(
                            format="float32x2", offset=24, shader_location=2,
                        ),
                        wgpu.VertexAttribute(
                            format="float32x4", offset=32, shader_location=3,
                        ),
                    ],
                )],
            ),
            primitive=wgpu.PrimitiveState(
                topology="line-list" if linhas else "triangle-list",
                cull_mode="none" if linhas else modo_cull,
            ),
            depth_stencil=wgpu.DepthStencilState(
                format="depth24plus",
                depth_write_enabled=grava_z,
                depth_compare=compara_z,
            ),
            fragment=wgpu.FragmentState(
                module=self._shader_malhas, entry_point="fs_main",
                targets=[wgpu.ColorTargetState(
                    format=self.formato, blend=self._blend_malhas,
                )],
            ),
        )
        self._pipelines_malhas[chave] = novo
        return novo

    def atualizar_iluminacao(self, cena):
        """Guarda a cena original para os próximos passes de renderização."""
        self._cena_luzes = cena

    def invalidar_texturas(self, caminho=None):
        """Invalida texturas da cena; a próxima renderização recarrega na GPU."""
        if caminho is None:
            self._texturas.clear()
        else:
            self._texturas.pop(str(caminho), None)

    def _textura(self, caminho):
        dinamica = (
            caminho is not None and hasattr(caminho, "data")
            and hasattr(caminho, "width") and hasattr(caminho, "height")
        )
        if dinamica:
            chave = ("imagem", id(caminho))
            origem = np.asarray(caminho.data)
            assinatura = (
                getattr(caminho, "modified", None), origem.shape,
            )
        else:
            chave = str(caminho or "")
            assinatura = assinatura_textura(chave)
        entrada = self._texturas.get(chave)
        if entrada is not None and entrada[0] == assinatura:
            return entrada[1]
        if dinamica:
            pixels = pixels_textura_rgba(origem)
        else:
            imagem = self.QtGui.QImage(chave) if chave else self.QtGui.QImage()
            if imagem.isNull():
                pixels = np.array([[[255, 255, 255, 255]]], dtype=np.uint8)
            else:
                imagem = imagem.convertToFormat(self.QtGui.QImage.Format_RGBA8888)
                w, h = imagem.width(), imagem.height()
                pixels = np.frombuffer(
                    imagem.bits().asstring(w * h * 4), dtype=np.uint8
                ).reshape((h, w, 4)).copy()
        h, w = pixels.shape[:2]
        wgpu = self.wgpu
        textura = self.device.create_texture(
            size=(w, h, 1), dimension="2d", format="rgba8unorm",
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        self.device.queue.write_texture(
            wgpu.TexelCopyTextureInfo(
                texture=textura, mip_level=0, origin=(0, 0, 0)
            ),
            pixels.tobytes(),
            wgpu.TexelCopyBufferLayout(
                offset=0, bytes_per_row=w*4, rows_per_image=h
            ),
            (w, h, 1),
        )
        self._texturas[chave] = (assinatura, textura)
        return textura

    def framebuffer_offscreen(self, largura, altura):
        """Aloca destino de renderização legível pela CPU, fora do swapchain."""
        from vulkan_offscreen import bytes_por_linha_alinhados
        largura, altura = int(largura), int(altura)
        bytes_por_linha_alinhados(largura)
        if altura < 1:
            raise ValueError("Altura offscreen deve ser positiva")
        if self.formato not in ("rgba8unorm", "rgba8unorm-srgb",
                                "bgra8unorm", "bgra8unorm-srgb"):
            raise ValueError("Formato de framebuffer não suportado: " + str(self.formato))
        return self.device.create_texture(
            size=(largura, altura, 1),
            dimension="2d",
            format=self.formato,
            usage=self.wgpu.TextureUsage.RENDER_ATTACHMENT
                  | self.wgpu.TextureUsage.COPY_SRC
                  | self.wgpu.TextureUsage.COPY_DST,
        )

    def ler_framebuffer_rgba(self, alvo):
        """Copia RGBA da GPU para memória CPU, preservando a transparência."""
        from vulkan_offscreen import (
            bytes_por_linha_alinhados, decodificar_buffer_rgba,
        )
        largura, altura = alvo.size[:2]
        stride = bytes_por_linha_alinhados(largura)
        buffer = self.device.create_buffer(
            size=stride * altura,
            usage=self.wgpu.BufferUsage.COPY_DST
                  | self.wgpu.BufferUsage.MAP_READ,
        )
        encoder = self.device.create_command_encoder()
        encoder.copy_texture_to_buffer(
            self.wgpu.TexelCopyTextureInfo(
                texture=alvo, mip_level=0, origin=(0, 0, 0),
            ),
            self.wgpu.TexelCopyBufferInfo(
                buffer=buffer, offset=0, bytes_per_row=stride,
                rows_per_image=altura,
            ),
            (largura, altura, 1),
        )
        self.device.queue.submit([encoder.finish()])
        # queue.read_buffer() exige COPY_SRC, incompatível com MAP_READ
        # no buffer de staging. Mapear diretamente é o contrato correto.
        buffer.map_sync(self.wgpu.MapMode.READ)
        try:
            dados = buffer.read_mapped(copy=True)
        finally:
            buffer.unmap()
        return decodificar_buffer_rgba(dados, largura, altura, self.formato)

    def ler_framebuffer_rgb(self, alvo):
        """Lê RGB do framebuffer Vulkan, mantendo o contrato original."""
        return np.ascontiguousarray(self.ler_framebuffer_rgba(alvo)[:, :, :3])

    def capturar_framebuffer(self, mundo, cameras, largura=None, altura=None,
                             *, incluir_alfa=False, productionRender=False,
                             cor_fundo=None):
        """Render offscreen em tamanho independente e com opção de RGBA."""
        fisica_w, fisica_h = self.canvas.get_physical_size()
        if largura is None:
            largura = fisica_w
        if altura is None:
            altura = fisica_h
        if cor_fundo is None:
            cor_fundo = (0.5, 0.5, 0.5, 0.0 if incluir_alfa else 1.0)
        alvo = self.framebuffer_offscreen(largura, altura)
        self.desenhar(
            mundo, cameras, alvo=alvo, cor_fundo=cor_fundo,
            productionRender=productionRender,
        )
        if incluir_alfa:
            return self.ler_framebuffer_rgba(alvo)
        return self.ler_framebuffer_rgb(alvo)

    def desenhar(self, mundo, cameras, *, cor_fundo=(0.2, 0.2, 0.2, 1),
                alvo=None, productionRender=False):
        """Desenha na janela ou num alvo offscreen de resolução independente.

        A viewport e os parâmetros originais da câmera não são alterados.
        """
        wgpu = self.wgpu
        tamanho_janela = tuple(self.canvas.get_physical_size())
        if len(tamanho_janela) < 2 or min(tamanho_janela[:2]) < 1:
            return
        tamanho_janela = tuple(map(int, tamanho_janela[:2]))
        tamanho = tuple(map(int, alvo.size[:2])) if alvo is not None else tamanho_janela
        if alvo is None:
            if self._depth_size != tamanho:
                depth = self.device.create_texture(
                    size=(tamanho[0], tamanho[1], 1),
                    format="depth24plus",
                    usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
                )
                self._depth = depth.create_view()
                self._depth_size = tamanho
            depth_view = self._depth
            color_view = self.contexto.get_current_texture().create_view()
        else:
            depth = self.device.create_texture(
                size=(tamanho[0], tamanho[1], 1),
                format="depth24plus",
                usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
            )
            depth_view = depth.create_view()
            color_view = alvo.create_view()

        encoder = self.device.create_command_encoder()
        passagem = encoder.begin_render_pass(
            color_attachments=[wgpu.RenderPassColorAttachment(
                view=color_view,
                resolve_target=None,
                load_op="clear",
                store_op="store",
                clear_value=tuple(cor_fundo),
            )],
            depth_stencil_attachment=wgpu.RenderPassDepthStencilAttachment(
                view=depth_view,
                depth_load_op="clear", depth_store_op="store",
                depth_clear_value=1.0,
            ),
        )
        passagem.set_pipeline(self.pipeline)
        from vulkan_lighting import dados_iluminacao_cena
        ambiente, posicoes, cores, total_luzes = dados_iluminacao_cena(
            self._cena_luzes,
        )
        self.objetos_desenhados = 0
        self.linhas_desenhadas = 0
        if mundo is not None:
            for obj in sorted(mundo, key=lambda item: item.priority):
                if not obj.visibility:
                    continue
                if productionRender and getattr(obj, "excludeFromProduction", False):
                    continue
                try:
                    vertices, indices = preparar_malha_original(obj)
                except ValueError as erro:
                    if "primitiva não triangular" not in str(erro):
                        raise
                    # Ainda não há pipeline de linhas/points do overlay Qt.
                    # A migração será considerada parcial até esse caso
                    # receber tratamento explícito; não lançar exceção em loop.
                    if obj.name not in self._primitivas_pendentes:
                        self._primitivas_pendentes.add(obj.name)
                        print(
                            "MAKEHUMANO_VULKAN: pendente primitiva auxiliar "
                            + str(obj.name) + ": " + str(erro),
                            flush=True,
                        )
                    continue
                if not len(vertices) or not len(indices):
                    continue
                primitiva = np.asarray(obj.primitives)
                linhas = primitiva.ndim == 2 and primitiva.shape[1] == 2
                pipeline = self._pipeline_objeto(obj, linhas)
                passagem.set_pipeline(pipeline)
                cam = cameras[obj.cameraMode]
                if alvo is None:
                    mvp = matriz_wgpu(cam, obj)
                else:
                    # getMatrices usa G.windowWidth/Height (projeção original).
                    # Não alterar G: ajustamos apenas a matriz para o alvo.
                    from core import G
                    mvp = matriz_wgpu(
                        cam, obj,
                        tamanho_origem=(G.windowWidth, G.windowHeight),
                        tamanho_destino=tamanho,
                    )
                cor, flags = parametros_material_vulkan(obj)
                especular, emissiva, opacidade = aparencia_material_vulkan(obj)
                cor[3] = opacidade
                flags[2] = float(total_luzes)
                modelo = np.asarray(cam.getModelMatrix(obj), dtype=np.float32)
                if modelo.shape != (4, 4) or not np.isfinite(modelo).all():
                    raise ValueError("Modelo da câmera original inválido")
                # getMatrices fornece a view original; a câmera não é mutada.
                if not getattr(cam, "updated", True):
                    cam.updateCamera()
                    cam.updated = True
                _, view = cam.getMatrices(0)
                view = np.asarray(view, dtype=np.float32)
                if view.shape != (4, 4) or not np.isfinite(view).all():
                    raise ValueError("View original inválida para iluminação")
                try:
                    posicao_camera = np.linalg.inv(view)[:3, 3]
                except np.linalg.LinAlgError as exc:
                    raise ValueError("View original não inversível") from exc
                observador = np.array([*posicao_camera, 1.0], np.float32)
                uniforms = np.concatenate((
                    mvp.T.reshape(-1), modelo.T.reshape(-1),
                    cor, flags, ambiente, especular, emissiva, observador,
                    posicoes.reshape(-1), cores.reshape(-1),
                )).astype(np.float32)
                buf_u = self.device.create_buffer_with_data(
                    data=uniforms, usage=wgpu.BufferUsage.UNIFORM
                )
                buf_v = self.device.create_buffer_with_data(
                    data=vertices, usage=wgpu.BufferUsage.VERTEX
                )
                buf_i = self.device.create_buffer_with_data(
                    data=indices, usage=wgpu.BufferUsage.INDEX
                )
                textura = self._textura(getattr(obj, "texture", None))
                bind = self.device.create_bind_group(
                    layout=pipeline.get_bind_group_layout(0),
                    entries=[
                        wgpu.BindGroupEntry(
                            binding=0,
                            resource=wgpu.BufferBinding(buffer=buf_u),
                        ),
                        wgpu.BindGroupEntry(
                            binding=1, resource=textura.create_view()
                        ),
                        wgpu.BindGroupEntry(
                            binding=2, resource=self.amostra
                        ),
                    ],
                )
                passagem.set_bind_group(0, bind)
                passagem.set_vertex_buffer(0, buf_v)
                passagem.set_index_buffer(buf_i, "uint32")
                passagem.draw_indexed(len(indices))
                self.objetos_desenhados += 1
                if linhas:
                    self.linhas_desenhadas += len(indices) // 2
        passagem.end()
        self.device.queue.submit([encoder.finish()])
        self.frames += 1
