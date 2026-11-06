"""Primeira ponte Vulkan com a CENA ORIGINAL do MakeHuman (G.world).

Não carrega um segundo personagem, não aplica alvos morfológicos próprios.
Converte o Object3D de renderização que o MakeHuman já atualiza em dados
para GPU. O piloto é incompleto: picking, transparência, render offscreen
e shaders customizados ainda precisam ser migrados antes de remover OpenGL.
"""

import os

import numpy as np

from vulkan_material_maps import parametros_mapa, mapa_transparencia_ativo


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



def preparar_malha_original(obj, camera=None):
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
    material = getattr(obj, "material", None)
    total_transparentes = int(getattr(obj, "nTransparentPrimitives", 0))
    if (bool(getattr(material, "transparent", False))
            or float(getattr(material, "opacity", 1.0)) < 1.0
            or mapa_transparencia_ativo(material)):
        total_transparentes = len(face)
    total_transparentes = min(max(total_transparentes, 0), len(face))
    transparentes = np.arange(len(face)) >= len(face) - total_transparentes
    if face.shape[1] == 4:
        # MakeHuman mantém triangulações na sequência das faces visíveis.
        indices = np.concatenate(
            (face[:, [0, 1, 2]], face[:, [0, 2, 3]]), axis=0
        )
        transparentes = np.tile(transparentes, 2)
    else:
        indices = face
    if face.shape[1] == 2:
        # O grid e outras linhas auxiliares têm pares de vértices.
        indices = indices[indices[:, 0] != indices[:, 1]]
    else:
        # Quads degenerados são usados pelo MakeHuman para representar tris.
        validos = (
            (indices[:, 0] != indices[:, 1])
            & (indices[:, 1] != indices[:, 2])
            & (indices[:, 0] != indices[:, 2])
        )
        indices = indices[validos]
        transparentes = transparentes[validos]
        if camera is not None and np.any(transparentes):
            indices = ordenar_triangulos_vulkan(obj, camera, indices, transparentes)
    if not np.isfinite(vertices).all():
        raise ValueError("Object3D original: coordenadas não finitas")
    return (np.ascontiguousarray(vertices),
            np.ascontiguousarray(indices.reshape(-1), dtype=np.uint32))


def ordenar_triangulos_vulkan(obj, camera, triangulos, transparentes):
    """Ordenar faces alpha em espaço da câmera sem modificar a malha original.

    Faces opacas permanecem primeiro. Quads já foram triangulados e os
    triângulos degenerados removidos. Recalcular por câmera também atende
    rotações e modificadores. Interseções cíclicas ainda exigem OIT ou split.
    """
    if not getattr(camera, "updated", True):
        camera.updateCamera()
        camera.updated = True
    _, view = camera.getMatrices(0)
    modelview = np.asarray(view, dtype=np.float64) @ np.asarray(
        camera.getModelMatrix(obj), dtype=np.float64)
    centros = np.mean(np.asarray(obj.verts)[triangulos[transparentes]], axis=1)
    centros = np.column_stack((centros, np.ones(len(centros)))) @ modelview.T
    if not np.isfinite(centros).all() or np.any(np.abs(centros[:, 3]) < 1e-8):
        raise ValueError("Triângulo translúcido não projetável")
    ordem = np.argsort(centros[:, 2] / centros[:, 3], kind="stable")
    return np.concatenate((triangulos[~transparentes], triangulos[transparentes][ordem]))


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


def matriz_normal_vulkan(modelo):
    """Inversa transposta do modelo para iluminação sob escala não uniforme."""
    m = np.asarray(modelo, dtype=np.float32)
    if m.shape != (4, 4) or not np.isfinite(m).all():
        raise ValueError("Matriz de modelo inválida para cálculo das normais")
    try:
        inv_t = np.linalg.inv(m[:3, :3].astype(np.float64)).T
    except np.linalg.LinAlgError as exc:
        raise ValueError("Transformação de objeto degenerada") from exc
    normal = np.eye(4, dtype=np.float32)
    normal[:3, :3] = inv_t
    return normal


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


