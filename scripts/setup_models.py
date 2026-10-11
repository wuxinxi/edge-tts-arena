#!/usr/bin/env python3
"""为真实推理准备独立环境、固定版本源码和辅助资源。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ENVIRONMENTS = {
    'kokoro': ('3.12', None), 'qwen3': ('3.12', None), 'parler': ('3.12', None),
    'chattts': ('3.12', None), 'f5tts': ('3.12', None),
    'melotts': ('3.11', 'MeloTTS'), 'cosyvoice3': ('3.11', 'CosyVoice'),
    'fish-speech': ('3.11', 'fish-speech'), 'maskgct': ('3.11', 'Amphion'),
}


def command(args, cwd=ROOT):
    subprocess.run([str(item) for item in args], cwd=cwd, check=True)


def python_for(name):
    return ROOT / '.venvs' / name / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def prepare_source(name):
    source = ENVIRONMENTS[name][1]
    if not source:
        return
    info = json.loads((ROOT / 'scripts/model_sources.json').read_text())[source]
    directory = ROOT / 'third_party' / source
    if not directory.exists():
        directory.parent.mkdir(exist_ok=True)
        command(['git', 'clone', '--filter=blob:none', '--no-checkout', info['url'], directory])
        if source == 'Amphion':
            command(['git', 'sparse-checkout', 'init', '--cone'], directory)
            command(['git', 'sparse-checkout', 'set', 'models/tts/maskgct', 'models/codec', 'utils'], directory)
        command(['git', 'checkout', info['revision']], directory)
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=directory, text=True).strip()
    if actual != info['revision']:
        raise RuntimeError(f'{source} 源码版本与已验证版本不同，请保留现有修改后使用 {info["revision"]}。')
    if source == 'CosyVoice':
        command(['git', 'submodule', 'update', '--init', '--depth', '1', 'third_party/Matcha-TTS'], directory)
    patches = {'MeloTTS': 'melo-lazy-languages.patch', 'Amphion': 'maskgct-local-assets.patch'}
    if source in patches:
        patch = ROOT / 'scripts/vendor_patches' / patches[source]
        applied = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=directory, capture_output=True).returncode == 0
        if not applied:
            command(['git', 'apply', '--check', patch], directory)
            command(['git', 'apply', patch], directory)


def prepare_assets(name):
    # Use the model's own hub/transformer version, with network access only during setup.
    snippets = []
    if name == 'melotts':
        snippets.append("from huggingface_hub import snapshot_download; snapshot_download('bert-base-multilingual-uncased', allow_patterns=['config.json','tokenizer_config.json','tokenizer.json','vocab.txt','model.safetensors']); snapshot_download('bert-base-uncased', allow_patterns=['config.json','tokenizer_config.json','tokenizer.json','vocab.txt'])")
    if name == 'maskgct':
        snippets.append("from huggingface_hub import snapshot_download; snapshot_download('facebook/w2v-bert-2.0', local_dir='checkpoints/support/w2v-bert-2.0', allow_patterns=['config.json','preprocessor_config.json','model.safetensors'])")
    if name in ['melotts', 'maskgct']:
        snippets.append("import nltk; [nltk.download(name, raise_on_error=True) for name in ['cmudict','averaged_perceptron_tagger','averaged_perceptron_tagger_eng']]")
    environment = os.environ.copy()
    environment['HF_HUB_OFFLINE'] = '0'
    environment.setdefault('HF_HUB_DISABLE_XET', '1')
    for snippet in snippets:
        subprocess.run([str(python_for(name)), '-c', snippet], cwd=ROOT, env=environment, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--all', action='store_true', help='准备全部 9 个独立环境，覆盖 10 款模型；不下载主权重')
    selection.add_argument('--models', help='独立环境名，逗号分隔：' + ','.join(ENVIRONMENTS) + '；qwen3 包含两种版本；省略时与 --all 相同')
    parser.add_argument('--assets', action='store_true', help='仅下载辅助模型与文本资源')
    parser.add_argument('--index-url', help='可选 Python 包下载源')
    args = parser.parse_args()
    names = list(ENVIRONMENTS) if args.models is None else list(dict.fromkeys(name.strip() for name in args.models.split(',')))
    # Validate the complete selection before any installation or resource preparation.
    for name in names:
        if name not in ENVIRONMENTS:
            parser.error('未知环境: ' + name)
    for name in names:
        if not args.assets:
            prepare_source(name)
            python = python_for(name)
            if not python.is_file():
                command(['uv', 'venv', '--python', ENVIRONMENTS[name][0], python.parents[1]])
            install = ['uv', 'pip', 'install', '--python', python, '-r', ROOT / f'scripts/model_requirements/{name}.txt']
            if args.index_url:
                install.extend(['--index-url', args.index_url])
            command(install)
        prepare_assets(name)
        print(name + ': 准备完成（仍需下载 checkpoints 主权重并进行生成验证）', flush=True)


if __name__ == '__main__':
    main()
