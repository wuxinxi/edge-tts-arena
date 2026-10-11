"""Replay fixed Qwen codec tokens across decoders; offline diagnostic, never a benchmark."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

from backend.app.core.inference_lock import exclusive_inference
from backend.app.workers.runtime import run
from backend.app.workers.worker_settings import seed_generation


def main():
    import gc
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel
    from qwen_tts.inference.qwen3_tts_tokenizer import Qwen3TTSTokenizer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    if record['model_key'] != 'qwen3-tts-1.7b':
        raise ValueError('Only the 1.7B CustomVoice repro is supported.')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report_path = args.output_dir / 'report.json'
    checkpoint = ROOT / 'checkpoints/qwen3-tts-1.7b'
    original = ROOT / 'outputs' / record['audio_file']
    reference, reference_rate = sf.read(original, dtype='float32')
    report = dict(source=str(original), user_confirmed_symptom='开头额外的哦声',
                  production_settings_changed=False, cropped=False,
                  scope='固定 codec 解码诊断，不计入模型评测', variants=[])

    def save_report():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    def save_audio(label, waveform, rate, decoder):
        waveform = np.asarray(waveform, dtype='float32')
        if waveform.shape != reference.shape or rate != reference_rate:
            raise ValueError('Decoder comparison changed shape or sample rate.')
        if not np.isfinite(waveform).all():
            raise ValueError('Decoder returned non-finite audio.')
        path = args.output_dir / f'{label}.wav'
        sf.write(path, waveform, rate)
        quantized, _ = sf.read(path, dtype='float32')
        comparisons = {}
        for name, length in [('first_0.4s', int(rate * .4)), ('full', len(reference))]:
            a, b = reference[:length], quantized[:length]
            rms = float(np.sqrt(np.mean(a * a)))
            error = float(np.sqrt(np.mean((a - b) ** 2)))
            comparisons[name] = dict(reference_rms=rms, difference_rms=error,
                                     relative_difference_rms=error / max(rms, 1e-12))
        value = dict(label=label, file=str(path.resolve()),
                     decoder_device=str(decoder.model.device),
                     decoder_dtype=str(decoder.model.dtype),
                     duration_sec=len(waveform) / rate,
                     same_pcm_as_original=bool(np.array_equal(reference, quantized)),
                     same_file_as_original=path.read_bytes() == original.read_bytes(),
                     comparisons=comparisons, human_review='待试听确认')
        report['variants'].append(value)
        save_report()
        print(json.dumps(value, ensure_ascii=False), flush=True)

    with exclusive_inference(ROOT / 'outputs/.inference.lock'):
        print('重放已确认的原始生成，捕获未修改的语音编码。', flush=True)
        model = Qwen3TTSModel.from_pretrained(str(checkpoint), device_map='mps',
            dtype=torch.bfloat16, attn_implementation='eager', local_files_only=True)
        tokenizer = model.model.speech_tokenizer
        original_decode = tokenizer.decode
        captured = []

        def capture_decode(encoded, **kwargs):
            captured.extend(item['audio_codes'].detach().cpu().clone() for item in encoded)
            return original_decode(encoded, **kwargs)

        tokenizer.decode = capture_decode
        seed_generation(record['settings']['options'])
        try:
            waves, rate = model.generate_custom_voice(text=record['text'], speaker=record['voice'],
                language=record['settings']['effective_options']['language'],
                instruct=record['settings']['prompt'] or None, non_streaming_mode=True,
                max_new_tokens=min(4096, max(256, len(record['text']) * 24)))
        finally:
            tokenizer.decode = original_decode
        if len(captured) != 1:
            raise ValueError('Expected exactly one captured codec sequence.')
        codes = captured[0]
        codec_file = args.output_dir / 'original-codes.npy'
        np.save(codec_file, codes.numpy(), allow_pickle=False)
        report['codec_shape'] = list(codes.shape)
        report['codec_sha256'] = hashlib.sha256(codec_file.read_bytes()).hexdigest()
        save_audio('original-mps', waves[0], rate, tokenizer)
        if not report['variants'][0]['same_file_as_original']:
            raise ValueError('Known-bad audio was not reproduced exactly; stop comparison.')
        del model, tokenizer, original_decode, waves
        gc.collect()
        torch.mps.empty_cache()

        for selected in ['mps', 'cpu']:
            print(f'只解码同一份语音编码：{selected} / float32。', flush=True)
            decoder = Qwen3TTSTokenizer.from_pretrained(str(checkpoint / 'speech_tokenizer'),
                device_map=selected, dtype=torch.float32,
                attn_implementation='eager', local_files_only=True)
            waves, rate = decoder.decode([dict(audio_codes=codes)])
            save_audio(f'{selected}-float32', waves[0], rate, decoder)
            del decoder, waves
            gc.collect()
            torch.mps.empty_cache()
        report['status'] = '解码对照完成；是否消除额外哦声需人工听评，未判定修复'
        save_report()


if __name__ == '__main__':
    run(main, fast_exit=sys.platform == 'darwin')
