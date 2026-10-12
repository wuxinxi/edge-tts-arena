import io
import subprocess
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from scripts import setup_models
from backend.app.adapters.factory import AdapterFactory
from backend.app.core.config import MODELS_CATALOG


class SetupModelsTests(unittest.TestCase):
    def invoke(self, arguments):
        with patch('sys.argv', ['setup_models.py', *arguments]), \
                patch.object(setup_models, 'prepare_source') as source, \
                patch.object(setup_models, 'prepare_assets') as assets, \
                patch.object(setup_models, 'command') as command, \
                patch.object(Path, 'is_file', return_value=True), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            setup_models.main()
        return source, assets, command

    def test_all_prepares_every_catalog_environment_without_main_weights(self):
        source, assets, command = self.invoke(['--all'])
        expected = set(setup_models.ENVIRONMENTS)
        self.assertEqual(expected, {AdapterFactory.get_adapter(key).environment_name for key in MODELS_CATALOG})
        self.assertEqual({call.args[0] for call in source.call_args_list}, expected)
        self.assertEqual({call.args[0] for call in assets.call_args_list}, expected)
        self.assertEqual(command.call_count, 9)
        for call in command.call_args_list:
            arguments = call.args[0]
            self.assertEqual(arguments[:3], ['uv', 'pip', 'install'])
            requirement = arguments[arguments.index('-r') + 1]
            self.assertTrue(requirement.exists())
            self.assertNotIn('download_models.py', str(arguments))

    def test_no_selection_preserves_all_environments_behavior(self):
        source, _, _ = self.invoke([])
        self.assertEqual(source.call_count, len(setup_models.ENVIRONMENTS))

    def test_selected_environments_trim_deduplicate_and_forward_index(self):
        source, _, command = self.invoke(['--models', ' chattts, f5tts,chattts ', '--index-url', 'https://example.test/simple'])
        self.assertEqual([call.args[0] for call in source.call_args_list], ['chattts', 'f5tts'])
        for call in command.call_args_list:
            self.assertEqual(call.args[0][-2:], ['--index-url', 'https://example.test/simple'])

    def test_all_assets_does_not_install_or_prepare_source(self):
        source, assets, command = self.invoke(['--all', '--assets'])
        source.assert_not_called()
        command.assert_not_called()
        self.assertEqual(assets.call_count, len(setup_models.ENVIRONMENTS))

    def test_invalid_selection_has_no_installation_side_effects(self):
        for arguments in (['--all', '--models', 'kokoro'], ['--models', 'kokoro,missing'], ['--models', '']):
            with self.subTest(arguments=arguments), patch('sys.argv', ['setup_models.py', *arguments]), \
                    patch.object(setup_models, 'prepare_source') as source, \
                    patch.object(setup_models, 'prepare_assets') as assets, \
                    patch.object(setup_models, 'command') as command, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    setup_models.main()
                self.assertEqual(error.exception.code, 2)
                source.assert_not_called()
                assets.assert_not_called()
                command.assert_not_called()

    def test_failed_assets_do_not_prevent_remaining_environments_and_exit_nonzero(self):
        output = io.StringIO()
        def assets(name):
            if name == 'melotts':
                raise subprocess.CalledProcessError(1, ['python', 'setup_nltk.py'])
        with patch('sys.argv', ['setup_models.py', '--all']), \
                patch.object(setup_models, 'prepare_source') as source, \
                patch.object(setup_models, 'prepare_assets', side_effect=assets), \
                patch.object(setup_models, 'command'), \
                patch.object(Path, 'is_file', return_value=True), \
                redirect_stdout(output), redirect_stderr(output):
            with self.assertRaises(SystemExit) as error:
                setup_models.main()
        self.assertEqual(error.exception.code, 1)
        self.assertEqual([call.args[0] for call in source.call_args_list], list(setup_models.ENVIRONMENTS))
        self.assertIn('失败 1', output.getvalue())
        self.assertIn('--models melotts', output.getvalue())
        self.assertIn('maskgct: 准备完成', output.getvalue())


if __name__ == '__main__':
    unittest.main()
