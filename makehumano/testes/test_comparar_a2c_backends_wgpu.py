"""Contrato dos relatórios A2C GL/Vulkan, sem GPU."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comparar_a2c_backends import comparar_manifestos


def modelos():
    textura = {
        "sha256_png": "a" * 64,
        "sha256_rgba": "b" * 64,
        "alfa_textura": 128,
    }
    camera = {"fov": 90, "radius": 12, "centro": [0, 0, 0], "projecao": 0}
    gl = {
        "estado": "CAPTURADO", "backend": "OpenGL",
        "dimensoes_imagem": [1024, 768],
        "textura_controle": textura, "camera": camera,
        "suporte_msaa": {"testavel": True},
        "resultado_a2c": "EXECUTADO_COM_MSAA_4X",
        "controles": {}, "comparacao": {
            "a2c_4x_off_vs_on": {"pixels_divergentes": 77}
        },
    }
    vk = {
        "estado": "OBSERVADO", "backend": "Vulkan",
        "dimensoes_imagem": [1024, 768],
        "textura_controle": copy.deepcopy(textura),
        "camera": copy.deepcopy(camera),
        "suporte_msaa": {"disponivel": True},
        "resultado_a2c": "EXECUTADO_DIFERENCA_RGB",
        "controles": {}, "comparacao": {
            "a2c_4x_off_vs_on": {"pixels_divergentes": 88}
        },
    }
    for nome in ("1x_sem_a2c", "4x_sem_a2c", "4x_com_a2c", "4x_inelegivel"):
        amostras = 1 if nome == "1x_sem_a2c" else 4
        enabled = nome == "4x_com_a2c"
        faces = 0 if nome == "4x_inelegivel" else 18486
        gl["controles"][nome] = {
            "a2c_elegivel": enabled, "pipeline_a2c_observado": enabled,
            "amostras": amostras, "amostras_fbo_observadas": 0 if amostras == 1 else 4,
            "captura_rgb": True, "sha256_rgb": "c" * 64,
            "nTransparentPrimitives": faces,
            "rastros_gl": {"ativacoes_a2c": 1 if enabled else 0},
        }
        vk["controles"][nome] = {
            "a2c_elegivel": enabled, "pipeline_a2c_observado": enabled,
            "amostras": amostras, "captura_rgb": True,
            "sha256_rgb": "d" * 64, "nTransparentPrimitives": faces,
        }
    # Controles ON/OFF originais e variantes intermediárias com estados
    # comprovados, reproduzidos só como fixtures (sem GPU).
    est = {
        "4x_sem_a2c": (True, False, False),
        "4x_sem_a2c_sem_blend_sem_z": (False, False, False),
        "4x_sem_a2c_sem_blend_com_z": (False, True, False),
        "4x_com_a2c": (False, True, True),
    }
    for nome, (blend, z, enabled) in est.items():
        for m in (gl, vk):
            reg = m["controles"].setdefault(nome, {
                "a2c_elegivel": enabled, "pipeline_a2c_observado": enabled,
                "amostras": 4, "captura_rgb": True,
                "sha256_rgb": "c" * 64, "nTransparentPrimitives": 18486,
            })
            reg["blend_habilitado_observado"] = blend
            reg["escrita_z_observada"] = z
            if m is gl:
                reg["amostras_fbo_observadas"] = 4
                reg["rastros_gl"] = {
                    "ativacoes_a2c": int(enabled),
                    "draw_states": [{
                        "blend": blend, "escrita_z": z, "a2c": enabled,
                    }],
                }
            else:
                reg["pipeline_chave_cache_confirmada"] = True
                reg["rastros_pipeline_corpo"] = [{
                    "blend_habilitado_previsto": blend,
                    "escrita_z_prevista": z, "a2c_calculado": enabled,
                }]
    for m in (gl, vk):
        for chave in ("somente_blend_4x", "somente_depth_write_4x",
                      "somente_a2c_4x"):
            m["comparacao"][chave] = {"pixels_divergentes": 4}
    return gl, vk


class TesteContratoA2C(unittest.TestCase):
    def test_prova_dos_dois_backends_sem_homologar(self):
        gl, vk = modelos()
        doc = comparar_manifestos(gl, vk)
        self.assertEqual(doc["estado"], "CONTROLES_RGB_4X_EM_AMBOS_BACKENDS")
        self.assertTrue(doc["nao_homologado"])
        self.assertEqual(doc["mudanca_4x_off_on_rgb"]["opengl"]["pixels_divergentes"], 77)
        self.assertEqual(doc["isolamento_estados"]["estado"],
                         "CONTROLES_INTERMEDIARIOS_VALIDOS")
        self.assertIn("somente_a2c_4x", doc["isolamento_estados"]["fatores"])

    def test_rejeita_blend_incorreto_no_controle_intermediario(self):
        gl, vk = modelos()
        gl["controles"]["4x_sem_a2c_sem_blend_sem_z"]["blend_habilitado_observado"] = True
        with self.assertRaisesRegex(ValueError, "Blending"):
            comparar_manifestos(gl, vk)

    def test_rejeita_z_incorreto_no_vulkan(self):
        gl, vk = modelos()
        vk["controles"]["4x_sem_a2c_sem_blend_com_z"]["escrita_z_observada"] = False
        with self.assertRaisesRegex(ValueError, "Escrita Z"):
            comparar_manifestos(gl, vk)

    def test_rejeita_trace_draw_gl_ausente(self):
        gl, vk = modelos()
        gl["controles"]["4x_sem_a2c_sem_blend_com_z"]["rastros_gl"]["draw_states"] = []
        with self.assertRaisesRegex(ValueError, "FBO/draw GL"):
            comparar_manifestos(gl, vk)

    def test_rejeita_pipeline_vk_inconsistente(self):
        gl, vk = modelos()
        vk["controles"]["4x_sem_a2c_sem_blend_sem_z"]["rastros_pipeline_corpo"][0]["a2c_calculado"] = True
        with self.assertRaisesRegex(ValueError, "Vulkan previsto"):
            comparar_manifestos(gl, vk)

    def test_nao_testavel_sem_driver_gl_4x(self):
        gl, vk = modelos()
        gl["suporte_msaa"]["testavel"] = False
        gl["resultado_a2c"] = "NAO_TESTAVEL_MSAA_4X"
        self.assertEqual(comparar_manifestos(gl, vk)["estado"], "NAO_TESTAVEL_OPENGL_4X")

    def test_rejeita_amostra_gl_nao_observada(self):
        gl, vk = modelos()
        gl["controles"]["4x_com_a2c"]["amostras_fbo_observadas"] = 0
        with self.assertRaisesRegex(ValueError, "GL_SAMPLES"):
            comparar_manifestos(gl, vk)

    def test_rejeita_cobertura_gl_sem_ativacao(self):
        gl, vk = modelos()
        gl["controles"]["4x_com_a2c"]["rastros_gl"]["ativacoes_a2c"] = 0
        with self.assertRaisesRegex(ValueError, "GL_SAMPLE_ALPHA_TO_COVERAGE"):
            comparar_manifestos(gl, vk)

    def test_rejeita_textura_diferente(self):
        gl, vk = modelos()
        vk["textura_controle"]["sha256_png"] = "x" * 64
        with self.assertRaisesRegex(ValueError, "Textura"):
            comparar_manifestos(gl, vk)

    def test_rejeita_camera_diferente(self):
        gl, vk = modelos()
        vk["camera"]["fov"] = 60
        with self.assertRaisesRegex(ValueError, "Câmera"):
            comparar_manifestos(gl, vk)


if __name__ == "__main__":
    unittest.main()
