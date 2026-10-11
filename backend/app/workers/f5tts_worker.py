import sys
import json
import traceback
import argparse
from pathlib import Path
import os
try:
    from worker_settings import load_options, seed_generation
except ModuleNotFoundError:
    from backend.app.workers.worker_settings import load_options, seed_generation


def load_architecture():
    from importlib.resources import files
    from omegaconf import OmegaConf
    # 本地 model_1200000 属于旧版 Base；DiT 的新版默认参数不适用于该权重。
    config = OmegaConf.load(str(files('f5_tts').joinpath('configs/F5TTS_Base.yaml')))
    return OmegaConf.to_container(config.model.arch)

def main():
    parser = argparse.ArgumentParser(description="F5-TTS Worker")
    parser.add_argument("--text", type=str, required=True)
    parser.add_argument("--ref_audio", type=str, required=False, help="Reference audio path")
    parser.add_argument("--ref_text", type=str, required=False, help="Reference text")
    parser.add_argument("--output", type=str, required=True, help="Output wav file")
    parser.add_argument("--checkpoint_dir", type=str, required=True, help="Model weights dir")
    parser.add_argument('--speed', type=float, default=1.0)
    parser.add_argument('--device', choices=['auto', 'cpu', 'mps', 'cuda'], default='auto')
    parser.add_argument('--options', type=load_options, default={})

    args = parser.parse_args()

    try:
        import torch
        import soundfile as sf
        from f5_tts.model import DiT
        from f5_tts.infer.utils_infer import load_vocoder, load_model, infer_process
        device = args.device
        if device == 'auto':
            device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')

        # Look for the checkpoint file inside args.checkpoint_dir/F5TTS_Base
        base_dir = os.path.join(args.checkpoint_dir, "F5TTS_Base")
        ckpt_path = os.path.join(base_dir, "model_1200000.safetensors")
        if not os.path.exists(ckpt_path):
            ckpt_path = os.path.join(base_dir, "model_1200000.pt")

        vocab_file = os.path.join(base_dir, "vocab.txt")

        # Load vocoder locally
        vocoder_path = os.path.join(args.checkpoint_dir, "vocoder")
        vocoder = load_vocoder(is_local=True, local_path=vocoder_path, device=device)

        # load model
        model_cls = DiT
        model_cfg = load_architecture()
        ema_model = load_model(model_cls, model_cfg, ckpt_path, mel_spec_type="vocos", vocab_file=vocab_file, device=device)

        if not args.ref_audio or not args.ref_text:
            raise ValueError("F5-TTS requires both ref_audio and ref_text")

        # Run inference
        seed_generation(args.options)
        audio, sample_rate, _ = infer_process(
            args.ref_audio,
            args.ref_text,
            args.text,
            ema_model,
            vocoder,
            mel_spec_type="vocos",
            speed=args.speed,
            nfe_step=args.options.get('nfe_step', 32),
            cfg_strength=args.options.get('cfg_strength', 2.0),
            device=device,
        )

        sf.write(args.output, audio, sample_rate)

        print(json.dumps({"status": "success", "output": args.output, "sample_rate": sample_rate, "device": device,
                          "effective_options": args.options}))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e), "traceback": traceback.format_exc()}))
        sys.exit(1)

if __name__ == "__main__":
    main()
