from pathlib import Path
import re

from runtime import parser, device, finish, run


def main():
    args = parser().parse_args()
    import numpy as np
    import importlib.util
    from kokoro import KModel, KPipeline
    directory = Path(args.checkpoint_dir)
    selected = device(args.device, mps=False)
    weights = directory / 'kokoro-v1_0.pth'
    if not weights.is_file():
        weights = next(directory.glob('kokoro-v*.pth'))
    model = KModel(config=str(directory / 'config.json'), model=str(weights)).to(selected).eval()
    voice = args.voice if args.voice != 'default' else 'zf_xiaobei'
    voice_path = directory / 'voices' / f'{voice}.pt'
    if not voice_path.is_file():
        raise ValueError(f'本地没有音色 {voice} 的文件。')
    voice_pack = str(voice_path)
    if args.options.get('blend_voice'):
        import torch
        second = args.options['blend_voice']
        if second[0] != voice[0]:
            raise ValueError('混合音色必须属于同一语言。')
        second_path = directory / 'voices' / f'{second}.pt'
        ratio = args.options.get('blend_ratio', 0.5)
        voice_pack = torch.load(voice_path, weights_only=True) * (1 - ratio) + torch.load(second_path, weights_only=True) * ratio
    language = voice[0]
    if (language in 'ab' or re.search(r'[A-Za-z]', args.text)) and not importlib.util.find_spec('en_core_web_sm'):
        raise ValueError('Kokoro 英文或中英混读需要 en_core_web_sm，请运行模型环境安装脚本补齐英文资源。')
    if language == 'z' and not re.search(r'[\u4e00-\u9fff]', args.text):
        language = 'a'
    pipeline = KPipeline(lang_code=language, model=model, repo_id='hexgrad/Kokoro-82M')
    if language == 'z' and re.search(r'[A-Za-z]', args.text):
        from misaki.en import G2P
        english = G2P(trf=False)
        chinese = pipeline.g2p
        def bilingual(text):
            parts = re.split(r"([A-Za-z][A-Za-z \t'-]*)", text)
            return ''.join((english(part)[0] if re.match('[A-Za-z]', part) else chinese(part)[0])
                           for part in parts if part), None
        pipeline.g2p = bilingual
    chunks = [result.audio.detach().cpu().numpy() for result in pipeline(args.text, voice=voice_pack, speed=args.speed)]
    if not chunks:
        raise RuntimeError('Kokoro 没有生成音频。')
    finish(np.concatenate(chunks), 24000, args.output, selected, effective_options=dict(args.options, language=language))


if __name__ == '__main__':
    run(main)
