"""使用已有本地资源，串行验证配音预设；不会安装或下载资源。"""

import json
import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.api.routes import TTSGenerateRequest, generate_audio
from backend.app.core.config import OUTPUTS_DIR


CASES = [
    ('kokoro-82m', 'default', {'blend_voice': 'zf_xiaoyi', 'blend_ratio': 0.5}),
    ('melotts-zh', 'steady', {}),
    ('chattts', 'verbatim', {}),
    ('f5-tts', 'fast', {}),
    ('qwen3-tts-1.7b', 'energetic', {'language': 'Chinese'}),
    ('cosyvoice3', 'default', {'mode': 'cross_lingual'}),
    ('qwen3-tts-0.6b', 'timbre', {'language': 'Chinese'}),
    ('fish-speech-1.5', 'default', {}),
    ('maskgct', 'fast', {'target_duration': 5.0}),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('models', nargs='*')
    parser.add_argument('--report', default='customization-verification.json')
    args = parser.parse_args()
    results = []
    keys = set(args.models)
    for key, preset, options in CASES:
        if keys and key not in keys:
            continue
        print(json.dumps({'model': key, 'state': 'running'}, ensure_ascii=False), flush=True)
        try:
            result = generate_audio(TTSGenerateRequest(model_key=key,
                text='今天阳光很好，让我们用清晰自然的声音，讲述一个新的故事。',
                preset=preset, options=options))['data']
            audio, rate = sf.read(OUTPUTS_DIR / result['audio_file'])
            if not np.isfinite(audio).all() or np.max(np.abs(audio)) < 0.01:
                raise RuntimeError('音频无效或几乎静音')
            results.append(result)
            print(json.dumps({'model': key, 'state': 'success', 'duration': len(audio) / rate,
                              'effective_options': result['settings']['effective_options']}, ensure_ascii=False), flush=True)
        except Exception as error:
            results.append({'success': False, 'model_key': key, 'error': str(error)})
            print(json.dumps(results[-1], ensure_ascii=False), flush=True)
        (OUTPUTS_DIR / args.report).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    if any(not result['success'] for result in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
