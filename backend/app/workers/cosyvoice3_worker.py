try:
    from runtime import parser, finish, run
    from worker_settings import seed_generation
except ModuleNotFoundError:
    from backend.app.workers.runtime import parser, finish, run
    from backend.app.workers.worker_settings import seed_generation


def inference_output(model, args):
    mode = args.options.get('mode', 'auto')
    if mode == 'cross_lingual':
        # CosyVoice 3 将前缀与待说文本放在同一输入；边界缺失会导致语音编码过短。
        text = 'You are a helpful assistant.<|endofprompt|>' + args.text
        return model.inference_cross_lingual(text, args.ref_audio,
                                            stream=False, speed=args.speed, text_frontend=False)
    if args.prompt and mode == 'auto':
        instruction = f'You are a helpful assistant. {args.prompt}<|endofprompt|>'
        return model.inference_instruct2(args.text, instruction, args.ref_audio,
                                        stream=False, speed=args.speed, text_frontend=False)
    reference = 'You are a helpful assistant.<|endofprompt|>' + args.ref_text
    return model.inference_zero_shot(args.text, reference, args.ref_audio,
                                    stream=False, speed=args.speed, text_frontend=False)


def main():
    args = parser().parse_args()
    mode = args.options.get('mode', 'auto')
    if not args.ref_audio or (mode != 'cross_lingual' and not args.ref_text):
        raise ValueError('CosyVoice 3 需要参考音频及对应文字。')
    if args.device == 'mps':
        raise ValueError('当前 CosyVoice 官方实现支持 CPU / CUDA，未接入 MPS。')
    import numpy as np
    from cosyvoice.cli.cosyvoice import AutoModel
    model = AutoModel(model_dir=args.checkpoint_dir, fp16=False, load_trt=False, load_vllm=False)
    if args.device == 'cpu' and str(model.model.device) != 'cpu':
        raise ValueError('本环境默认启用了 CUDA，请使用 auto 或禁用 CUDA 后使用 CPU。')
    seed_generation(args.options)
    output = inference_output(model, args)
    chunks = [part['tts_speech'].detach().cpu().numpy().reshape(-1) for part in output]
    if not chunks:
        raise RuntimeError('CosyVoice 没有生成音频。')
    actual_mode = 'cross_lingual' if mode == 'cross_lingual' else 'instruct' if args.prompt else 'zero_shot'
    finish(np.concatenate(chunks), model.sample_rate, args.output, str(model.model.device),
           effective_options=dict(args.options, mode=actual_mode))


if __name__ == '__main__':
    run(main)