def parametros_normalmap_vulkan(obj):
    """Retorna textura e intensidade da normal map do material original.

    Respeita shaderConfig['normal'] e valida as opções da interface .mhmat.
    Nenhuma textura extra é amostrada quando o mapa está desativado.
    """
    material = getattr(obj, "material", None)
    if material is None:
        return None, 0.0
    caminho = getattr(material, "normalMapTexture", None)
    config = getattr(material, "shaderConfig", {})
    if not caminho or not config.get("normal", True):
        return None, 0.0
    intensidade = float(getattr(material, "normalMapIntensity", 1.0))
    if not np.isfinite(intensidade):
        raise ValueError("Material original: intensidade da normal map inválida")
    if isinstance(caminho, (str, os.PathLike)) and not os.path.isfile(caminho):
        return None, 0.0
    intensidade = float(np.clip(intensidade, 0.0, 1.0))
    return caminho, intensidade


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
    transparente = (bool(getattr(material, "transparent", False))
                    or mapa_transparencia_ativo(material))
    # glmodule.drawObject() desativava glDepthMask para malhas com
    # transparentPrimitives ao usar glAlphaFunc(GL_GREATER, 0).
    # O Vulkan deve preservar o contrato da malha original mesmo
    # quando material.transparent não foi marcado explicitamente.
    recorte_alfa = bool(getattr(obj, "nTransparentPrimitives", 0))
    escrever_profundidade = (
        not linhas and not sem_profundidade
        and not transparente and not recorte_alfa and opacidade >= 1.0
    )
    comparacao = "always" if sem_profundidade else "less-equal"
    return modo_cull, escrever_profundidade, comparacao


def objeto_translucido_vulkan(obj):
    """Classifica camadas para composição alpha, sem inferir pela textura.

    Mantém o contrato do MakeHuman: transparentPrimitives, opacity e
    material.transparent indicam superfícies que não gravam profundidade.
    """
    material = getattr(obj, "material", None)
    opacity = float(getattr(material, "opacity", 1.0))
    if not np.isfinite(opacity):
        raise ValueError("Opacidade não finita na ordenação Vulkan")
    return (bool(getattr(obj, "nTransparentPrimitives", 0))
            or bool(getattr(material, "transparent", False))
            or opacity < 1.0 or mapa_transparencia_ativo(material))


