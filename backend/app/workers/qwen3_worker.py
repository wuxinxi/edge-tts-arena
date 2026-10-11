from pathlib import Path

from runtime import parser, device, finish, run
from worker_settings import qwen_language, qwen_precision, seed_generation


def main():
    arguments = parser()
    arguments.add_argument('--model_key', required=True)
    args = arguments.parse_args()
    import torch
    from qwen_tts import Qwen3TTSModel
    base_model = args.model_key == 'qwen3-tts-0.6b'
    selected = device(args.device, mps=not base_model)
    if selected == 'mps' and not torch.backends.mps.is_macos_or_newer(14, 0):
        selected = 'cpu'
    model = Qwen3TTSModel.from_pretrained(
        args.checkpoint_dir, device_map=selected,
        dtype=getattr(torch, qwen_precision(selected)),
        attn_implementation='eager', local_files_only=True,
    )
    seed_generation(args.options)
    language = args.options.get('language', 'Auto')
    if language == 'Auto':
        language = qwen_language(args.text)
    generation = dict(text=args.text, language=language, non_streaming_mode=True,
                      max_new_tokens=min(4096, max(256, len(args.text) * 24)))
    if args.model_key == 'qwen3-tts-0.6b':
        if not args.ref_audio or (not args.options.get('x_vector_only', False) and not args.ref_text):
            raise ValueError('Qwen3 Base 需要参考音频及对应文字。')
        audio, rate = model.generate_voice_clone(**generation, ref_audio=args.ref_audio, ref_text=args.ref_text or None,
                                                x_vector_only_mode=args.options.get('x_vector_only', False))
    else:
        voice = args.voice if args.voice != 'default' else 'vivian'
        audio, rate = model.generate_custom_voice(**generation, speaker=voice, instruct=args.prompt or None)
    finish(audio[0], rate, args.output, selected, args.speed,
           dict(args.options, language=language, precision=qwen_precision(selected)))


if __name__ == '__main__':
    import sys
    run(main, fast_exit=sys.platform == 'darwin')
