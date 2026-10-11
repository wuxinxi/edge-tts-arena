"""检查会改变实际发音的权重架构配置，使用已安装的模型环境。"""

import json
import subprocess
import unittest

from backend.app.core.config import PROJECT_ROOT
from backend.app.core.audio_validation import validate_audio_duration
from backend.app.workers.worker_settings import qwen_language, qwen_precision


class WorkerConfigurationTests(unittest.TestCase):
    def test_f5_legacy_checkpoint_uses_legacy_architecture(self):
        python = PROJECT_ROOT / '.venvs/f5tts/bin/python'
        if not python.is_file():
            self.skipTest('需要本地 F5-TTS 环境')
        result = subprocess.run([str(python), '-c',
            'import json; from backend.app.workers.f5tts_worker import load_architecture; '
            'print(json.dumps(load_architecture()))'], cwd=PROJECT_ROOT,
            capture_output=True, text=True, check=True)
        config = json.loads(result.stdout)
        self.assertIs(config['text_mask_padding'], False)
        self.assertEqual(config['pe_attn_head'], 1)
        self.assertEqual(config['text_dim'], 512)

    def test_duration_guard_respects_speed_and_short_prompts(self):
        text = '你好，这是一个用于检查语音合成的完整中文测试句子。'
        with self.assertRaisesRegex(RuntimeError, '明显过短'):
            validate_audio_duration(text, 0.33)
        validate_audio_duration(text, 1.0, speed=2)
        validate_audio_duration('你好', 0.2)

    def test_qwen_chinese_mixed_text_has_explicit_language(self):
        self.assertEqual(qwen_language('你好，正在测试 Apple Silicon 芯片。'), 'Chinese')
        self.assertEqual(qwen_language('日本語のテストです'), 'Auto')
        self.assertEqual(qwen_language('Hello, good morning.'), 'Auto')

    def test_qwen_mps_precision_matches_local_weights(self):
        checkpoint = PROJECT_ROOT / 'checkpoints/qwen3-tts-1.7b/model.safetensors'
        if not checkpoint.is_file():
            self.skipTest('需要本地 Qwen3 权重')
        with checkpoint.open('rb') as handle:
            header = json.loads(handle.read(int.from_bytes(handle.read(8), 'little')))
        self.assertEqual({entry['dtype'] for key, entry in header.items() if key != '__metadata__'}, {'BF16'})
        self.assertEqual(qwen_precision('mps'), 'bfloat16')
        self.assertEqual(qwen_precision('cpu'), 'float32')
