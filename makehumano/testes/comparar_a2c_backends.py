"""Audita controle A2C RGB em GL original e Vulkan, sem homologar paridade.

O baseline OFF/ON muda três estados: cobertura, blending e escrita Z. Os
controles extras isolam essas três TRANSIÇÕES, sem igualar cores GL/Vulkan.
"""
import argparse
import json
from pathlib import Path


CASOS = ("1x_sem_a2c", "4x_sem_a2c", "4x_com_a2c", "4x_inelegivel")
CONTROLES_EXTRAS = (
    "4x_sem_a2c_sem_blend_sem_z",
    "4x_sem_a2c_sem_blend_com_z",
)
FATORES = {
    # Cada par altera SOMENTE o estado indicado, sob MSAA 4x.
    "somente_blend_4x": ("4x_sem_a2c", "4x_sem_a2c_sem_blend_sem_z"),
    "somente_depth_write_4x": (
        "4x_sem_a2c_sem_blend_sem_z", "4x_sem_a2c_sem_blend_com_z",
    ),
    "somente_a2c_4x": ("4x_sem_a2c_sem_blend_com_z", "4x_com_a2c"),
}


def _assert(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def comparar_manifestos(gl, vk):
    _assert(gl.get("estado") == "CAPTURADO", "Manifesto OpenGL incompleto")
    _assert(vk.get("estado") == "OBSERVADO", "Manifesto Vulkan incompleto")
    _assert(gl.get("backend") == "OpenGL", "Backend GL incorreto")
    _assert(vk.get("backend") == "Vulkan", "Backend Vulkan incorreto")
    _assert(gl.get("dimensoes_imagem") == vk.get("dimensoes_imagem") == [1024, 768],
            "Dimensões incompatíveis")
    controle_gl = gl["textura_controle"]
    controle_vk = vk["textura_controle"]
    for chave in ("sha256_png", "sha256_rgba", "alfa_textura"):
        _assert(controle_gl[chave] == controle_vk[chave],
                "Textura de referência incompatível: " + chave)
    _assert(controle_gl["alfa_textura"] == 128,
            "A2C exige controle RGBA de alfa 128")
    for chave in ("fov", "radius", "centro", "projecao"):
        _assert(gl["camera"][chave] == vk["camera"][chave],
                "Câmera distinta: " + chave)
    _assert("1x_sem_a2c" in gl.get("controles", {}),
            "Falta captura RGB 1x GL")
    _assert("1x_sem_a2c" in vk.get("controles", {}),
            "Falta captura RGB 1x Vulkan")
    _assert(gl["controles"]["1x_sem_a2c"]["a2c_elegivel"] is False,
            "GL baseline A2C incorreto")
    _assert(vk["controles"]["1x_sem_a2c"]["a2c_elegivel"] is False,
            "VK baseline A2C incorreto")
    relatorio = {
        "tipo": "COMPARACAO_A2C_RGB_SEM_HOMOLOGACAO",
        "nao_homologado": True,
        "shader": "Phong",
        "controle_alfa": 128,
        "sha256_textura_png": controle_gl["sha256_png"],
        "dimensoes": [1024, 768],
        "observado": {},
        "limites": (
            "RGB 4x baseline OFF/ON mistura cobertura, blend e escrita Z. "
            "Os três contrastes controlados isolam mudanças de estado, "
            "mas não homologam a paridade de amostragem ou cor."
        ),
    }
    if not vk["suporte_msaa"].get("disponivel"):
        relatorio["estado"] = "NAO_TESTAVEL_VULKAN_4X"
        return relatorio
    if not gl["suporte_msaa"].get("testavel"):
        relatorio["estado"] = "NAO_TESTAVEL_OPENGL_4X"
        relatorio["motivo"] = gl["suporte_msaa"].get(
            "erro_fbo_4x", "GL_ARB_multisample ou FBO 4x indisponível"
        )
        return relatorio
    _assert(gl.get("resultado_a2c") == "EXECUTADO_COM_MSAA_4X",
            "GL não comprovou uso de MSAA 4x")
    _assert(vk.get("resultado_a2c") in (
        "EXECUTADO_DIFERENCA_RGB", "EXECUTADO_SEM_DIFERENCA_RGB"
    ), "Vulkan não comprovou captura RGB 4x")
    for nome in CASOS:
        a, b = gl["controles"][nome], vk["controles"][nome]
        esperado = nome == "4x_com_a2c"
        _assert(a["a2c_elegivel"] is esperado and
                b["a2c_elegivel"] is esperado,
                "A2C elegibilidade divergente: " + nome)
        _assert(a["pipeline_a2c_observado"] is esperado and
                b["pipeline_a2c_observado"] is esperado,
                "Pipeline A2C não observado: " + nome)
        quantidade = 1 if nome == "1x_sem_a2c" else 4
        _assert(a["amostras"] == b["amostras"] == quantidade,
                "Amostras reais inconsistentes: " + nome)
        _assert(a["amostras_fbo_observadas"] == (0 if quantidade == 1 else 4),
                "GL_SAMPLES real inconsistente: " + nome)
        _assert(a["captura_rgb"] is True and b["captura_rgb"] is True
                and len(a["sha256_rgb"]) == len(b["sha256_rgb"]) == 64,
                "Capturas RGB não comprovadas: " + nome)
        if esperado:
            _assert(a["rastros_gl"]["ativacoes_a2c"] > 0,
                    "GL_SAMPLE_ALPHA_TO_COVERAGE não observado")
            _assert(a["nTransparentPrimitives"] > 0 and
                    b["nTransparentPrimitives"] > 0,
                    "Corpo sem primitivas A2C: " + nome)
        if nome == "4x_inelegivel":
            _assert(a["nTransparentPrimitives"] == b["nTransparentPrimitives"] == 0,
                    "Controle negativo não é inelegível")
        relatorio["observado"][nome] = {
            "amostras_reais": quantidade,
            "opengl_ativou_gl_sample_alpha_to_coverage": bool(
                a["rastros_gl"]["ativacoes_a2c"]
            ),
            "vulkan_a2c_pipeline": b["pipeline_a2c_observado"],
            "primitivas_gl": a["nTransparentPrimitives"],
            "primitivas_vk": b["nTransparentPrimitives"],
        }
    estados_esperados = {
        "4x_sem_a2c": (True, False, False),
        "4x_sem_a2c_sem_blend_sem_z": (False, False, False),
        "4x_sem_a2c_sem_blend_com_z": (False, True, False),
        "4x_com_a2c": (False, True, True),
    }
    for nome, (blend, escrever_z, a2c_ativo) in estados_esperados.items():
        for backend, manifesto in (("OpenGL", gl), ("Vulkan", vk)):
            registro = manifesto["controles"].get(nome)
            _assert(registro is not None,
                    f"Falta controle de isolamento {nome} em {backend}")
            _assert(registro["amostras"] == 4
                    and registro["nTransparentPrimitives"] > 0
                    and registro["captura_rgb"] is True,
                    f"Controle MSAA 4x inválido: {backend} {nome}")
            _assert(registro["blend_habilitado_observado"] is blend,
                    f"Blending observado incorreto: {backend} {nome}")
            _assert(registro["escrita_z_observada"] is escrever_z,
                    f"Escrita Z observada incorreta: {backend} {nome}")
            _assert(registro["pipeline_a2c_observado"] is a2c_ativo,
                    f"A2C observado incorreto: {backend} {nome}")
            if backend == "OpenGL":
                _assert(registro["amostras_fbo_observadas"] == 4
                        and registro["rastros_gl"]["draw_states"],
                        f"FBO/draw GL ausente: {nome}")
                _assert(all(
                    d == {"blend": blend, "escrita_z": escrever_z,
                          "a2c": a2c_ativo}
                    for d in registro["rastros_gl"]["draw_states"]
                ), f"Estado GL efetivo diferente: {nome}")
            else:
                _assert(registro["pipeline_chave_cache_confirmada"] is True
                        and registro["rastros_pipeline_corpo"],
                        f"Pipeline Vulkan ausente: {nome}")
                _assert(all(
                    d["blend_habilitado_previsto"] is blend
                    and d["escrita_z_prevista"] is escrever_z
                    and d["a2c_calculado"] is a2c_ativo
                    for d in registro["rastros_pipeline_corpo"]
                ), f"Estado Vulkan previsto diferente: {nome}")
    relatorio["isolamento_estados"] = {
        "estado": "CONTROLES_INTERMEDIARIOS_VALIDOS",
        "fatores": {
            nome: {
                "de": de, "para": para,
                "opengl": gl["comparacao"][nome],
                "vulkan": vk["comparacao"][nome],
            }
            for nome, (de, para) in FATORES.items()
        },
        "ressalva": (
            "O isolamento mantém fixos blend e escrita Z no ensaio de "
            "cobertura A2C. Ainda há diferenças de implementação de "
            "amostras e shader entre OpenGL e Vulkan."
        ),
    }
    relatorio["estado"] = "CONTROLES_RGB_4X_EM_AMBOS_BACKENDS"
    relatorio["mudanca_4x_off_on_rgb"] = {
        "opengl": gl["comparacao"]["a2c_4x_off_vs_on"],
        "vulkan": vk["comparacao"]["a2c_4x_off_vs_on"],
    }
    return relatorio


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opengl", type=Path, required=True)
    p.add_argument("--vulkan", type=Path, required=True)
    p.add_argument("--json", type=Path, required=True)
    args = p.parse_args()
    gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    resultado = comparar_manifestos(gl, vk)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
