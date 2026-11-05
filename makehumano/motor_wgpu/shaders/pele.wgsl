// MakeHumano: primeiro material de pele em WGSL.
// Diffuse + especular GGX (dielétrico), sem subsurface scattering.
// A textura UV e a tonalidade podem ser trocadas sem recriar o renderizador.

struct CameraMaterial {
    mvp: mat4x4f,
    model: mat4x4f,
    tint: vec4f,
    surface: vec4f, // x = roughness
    eye: vec4f,
};

@group(0) @binding(0) var<uniform> material: CameraMaterial;
@group(0) @binding(1) var color_map: texture_2d<f32>;
@group(0) @binding(2) var color_sampler: sampler;

struct VertexIn {
    @location(0) position: vec3f,
    @location(1) normal: vec3f,
    @location(2) uv: vec2f,
};

struct VertexOut {
    @builtin(position) clip_position: vec4f,
    @location(0) world_position: vec3f,
    @location(1) world_normal: vec3f,
    @location(2) uv: vec2f,
};

@vertex
fn vs_main(in: VertexIn) -> VertexOut {
    var out: VertexOut;
    let p = material.model * vec4f(in.position, 1.0);
    out.clip_position = material.mvp * vec4f(in.position, 1.0);
    out.world_position = p.xyz;
    out.world_normal = normalize((material.model * vec4f(in.normal, 0.0)).xyz);
    out.uv = in.uv;
    return out;
}

@fragment
fn fs_main(in: VertexOut) -> @location(0) vec4f {
    let n = normalize(in.world_normal);
    let l = normalize(vec3f(0.35, 0.8, 0.55));
    let v = normalize(material.eye.xyz - in.world_position);
    let h = normalize(l + v);
    let nl = max(dot(n, l), 0.0);
    let nv = max(dot(n, v), 0.001);
    let nh = max(dot(n, h), 0.0);
    let vh = max(dot(v, h), 0.0);

    // A cor da textura é codificada em sRGB e é convertida para linear.
    let tex_srgb = textureSample(color_map, color_sampler, in.uv).rgb;
    let albedo = pow(tex_srgb * material.tint.rgb, vec3f(2.2));

    let roughness = clamp(material.surface.x, 0.05, 1.0);
    let a = roughness * roughness;
    let a2 = a * a;
    let denom = nh * nh * (a2 - 1.0) + 1.0;
    let distribution = a2 / max(3.14159265 * denom * denom, 0.00001);

    let k = pow(roughness + 1.0, 2.0) / 8.0;
    let shadow = (nl / (nl * (1.0 - k) + k)) *
                 (nv / (nv * (1.0 - k) + k));
    let f0 = vec3f(0.035); // material isolante; aproximação inicial para pele
    let fresnel = f0 + (vec3f(1.0) - f0) * pow(1.0 - vh, 5.0);
    let specular = (distribution * shadow * fresnel) / max(4.0 * nl * nv, 0.001);
    let diffuse = (vec3f(1.0) - fresnel) * albedo / 3.14159265;

    let linear_color = albedo * 0.20 + (diffuse + specular) * nl * 2.25;
    // Compressão de altas luzes e codificação para saída sRGB aproximada.
    let mapped = linear_color / (vec3f(1.0) + linear_color);
    return vec4f(pow(mapped, vec3f(1.0 / 2.2)), 1.0);
}
