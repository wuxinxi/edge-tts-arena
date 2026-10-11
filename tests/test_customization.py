import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

import numpy as np
from pydantic import ValidationError

from backend.app.adapters.factory import AdapterFactory
from backend.app.api.routes import TTSCompareRequest, TTSGenerateRequest, compare_models, generate_audio
from backend.app.core.config import MODELS_CATALOG
from backend.app.core.model_profiles import profile_for, resolve_options
from backend.app.core.run_records import recent_runs
from backend.app.workers.worker_settings import chat_refine_prompt
from backend.app.core.audio_effects import stretch_audio


class CustomizationTests(unittest.TestCase):
    def setUp(self):
        AdapterFactory._instances.clear()

    def test_bad_controls_are_rejected_before_inference(self):
        model = MODELS_CATALOG['f5-tts']
        for options in ({'nfe_step': 999}, {'seed': True}, {'seed': 1.5}, {'seed': float('nan')},
                        {'cfg_strength': 100}, {'unsupported': 'value'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                resolve_options(model, options)
        adapter = AdapterFactory.get_adapter('f5-tts')
        with patch.object(adapter, 'is_available', return_value=True), patch.object(adapter, 'load') as load:
            with self.assertRaises(ValueError):
                adapter.generate('测试', options={'nfe_step': 999})
            load.assert_not_called()

    def test_variants_do_not_offer_wrong_features(self):
        base = profile_for(MODELS_CATALOG['qwen3-tts-0.6b'])
        custom = profile_for(MODELS_CATALOG['qwen3-tts-1.7b'])
        self.assertEqual(base['prompt_kind'], 'none')
        self.assertEqual(custom['prompt_kind'], 'instruction')
        with self.assertRaises(ValueError):
            resolve_options(MODELS_CATALOG['qwen3-tts-1.7b'], {'x_vector_only': True})

    def test_audio_and_export_keep_actual_parameters_and_reference(self):
        adapter = AdapterFactory.get_adapter('f5-tts')
        captured = []
        def worker(arguments):
            captured.append(arguments)
            return np.ones(24000, dtype=np.float32) * 0.1, 24000
        with tempfile.TemporaryDirectory() as directory, patch('backend.app.adapters.base.OUTPUTS_DIR', Path(directory)), \
                patch.object(adapter, 'is_available', return_value=True), \
                patch.object(adapter, 'runtime_python', return_value=Path(__file__)), \
                patch.object(adapter, 'run_worker', side_effect=worker):
            result = generate_audio(TTSGenerateRequest(model_key='f5-tts', text='测试', preset='fast', options={'seed': 123}))['data']
            forwarded = json.loads(captured[0][captured[0].index('--options') + 1])
            self.assertEqual(forwarded['nfe_step'], 16)
            self.assertEqual(forwarded['seed'], 123)
            self.assertEqual(result['settings']['options'], forwarded)
            reference = result['settings']['reference']
            self.assertEqual(reference['source'], 'default')
            self.assertEqual(len(reference['sha256']), 64)
            persisted = recent_runs(Path(directory))
            self.assertEqual(persisted, [result])
            self.assertNotIn('ref_audio_path', json.dumps(persisted))

    def test_timbre_and_cross_lingual_allow_upload_without_transcript(self):
        for key, options in [('qwen3-tts-0.6b', {'x_vector_only': True}), ('cosyvoice3', {'mode': 'cross_lingual'})]:
            adapter = AdapterFactory.get_adapter(key)
            args = adapter.synthesis_arguments('测试', ref_audio_path='/tmp/voice.wav', options=options)
            self.assertIn('--ref_audio', args)
            self.assertNotIn('--ref_text', args)
            with self.assertRaises(ValueError):
                adapter.synthesis_arguments('测试', ref_audio_path='/tmp/voice.wav')

    def test_output_speed_keeps_model_speed_at_one_and_stretches_once(self):
        adapter = AdapterFactory.get_adapter('f5-tts')
        adapter.is_loaded = True
        audio = np.sin(np.arange(24000, dtype=np.float32) * 0.1)
        with tempfile.TemporaryDirectory() as directory, patch('backend.app.adapters.base.OUTPUTS_DIR', Path(directory)), \
                patch.object(adapter, 'is_available', return_value=True), \
                patch.object(adapter, 'synthesize', return_value=(audio, 24000)) as synthesize:
            result = adapter.generate('测试', speed=2, speed_mode='output')
        self.assertEqual(synthesize.call_args.kwargs['speed'], 1)
        self.assertEqual(result['metrics']['audio_duration_sec'], 0.5)
        self.assertEqual(result['settings']['speed_kind'], 'postprocess')

    def test_benchmark_is_independent_of_workstation_controls(self):
        captured = []
        adapter = SimpleNamespace(metadata=MODELS_CATALOG['chattts'])
        adapter.generate = lambda **kwargs: captured.append(kwargs) or {'success': True}
        with patch.object(AdapterFactory, 'get_adapter', return_value=adapter):
            compare_models(TTSCompareRequest(model_keys=['chattts', 'chattts'], text='测试', speed=1.2))
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]['speed_mode'], 'output')
        self.assertEqual(captured[0]['options'], {'refine_text': False})
        self.assertEqual(captured[0]['evaluation']['model_speed'], 1)
        with self.assertRaises(ValidationError):
            TTSCompareRequest(model_keys=['chattts'], text='测试', speed_mode='model')

    def test_recommended_comparison_records_its_specific_preset(self):
        captured = []
        adapter = SimpleNamespace(metadata=MODELS_CATALOG['qwen3-tts-1.7b'])
        adapter.generate = lambda **kwargs: captured.append(kwargs) or {'success': True}
        with patch.object(AdapterFactory, 'get_adapter', return_value=adapter):
            compare_models(TTSCompareRequest(model_keys=['qwen3-tts-1.7b'], text='测试', benchmark_mode='recommended'))
        self.assertEqual(captured[0]['preset'], 'news')
        self.assertEqual(captured[0]['evaluation']['mode'], 'recommended')

    def test_qwen_exploration_recommends_tested_instruction_but_uniform_keeps_raw_output(self):
        metadata = MODELS_CATALOG['qwen3-tts-1.7b']
        profile = profile_for(metadata)
        self.assertEqual(profile['exploration_preset'], 'news')
        _, recommended = resolve_options(metadata, preset_key=profile['exploration_preset'])
        self.assertEqual(recommended['prompt'], '用清晰、沉稳、专业的新闻播报语气说。')
        _, original = resolve_options(metadata, preset_key='default')
        self.assertEqual(original['prompt'], '')
        captured = []
        adapter = SimpleNamespace(metadata=metadata)
        adapter.generate = lambda **kwargs: captured.append(kwargs) or {'success': True}
        with patch.object(AdapterFactory, 'get_adapter', return_value=adapter):
            compare_models(TTSCompareRequest(model_keys=[metadata.key], text='测试', benchmark_mode='uniform'))
        self.assertEqual(captured[0]['preset'], 'default')
        self.assertEqual(captured[0]['options'], {})

    def test_cosy_modes_do_not_silently_ignore_instruction(self):
        adapter = AdapterFactory.get_adapter('cosyvoice3')
        with patch.object(adapter, 'is_available', return_value=True), self.assertRaisesRegex(ValueError, '自动模式'):
            adapter.generate('测试', prompt='温暖', options={'mode': 'cross_lingual'})

    def test_cosy3_cross_lingual_supplies_required_prompt_boundary(self):
        from backend.app.workers.cosyvoice3_worker import inference_output
        args = SimpleNamespace(text='今天阳光很好。', options={'mode': 'cross_lingual'},
                               ref_audio='/reference.wav', ref_text='', prompt='', speed=1)
        model = Mock()
        inference_output(model, args)
        text = model.inference_cross_lingual.call_args.args[0]
        self.assertEqual(text, 'You are a helpful assistant.<|endofprompt|>今天阳光很好。')
        self.assertEqual(model.inference_cross_lingual.call_args.args[1], args.ref_audio)

    def test_chat_control_tokens_are_bounded_and_not_natural_language(self):
        self.assertEqual(chat_refine_prompt({'oral': 2, 'laugh': 1, 'break': 6}), '[oral_2][laugh_1][break_6]')
        with self.assertRaises(ValueError):
            chat_refine_prompt({}, '温暖亲切')

    def test_corrupt_or_missing_audio_history_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bad.run.json').write_text('{invalid')
            (root / 'missing.run.json').write_text(json.dumps({'audio_file': 'missing.wav'}))
            self.assertEqual(recent_runs(root), [])

    def test_output_stretch_preserves_pitch_and_short_audio_is_finite(self):
        sample_rate = 24000
        source = np.sin(2 * np.pi * 440 * np.arange(sample_rate * 2) / sample_rate).astype(np.float32)
        for rate in (0.5, 0.8, 1.5, 2):
            audio = stretch_audio(source, rate)
            self.assertEqual(len(audio), round(len(source) / rate))
            peak = np.argmax(abs(np.fft.rfft(audio[2048:-2048])))
            frequency = peak * sample_rate / len(audio[2048:-2048])
            self.assertLess(abs(frequency - 440), 3)
            self.assertTrue(np.isfinite(audio).all())
        for length in (1, 10, 240):
            self.assertTrue(np.isfinite(stretch_audio(np.ones(length), 1.5)).all())


if __name__ == '__main__':
    unittest.main()