def profundidade_camada_vulkan(obj, cam):
    """Centro da malha em espaço de vista; Z menor é mais distante em GL.

    Objetos originais usam a transformação de getModelMatrix() da própria
    câmera MakeHuman. Não altera a câmera nem move vértices do personagem.
    """
    coords = np.asarray(getattr(obj, "verts", ()), dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 3 or not len(coords):
        raise ValueError("Camada translúcida sem vértices 3D")
    if not np.isfinite(coords).all():
        raise ValueError("Vértices não finitos em camada translúcida")
    if not getattr(cam, "updated", True):
        cam.updateCamera()
        cam.updated = True
    _, view = cam.getMatrices(0)
    view = np.asarray(view, dtype=np.float64)
    model = np.asarray(cam.getModelMatrix(obj), dtype=np.float64)
    if (view.shape != (4, 4) or model.shape != (4, 4)
            or not np.isfinite(view).all() or not np.isfinite(model).all()):
        raise ValueError("Matriz inválida na ordenação de camadas")
    centro = np.append(np.mean(coords, axis=0), 1.0)
    eye = view @ model @ centro
    if not np.isfinite(eye).all() or abs(eye[3]) < 1e-8:
        raise ValueError("Camada translúcida com centro não projetável")
    return float(eye[2] / eye[3])


def ordenar_objetos_vulkan(mundo, cameras):
    """Prioridades originais + render de camadas alpha atrás → frente.

    Dentro de cada bloco de mesma priority e cameraMode, desenha primeiro
    os opacos, depois os translúcidos em profundidade de câmera crescente
    (OpenGL: Z mais negativo está mais distante), e por último overlays
    depthless. Em empates, Python sort mantém a ordem do MakeHuman.
    Não reordena objetos de câmeras diferentes ou prioridades diferentes.
    """
    if mundo is None:
        return []
    ordenados = sorted(mundo, key=lambda obj: obj.priority)
    resultado = []
    inicio = 0
    while inicio < len(ordenados):
        atual = ordenados[inicio]
        fim = inicio + 1
        while (fim < len(ordenados)
               and ordenados[fim].priority == atual.priority
               and ordenados[fim].cameraMode == atual.cameraMode):
            fim += 1
        grupo = ordenados[inicio:fim]
        opacos, translucidos, overlays = [], [], []
        for obj in grupo:
            if bool(getattr(obj, "depthless", False)):
                overlays.append(obj)
            elif objeto_translucido_vulkan(obj):
                translucidos.append(obj)
            else:
                opacos.append(obj)
        if len(translucidos) > 1:
            cam = cameras[atual.cameraMode]
            translucidos.sort(
                key=lambda obj: profundidade_camada_vulkan(obj, cam),
            )
        resultado.extend(opacos)
        resultado.extend(translucidos)
        resultado.extend(overlays)
        inicio = fim
    return resultado


def arestas_wireframe(faces):
    """Arestas das faces originais, sem diagonais da triangulação dos quads."""
    faces = np.asarray(faces, dtype=np.uint32)
    if faces.ndim != 2 or faces.shape[1] not in (3, 4):
        raise ValueError("Wireframe exige triângulos ou quads originais")
    edges = np.stack((faces, np.roll(faces, -1, axis=1)), axis=-1).reshape(-1, 2)
    edges = edges[edges[:, 0] != edges[:, 1]]
    return np.unique(np.sort(edges, axis=1), axis=0)


class _MaterialWireframe:
    shader = None
    shaderParameters = {}
    shaderConfig = {"normal": False, "bump": False, "ambientOcclusion": False, "diffuse": False, "spec": False, "transparency": False}
    normalMapTexture = None
    transparent = False

    def __init__(self, original, linhas):
        self.original = original
        if linhas:
            from types import SimpleNamespace
            self.diffuseColor = SimpleNamespace(values=(0., 0., 0.))
            self.emissiveColor = SimpleNamespace(values=(0., 0., 0.))
            self.specularColor = SimpleNamespace(values=(0., 0., 0.))
            self.opacity = 1.0

    def __getattr__(self, name):
        return getattr(self.original, name)


class _PasseWireframe:
    isTextured = False
    texture = None
    nTransparentPrimitives = 0
    solid = True

    def __init__(self, original, linhas):
        self.original = original
        self.material = _MaterialWireframe(original.material, linhas)
        self.shadeless = linhas or original.shadeless
        self._wireframe_preenchimento = not linhas
        self.primitives = arestas_wireframe(original.primitives) if linhas else original.primitives

    def __getattr__(self, name):
        return getattr(self.original, name)


def passes_wireframe(objetos):
    """Preservar o modo original: superfície sem textura e arestas pretas."""
    for obj in objetos:
        if not getattr(obj, "solid", True) and np.asarray(obj.primitives).shape[-1] in (3, 4):
            yield _PasseWireframe(obj, False)
            yield _PasseWireframe(obj, True)
        else:
            yield obj


class CenaVulkan:
    """Renderização piloto de objetos G.world na própria janela MakeHuman."""

    def __init__(self, canvas):
        from vulkan_runtime import preparar_runtime_vulkan
        preparar_runtime_vulkan()
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
    normal_modelo: mat4x4<f32>,
    visao: mat4x4<f32>,
    cor: vec4<f32>,
    flags: vec4<f32>,
    ambiente: vec4<f32>,
    especular: vec4<f32>,
    emissiva: vec4<f32>,
    observador: vec4<f32>,
    shader_preset: vec4<f32>,
    shader_parametros: vec4<f32>,
    shader_parametros_extra: vec4<f32>,
    luzes_posicao: array<vec4<f32>, 8>,
    luzes_cor: array<vec4<f32>, 8>,
    luzes_especular: array<vec4<f32>, 8>,
    mapas_parametros: vec4<f32>,
    luzes_direcao: array<vec4<f32>, 8>,
    luzes_atenuacao: array<vec4<f32>, 8>,
};
@group(0) @binding(0) var<uniform> dados: Globals;
@group(0) @binding(1) var mapa: texture_2d<f32>;
@group(0) @binding(2) var amostra: sampler;
@group(0) @binding(3) var mapa_normais: texture_2d<f32>;
@group(0) @binding(4) var mapa_litsphere: texture_2d<f32>;
@group(0) @binding(5) var mapa_ao: texture_2d<f32>;
@group(0) @binding(6) var mapa_gradiente: texture_2d<f32>;
@group(0) @binding(7) var mapa_especular: texture_2d<f32>;
@group(0) @binding(8) var mapa_transparencia: texture_2d<f32>;
@group(0) @binding(9) var mapa_altura: texture_2d<f32>;
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
    o.normal = normalize((dados.normal_modelo * vec4<f32>(v.normal, 0.0)).xyz);
    o.mundo = (dados.modelo * vec4<f32>(v.pos, 1.0)).xyz;
    o.uv = v.uv;
    o.cor = v.cor;
    return o;
}
fn fator_luz(indice: i32, mundo: vec3<f32>) -> f32 {
    let delta = mundo - dados.luzes_posicao[indice].xyz;
    let distancia2 = dot(delta, delta);
    var fator = 1.0 / (1.0 + dados.luzes_atenuacao[indice].x * distancia2);
    let foco = dados.luzes_direcao[indice];
    if (foco.w > -0.5) {
        let direcao = delta * inverseSqrt(max(distancia2, 0.000000000001));
        fator *= select(0.0, 1.0, dot(direcao, foco.xyz) >= foco.w);
    }
    return fator;
}
fn cor_fragmento(i: Fragmento) -> vec4<f32> {
    let uv = vec2<f32>(i.uv.x, 1.0 - i.uv.y);
    let tex = textureSample(mapa, amostra, uv);
    let spec_map = textureSample(mapa_especular, amostra, uv).rgb;
    let spec_factor = mix(vec3<f32>(1.0), spec_map, dados.mapas_parametros.x);
    let cor_especular = dados.especular.rgb * spec_factor;
    let ao_factor = mix(vec3<f32>(1.0),
                        textureSample(mapa_ao, amostra, uv).rgb,
                        dados.mapas_parametros.w);
    let usar_textura = dados.flags.y > 0.5;
    let rgb = select(vec3<f32>(1.0), tex.rgb, usar_textura);
    let alfa = select(1.0, tex.a, usar_textura);
    var iluminacao = dados.ambiente.rgb;
    var reflexo = vec3<f32>(0.0);
    var normal = normalize(i.normal);
    if (dados.flags.w > 0.001) {
        let sample_normal = textureSample(mapa_normais, amostra, uv).xyz
                            * 2.0 - vec3<f32>(1.0);
        let dx = dpdx(i.mundo);
        let dy = dpdy(i.mundo);
        let duv_dx = dpdx(uv);
        let duv_dy = dpdy(uv);
        let determinante = duv_dx.x * duv_dy.y - duv_dx.y * duv_dy.x;
        if (abs(determinante) > 0.00001) {
            let tangente = normalize((dx * duv_dy.y - dy * duv_dx.y)
                                     / determinante);
            let bitangente = normalize((dy * duv_dx.x - dx * duv_dy.x)
                                       / determinante);
            normal = normalize(
                normal * sample_normal.z
                + dados.flags.w * (
                    tangente * sample_normal.x
                    + bitangente * sample_normal.y
                )
            );
        }
    }
    // Gradiente de altura na superfície em coordenadas de mundo. Derivadas
    // fora do ramo evitam controle de fluxo não uniforme no fragment shader.
    let altura = dot(textureSample(mapa_altura, amostra, uv).rgb,
                     vec3<f32>(1.0 / 3.0));
    let dhdx = dpdx(altura);
    let dhdy = dpdy(altura);
    let dp_dx = dpdx(i.mundo);
    let dp_dy = dpdy(i.mundo);
    if (dados.mapas_parametros.z > 0.0) {
        let r1 = cross(dp_dy, normal);
        let r2 = cross(normal, dp_dx);
        let det = dot(dp_dx, r1);
        if (abs(det) > 0.000000000001) {
            let gradiente = sign(det) * (dhdx * r1 + dhdy * r2);
            normal = normalize(abs(det) * normal
                     - dados.mapas_parametros.z * gradiente);
        }
    }
    let direcao_visao = normalize(dados.observador.xyz - i.mundo);
    // Skin GLSL oficial: oclusão ambiente, textura difusa e gradiente
    // horizontal de temperatura de cor (sampler1D legado em textura 2D).
    if (dados.shader_preset.x > 5.5 && dados.shader_preset.x < 6.5) {
        let ao = textureSample(mapa_ao, amostra, uv);
        var cor_skin = dados.ambiente.rgb * dados.cor.rgb * tex.rgb;
        if (dados.flags.z > 0.5) {
            let luz_skin = normalize(dados.luzes_posicao[0].xyz - i.mundo);
            let ndotl = max(dot(normal, luz_skin), 0.0);
            if (ndotl > 0.0) {
                let gradiente_x = clamp(ndotl * ao.b, 0.01, 0.99);
                let gradiente = textureSample(
                    mapa_gradiente, amostra,
                    vec2<f32>(gradiente_x, 0.5),
                ).rgb;
                cor_skin += fator_luz(0, i.mundo) * ndotl * ao.b * gradiente * tex.rgb;
                let meio = normalize(luz_skin + direcao_visao);
                let brilho = pow(
                    max(dot(normal, meio), 0.0),
                    max(dados.especular.w, 0.001),
                );
                cor_skin += dados.luzes_especular[0].rgb
                            * cor_especular * brilho * fator_luz(0, i.mundo);
            }
        }
        return vec4<f32>(cor_skin, tex.a * dados.cor.a);
    }
    // Phong original: iluminação por fragmento, uma luz, cor difusa,
    // ambiente, especular e mapa AO do Material original.
    if (dados.shader_preset.x > 2.5 && dados.shader_preset.x < 3.5) {
        let ambiente_phong = dados.ambiente.rgb * dados.shader_parametros.xyz;
        let tex_phong = rgb * ao_factor;
        var color_phong = ambiente_phong * tex_phong * dados.cor.rgb;
        if (dados.flags.z > 0.5) {
            let light_dir = normalize(dados.luzes_posicao[0].xyz - i.mundo);
            let ndotl = max(dot(normal, light_dir), 0.0);
            color_phong += dados.luzes_cor[0].rgb * tex_phong
                           * dados.cor.rgb * ndotl * fator_luz(0, i.mundo);
            if (ndotl > 0.0) {
                let half_dir = normalize(light_dir + direcao_visao);
                let expoente = max(1.0, dados.especular.w
                                       * (255.0 / 128.0));
                let especular_phong = pow(
                    max(dot(normal, half_dir), 0.0), expoente
                );
                color_phong += dados.luzes_especular[0].rgb
                               * cor_especular * especular_phong * fator_luz(0, i.mundo);
            }
        }
        return vec4<f32>(
            color_phong + dados.emissiva.rgb,
            alfa * dados.cor.a * i.cor.a,
        );
    }
    // Normalmap original: luz em espaço tangente. A base TBN é calculada
    // de derivadas da malha (acima), em vez do atributo GLSL gl_Tangent.
    // Usa a primeira luz e alfa opaco do fragment shader legado.
    if (dados.shader_preset.x > 4.5 && dados.shader_preset.x < 5.5) {
        let tex_color = tex.rgb;
        var rgb_normalmap = dados.ambiente.rgb * dados.cor.rgb * tex_color;
        if (dados.flags.z > 0.5) {
            let direcao = normalize(dados.luzes_posicao[0].xyz - i.mundo);
            let difusa = max(dot(direcao, normal), 0.0);
            rgb_normalmap += dados.luzes_cor[0].rgb * dados.cor.rgb
                             * tex_color * difusa * fator_luz(0, i.mundo);
            let especular_normal = pow(
                clamp(dot(reflect(-direcao, normal), direcao_visao), 0.0, 1.0),
                max(dados.especular.w, 0.001),
            );
            rgb_normalmap += dados.luzes_especular[0].rgb
                             * cor_especular * especular_normal * fator_luz(0, i.mundo);
        }
        return vec4<f32>(rgb_normalmap, 1.0);
    }
    // Toon original: limiar de silhueta, faixas de difusa e especular
    // com smoothstep, primeira luz e alfa da textura difusa.
    if (dados.shader_preset.x > 3.5 && dados.shader_preset.x < 4.5) {
        let sil = max(dot(normal, direcao_visao), 0.0);
        if (sil < dados.shader_parametros.x) {
            return vec4<f32>(0.0, 0.0, 0.0,
                             tex.a * dados.cor.a);
        }
        var multiplier = dados.shader_parametros.z;
        if (dados.flags.z > 0.5) {
            let light_dir = normalize(dados.luzes_posicao[0].xyz - i.mundo);
            let meio = normalize(light_dir + direcao_visao);
            let spec = pow(
                max(dot(normal, meio), 0.0),
                max(dados.shader_parametros.y, 0.0001),
            );
            multiplier += fator_luz(0, i.mundo) * dados.shader_parametros.w
                          * dot(spec_factor, vec3<f32>(1.0 / 3.0)) * smoothstep(
                dados.shader_parametros_extra.y - 0.01,
                dados.shader_parametros_extra.y,
                spec,
            );
            let diff = max(dot(normal, light_dir), 0.0);
            multiplier += fator_luz(0, i.mundo) * dados.shader_parametros_extra.x * smoothstep(
                dados.shader_parametros_extra.z - 0.01,
                dados.shader_parametros_extra.z,
                diff,
            );
        }
        return vec4<f32>(
            multiplier * tex.rgb, tex.a * dados.cor.a,
        );
    }
    // Port do litsphere_fragment_shader.txt: iluminação capturada em
    // textura indexada pela normal em espaço de câmera, sem luzes GLSL.
    if (dados.shader_preset.x > 1.5 && dados.shader_preset.x < 2.5) {
        let normal_visao = normalize(
            (dados.visao * vec4<f32>(normal, 0.0)).xyz
        );
        let coords = normal_visao.xy * 0.495 + vec2<f32>(0.5);
        // Qt/QImage lê a origem no topo; as UVs GLSL são bottom-up.
        let lit_uv = vec2<f32>(coords.x, 1.0 - coords.y);
        var iluminacao_lit = textureSample(mapa_litsphere, amostra, lit_uv).rgb;
        if (dados.shader_parametros.y > 0.5) {
            iluminacao_lit *= i.cor.rgb;
        }
        var cor_lit = iluminacao_lit;
        var alfa_lit = 1.0;
        if (dados.shader_parametros.z > 0.5) {
            let aditivo = dados.shader_parametros.x;
            let media = (iluminacao_lit.r + iluminacao_lit.g
                         + iluminacao_lit.b) / 3.0;
            cor_lit = (1.0 - aditivo) * iluminacao_lit * tex.rgb
                      * (2.0 - media)
                      + aditivo * (iluminacao_lit + tex.rgb);
            alfa_lit = tex.a;
        }
        return vec4<f32>(cor_lit, alfa_lit * dados.cor.a);
    }
    // Port do shader GLSL xray_fragment_shader.txt do MakeHuman.
    // Conserva o fade de contorno e os parâmetros de material originais.
    if (dados.shader_preset.x > 0.5 && dados.shader_preset.x < 1.5) {
        let frente = abs(dot(normal, direcao_visao));
        let intensidade = dados.shader_parametros.z;
        let contorno = dados.shader_parametros.x + intensidade
                     * (1.0 - pow(frente,
                                   max(dados.shader_parametros.y, 0.0001)));
        let cor_vertice = select(vec3<f32>(1.0), i.cor.rgb,
                                dados.shader_parametros.w > 0.5);
        let cor_xray = cor_vertice
                       + select(vec3<f32>(0.0), tex.rgb, usar_textura);
        return vec4<f32>(contorno * cor_xray, contorno);
    }
    for (var j: i32 = 0; j < 8; j = j + 1) {
        if (j >= i32(dados.flags.z)) {
            break;
        }
        let deslocamento = dados.luzes_posicao[j].xyz - i.mundo;
        let direcao = normalize(deslocamento);
        let difusa = max(dot(normal, direcao), 0.0);
        iluminacao += dados.luzes_cor[j].rgb * difusa * fator_luz(j, i.mundo);
        if (difusa > 0.0 && dados.especular.w > 0.0) {
            let meio = normalize(direcao + direcao_visao);
            let intensidade = pow(max(dot(normal, meio), 0.0),
                                  dados.especular.w);
            reflexo += dados.luzes_especular[j].rgb * cor_especular
                     * intensidade * fator_luz(j, i.mundo);
        }
    }
    let luz = select(iluminacao, vec3<f32>(1.0), dados.flags.x > 0.5);
    let brilho = select(reflexo, vec3<f32>(0.0), dados.flags.x > 0.5);
    let oclusao = select(ao_factor, vec3<f32>(1.0), dados.flags.x > 0.5);
    return vec4<f32>(rgb * oclusao * i.cor.rgb * dados.cor.rgb * luz
                     + brilho + dados.emissiva.rgb,
                     alfa * i.cor.a * dados.cor.a);
}

