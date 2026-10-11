"""每份音频保存独立、可导出的参数记录；不保存上传音频的临时路径。"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf

from backend.app.core.reference import default_reference


def reference_record(metadata, audio_path, text):
    if not metadata.supports_clone:
        return {'source': 'none'}
    source = 'uploaded' if audio_path else 'default'
    if not audio_path:
        audio_path, text = default_reference()
    path = Path(audio_path)
    if not path.is_file():
        # 参数校验与模型推理仍负责报告无效文件；兼容测试和外部适配器。
        return {'source': source, 'text': text or '', 'sha256': None}
    return {'source': source, 'text': text or '', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'duration_sec': round(sf.info(path).duration, 3)}


def save_run(result, directory):
    result['created_at'] = datetime.now(timezone.utc).isoformat()
    result['record_url'] = '/api/runs/' + result['audio_file'].replace('.wav', '.run.json')
    path = directory / result['audio_file'].replace('.wav', '.run.json')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def recent_runs(directory, limit=50):
    from backend.app.core.run_history import RunHistory
    return RunHistory(directory).paginate(limit=limit)['items']
