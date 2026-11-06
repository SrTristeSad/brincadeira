"""Regressões da migração: Vulkan deve iniciar sem a pilha OpenGL.

Testes estáticos, independentes de Qt e de uma GPU física.
O smoke_gui.py verifica a execução real com o Qt e Lavapipe.
"""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "codigo" / "makehuman"

ARQUIVOS_RUNTIME = (
    "lib/mh.py",
    "lib/qtui.py",
    "lib/camera.py",
    "core/mhmain.py",
    "plugins/0_modeling_background.py",
    "plugins/7_material_editor.py",
)


class TestarBackendVulkanPadrao(unittest.TestCase):
    def test_runtime_principal_nao_importa_open_gl(self):
        for relativo in ARQUIVOS_RUNTIME:
            with self.subTest(arquivo=relativo):
                arvore = ast.parse((APP / relativo).read_text(encoding="utf-8"))
                for node in ast.walk(arvore):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertNotIn(
                                alias.name.split(".")[0], ("OpenGL", "glmodule",
                                                             "texture", "shader"),
                            )
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        self.assertNotIn(
                            node.module.split(".")[0], ("OpenGL", "glmodule",
                                                         "texture", "shader"),
                        )

    def test_canvas_qt_nao_requer_qopenglwidget(self):
        source = (APP / "lib" / "qtui.py").read_text(encoding="utf-8")
        arvore = ast.parse(source)
        self.assertFalse(any(
            isinstance(node, ast.Attribute) and node.attr == "QOpenGLWidget"
            for node in ast.walk(arvore)
        ))
        self.assertIn("Canvas = criar_canvas_vulkan(CanvasEvents)", source)

    def test_variavel_de_piloto_nao_controla_inicializacao(self):
        for relativo in ARQUIVOS_RUNTIME:
            with self.subTest(arquivo=relativo):
                source = (APP / relativo).read_text(encoding="utf-8")
                self.assertNotIn("MAKEHUMANO_VULKAN_PILOT", source)

    def test_smoke_inicia_gui_com_shaders_sem_aviso_glsl_bloqueante(self):
        smoke = (ROOT / "testes" / "smoke_gui.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('"--noshaders"', smoke)
        self.assertNotIn("'--noshaders'", smoke)
        app = (APP / "core" / "mhmain.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "Only simple shading will be available.", app,
        )
        self.assertIn(
            "presets WGSL nativos disponíveis", app,
        )

    def test_dependencias_padrao_nao_instalam_pyopengl(self):
        for path in (ROOT / "codigo" / "requirements.txt",):
            with self.subTest(arquivo=path.name):
                linhas = path.read_text(encoding="utf-8").splitlines()
                reqs = [
                    linha.strip() for linha in linhas
                    if linha.strip() and not linha.lstrip().startswith("#")
                ]
                self.assertFalse(any(
                    "PyOpenGL" in linha or "OpenGL" in linha for linha in reqs
                ))


if __name__ == "__main__":
    unittest.main()
