import json
import base64
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stdout
from fastapi import HTTPException
from pydantic import ValidationError

import numpy as np
import soundfile as sf

from backend.app.adapters.factory import AdapterFactory
from backend.app.api.routes import TTSCompareRequest, TTSGenerateRequest, compare_models, generate_audio
from backend.app.core.metrics import GenerationTracker
from backend.app.core.config import MODELS_CATALOG, PROJECT_ROOT
from backend.app.core.reference import DEFAULT_REFERENCE_AUDIO, default_reference, resolve_reference


class GenerationRegressionTests(unittest.TestCase):
    def setUp(self):
        AdapterFactory._instances.clear()

    def test_real_adapters_initialize_before_worker_and_use_absolute_paths(self):
        def worker(cmd, **kwargs):
            self.assertTrue(Path(cmd[0]).is_absolute())
            self.assertTrue(Path(cmd[1]).is_absolute())
            if 'f5tts_worker.py' in cmd[1]:
                self.assertEqual(cmd[cmd.index('--speed') + 1], '1.3')
            else:
                self.assertEqual(cmd[cmd.index('--voice_seed') + 1], '2222')
            output = cmd[cmd.index('--output') + 1]
            sf.write(output, np.ones(240, dtype=np.float32) * 0.1, 24000)
            return SimpleNamespace(returncode=0, stdout=json.dumps({'status': 'success'}), stderr='')

        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            sf.write(reference, np.ones(240, dtype=np.float32), 24000)
            for key in ['f5-tts', 'chattts']:
                adapter = AdapterFactory.get_adapter(key)
                python = Path(directory) / 'python'
                python.touch()
                with self.subTest(model=key), patch('backend.app.adapters.base.OUTPUTS_DIR', Path(directory)), patch(
                    'backend.app.adapters.worker.subprocess.run', side_effect=worker
                ), patch.object(adapter, 'is_available', return_value=True), patch.object(adapter, 'runtime_python', return_value=python):
                    result = adapter.generate(text='测试', ref_audio_path=str(reference), ref_text='参考', speed=1.3)
                    self.assertTrue(result['success'])
                    self.assertTrue(adapter.is_loaded)
                    self.assertEqual(Path(adapter.checkpoint_dir), PROJECT_ROOT / 'checkpoints' / key)
                    self.assertIsNone(result['metrics']['ttfb_ms'])

    def test_documentation_alone_is_not_downloaded_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = AdapterFactory.get_adapter('chattts')
            adapter.model_dir = Path(directory)
            (adapter.model_dir / 'README.md').write_text('model documentation')
            self.assertFalse(adapter.is_available())

    def test_download_marker_and_incomplete_weights_do_not_skip_download(self):
        from scripts.download_models import is_model_already_downloaded
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / 'qwen3-tokenizer'
            model.mkdir()
            (model / '.download_complete').write_text('old marker')
            (model / 'config.json').write_text('{}')
            (model / 'model.safetensors.incomplete').write_bytes(b'partial')
            self.assertFalse(is_model_already_downloaded(model, ['*.json', '*.safetensors']))

    def test_f5_download_completes_vocoder_before_writing_marker(self):
        from scripts.download_models import download_single_model, MODELS_REGISTRY

        def main_model(key, info, directory):
            model = directory / 'F5TTS_Base'
            model.mkdir(parents=True)
            (model / 'model_1200000.safetensors').write_bytes(b'weights')
            (model / 'vocab.txt').write_text('vocabulary')
            return True

        def vocoder(key, info, directory, token=None):
            self.assertEqual(info['repo_id'], 'charactr/vocos-mel-24khz')
            self.assertFalse((directory.parent / '.download_complete').exists())
            directory.mkdir()
            (directory / 'config.yaml').write_text('config')
            (directory / 'pytorch_model.bin').write_bytes(b'weights')
            return True

        with tempfile.TemporaryDirectory() as directory, patch('scripts.download_models.download_from_modelscope',
                side_effect=main_model), patch('scripts.download_models.download_from_huggingface',
                side_effect=vocoder), redirect_stdout(io.StringIO()):
            self.assertTrue(download_single_model('f5-tts', MODELS_REGISTRY['f5-tts'], Path(directory)))
            self.assertTrue((Path(directory) / 'f5-tts' / '.download_complete').is_file())

    def test_incomplete_snapshot_cannot_be_marked_complete(self):
        from scripts.download_models import download_single_model, MODELS_REGISTRY
        with tempfile.TemporaryDirectory() as directory, patch('scripts.download_models.download_from_modelscope',
                return_value=True), redirect_stdout(io.StringIO()):
            self.assertFalse(download_single_model('chattts', MODELS_REGISTRY['chattts'], Path(directory)))
            self.assertFalse((Path(directory) / 'chattts' / '.download_complete').exists())

    def test_comparison_forwards_reference_to_clone_models(self):
        captured = {}
        adapter = SimpleNamespace(metadata=MODELS_CATALOG['f5-tts'])

        def generate(**kwargs):
            captured.update(kwargs)
            self.assertTrue(Path(kwargs['ref_audio_path']).is_file())
            return {'success': True, 'model_key': 'f5-tts'}

        adapter.generate = generate
        audio = io.BytesIO()
        sf.write(audio, np.ones(240), 24000, format='WAV')
        with patch.object(AdapterFactory, 'get_adapter', return_value=adapter):
            request = TTSCompareRequest(model_keys=['f5-tts'], text='测试', ref_audio=base64.b64encode(audio.getvalue()).decode(), ref_text='参考')
            result = compare_models(request)
        self.assertTrue(result['results'][0]['success'])
        self.assertEqual(captured['ref_text'], '参考')
        self.assertFalse(Path(captured['ref_audio_path']).exists())

    def test_new_adapters_call_real_workers_and_forward_shared_arguments(self):
        calls = []
        def worker(command, **kwargs):
            calls.append(command)
            output = command[command.index('--output') + 1]
            sf.write(output, np.ones(240, dtype=np.float32) * 0.1, 24000)
            return SimpleNamespace(returncode=0, stdout=json.dumps({'status': 'success', 'device': 'cpu'}), stderr='')
        with tempfile.TemporaryDirectory() as directory, patch('backend.app.adapters.base.OUTPUTS_DIR', Path(directory)), \
                patch('backend.app.adapters.worker.subprocess.run', side_effect=worker):
            python = Path(directory) / 'python'
            python.touch()
            for key in ['kokoro-82m', 'melotts-zh', 'cosyvoice3', 'qwen3-tts-0.6b',
                        'qwen3-tts-1.7b', 'fish-speech-1.5', 'maskgct', 'parler-tts-mini']:
                adapter = AdapterFactory.get_adapter(key)
                with self.subTest(model=key), patch.object(adapter, 'is_available', return_value=True), \
                        patch.object(adapter, 'runtime_python', return_value=python):
                    result = adapter.generate(text='测试', speed=1.2, ref_audio_path='/tmp/reference.wav', ref_text='参考')
                    self.assertTrue(result['success'])
                    self.assertEqual(result['device'], 'cpu')
                    command = calls[-1]
                    self.assertTrue(Path(command[1]).is_file())
                    self.assertEqual(command[command.index('--speed') + 1], '1.2')
                    self.assertEqual(command[command.index('--ref_text') + 1], '参考')
                    if key.startswith('qwen3-tts'):
                        self.assertEqual(command[command.index('--model_key') + 1], key)

    def test_reference_requirements_match_model_variants(self):
        for key in ['f5-tts', 'cosyvoice3', 'qwen3-tts-0.6b', 'maskgct', 'fish-speech-1.5']:
            adapter = AdapterFactory.get_adapter(key)
            with self.subTest(model=key):
                arguments = adapter.synthesis_arguments('测试')
                self.assertEqual(arguments[arguments.index('--ref_audio') + 1], str(DEFAULT_REFERENCE_AUDIO))
                self.assertEqual(arguments[arguments.index('--ref_text') + 1], default_reference()[1])
                with self.assertRaises(ValueError):
                    adapter.synthesis_arguments('测试', ref_audio_path='/tmp/custom.wav', ref_text=' ')
        custom = AdapterFactory.get_adapter('qwen3-tts-1.7b')
        self.assertFalse(custom.metadata.supports_clone)
        self.assertNotIn('--ref_audio', custom.synthesis_arguments('测试'))

    def test_default_reference_pair_is_valid_and_ignores_orphan_text(self):
        audio, text = resolve_reference(None, '没有对应音频的文字', required=True)
        self.assertEqual((audio, text), default_reference())
        self.assertGreater(sf.info(audio).frames, 0)
        self.assertEqual(resolve_reference('/tmp/custom.wav', ' 自定义原文 ', required=True),
                         ('/tmp/custom.wav', '自定义原文'))
        self.assertEqual(resolve_reference(None, None, required=False), (None, None))

    def test_missing_default_reference_is_reported(self):
        with patch('backend.app.core.reference.DEFAULT_REFERENCE_AUDIO', Path('/missing/default.wav')):
            with self.assertRaises(FileNotFoundError):
                default_reference()

    def test_api_single_and_comparison_use_default_reference_without_upload(self):
        def worker(arguments):
            self.assertEqual(arguments[arguments.index('--ref_audio') + 1], str(DEFAULT_REFERENCE_AUDIO))
            self.assertEqual(arguments[arguments.index('--ref_text') + 1], default_reference()[1])
            return np.ones(240, dtype=np.float32) * 0.1, 24000

        with tempfile.TemporaryDirectory() as directory, patch('backend.app.adapters.base.OUTPUTS_DIR', Path(directory)):
            for key in ['f5-tts', 'cosyvoice3', 'qwen3-tts-0.6b', 'maskgct', 'fish-speech-1.5']:
                adapter = AdapterFactory.get_adapter(key)
                with self.subTest(model=key), patch.object(adapter, 'is_available', return_value=True), \
                        patch.object(adapter, 'runtime_python', return_value=Path(__file__)), \
                        patch.object(adapter, 'run_worker', side_effect=worker):
                    single = generate_audio(TTSGenerateRequest(model_key=key, text='测试'))
                    self.assertTrue(single['data']['success'])
                    comparison = compare_models(TTSCompareRequest(model_keys=[key], text='测试'))
                    self.assertTrue(comparison['results'][0]['success'])

    def test_worker_error_is_reported_without_substitute_audio(self):
        adapter = AdapterFactory.get_adapter('kokoro-82m')
        adapter.python_bin = '/python'
        adapter.worker_script = '/worker.py'
        adapter.checkpoint_dir = '/model'
        error = SimpleNamespace(returncode=1, stdout=json.dumps({'status': 'error', 'message': '真实推理失败'}), stderr='')
        with patch('backend.app.adapters.worker.subprocess.run', return_value=error), self.assertRaisesRegex(RuntimeError, '真实推理失败'):
            adapter.run_worker(['--text', '测试'])

    def test_worker_environment_forces_offline_mode(self):
        adapter = AdapterFactory.get_adapter('kokoro-82m')
        with patch.dict(os.environ, {'HF_HUB_OFFLINE': '0', 'TRANSFORMERS_OFFLINE': '0'}):
            environment = adapter.worker_environment()
        self.assertEqual(environment['HF_HUB_OFFLINE'], '1')
        self.assertEqual(environment['TRANSFORMERS_OFFLINE'], '1')

    @unittest.skipIf(os.name == 'nt', 'Unix 文件锁检查')
    def test_inference_lock_excludes_other_processes_and_releases_on_error(self):
        from backend.app.core.inference_lock import exclusive_inference
        probe = ('import fcntl,sys; f=open(sys.argv[1],"a+b"); '
                 'fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'inference.lock'
            with self.assertRaisesRegex(ValueError, '测试异常'):
                with exclusive_inference(path):
                    result = subprocess.run([sys.executable, '-c', probe, str(path)], capture_output=True)
                    self.assertNotEqual(result.returncode, 0)
                    raise ValueError('测试异常')
            result = subprocess.run([sys.executable, '-c', probe, str(path)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_unknown_comparison_model_is_reported(self):
        result = compare_models(TTSCompareRequest(model_keys=['unknown-model'], text='测试'))
        self.assertEqual(len(result['results']), 1)
        self.assertFalse(result['results'][0]['success'])

    def test_invalid_reference_audio_and_whitespace_text_are_rejected(self):
        for encoded in ['invalid-base64!', 'dGVzdA==']:
            with self.subTest(encoded=encoded), self.assertRaises(HTTPException) as error:
                generate_audio(TTSGenerateRequest(model_key='chattts', text='测试', ref_audio=encoded))
            self.assertEqual(error.exception.status_code, 400)
        with self.assertRaises(ValidationError):
            TTSGenerateRequest(model_key='chattts', text='  ')

    def test_memory_sampling_includes_worker_children_and_no_fake_ttfb(self):
        tracker = GenerationTracker('chattts')
        child = SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=20 * 1024 * 1024))
        tracker.process = SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=10 * 1024 * 1024),
                                          children=lambda recursive: [child])
        with tracker:
            pass
        result = tracker.compute_metrics(sample_rate=24000, audio_length_samples=24000)
        self.assertEqual(result['memory_peak_mb'], 30)
        self.assertIsNone(result['ttfb_ms'])

    def test_long_text_with_prematurely_ended_audio_is_not_successful(self):
        adapter = AdapterFactory.get_adapter('kokoro-82m')
        adapter.is_loaded = True
        text = '你好，这是端侧主流 TTS 语音合成评测。我们正在测试 Apple Silicon M 系列芯片上的运行性能！'
        with tempfile.TemporaryDirectory() as directory, patch('backend.app.adapters.base.OUTPUTS_DIR', Path(directory)), \
                patch.object(adapter, 'is_available', return_value=True), \
                patch.object(adapter, 'synthesize', return_value=(np.ones(int(44100 * 0.325), dtype=np.float32), 44100)):
            with self.assertRaisesRegex(RuntimeError, '明显过短'):
                adapter.generate(text=text)
            self.assertEqual(list(Path(directory).glob('*.wav')), [])

    def test_benchmark_failure_does_not_abort_remaining_models(self):
        from scripts.benchmark import run_benchmark
        good = SimpleNamespace(metadata=MODELS_CATALOG['chattts'], get_status=lambda: {'is_ready': True})
        good.generate = lambda **kwargs: {'metrics': {'elapsed_time_sec': 1, 'audio_duration_sec': 2,
                                                      'rtf': 0.5, 'memory_peak_mb': 100}}
        with tempfile.TemporaryDirectory() as directory, patch('scripts.benchmark.get_hardware_info',
                return_value={'chip': 'test', 'total_memory_gb': 16}), patch.object(AdapterFactory, 'get_adapter',
                side_effect=[None, good]), redirect_stdout(io.StringIO()):
            report = Path(directory) / 'report.md'
            count = run_benchmark('short', ['missing', 'chattts'], report_path=report)
            self.assertEqual(count, 1)
            self.assertIn('ChatTTS | 成功', report.read_text())


if __name__ == '__main__':
    unittest.main()
