"""Oclusão de luz Vulkan: BVH CPU da cena original, raios executados em WGSL.

Não há rasterizador CPU nem dependência de extensões de ray tracing. A árvore
é achatada em pré-ordem, com índices de escape para percurso sem pilha GPU.
A cobertura do Material original controla recorte e transmissão escalar.
"""
import hashlib
import numpy as np

NODE_DTYPE = np.dtype([('minimum', '<f4', 4), ('maximum', '<f4', 4), ('span', '<u4', 4)])


def construir_bvh(triangles, leaf_size=8, *, metadata=False):
    triangles = np.asarray(triangles, dtype=np.float32)
    if triangles.shape == (0,):
        triangles = triangles.reshape(0, 3, 3)
    if triangles.ndim != 3 or triangles.shape[1:] != (3, 3) or not np.isfinite(triangles).all():
        raise ValueError('Sombras exigem triângulos finitos Nx3x3')
    if leaf_size < 1:
        raise ValueError('Folhas da BVH devem conter ao menos um triângulo')
    if not len(triangles):
        empty = (np.zeros(0, NODE_DTYPE), np.zeros((0, 3, 4), np.float32))
        return (*empty, np.zeros(0, np.intp), ()) if metadata else empty
    minimum = triangles.min(axis=1)
    maximum = triangles.max(axis=1)
    centers = (minimum + maximum) * .5
    nodes, ordered = [], []

    def visit(indices):
        index = len(nodes)
        lo, hi = minimum[indices].min(axis=0), maximum[indices].max(axis=0)
        nodes.append(None)
        first, count = 0, 0
        if len(indices) <= leaf_size:
            first, count = len(ordered), len(indices)
            ordered.extend(indices)
        else:
            axis = int(np.argmax(np.ptp(centers[indices], axis=0)))
            sequence = indices[np.argsort(centers[indices, axis], kind='stable')]
            middle = len(sequence)//2
            visit(sequence[:middle])
            visit(sequence[middle:])
        nodes[index] = (lo, hi, first, count, len(nodes))

    visit(np.arange(len(triangles)))
    result = np.zeros(len(nodes), NODE_DTYPE)
    for index, (lo, hi, first, count, escape) in enumerate(nodes):
        result['minimum'][index, :3] = lo
        result['maximum'][index, :3] = hi
        result['span'][index, :3] = (first, count, escape)
    packed = np.zeros((len(triangles), 3, 4), np.float32)
    packed[:, :, :3] = triangles[ordered]
    if not metadata:
        return result, packed
    levels, current = [], np.array([0], np.intp)
    while len(current):
        internal = current[result['span'][current, 1] == 0]
        if not len(internal):
            break
        levels.append(internal)
        left = internal+1
        current = np.concatenate((left, result['span'][left, 2])).astype(np.intp)
    return result, packed, np.asarray(ordered, np.intp), tuple(reversed(levels))


def reajustar_bvh(triangles, nodes, order, levels):
    """Recalcula limites após morph/pose sem particionar novamente a malha."""
    packed = np.zeros((len(order), 3, 4), np.float32)
    if not len(order):
        return packed
    packed[:, :, :3] = triangles[order]
    leaves = np.flatnonzero(nodes['span'][:, 1])
    starts = nodes['span'][leaves, 0]
    nodes['minimum'][leaves, :3] = np.minimum.reduceat(packed[:, :, :3].min(axis=1), starts, axis=0)
    nodes['maximum'][leaves, :3] = np.maximum.reduceat(packed[:, :, :3].max(axis=1), starts, axis=0)
    for internal in levels:
        left = internal+1
        right = nodes['span'][left, 2]
        nodes['minimum'][internal, :3] = np.minimum(nodes['minimum'][left, :3], nodes['minimum'][right, :3])
        nodes['maximum'][internal, :3] = np.maximum(nodes['maximum'][left, :3], nodes['maximum'][right, :3])
    return packed


