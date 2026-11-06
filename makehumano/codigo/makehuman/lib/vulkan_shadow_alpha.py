"""Dados de cobertura originais para os raios de sombra WGSL.

Alfa8 e somas RGB uint16 são empacotados sem redimensionar ou quantização
adicional; o shader interpola os mesmos texels
com clamp-to-edge, filtro bilinear e origem superior usados pelo renderer.
"""
import os
import numpy as np

SURFACE_DTYPE = np.dtype([
    ('uv01', '<f4', 4), ('uv2_opacity', '<f4', 4), ('vertex_alpha', '<f4', 4),
    ('diffuse', '<u4', 4), ('transparency', '<u4', 4),
])


class PixelsSombra:
    def __init__(self):
        self.chunks = [np.array([0xffffffff], dtype='<u4')]
        self.count = 1
        self.descriptors = {}

    def registrar(self, resource, *, alpha_only=False):
        if resource is None:
            return (0, 0, 0, 0)
        from image import Image
        from vulkan_texture import getTexture
        from vulkan_scene import pixels_textura_rgba
        if isinstance(resource, (str, os.PathLike, Image)):
            resource = getTexture(resource)
        if resource is None:
            return (0, 0, 0, 0)
        data = np.asarray(resource.data)
        if (alpha_only and data.dtype == np.uint8 and data.ndim == 3
                and min(data.shape[:2]) > 0 and data.shape[2] in (1, 2, 3, 4)
                and (data.shape[2] in (1, 3) or np.all(data[:, :, -1] == 255))):
            return (0, 0, 0, 0)
        key = (id(resource), bool(alpha_only))
        if key in self.descriptors:
            return self.descriptors[key]
        rgba = pixels_textura_rgba(data)
        height, width = rgba.shape[:2]
        if alpha_only:
            values = np.ascontiguousarray(rgba[:, :, 3]).reshape(-1)
            values = np.pad(values, (0, (-len(values)) % 4))
            kind = 1
        else:
            # sum(R,G,B) is an exact integer 0..765. Keeping it avoids
            # quantizing luminance to an 8-bit average before filtering.
            values = rgba[:, :, :3].sum(axis=2, dtype=np.uint16).astype('<u2').reshape(-1)
            values = np.pad(values, (0, (-len(values)) % 2))
            kind = 2
        words = values.view('<u4')
        descriptor = (self.count, width, height, kind)
        self.chunks.append(words)
        self.count += len(words)
        self.descriptors[key] = descriptor
        return descriptor

    def pixels(self):
        return np.concatenate(self.chunks)


def superficies(obj, vertices, indices, pixels):
    from vulkan_material_maps import parametros_mapa
    from vulkan_shader import nome_preset_nativo
    material = getattr(obj, 'material', None)
    preset = nome_preset_nativo(getattr(material, 'shader', None))
    opacity = float(getattr(material, 'opacity', 1.))
    if not np.isfinite(opacity):
        raise ValueError('Opacidade não finita para sombras')
    opacity = float(np.clip(opacity, 0., 1.))
    config = getattr(material, 'shaderConfig', {}) or {}
    texture = getattr(obj, 'texture', None)
    if preset == 'normalmap':
        # O fragment shader oficial retorna alfa 1 antes do mapa separado.
        texture, opacity = None, 1.
    elif preset == 'litsphere':
        if not config.get('diffuse', False):
            texture = None
    elif preset not in ('toon', 'skin') and not getattr(obj, 'isTextured', True):
        texture = None
    transparency, strength = parametros_mapa(material, 'transparency')
    result = np.zeros(len(indices), SURFACE_DTYPE)
    uvs = vertices[:, 6:8][indices]
    result['uv01'] = uvs[:, :2].reshape(-1, 4)
    result['uv2_opacity'][:, :2] = uvs[:, 2]
    result['uv2_opacity'][:, 2:] = (opacity, strength)
    result['vertex_alpha'][:, :3] = (
        vertices[:, 11][indices] if preset in (None, 'phong') else 1.
    )
    result['diffuse'] = pixels.registrar(texture, alpha_only=True)
    result['transparency'] = pixels.registrar(transparency)
    return result


WGSL = """
struct ShadowSurface {
    uv01: vec4<f32>,
    uv2_opacity: vec4<f32>,
    vertex_alpha: vec4<f32>,
    diffuse: vec4<u32>,
    transparency: vec4<u32>,
};
@group(0) @binding(12) var<storage, read> shadow_surfaces: array<ShadowSurface>;
@group(0) @binding(13) var<storage, read> shadow_pixels: array<u32>;

fn shadow_texel(descriptor: vec4<u32>, coordinate: vec2<i32>) -> f32 {
    let pixel = clamp(coordinate, vec2<i32>(0), vec2<i32>(descriptor.yz) - vec2<i32>(1));
    let index = u32(pixel.y)*descriptor.y + u32(pixel.x);
    if (descriptor.w == 1u) {
        let word = shadow_pixels[descriptor.x + index/4u];
        return f32((word >> ((index%4u)*8u)) & 255u)/255.0;
    }
    let word = shadow_pixels[descriptor.x + index/2u];
    return f32((word >> ((index%2u)*16u)) & 65535u)/765.0;
}
fn shadow_sample(descriptor: vec4<u32>, uv: vec2<f32>) -> f32 {
    if (descriptor.y == 0u) { return 1.0; }
    let coordinate = clamp(vec2<f32>(uv.x, 1.0-uv.y), vec2<f32>(0.0), vec2<f32>(1.0))
                     * vec2<f32>(descriptor.yz) - vec2<f32>(0.5);
    let lower = vec2<i32>(floor(coordinate));
    let fraction = fract(coordinate);
    let a = mix(shadow_texel(descriptor, lower), shadow_texel(descriptor, lower + vec2<i32>(1, 0)), fraction.x);
    let b = mix(shadow_texel(descriptor, lower + vec2<i32>(0, 1)), shadow_texel(descriptor, lower + vec2<i32>(1, 1)), fraction.x);
    return mix(a, b, fraction.y);
}
fn shadow_alpha(index: u32, barycentric: vec3<f32>) -> f32 {
    let surface = shadow_surfaces[index];
    let uv = surface.uv01.xy * barycentric.x + surface.uv01.zw * barycentric.y
             + surface.uv2_opacity.xy * barycentric.z;
    let diffuse = shadow_sample(surface.diffuse, uv);
    let transparency = shadow_sample(surface.transparency, uv);
    let vertex = dot(surface.vertex_alpha.xyz, barycentric);
    return clamp(diffuse * surface.uv2_opacity.z * vertex
                 * (1.0 - surface.uv2_opacity.w * transparency), 0.0, 1.0);
}
"""
