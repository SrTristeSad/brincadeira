"""Oclusão de luz Vulkan: BVH CPU da cena original, raios executados em WGSL.

Não há rasterizador CPU nem dependência de extensões de ray tracing. A árvore
é achatada em pré-ordem, com índices de escape para percurso sem pilha GPU.
Nesta etapa somente superfícies opacas lançam sombras.
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


def triangulos_cena(mundo, cameras, production=False):
    from vulkan_scene import preparar_malha_original, mapa_transparencia_ativo
    from vulkan_texture import getTexture
    from vulkan_scene import pixels_textura_rgba
    result = []
    for obj in mundo or ():
        material = getattr(obj, 'material', None)
        if (not obj.visibility or obj.cameraMode != 0 or getattr(obj, 'depthless', False)
                or not getattr(material, 'castShadows', True)
                or (production and getattr(obj, 'excludeFromProduction', False))):
            continue
        faces = np.asarray(obj.primitives)
        if faces.ndim != 2 or faces.shape[1] not in (3, 4) or not len(faces):
            continue
        if (getattr(material, 'transparent', False)
                or float(getattr(material, 'opacity', 1.)) < 1.
                or mapa_transparencia_ativo(material)):
            continue
        # Não projetar o retângulo opaco de texturas com recortes alpha.
        # Oclusão com transmissão/recorte requer outro contrato de material.
        if getattr(obj, 'isTextured', False) and getattr(obj, 'texture', None) is not None:
            resource = obj.texture
            if isinstance(resource, (str, bytes)) or hasattr(resource, '__fspath__'):
                resource = getTexture(resource)
            from image import Image
            if isinstance(resource, Image):
                resource = getTexture(resource)
            if resource is not None and hasattr(resource, 'data'):
                rgba = pixels_textura_rgba(np.asarray(resource.data))
                if np.any(rgba[:, :, 3] < 255):
                    continue
        if np.any(np.asarray(obj.color)[:, 3] < 255):
            continue
        # Faces translúcidas originais ficam no fim da lista de primitivas.
        opaque = len(faces) - min(max(int(getattr(obj, 'nTransparentPrimitives', 0)), 0), len(faces))
        if not opaque:
            continue
        vertices, indices = preparar_malha_original(obj)
        indices = indices.reshape(-1, 3)
        if faces.shape[1] == 4:
            mask = np.arange(len(faces)) < opaque
            raw = np.concatenate((faces[:, [0, 1, 2]], faces[:, [0, 2, 3]]))
            valid = (raw[:, 0] != raw[:, 1]) & (raw[:, 1] != raw[:, 2]) & (raw[:, 0] != raw[:, 2])
            indices = raw[valid & np.tile(mask, 2)]
        elif opaque < len(faces):
            raw = faces[:opaque]
            indices = raw[(raw[:, 0] != raw[:, 1]) & (raw[:, 1] != raw[:, 2]) & (raw[:, 0] != raw[:, 2])]
        model = np.asarray(cameras[obj.cameraMode].getModelMatrix(obj), np.float32)
        if model.shape != (4, 4) or not np.isfinite(model).all():
            raise ValueError('Modelo original inválido para sombras')
        positions = vertices[:, :3] @ model[:3, :3].T + model[:3, 3]
        result.append(positions[indices])
    return np.ascontiguousarray(np.concatenate(result) if result else np.empty((0, 3, 3)), dtype=np.float32)


def preparar_buffers(cena, mundo, cameras, production=False):
    triangles = triangulos_cena(mundo, cameras, production)
    signature = hashlib.blake2b(triangles, digest_size=16).digest()
    cache = getattr(cena, '_shadow_cache', None)
    if cache is not None and cache[0] == signature:
        return cache[1:]
    topology = getattr(cena, '_shadow_topology', None)
    if topology is not None and len(topology[1]) == len(triangles):
        nodes, order, levels = topology
        packed = reajustar_bvh(triangles, nodes, order, levels)
    else:
        nodes, packed, order, levels = construir_bvh(triangles, metadata=True)
        cena._shadow_topology = (nodes, order, levels)
    usage = cena.wgpu.BufferUsage.STORAGE
    node_buffer = cena.device.create_buffer_with_data(data=nodes if len(nodes) else np.zeros(1, NODE_DTYPE), usage=usage)
    triangle_buffer = cena.device.create_buffer_with_data(data=packed if len(packed) else np.zeros((1, 3, 4), np.float32), usage=usage)
    extent = float(np.linalg.norm(np.ptp(triangles.reshape(-1, 3), axis=0))) if len(triangles) else 1.
    bias = max(1e-6, extent*2e-5)
    cena._shadow_cache = (signature, node_buffer, triangle_buffer, len(nodes), bias)
    return cena._shadow_cache[1:]


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
fn shadow_hit(origin: vec3<f32>, direction: vec3<f32>, triangle: ShadowTriangle, limit: f32, bias: f32) -> bool {
    let edge1 = triangle.b.xyz - triangle.a.xyz;
    let edge2 = triangle.c.xyz - triangle.a.xyz;
    let p = cross(direction, edge2);
    let determinant = dot(edge1, p);
    if (abs(determinant) < 0.00000001) { return false; }
    let inverse = 1.0 / determinant;
    let delta = origin - triangle.a.xyz;
    let u = dot(delta, p) * inverse;
    if (u < 0.0 || u > 1.0) { return false; }
    let q = cross(delta, edge1);
    let v = dot(direction, q) * inverse;
    if (v < 0.0 || u + v > 1.0) { return false; }
    let distance = dot(edge2, q) * inverse;
    return distance > bias && distance < limit - bias;
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
    loop {
        if (index >= count) { break; }
        let node = shadow_nodes[index];
        if (!shadow_box(position, direction, node, distance)) {
            index = node.span.z;
        } else if (node.span.y == 0u) {
            index += 1u;
        } else {
            for (var t = 0u; t < node.span.y; t++) {
                if (shadow_hit(position, direction, shadow_triangles[node.span.x + t], distance, bias)) { return 0.0; }
            }
            index = node.span.z;
        }
    }
    return 1.0;
}
"""
