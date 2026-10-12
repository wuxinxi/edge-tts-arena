#!/usr/bin/env python3
"""在模型解释器中准备 NLTK 资源，完整的本地缓存不触发联网。"""
import sys


RESOURCES = {
    # g2p_en 在导入时查找这两个 zip；仅复制解压目录仍会触发它的下载。
    'cmudict': ('corpora/cmudict/cmudict', 'corpora/cmudict.zip'),
    'averaged_perceptron_tagger': ('taggers/averaged_perceptron_tagger.zip',),
    'averaged_perceptron_tagger_eng': tuple(
        f'taggers/averaged_perceptron_tagger_eng/averaged_perceptron_tagger_eng.{part}.json'
        for part in ('weights', 'tagdict', 'classes')),
}


def resource_present(nltk, paths):
    try:
        for path in paths:
            nltk.data.find(path)
        return True
    except LookupError:
        return False


def prepare_resources(nltk):
    for name, paths in RESOURCES.items():
        if resource_present(nltk, paths):
            print(f'NLTK {name}: 本地已就绪，跳过下载', flush=True)
            continue
        print(f'NLTK {name}: 准备缺失资源', flush=True)
        if not nltk.download(name, raise_on_error=True) or not resource_present(nltk, paths):
            raise RuntimeError(f'NLTK {name} 下载后仍不完整，请检查 nltk_data 目录。')


def main():
    import nltk
    print(f'NLTK {nltk.__version__}: 检查本地语言资源', flush=True)
    try:
        prepare_resources(nltk)
    except (ValueError, RuntimeError, OSError) as error:
        print(f'NLTK 资源准备失败: {error}', file=sys.stderr)
        if 'SSRF' in str(error) or 'restricted IP' in str(error):
            print(
                '下载地址被 NLTK 网络安全检查拒绝。若使用 TUN / Fake-IP，'
                '请让 raw.githubusercontent.com 返回真实公网 IP 后重试；'
                '也可从已准备好的电脑复制完整 ~/nltk_data（包括 zip 文件），'
                '放在本机同名目录，或通过 NLTK_DATA 指定该目录。',
                file=sys.stderr)
        elif 'proxy' in str(error).lower():
            print('当前代理请求被 NLTK 拒绝；可使用可直连的网络，'
                  '或复制已有完整语言资源并设置 NLTK_DATA。', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
