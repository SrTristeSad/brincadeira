// MakeHumano: material WGSL com GGX e aproximação ARTÍSTICA de dispersão.
// Dispersão single-pass aproximada: não é SSS físico (sem espessura nem blur).
// A textura UV, o mapa de normais e a rugosidade podem ser trocados em tempo real.

struct CameraMaterial {
    mvp: mat4x4f,
    model: mat4x4f,
    tint: vec4f,
    surface: vec4f, // x = roughness; y = normal map ativo; z = dispersao
    eye: vec4f,
};

@group(0) @binding(0) var<uniform> material: CameraMaterial;
@group(0) @binding(1) var color_map: texture_2d<f32>;
@group(0) @binding(2) var color_sampler: sampler;
@group(0) @binding(3) var normal_map: texture_2d<f32>;
@group(0) @binding(4) var roughness_map: texture_2d<f32>;

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
    var n = normalize(in.world_normal);

    // Base tangente calculada a partir das derivadas de posição e UV.
    // Não altera a topologia nem os buffers de vértices do MakeHuman.
    // Os mapas de normais seguem a convenção OpenGL (+Y).
    let dp_x = dpdx(in.world_position);
    let dp_y = dpdy(in.world_position);
    let duv_x = dpdx(in.uv);
    let duv_y = dpdy(in.uv);
    let determinante = duv_x.x * duv_y.y - duv_x.y * duv_y.x;
    if (material.surface.y > 0.5 && abs(determinante) > 0.000001) {
        let sinal = select(-1.0, 1.0, determinante >= 0.0);
        let tangente_raw = (dp_x * duv_y.y - dp_y * duv_x.y) * sinal;
        let tangente = tangente_raw - n * dot(n, tangente_raw);
        if (dot(tangente, tangente) > 0.00000001) {
            let t = normalize(tangente);
            let b = normalize(cross(n, t)) * sinal;
            let normal_ts = normalize(
                textureSample(normal_map, color_sampler, in.uv).xyz * 2.0
                - vec3f(1.0)
            );
            n = normalize(t * normal_ts.x + b * normal_ts.y + n * normal_ts.z);
        }
    }

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

    // O mapa de rugosidade utiliza o canal R em espaço linear.
    // Branco = fator 1; por isso a ausência do mapa preserva o slider.
    let roughness = clamp(
        material.surface.x * textureSample(roughness_map, color_sampler, in.uv).r,
        0.05, 1.0
    );
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

    // Dispersão difusa aproximada: amplia suavemente o lóbulo de iluminação
    // na borda e aquece a resposta (simulando parte da luz espalhada na pele).
    // Sem translucência volumétrica, blur, mapa de espessura ou ray tracing.
    // Intensidade zero reproduz exatamente a iluminação anterior.
    let ndotl = dot(n, l);
    let wrapped = max((ndotl + 0.45) / 1.45, 0.0);
    let espalhamento = max(wrapped - nl, 0.0);
    let tinta_subsuperficie = vec3f(1.0, 0.46, 0.34);
    let extra_difuso = (albedo / 3.14159265) * tinta_subsuperficie
        * espalhamento * 1.2 * clamp(material.surface.z, 0.0, 1.0);

    let linear_color = albedo * 0.20
        + (diffuse * nl + specular * nl + extra_difuso) * 2.25;
    // Compressão de altas luzes e codificação para saída sRGB aproximada.
    let mapped = linear_color / (vec3f(1.0) + linear_color);
    return vec4f(pow(mapped, vec3f(1.0 / 2.2)), 1.0);
}