@fragment fn fs_main(i: Fragmento) -> @location(0) vec4<f32> {
    var resultado = cor_fragmento(i);
    // O mapa separado representa transparência (branco = transparente),
    // conforme TransparencyFactor do material/exportador original. Intensidade
    // zero preserva o alfa anterior, sem confundir transparência com opacidade.
    let uv = vec2<f32>(i.uv.x, 1.0 - i.uv.y);
    let trans = textureSample(mapa_transparencia, amostra, uv).rgb;
    resultado.a *= 1.0 - dados.mapas_parametros.y
                         * dot(trans, vec3<f32>(1.0 / 3.0));
    // Contrato original: glAlphaFunc(GL_GREATER, 0.0) descarta pixels
    // totalmente transparentes em malhas com partes recortadas.
    // O descarte ocorre antes de qualquer escrita de profundidade.
    if ((dados.shader_preset.z > 0.5 || dados.mapas_parametros.y > 0.0)
            && resultado.a <= 0.0) {
        discard;
    }
    return resultado;
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
        self._shaders_pendentes = set()
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
        preenchimento_wireframe = bool(getattr(obj, "_wireframe_preenchimento", False))
        chave = (bool(linhas), preenchimento_wireframe, *config)
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
                depth_bias=1 if preenchimento_wireframe else 0,
                depth_bias_slope_scale=1.0 if preenchimento_wireframe else 0.0,
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

    def framebuffer_offscreen(self, largura, altura, *, formato=None):
        """Aloca destino de renderização legível pela CPU, fora do swapchain."""
        from vulkan_offscreen import bytes_por_linha_alinhados
        largura, altura = int(largura), int(altura)
        bytes_por_linha_alinhados(largura)
        if altura < 1:
            raise ValueError("Altura offscreen deve ser positiva")
        formato = self.formato if formato is None else formato
        if formato not in ("rgba8unorm", "rgba8unorm-srgb",
                                "bgra8unorm", "bgra8unorm-srgb"):
            raise ValueError("Formato de framebuffer não suportado: " + str(formato))
        return self.device.create_texture(
            size=(largura, altura, 1),
            dimension="2d",
            format=formato,
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
        return decodificar_buffer_rgba(dados, largura, altura, alvo.format)

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
        from vulkan_lighting import (
            dados_iluminacao_cena, cores_especulares_cena, parametros_foco_atenuacao,
        )
        ambiente, posicoes, cores, total_luzes = dados_iluminacao_cena(
            self._cena_luzes,
        )
        cores_especulares = cores_especulares_cena(self._cena_luzes)
        direcoes_luzes, atenuacoes_luzes = parametros_foco_atenuacao(self._cena_luzes)
        self.objetos_desenhados = 0
        self.linhas_desenhadas = 0
        if mundo is not None:
            for obj in passes_wireframe(ordenar_objetos_vulkan(mundo, cameras)):
                if not obj.visibility:
                    continue
                if productionRender and getattr(obj, "excludeFromProduction", False):
                    continue
                try:
                    vertices, indices = preparar_malha_original(obj, cameras[obj.cameraMode])
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
                from vulkan_shader import (
                    configuracao_shader_nativo, textura_litsphere_nativa,
                    parametros_extras_shader_nativo,
                    textura_normalmap_nativa,
                    texturas_skin_nativas,
                )
                material_obj = getattr(obj, "material", None)
                modo_shader, shader_parametros, shader_pendente = (
                    configuracao_shader_nativo(material_obj)
                )
                textura_litsphere = (
                    textura_litsphere_nativa(material_obj)
                    if modo_shader == 2 else None
                )
                if modo_shader == 2 and textura_litsphere is None:
                    # Nunca declarar uma LitSphere branca como se fosse pele.
                    raise ValueError(
                        "Material LitSphere não contém litsphereTexture"
                    )
                if (shader_pendente and shader_pendente
                        not in self._shaders_pendentes):
                    self._shaders_pendentes.add(shader_pendente)
                    print(
                        "MAKEHUMANO_VULKAN: shader GLSL ainda não portado: "
                        + shader_pendente, flush=True,
                    )
                especular, emissiva, opacidade = aparencia_material_vulkan(obj)
                cor[3] = opacidade
                flags[2] = float(total_luzes)
                caminho_normal, intensidade_normal = parametros_normalmap_vulkan(obj)
                if modo_shader == 5:
                    caminho_normal = textura_normalmap_nativa(material_obj)
                    if caminho_normal is None:
                        raise ValueError(
                            "Preset normalmap exige normalmapTexture válida"
                        )
                    # O GLSL normalmap sempre utiliza a normal amostrada.
                    intensidade_normal = 1.0
                flags[3] = intensidade_normal
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
                normal_modelo = matriz_normal_vulkan(modelo)
                textura_ao = None
                forca_ao = 0.0
                textura_gradiente = None
                if modo_shader in (0, 3):
                    textura_ao, forca_ao = parametros_mapa(material_obj, "ao")
                elif modo_shader == 6:
                    textura_ao, textura_gradiente = (
                        texturas_skin_nativas(material_obj)
                    )
                    if textura_ao is None or textura_gradiente is None:
                        raise ValueError(
                            "Preset skin exige ambientOcclusionMap e gradientMap"
                        )
                shader_preset = np.array(
                    [
                        float(modo_shader),
                        float(textura_ao is not None),
                        float(bool(getattr(obj, "nTransparentPrimitives", 0))),
                        0.0,
                    ],
                    np.float32,
                )
                shader_extra = np.asarray(
                    parametros_extras_shader_nativo(material_obj),
                    dtype=np.float32,
                )
                mapa_spec, forca_spec = parametros_mapa(material_obj, "specular")
                mapa_trans, forca_trans = parametros_mapa(material_obj, "transparency")
                # Material._updateShaderConfig prioriza normal maps sobre bump.
                mapa_bump, forca_bump = (None, 0.0)
                if caminho_normal is None:
                    mapa_bump, forca_bump = parametros_mapa(material_obj, "bump")
                mapas_parametros = np.array([forca_spec, forca_trans, forca_bump, forca_ao], np.float32)
                uniforms = np.concatenate((
                    mvp.T.reshape(-1), modelo.T.reshape(-1),
                    normal_modelo.T.reshape(-1), view.T.reshape(-1),
                    cor, flags, ambiente, especular, emissiva, observador,
                    shader_preset, np.asarray(shader_parametros, np.float32),
                    shader_extra, posicoes.reshape(-1), cores.reshape(-1),
                    cores_especulares.reshape(-1), mapas_parametros,
                    direcoes_luzes.reshape(-1), atenuacoes_luzes.reshape(-1),
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
                textura_normal = self._textura(caminho_normal)
                textura_lit = self._textura(textura_litsphere)
                textura_oclusa = self._textura(textura_ao)
                textura_grad = self._textura(textura_gradiente)
                textura_spec = self._textura(mapa_spec)
                textura_trans = self._textura(mapa_trans)
                textura_altura = self._textura(mapa_bump)
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
                        wgpu.BindGroupEntry(
                            binding=3, resource=textura_normal.create_view()
                        ),
                        wgpu.BindGroupEntry(
                            binding=4, resource=textura_lit.create_view()
                        ),
                        wgpu.BindGroupEntry(
                            binding=5, resource=textura_oclusa.create_view()
                        ),
                        wgpu.BindGroupEntry(
                            binding=6, resource=textura_grad.create_view()
                        ),
                        wgpu.BindGroupEntry(binding=7, resource=textura_spec.create_view()),
                        wgpu.BindGroupEntry(binding=8, resource=textura_trans.create_view()),
                        wgpu.BindGroupEntry(binding=9, resource=textura_altura.create_view()),
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