def dados_cena(mundo, cameras, production=False):
    from vulkan_scene import preparar_malha_original
    from vulkan_shadow_alpha import superficies, PixelsSombra
    from vulkan_shader import nome_preset_nativo
    result, surface_data = [], []
    pixels = PixelsSombra()
    for obj in mundo or ():
        material = getattr(obj, 'material', None)
        if (not obj.visibility or obj.cameraMode != 0 or getattr(obj, 'depthless', False)
                or not getattr(material, 'castShadows', True)
                or (production and getattr(obj, 'excludeFromProduction', False))):
            continue
        faces = np.asarray(obj.primitives)
        if faces.ndim != 2 or faces.shape[1] not in (3, 4) or not len(faces):
            continue
        if nome_preset_nativo(getattr(material, 'shader', None)) == 'xray':
            continue
        vertices, indices = preparar_malha_original(obj)
        indices = indices.reshape(-1, 3)
        if not len(indices):
            continue
        surface_data.append(superficies(obj, vertices, indices, pixels))
        model = np.asarray(cameras[obj.cameraMode].getModelMatrix(obj), np.float32)
        if model.shape != (4, 4) or not np.isfinite(model).all():
            raise ValueError('Modelo original inválido para sombras')
        positions = vertices[:, :3] @ model[:3, :3].T + model[:3, 3]
        result.append(positions[indices])
    from vulkan_shadow_alpha import SURFACE_DTYPE
    triangles = np.ascontiguousarray(np.concatenate(result) if result else np.empty((0, 3, 3)), dtype=np.float32)
    surfaces = np.concatenate(surface_data) if surface_data else np.zeros(0, SURFACE_DTYPE)
    return triangles, surfaces, pixels.pixels()


def triangulos_cena(mundo, cameras, production=False):
    """Geometria visível dos oclusores, sem excluir faces só por serem alpha."""
    return dados_cena(mundo, cameras, production)[0]


def preparar_buffers(cena, mundo, cameras, production=False):
    from vulkan_shadow_alpha import SURFACE_DTYPE
    triangles, surfaces, pixels = dados_cena(mundo, cameras, production)
    signature = hashlib.blake2b(triangles, digest_size=16).digest()
    cache = getattr(cena, '_shadow_cache', None)
    usage = cena.wgpu.BufferUsage.STORAGE
    if cache is None or cache[0] != signature:
        topology = getattr(cena, '_shadow_topology', None)
        if topology is not None and len(topology[1]) == len(triangles):
            nodes, order, levels = topology
            packed = reajustar_bvh(triangles, nodes, order, levels)
        else:
            nodes, packed, order, levels = construir_bvh(triangles, metadata=True)
            cena._shadow_topology = (nodes, order, levels)
        node_buffer = cena.device.create_buffer_with_data(data=nodes if len(nodes) else np.zeros(1, NODE_DTYPE), usage=usage)
        triangle_buffer = cena.device.create_buffer_with_data(data=packed if len(packed) else np.zeros((1, 3, 4), np.float32), usage=usage)
        extent = float(np.linalg.norm(np.ptp(triangles.reshape(-1, 3), axis=0))) if len(triangles) else 1.
        bias = max(1e-6, extent*2e-5)
        cache = cena._shadow_cache = (signature, node_buffer, triangle_buffer, len(nodes), bias)
    order = cena._shadow_topology[1]
    ordered_surfaces = np.ascontiguousarray(surfaces[order])
    hasher = hashlib.blake2b(ordered_surfaces, digest_size=16)
    hasher.update(pixels)
    alpha_signature = hasher.digest()
    alpha_cache = getattr(cena, '_shadow_alpha_cache', None)
    if alpha_cache is None or alpha_cache[0] != alpha_signature:
        limit = getattr(cena.device, 'limits', {}).get('max-storage-buffer-binding-size', 128*1024*1024)
        if max(ordered_surfaces.nbytes, pixels.nbytes) > limit:
            raise ValueError('Dados alpha de sombras excedem o limite de storage buffer do dispositivo')
        surface_buffer = cena.device.create_buffer_with_data(
            data=ordered_surfaces if len(ordered_surfaces) else np.zeros(1, SURFACE_DTYPE), usage=usage)
        pixel_buffer = cena.device.create_buffer_with_data(data=pixels, usage=usage)
        alpha_cache = cena._shadow_alpha_cache = (alpha_signature, surface_buffer, pixel_buffer)
    return cache[1], cache[2], alpha_cache[1], alpha_cache[2], cache[3], cache[4]


