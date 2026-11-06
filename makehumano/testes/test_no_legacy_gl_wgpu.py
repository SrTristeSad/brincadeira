"""Regressões: aplicação original sem importação do antigo motor OpenGL.

Não confundir nomes históricos de plugins/formatos com uso ativo de OpenGL.
"""
import ast
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1] / "codigo" / "makehuman"
sys.path.insert(0, str(RAIZ / "lib"))
sys.path.insert(0, str(RAIZ / "core"))

from object3d import Object3D
from debugdump import DebugDump


class SemMotorOpenGLLegado(unittest.TestCase):
    def test_glmodule_original_removido(self):
        self.assertFalse((RAIZ / "lib" / "glmodule.py").exists())

    def test_nenhum_modulo_original_importa_pyopengl_ou_glmodule(self):
        for path in sorted(RAIZ.rglob("*.py")):
            with self.subTest(path=path.relative_to(RAIZ)):
                codigo = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(codigo):
                    if isinstance(node, ast.Import):
                        modulos = [item.name for item in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        modulos = [node.module]
                    else:
                        continue
                    for modulo in modulos:
                        self.assertNotIn(
                            modulo.split(".")[0], ("OpenGL", "glmodule"),
                            f"Importação GL obsoleta em {path}: {modulo}",
                        )

    def test_apis_imediatas_obsoletas_falham_sem_puxar_opengl(self):
        obj = Object3D.__new__(Object3D)
        with self.assertRaisesRegex(NotImplementedError, "mh.redraw"):
            obj.draw()
        with self.assertRaisesRegex(NotImplementedError, "mh.getPickedColor"):
            obj.pick()

    def test_diagnostico_historico_registra_backend_vulkan(self):
        dump = DebugDump()
        mensagens = []
        dump.open = lambda: None
        dump.write = lambda texto, *args: mensagens.append(texto % args)
        dump.close = lambda: None
        dump.appendGL()
        self.assertIn("RENDERER.BACKEND: Vulkan", mensagens)
        self.assertTrue(any(
            valor.startswith("VULKAN.ADAPTER: ") for valor in mensagens
        ))
        self.assertFalse(any("PYOPENGL" in valor for valor in mensagens))


if __name__ == "__main__":
    unittest.main()
