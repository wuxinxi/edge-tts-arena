"""Offline single-variable Qwen generation probes; raw audio and explicit pending listening verdicts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

from backend.app.core.inference_lock import exclusive_inference
from backend.app.core.model_profiles import PROFILES
from backend.app.workers.runtime import run
from backend.app.workers.worker_settings import seed_generation
from scripts.diagnostics.qwen_onset_comparison import onset_segments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    if record['model_key'] != 'qwen3-tts-1.7b' or record['settings']['prompt']:
        raise ValueError('Expected the CustomVoice repro with no original instruction.')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    news = next(p['prompt'] for p in PROFILES['qwen3-tts-1.7b']['presets'] if p['key'] == 'news')
    original = ROOT / 'outputs' / record['audio_file']
    report_path = args.output_dir / 'report.json'
    report = dict(source=str(original), source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                  source_user_verdict='开头有额外哦声；CPU float32 解码后仍有',
                  source_text=record['text'], source_voice=record['voice'],
                  purpose='生成参数单变量诊断，不计入性能评测',
                  production_defaults_changed=False, variants=[])

    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    save()
    with exclusive_inference(ROOT / 'outputs/.inference.lock'):
        model = Qwen3TTSModel.from_pretrained(str(ROOT / 'checkpoints/qwen3-tts-1.7b'),
            device_map='mps', dtype=torch.bfloat16, attn_implementation='eager', local_files_only=True)
        original_decode = model.model.speech_tokenizer.decode
        captured = []

        def capture(encoded, **kwargs):
            captured.extend(item['audio_codes'].detach().cpu().clone() for item in encoded)
            return original_decode(encoded, **kwargs)

        model.model.speech_tokenizer.decode = capture
        try:
            for label, overrides in [('news-instruction', dict(instruct=news)),
                                     ('greedy-talker', dict(do_sample=False))]:
                captured.clear()
                seed_generation(record['settings']['options'])
                generation = dict(text=record['text'], speaker=record['voice'],
                    language=record['settings']['effective_options']['language'],
                    instruct=None, non_streaming_mode=True,
                    max_new_tokens=min(4096, max(256, len(record['text']) * 24)))
                generation.update(overrides)
                print(f'开始单变量生成对照：{label}。', flush=True)
                started = time.perf_counter()
                waves, rate = model.generate_custom_voice(**generation)
                elapsed = time.perf_counter() - started
                audio = np.asarray(waves[0], dtype=np.float32)
                if len(captured) != 1 or not audio.size or not np.isfinite(audio).all():
                    raise ValueError('Invalid diagnostic output.')
                path = args.output_dir / f'{label}.wav'
                sf.write(path, audio, rate)
                codes = captured[0].numpy()
                np.save(args.output_dir / f'{label}-codes.npy', codes, allow_pickle=False)
                value = dict(label=label, file=str(path.resolve()), seed=record['settings']['options']['seed'],
                    changed_parameter=overrides, generation=generation,
                    resolved_sampling=model._merge_generate_kwargs(**{
                        key: value for key, value in generation.items()
                        if key not in ['text', 'speaker', 'language', 'instruct', 'non_streaming_mode']}),
                    diagnostic_generation_sec=round(elapsed, 3), duration_sec=len(audio) / rate,
                    codec_shape=list(codes.shape), onset=onset_segments(audio, rate),
                    waveform_modified=False, human_review='待试听，未判定修复')
                report['variants'].append(value)
                save()
                print(json.dumps(dict(label=label, duration_sec=value['duration_sec'], onset=value['onset']),
                                 ensure_ascii=False), flush=True)
        finally:
            model.model.speech_tokenizer.decode = original_decode
        report['status'] = '生成对照完成，等待对额外哦声和正文完整度的听评'
        save()


if __name__ == '__main__':
    run(main, fast_exit=sys.platform == 'darwin')
