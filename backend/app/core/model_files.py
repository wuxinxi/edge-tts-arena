"""检查推理必需文件；说明文档和未完成下载不算模型权重。"""

from pathlib import Path


# 每组至少存在一个非空文件，各组都满足才视为权重已下载。
REQUIRED_FILES = {
    'kokoro-82m': [('kokoro-v*.pth',), ('config.json',), ('voices/*.pt',)],
    'melotts-zh': [('checkpoint.pth',), ('config.json',)],
    'f5-tts': [('F5TTS_Base/model_1200000.safetensors', 'F5TTS_Base/model_1200000.pt'),
               ('F5TTS_Base/vocab.txt',), ('vocoder/config.yaml',), ('vocoder/pytorch_model.bin',)],
    'chattts': [('asset/Decoder.safetensors',), ('asset/Embed.safetensors',),
                ('asset/DVAE.safetensors',), ('asset/Vocos.safetensors',),
                ('asset/gpt/model.safetensors',), ('asset/gpt/config.json',),
                ('asset/tokenizer/tokenizer.json',), ('asset/tokenizer/tokenizer_config.json',),
                ('asset/tokenizer/special_tokens_map.json',)],
    'cosyvoice3': [('llm.pt',), ('flow.pt',), ('hift.pt',), ('cosyvoice3.yaml',),
                   ('campplus.onnx',), ('speech_tokenizer_v3.onnx',), ('CosyVoice-BlankEN/model.safetensors',)],
    'qwen3-tts-0.6b': [('model.safetensors',), ('config.json',), ('tokenizer_config.json',),
                      ('speech_tokenizer/model.safetensors',), ('speech_tokenizer/config.json',)],
    'qwen3-tts-1.7b': [('model.safetensors',), ('config.json',), ('tokenizer_config.json',),
                      ('speech_tokenizer/model.safetensors',), ('speech_tokenizer/config.json',)],
    'qwen3-tokenizer': [('model.safetensors',), ('config.json',)],
    'parler-tts-mini': [('model.safetensors', 'pytorch_model.bin'), ('config.json',), ('tokenizer.json',)],
    'fish-speech-1.5': [('model.pth',), ('firefly-gan-vq-fsq-8x1024-21hz-generator.pth',),
                       ('config.json',), ('tokenizer.tiktoken',)],
    'maskgct': [('semantic_codec/model.safetensors',), ('acoustic_codec/model.safetensors',),
                ('acoustic_codec/model_1.safetensors',), ('t2s_model/model.safetensors',),
                ('s2a_model/s2a_model_1layer/model.safetensors',),
                ('s2a_model/s2a_model_full/model.safetensors',)],
}


def missing_model_files(key: str, directory: Path) -> list[str]:
    groups = REQUIRED_FILES.get(key)
    if groups is None:
        return ['未定义权重检查规则']
    return [
        ' / '.join(group)
        for group in groups
        if not any(path.is_file() and path.stat().st_size > 0
                   for pattern in group for path in directory.glob(pattern))
    ]
