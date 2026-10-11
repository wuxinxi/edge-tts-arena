"""使用已有 Qwen 权重对比开头发声；不裁剪、不改默认配置、不下载资源。"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

from backend.app.core.inference_lock import exclusive_inference
from backend.app.workers.worker_settings import qwen_precision, seed_generation
from backend.app.workers.runtime import device, run


def onset_segments(audio, rate):
    """仅描述波形活动段；不能识别字词或自动判断是否多说了内容。"""
    import numpy as np
    frames = int(rate * .02)
    part = np.asarray(audio[:int(rate * 1.2)])
    rms = np.array([np.sqrt(np.mean(part[i:i+frames] ** 2)) for i in range(0, len(part), frames)])
    threshold = max(.003, float(rms.max()) * .035)
    active = rms >= threshold
    segments = []
    start = None
    for index, value in enumerate([*active, False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            segments.append([round(start * .02, 3), round(index * .02, 3)])
            start = None
    return dict(window_sec=1.2, frame_sec=.02, rms_threshold=threshold, activity_segments=segments,
                interpretation='波形活动段仅供定位，内容与听感必须人工确认')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    if record['model_key'] != 'qwen3-tts-1.7b':
        raise ValueError('此诊断仅用于 Qwen3 1.7B CustomVoice')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report_path = args.output_dir / 'report.json'
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel
    original_path = ROOT / 'outputs' / record['audio_file']
    original_audio, original_rate = sf.read(original_path, dtype='float32')
    report = dict(source_record=str(args.record.resolve()), source_audio=str(original_path),
                  source_sha256=hashlib.sha256(original_path.read_bytes()).hexdigest(),
                  source_onset=onset_segments(original_audio, original_rate),
                  source_voice=record['voice'], source_text=record['text'],
                  scope='诊断：同进程预加载，不用于冷启动性能排名', variants=[])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    with exclusive_inference(ROOT / 'outputs/.inference.lock'):
        selected = device('auto')
        precision = qwen_precision(selected)
        print('正在加载已有 Qwen 权重，不下载资源。', flush=True)
        model = Qwen3TTSModel.from_pretrained(str(ROOT / 'checkpoints/qwen3-tts-1.7b'),
            device_map=selected, dtype=getattr(torch, precision), attn_implementation='eager', local_files_only=True)
        seed = record['settings']['options'].get('seed', 42)
        for label, streaming_mode, variant_seed in [('same-settings', True, seed),
                                                   ('text-sequential', False, seed),
                                                   ('alternate-seed', True, seed+1)]:
            seed_generation(dict(seed=variant_seed))
            generation = dict(text=record['text'], speaker=record['voice'],
                language=record['settings']['effective_options']['language'],
                instruct=record['settings']['prompt'] or None, non_streaming_mode=streaming_mode,
                max_new_tokens=min(4096, max(256, len(record['text'])*24)))
            print(f'开始诊断：{label}，seed={variant_seed}。', flush=True)
            started = time.perf_counter()
            waves, rate = model.generate_custom_voice(**generation)
            audio = np.asarray(waves[0], dtype=np.float32)
            if not audio.size or not np.isfinite(audio).all():
                raise ValueError('返回无效音频')
            filename = args.output_dir / (label + '.wav')
            sf.write(filename, audio, rate)
            values = dict(label=label, audio_file=str(filename.resolve()), device=selected, precision=precision,
                          seed=variant_seed, generation=generation,
                          sampling=model._merge_generate_kwargs(max_new_tokens=generation['max_new_tokens']),
                          diagnostic_generation_sec=round(time.perf_counter()-started,3),
                          duration_sec=len(audio)/rate, onset=onset_segments(audio, rate),
                          waveform_modified=False, human_review='待确认')
            report['variants'].append(values)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps(dict(label=label, duration_sec=values['duration_sec'], onset=values['onset']),ensure_ascii=False),flush=True)


if __name__ == '__main__':
    run(main, fast_exit=sys.platform == 'darwin')
