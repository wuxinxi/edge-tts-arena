from pathlib import Path

from runtime import parser, device, finish, run
from worker_settings import seed_generation


def main():
    args = parser().parse_args()
    from melo.api import TTS
    selected = device(args.device, mps=False)
    if selected == 'mps':
        raise ValueError('MeloTTS 的卷积在当前 MPS 环境不受支持，请使用 CPU。')
    directory = Path(args.checkpoint_dir)
    model = TTS(language='ZH', device=selected,
                config_path=str(directory / 'config.json'), ckpt_path=str(directory / 'checkpoint.pth'))
    speakers = model.hps.data.spk2id
    voice = args.voice if args.voice in speakers else 'ZH'
    seed_generation(args.options)
    audio = model.tts_to_file(args.text, speakers[voice], output_path=None, speed=args.speed, quiet=True,
                              noise_scale=args.options.get('noise_scale', 0.6),
                              noise_scale_w=args.options.get('noise_scale_w', 0.8))
    finish(audio, model.hps.data.sampling_rate, args.output, selected, effective_options=args.options)


if __name__ == '__main__':
    run(main)
