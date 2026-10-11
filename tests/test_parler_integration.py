import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException

from backend.app.adapters.factory import AdapterFactory
from backend.app.api.routes import TTSGenerateRequest, generate_audio
from backend.app.core.run_records import recent_runs
from backend.app.workers.worker_settings import parler_description, validate_parler_text


class ParlerIntegrationTests(unittest.TestCase):
    def setUp(self):
        AdapterFactory._instances.clear()

    def test_unsupported_scripts_fail_before_loading_or_invoking_worker(self):
        adapter = AdapterFactory.get_adapter('parler-tts-mini')
        with patch.object(adapter, 'load') as load, patch.object(adapter, 'run_worker') as worker:
            for text in ('你好。', 'Hello, 世界', 'こんにちは', '안녕하세요', 'Привет'):
                with self.subTest(text=text), self.assertRaises(HTTPException) as error:
                    generate_audio(TTSGenerateRequest(model_key='parler-tts-mini', text=text))
                self.assertEqual(error.exception.status_code, 400)
            load.assert_not_called()
            worker.assert_not_called()

    def test_english_punctuation_and_accents_are_not_rejected(self):
        validate_parler_text('“Hello!” she said. Café at 9:30 costs $12.50.')

    def test_named_speaker_preserves_custom_description(self):
        description = 'Very clear audio, a low pitch and slow delivery.'
        self.assertEqual(parler_description(description, 'Jon'), "Jon's voice. " + description)
        self.assertEqual(parler_description(description), description)

    def test_named_preset_and_seed_are_forwarded_and_saved_without_reference(self):
        adapter = AdapterFactory.get_adapter('parler-tts-mini')
        commands = []
        def worker(arguments):
            commands.append(arguments)
            return np.ones(24000, dtype=np.float32) * 0.1, 24000
        with tempfile.TemporaryDirectory() as directory, patch('backend.app.adapters.base.OUTPUTS_DIR', Path(directory)), \
                patch.object(adapter, 'is_available', return_value=True), \
                patch.object(adapter, 'runtime_python', return_value=Path(__file__)), \
                patch.object(adapter, 'run_worker', side_effect=worker):
            result = generate_audio(TTSGenerateRequest(model_key='parler-tts-mini', text='Hello.',
                voice='Jon', preset='warm', options={'seed': 123}))['data']
            command = commands[0]
            self.assertEqual(command[command.index('--voice') + 1], 'Jon')
            self.assertIn('warm', command[command.index('--prompt') + 1])
            self.assertEqual(json.loads(command[command.index('--options') + 1]), {'seed': 123})
            self.assertNotIn('--ref_audio', command)
            self.assertEqual(result['settings']['reference']['source'], 'none')
            self.assertEqual(result['settings']['preset'], 'warm')
            self.assertEqual(recent_runs(Path(directory)), [result])


if __name__ == '__main__':
    unittest.main()
