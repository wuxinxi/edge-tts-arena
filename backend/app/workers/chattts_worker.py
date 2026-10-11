import sys
import json
import traceback
import argparse
from pathlib import Path
from worker_settings import load_options, seed_generation, chat_refine_prompt

def main():
    parser = argparse.ArgumentParser(description="ChatTTS Worker")
    parser.add_argument("--text", type=str, required=True)
    parser.add_argument("--voice_seed", type=int, default=2, help="Speaker seed")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--prompt", type=str, default="", help="Paralanguage/Prompt")
    parser.add_argument("--output", type=str, required=True, help="Output wav file")
    parser.add_argument("--checkpoint_dir", type=str, required=True, help="Model weights dir")
    parser.add_argument('--device', choices=['auto', 'cpu', 'mps', 'cuda'], default='auto')
    parser.add_argument('--options', type=load_options, default={})

    args = parser.parse_args()

    try:
        import torch
        import ChatTTS
        import soundfile as sf

        chat = ChatTTS.Chat()
        device = args.device
        if device == 'auto':
            # 当前 ChatTTS 实现混用 CPU / MPS 张量；默认使用稳定的 CPU 路径。
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        if not chat.load(source="custom", custom_path=args.checkpoint_dir, device=torch.device(device)):
            raise RuntimeError('ChatTTS 本地模型加载失败，请检查权重文件。')

        # Parse params
        text = args.text

        # ChatTTS requires text to be in a list
        texts = [text]

        # refine text parameter
        params_refine_text = ChatTTS.Chat.RefineTextParams(
            prompt=chat_refine_prompt(args.options, args.prompt)
        )

        # infer code parameter
        # speed is typically mapped 1-9 in ChatTTS but let's keep it default if not needed,
        # or we just map 1.0 -> speed_5
        speed_int = max(1, min(9, int(args.speed * 5)))

        spk_emb = None
        torch.manual_seed(args.voice_seed)
        spk_emb = chat.sample_random_speaker()
        seed_generation(args.options)

        params_infer_code = ChatTTS.Chat.InferCodeParams(
            spk_emb=spk_emb,
            prompt=f"[speed_{speed_int}]", temperature=args.options.get('temperature', 0.3),
            top_P=0.7, top_K=20,
        )

        # Synthesize
        wavs = chat.infer(texts, skip_refine_text=not args.options.get('refine_text', True),
                          params_refine_text=params_refine_text, params_infer_code=params_infer_code)

        if wavs and len(wavs) > 0:
            audio_data = wavs[0]
            # Ensure it's 1D for soundfile
            if len(audio_data.shape) > 1:
                audio_data = audio_data.flatten()
            sf.write(args.output, audio_data, 24000)

            print(json.dumps({"status": "success", "output": args.output, "sample_rate": 24000, "device": device,
                              "effective_options": dict(args.options, voice_seed=args.voice_seed,
                                                        speed_token=speed_int, refine_prompt=params_refine_text.prompt)}))
        else:
            raise RuntimeError('ChatTTS 没有生成音频。')

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e), "traceback": traceback.format_exc()}))
        sys.exit(1)

if __name__ == "__main__":
    main()
