#!/usr/bin/env python3
"""逐个执行真实推理，保存音频校验、内存和耗时的验证报告。"""
import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
import soundfile as sf
from backend.app.adapters.factory import AdapterFactory
from backend.app.core.config import OUTPUTS_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', help='逗号分隔；省略时仅验证本地资源就绪的模型')
    parser.add_argument('--ref-audio')
    parser.add_argument('--ref-text')
    parser.add_argument('--report', default=str(OUTPUTS_DIR / 'model_verification.json'))
    args = parser.parse_args()
    results = []
    keys = args.models.split(',') if args.models else [
        model['key'] for model in AdapterFactory.get_all_models_status() if model['is_ready']]
    if not keys:
        print('没有本地资源就绪的模型；不会自动下载。', flush=True)
        return 1
    for key in keys:
        adapter = AdapterFactory.get_adapter(key)
        print('验证 ' + key, flush=True)
        row = {'model_key': key, 'checked_at': datetime.now().astimezone().isoformat()}
        try:
            if not adapter:
                raise ValueError('未知模型')
            status = adapter.get_status()
            if not status['is_ready']:
                raise RuntimeError(status['unavailable_reason'])
            text = 'Hello, have a wonderful day.' if key == 'parler-tts-mini' else '你好，祝你今天愉快。'
            result = adapter.generate(text=text, ref_audio_path=args.ref_audio, ref_text=args.ref_text)
            audio, rate = sf.read(OUTPUTS_DIR / result['audio_file'])
            if not np.isfinite(audio).all() or np.max(np.abs(audio)) < 1e-5:
                raise RuntimeError('音频无效或完全静音')
            row.update(result, verified_frames=len(audio), verified_sample_rate=rate)
            print('成功 ' + key + ' ' + result['audio_file'], flush=True)
        except Exception as error:
            row.update(success=False, error=str(error))
            if adapter and getattr(adapter, 'last_worker_error', None):
                diagnostic = OUTPUTS_DIR / 'worker_errors' / (key + '.log')
                diagnostic.parent.mkdir(exist_ok=True)
                diagnostic.write_text(adapter.last_worker_error)
                row['diagnostics_file'] = str(diagnostic)
            print('失败 ' + key + ': ' + str(error), flush=True)
        results.append(row)
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    return 0 if all(row['success'] for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
