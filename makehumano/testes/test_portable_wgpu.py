"""Regressões de erros que o teste --license do portátil não detectava."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def entrypoint():
    spec = importlib.util.spec_from_file_location(
        "portable_entrypoint_test", ROOT / "codigo/makehuman/makehuman.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PortableStartupErrors(unittest.TestCase):
    def test_initialization_failure_is_not_reported_as_success(self):
        app = entrypoint()
        with patch.object(app, "install_portable_error_handler"), patch.object(
                app, "set_sys_path", side_effect=OSError("perfil indisponível")):
            with self.assertRaisesRegex(OSError, "perfil indisponível"):
                app.main()

    def test_error_report_includes_failure_after_gui_import(self):
        app = entrypoint()
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "erro.txt"
            with patch.dict("os.environ", {"MAKEHUMANO_PORTABLE_ERROR_LOG": str(logfile)}):
                with patch.object(sys, "excepthook") as previous:
                    app.install_portable_error_handler()
                    try:
                        raise RuntimeError("falha ao criar janela Vulkan")
                    except RuntimeError:
                        sys.excepthook(*sys.exc_info())
                    previous.assert_called_once()
            self.assertIn("falha ao criar janela Vulkan", logfile.read_text(encoding="utf-8"))

    def test_unwritable_error_log_preserves_original_exception(self):
        app = entrypoint()
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"MAKEHUMANO_PORTABLE_ERROR_LOG": directory}):
                with patch.object(sys, "excepthook") as previous:
                    app.install_portable_error_handler()
                    try:
                        raise RuntimeError("erro original")
                    except RuntimeError:
                        sys.excepthook(*sys.exc_info())
                    self.assertIs(previous.call_args.args[0], RuntimeError)


class OriginalModuleCompatibility(unittest.TestCase):
    def test_original_texture_import_uses_vulkan_implementation(self):
        sys.path.insert(0, str(ROOT / "codigo/makehuman/lib"))
        import texture
        import vulkan_texture
        self.assertIs(texture.Texture, vulkan_texture.Texture)
        self.assertIs(texture.getTexture, vulkan_texture.getTexture)
        image = texture.Texture(size=(3, 2), components=4)
        self.assertEqual(image.data.shape, (2, 3, 4))
        self.assertIsNone(image.textureId)
        self.assertFalse(any(name == "OpenGL" or name.startswith("OpenGL.") for name in sys.modules))

    def test_original_shader_import_does_not_attempt_opengl(self):
        sys.path.insert(0, str(ROOT / "codigo/makehuman/lib"))
        import shader
        import vulkan_shader
        self.assertIs(shader.Shader, vulkan_shader.Shader)
        self.assertFalse(shader.Shader.supported())
        with self.assertRaisesRegex(NotImplementedError, "GLSL"):
            shader.getShader("/custom/shader")
