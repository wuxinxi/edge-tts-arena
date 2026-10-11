"""Fish-Speech 1.5 / 官方 v1.5.1 的 Dual-AR 与 Firefly 编码器。"""

from pathlib import Path
from runtime import parser, device, finish, run
from worker_settings import seed_generation


def main():
    args = parser().parse_args()
    import torch
    import librosa
    from fish_speech.models.text2semantic.inference import load_model, generate_long
    from fish_speech.models.vqgan.inference import load_model as load_codec

    selected = device(args.device)
    seed_generation(args.options)
    checkpoint = Path(args.checkpoint_dir)
    precision = torch.float16 if selected == 'cuda' else torch.float32
    model, decode = load_model(checkpoint, selected, precision, compile=False)
    # Firefly 的卷积在当前 MPS 上不支持；语言模型仍使用 MPS，编码器使用 CPU。
    codec_device = 'cpu' if selected == 'mps' else selected
    codec = load_codec('firefly_gan_vq', str(checkpoint / 'firefly-gan-vq-fsq-8x1024-21hz-generator.pth'), codec_device)
    prompt_tokens = None
    if args.ref_audio:
        if not args.ref_text:
            raise ValueError('Fish-Speech 使用参考音频时需要对应文字。')
        reference, _ = librosa.load(args.ref_audio, sr=codec.spec_transform.sample_rate)
        audio = torch.from_numpy(reference).to(codec_device)[None, None, :]
        with torch.inference_mode():
            prompt_tokens = codec.encode(audio, torch.tensor([audio.shape[-1]], device=codec_device))[0][0].to(selected)
    with torch.inference_mode():
        with torch.device(selected):
            model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len, dtype=precision)
        chunks = [result.codes for result in generate_long(
            model=model, device=selected, decode_one_token=decode, text=args.text,
            prompt_text=args.ref_text if prompt_tokens is not None else None,
            prompt_tokens=prompt_tokens, compile=False,
            repetition_penalty=args.options.get('repetition_penalty', 1.2), top_p=args.options.get('top_p', 0.7),
            temperature=args.options.get('temperature', 0.7), chunk_length=args.options.get('chunk_length', 100),
        ) if result.action == 'sample']
        if not chunks:
            raise RuntimeError('Fish-Speech 没有生成语音编码。')
        codes = torch.cat(chunks, dim=1).to(codec_device)
        audio, _ = codec.decode(indices=codes[None], feature_lengths=torch.tensor([codes.shape[1]], device=codec_device))
    actual_device = 'mps + cpu' if selected == 'mps' else selected
    finish(audio[0, 0].float().cpu().numpy(), codec.spec_transform.sample_rate, args.output, actual_device, args.speed,
           args.options)


if __name__ == '__main__':
    run(main)