WGSL = """
struct ShadowNode {
    minimum: vec4<f32>,
    maximum: vec4<f32>,
    span: vec4<u32>,
};
struct ShadowTriangle { a: vec4<f32>, b: vec4<f32>, c: vec4<f32> };
@group(0) @binding(10) var<storage, read> shadow_nodes: array<ShadowNode>;
@group(0) @binding(11) var<storage, read> shadow_triangles: array<ShadowTriangle>;

fn shadow_box(origin: vec3<f32>, direction: vec3<f32>, node: ShadowNode, limit: f32) -> bool {
    var near = 0.0;
    var far = limit;
    for (var axis = 0u; axis < 3u; axis++) {
        if (abs(direction[axis]) < 0.00000001) {
            if (origin[axis] < node.minimum[axis] || origin[axis] > node.maximum[axis]) { return false; }
        } else {
            let a = (node.minimum[axis] - origin[axis]) / direction[axis];
            let b = (node.maximum[axis] - origin[axis]) / direction[axis];
            near = max(near, min(a, b));
            far = min(far, max(a, b));
            if (near > far) { return false; }
        }
    }
    return true;
}
fn shadow_edge(a: vec2<f32>, b: vec2<f32>) -> f32 {
    return a.x*b.y - a.y*b.x;
}
fn shadow_inclusive(a: vec2<f32>, b: vec2<f32>, orientation: f32) -> bool {
    let delta = (b-a)*orientation;
    return delta.y > 0.0 || (delta.y == 0.0 && delta.x < 0.0);
}
fn shadow_hit(origin: vec3<f32>, direction: vec3<f32>, triangle: ShadowTriangle, limit: f32, bias: f32) -> vec3<f32> {
    // Project onto the plane perpendicular to the dominant ray component.
    // Half-open edges assign a shared diagonal to exactly one triangle;
    // otherwise partial alpha would attenuate twice along a quad's seam.
    var kz = 0u;
    if (abs(direction.y) > abs(direction[kz])) { kz = 1u; }
    if (abs(direction.z) > abs(direction[kz])) { kz = 2u; }
    let kx = (kz+1u)%3u;
    let ky = (kx+1u)%3u;
    let shear = vec2<f32>(direction[kx], direction[ky])/direction[kz];
    let a = triangle.a.xyz-origin;
    let b = triangle.b.xyz-origin;
    let c = triangle.c.xyz-origin;
    let pa = vec2<f32>(a[kx], a[ky])-shear*a[kz];
    let pb = vec2<f32>(b[kx], b[ky])-shear*b[kz];
    let pc = vec2<f32>(c[kx], c[ky])-shear*c[kz];
    let weights = vec3<f32>(shadow_edge(pb, pc), shadow_edge(pc, pa), shadow_edge(pa, pb));
    let determinant = weights.x+weights.y+weights.z;
    let miss = vec3<f32>(-1.0);
    if (abs(determinant) < 0.000000000001) { return miss; }
    let orientation = sign(determinant);
    if (any(weights*orientation < vec3<f32>(0.0))) { return miss; }
    if (weights.x == 0.0 && !shadow_inclusive(pb, pc, orientation)) { return miss; }
    if (weights.y == 0.0 && !shadow_inclusive(pc, pa, orientation)) { return miss; }
    if (weights.z == 0.0 && !shadow_inclusive(pa, pb, orientation)) { return miss; }
    let barycentric = weights/determinant;
    let distance = dot(barycentric, vec3<f32>(a[kz], b[kz], c[kz]))/direction[kz];
    if (distance <= bias || distance >= limit-bias) { return miss; }
    return barycentric;
}
fn shadow_visibility(position: vec3<f32>, light: vec3<f32>) -> f32 {
    let count = u32(dados.amostragem_luzes.z);
    if (dados.amostragem_luzes.y < 0.5 || count == 0u) { return 1.0; }
    let delta = light - position;
    let distance = length(delta);
    let bias = dados.amostragem_luzes.w;
    if (distance <= 2.0 * bias) { return 1.0; }
    let direction = delta / distance;
    var index = 0u;
    var visibility = 1.0;
    loop {
        if (index >= count) { break; }
        let node = shadow_nodes[index];
        if (!shadow_box(position, direction, node, distance)) {
            index = node.span.z;
        } else if (node.span.y == 0u) {
            index += 1u;
        } else {
            for (var t = 0u; t < node.span.y; t++) {
                let triangle_index = node.span.x + t;
                let barycentric = shadow_hit(position, direction, shadow_triangles[triangle_index], distance, bias);
                if (barycentric.x >= 0.0) {
                    visibility *= 1.0-shadow_alpha(triangle_index, barycentric);
                    if (visibility <= 0.0) { return 0.0; }
                }
            }
            index = node.span.z;
        }
    }
    return visibility;
}
"""
