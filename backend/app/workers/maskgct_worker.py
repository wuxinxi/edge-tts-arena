"""MaskGCT 官方两阶段推理；模型文件与 W2V-BERT 均从本地读取。"""

import os
from pathlib import Path
from runtime import parser, device, finish, run
from worker_settings import seed_generation


def main():
    args = parser().parse_args()
    checkpoint = Path(args.checkpoint_dir).resolve()
    support = Path(__file__).resolve().parents[3] / 'checkpoints/support/w2v-bert-2.0'
    os.environ['MASKGCT_SEMANTIC_DIR'] = str(support)
    reference = str(Path(args.ref_audio).resolve()) if args.ref_audio else None
    if not reference or not args.ref_text:
        raise ValueError('MaskGCT 需要参考音频及其对应文字。')
    os.chdir(Path(__file__).resolve().parents[3] / 'third_party' / 'Amphion')
    import torch
    import safetensors.torch
    from accelerate import init_empty_weights
    import espeakng_loader
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    os.environ.setdefault('ESPEAK_DATA_PATH', espeakng_loader.get_data_path())
    EspeakWrapper.set_library(espeakng_loader.get_library_path())
    EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
    from models.tts.maskgct.maskgct_utils import (
        load_config, RepCodec, CodecEncoder, CodecDecoder, MaskGCT_T2S, MaskGCT_S2A,
        Wav2Vec2BertModel, MaskGCT_Inference_Pipeline,
    )

    selected = device(args.device, mps=False)
    target = torch.device(selected)
    cfg = load_config('./models/tts/maskgct/config/maskgct.json')
    semantic = Wav2Vec2BertModel.from_pretrained(
        str(support), local_files_only=True, low_cpu_mem_usage=True).eval().to(target)
    stats = torch.load('./models/tts/maskgct/ckpt/wav2vec2bert_stats.pt', map_location='cpu')
    mean, std = stats['mean'].to(target), stats['var'].sqrt().to(target)

    def load_model(model_class, config, filename):
        # 避免同时保留随机初始化参数与权重副本；缓冲区仍正常初始化。
        with init_empty_weights(include_buffers=False):
            model = model_class(cfg=config)
        weights = safetensors.torch.load_file(str(checkpoint / filename))
        # load_model 会拒绝官方解码器中切片保存的 ISTFT 缓冲区。
        model.load_state_dict(weights, strict=True, assign=True)
        return model.eval().to(target)

    semantic_codec = load_model(RepCodec, cfg.model.semantic_codec, 'semantic_codec/model.safetensors')
    encoder = load_model(CodecEncoder, cfg.model.acoustic_codec.encoder, 'acoustic_codec/model.safetensors')
    decoder = load_model(CodecDecoder, cfg.model.acoustic_codec.decoder, 'acoustic_codec/model_1.safetensors')
    t2s = load_model(MaskGCT_T2S, cfg.model.t2s_model, 't2s_model/model.safetensors')
    s2a_one = load_model(MaskGCT_S2A, cfg.model.s2a_model.s2a_1layer, 's2a_model/s2a_model_1layer/model.safetensors')
    s2a_full = load_model(MaskGCT_S2A, cfg.model.s2a_model.s2a_full, 's2a_model/s2a_model_full/model.safetensors')
    pipeline = MaskGCT_Inference_Pipeline(semantic, semantic_codec, encoder, decoder, t2s,
                                          s2a_one, s2a_full, mean, std, target)
    language = lambda text: 'zh' if any('\u4e00' <= char <= '\u9fff' for char in text) else 'en'
    seed_generation(args.options)
    target_language = args.options.get('language', 'auto')
    if target_language == 'auto':
        target_language = language(args.text)
    audio = pipeline.maskgct_inference(reference, args.ref_text, args.text,
                                     language=language(args.ref_text), target_language=target_language,
                                     target_len=args.options.get('target_duration', 0) or None,
                                     n_timesteps=args.options.get('n_timesteps', 25), cfg=args.options.get('cfg', 2.5))
    finish(audio, 24000, args.output, selected, args.speed, dict(args.options, language=target_language))


if __name__ == '__main__':
    run(main)
