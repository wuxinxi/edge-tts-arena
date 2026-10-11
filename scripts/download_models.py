#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
edge-tts-arena: PC 端侧主流 TTS 模型一键下载器
- 支持 10 个主流 TTS 模型（按参数量从小到大：82M -> 1.7B）
- 支持双下载源：ModelScope (魔搭社区，国内免翻墙高速直连) 与 Hugging Face (带国内镜像支持)
- 智能跳过：本地已下载完成的模型自动跳过，支持断点续传
"""

import os
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
import sys
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------
# 虚拟环境自动守护：确保强制使用项目 .venv 运行
# ---------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _PROJECT_ROOT / ".venv" / "bin" / "python"

if _VENV_PYTHON.exists() and Path(sys.executable).resolve() != _VENV_PYTHON.resolve():
    try:
        import huggingface_hub  # 尝试检查当前环境
        import modelscope
    except ImportError:
        # 若当前环境无依赖，无感切换到 .venv 解释器
        print(f"⚡ [环境守护] 检测到未激活虚拟环境，已自动切换为: {_VENV_PYTHON.relative_to(_PROJECT_ROOT)}")
        os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON)] + sys.argv)


if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 模型配置清单（按参数量从小到大严格排序，同时包含 HF 与 ModelScope 对应仓库）
MODELS_REGISTRY: Dict[str, dict] = {
    "kokoro-82m": {
        "name": "Kokoro-82M",
        "param_size": "82M",
        "repo_id": "hexgrad/Kokoro-82M",
        "ms_repo_id": "hexgrad/Kokoro-82M",
        "category": "极致轻量",
        "desc": "StyleTTS2 剪枝优化，当前 Hugging Face 全球月下载量第一（千万级）",
        "key_patterns": ["*.pth", "*.json"],
    },
    "melotts-zh": {
        "name": "MeloTTS (Chinese)",
        "param_size": "130M",
        "repo_id": "myshell-ai/MeloTTS-Chinese",
        "ms_repo_id": "myshell-ai/MeloTTS-Chinese",
        "category": "实用双语",
        "desc": "现代改良 VITS 架构，中英双语极度流畅，CPU/MPS 极低延迟",
        "key_patterns": ["*.pth", "config.json"],
    },
    "f5-tts": {
        "name": "F5-TTS",
        "param_size": "380M",
        "repo_id": "SWivid/F5-TTS",
        "ms_repo_id": "SWivid/F5-TTS",
        "category": "流匹配前沿",
        "desc": "Flow Matching 非自回归开创者，中英文零样本声音克隆顶流",
        "key_patterns": ["*.safetensors", "*.pt"],
    },
    "chattts": {
        "name": "ChatTTS",
        "param_size": "400M",
        "repo_id": "2noise/ChatTTS",
        "ms_repo_id": "AI-ModelScope/ChatTTS",
        "category": "拟真会话",
        "desc": "专为自然对话设计，包含拟真笑声、叹气、换气停顿等副语言",
        "key_patterns": ["*.pt", "*.json"],
    },
    "cosyvoice3": {
        "name": "CosyVoice 3.0 (0.5B)",
        "param_size": "500M",
        "repo_id": "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
        "ms_repo_id": "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
        "category": "最新全能",
        "desc": "阿里通义 2026 最新旗舰，中文/方言/多语种 3 秒克隆天花板",
        "key_patterns": ["*.pt", "*.yaml"],
    },
    "qwen3-tts-0.6b": {
        "name": "Qwen3-TTS 0.6B (Base)",
        "param_size": "600M",
        "repo_id": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "ms_repo_id": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "category": "千问双轨LM",
        "desc": "阿里千问 2026 重磅新发，首包低至 97ms 流式低延迟",
        "key_patterns": ["*.safetensors", "*.json"],
    },
    "qwen3-tokenizer": {
        "name": "Qwen3-TTS Tokenizer (12Hz)",
        "param_size": "20M",
        "repo_id": "Qwen/Qwen3-TTS-Tokenizer-12Hz",
        "ms_repo_id": "Qwen/Qwen3-TTS-Tokenizer-12Hz",
        "category": "基础分词器",
        "desc": "Qwen3-TTS 运行必需的 12Hz 语音 Tokenizer 模块",
        "key_patterns": ["*.json", "*.model"],
    },
    "parler-tts-mini": {
        "name": "Parler-TTS Mini",
        "param_size": "880M",
        "repo_id": "parler-tts/parler-tts-mini-v1",
        "ms_repo_id": "parler-tts/parler-tts-mini-v1",
        "category": "Prompt控制",
        "desc": "Hugging Face 官方旗舰，用自然语言 Prompt 描述控制说话人音色环境",
        "key_patterns": ["*.safetensors", "*.json"],
    },
    "fish-speech-1.5": {
        "name": "Fish-Speech 1.5",
        "param_size": "1B",
        "repo_id": "fishaudio/fish-speech-1.5",
        "ms_repo_id": "fishaudio/fish-speech-1.5",
        "category": "双流自回归",
        "desc": "Dual-AR 大模型架构，高度逼真、细腻情绪表达与高保真复刻",
        "key_patterns": ["*.safetensors", "*.json", "*.pth"],
    },
    "maskgct": {
        "name": "MaskGCT",
        "param_size": "1B",
        "repo_id": "amphion/MaskGCT",
        "ms_repo_id": "amphion/MaskGCT",
        "category": "掩码扩散",
        "desc": "上海 AI Lab / CUHK，非自回归两阶段掩码声学生成",
        "key_patterns": ["*.safetensors", "*.pt", "*.json"],
    },
    "qwen3-tts-1.7b": {
        "name": "Qwen3-TTS 1.7B (CustomVoice)",
        "param_size": "1.7B",
        "repo_id": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "ms_repo_id": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "category": "满血旗舰",
        "desc": "阿里千问 2026 大参数巅峰，端侧 16G/32G 统一内存上限压测",
        "key_patterns": ["*.safetensors", "*.json"],
    },
}

DEFAULT_CHECKPOINTS_DIR = _PROJECT_ROOT / "checkpoints"


def is_model_already_downloaded(target_dir: Path, key_patterns: List[str]) -> bool:
    """检查模型是否已经在本地存在并下载完整。"""
    # 下载标记和配置文件不能证明权重完整，统一使用后端的必需文件规则。
    from backend.app.core.model_files import missing_model_files
    key = target_dir.name
    return not missing_model_files(key, target_dir)


def print_model_table():
    """以表格形式打印当前支持的所有模型。"""
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="🎙️ edge-tts-arena 主流端侧 TTS 模型库 (从小到大)", show_header=True, header_style="bold cyan")
        table.add_column("Key", style="bold yellow", width=18)
        table.add_column("模型名称", style="green", width=22)
        table.add_column("参数量", style="magenta", width=10)
        table.add_column("类别", style="blue", width=14)
        table.add_column("本地状态", style="bold", width=12)
        table.add_column("ModelScope (国内源)", style="dim", width=34)

        for key, info in MODELS_REGISTRY.items():
            target_dir = DEFAULT_CHECKPOINTS_DIR / key
            downloaded = is_model_already_downloaded(target_dir, info["key_patterns"])
            status = "[bold green]已存在[/bold green]" if downloaded else "[dim]未下载[/dim]"
            table.add_row(
                key,
                info["name"],
                info["param_size"],
                info["category"],
                status,
                info.get("ms_repo_id", info["repo_id"]),
            )
        console.print(table)
    except ImportError:
        print("=" * 80)
        print(f"{'Key':<18} | {'模型名称':<22} | {'参数':<8} | {'状态':<8} | ModelScope / HF Repo")
        print("-" * 80)
        for key, info in MODELS_REGISTRY.items():
            target_dir = DEFAULT_CHECKPOINTS_DIR / key
            downloaded = is_model_already_downloaded(target_dir, info["key_patterns"])
            status = "已存在" if downloaded else "未下载"
            print(f"{key:<18} | {info['name']:<22} | {info['param_size']:<8} | {status:<8} | {info.get('ms_repo_id', info['repo_id'])}")
        print("=" * 80)


def download_from_modelscope(key: str, info: dict, target_dir: Path) -> bool:
    """使用 ModelScope 国内高速源下载。"""
    try:
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError:
        print("⚠️ 未安装 modelscope 库，请运行: pip install modelscope")
        return False

    ms_id = info.get("ms_repo_id", info["repo_id"])
    print(f"🇨🇳 [ModelScope 国内高速通道] 下载: {ms_id}")
    try:
        snapshot_download(
            model_id=ms_id,
            local_dir=str(target_dir),
        )
        return True
    except Exception as e:
        print(f"⚠️ ModelScope 下载遇到异常: {e}")
        return False


def download_from_huggingface(key: str, info: dict, target_dir: Path, token: Optional[str] = None) -> bool:
    """使用 Hugging Face 源下载。"""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("⚠️ 未安装 huggingface_hub 库，请运行: pip install huggingface_hub")
        return False

    hf_id = info["repo_id"]
    print(f"🌐 [Hugging Face 通道] 下载: {hf_id}")
    try:
        snapshot_download(
            repo_id=hf_id,
            local_dir=str(target_dir),
            token=token,
            max_workers=8,
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        return True
    except Exception as e:
        print(f"⚠️ Hugging Face 下载遇到异常: {e}")
        return False


def download_single_model(
    key: str,
    info: dict,
    output_dir: Path,
    source: str = "modelscope",
    force: bool = False,
    token: Optional[str] = None,
) -> bool:
    """下载单个模型，自动处理智能跳过与双源回退。"""
    target_dir = output_dir / key
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. 本地检查：如果已存在且未指定 force，直接跳过
    if not force and is_model_already_downloaded(target_dir, info["key_patterns"]):
        print(f"⏩ [已存在，跳过] {info['name']} ({info['param_size']}) -> {target_dir.relative_to(output_dir.parent)}")
        return True

    print(f"\n🚀 [开始下载] {info['name']} ({info['param_size']})")
    print(f"   └─ 目标路径: {target_dir}")

    start_time = time.time()
    ok = False

    # 优先源与备用源调度
    if source.lower() == "modelscope":
        ok = download_from_modelscope(key, info, target_dir)
        if not ok:
            print("🔄 尝试回退至 Hugging Face 镜像通道重试...")
            ok = download_from_huggingface(key, info, target_dir, token=token)
    else:
        ok = download_from_huggingface(key, info, target_dir, token=token)
        if not ok:
            print("🔄 尝试回退至 ModelScope 国内源重试...")
            ok = download_from_modelscope(key, info, target_dir)

    if ok and key == 'f5-tts':
        # 主模型快照不包含 Vocos，必须另行补全。
        vocoder_dir = target_dir / 'vocoder'
        vocoder_files = [vocoder_dir / name for name in ('config.yaml', 'pytorch_model.bin')]
        if not all(path.is_file() and path.stat().st_size > 0 for path in vocoder_files):
            print('📦 补充下载 F5-TTS 必需的 Vocos 24kHz 声码器...')
            ok = download_from_huggingface('f5-vocoder', {'repo_id': 'charactr/vocos-mel-24khz'}, vocoder_dir, token=token)

    if ok and not is_model_already_downloaded(target_dir, info['key_patterns']):
        print(f'❌ 下载返回成功，但 {key} 的必需文件仍不完整。')
        ok = False

    if ok:
        (target_dir / ".download_complete").write_text(f"completed_at: {time.time()}\nsource: {source}")
        cost = time.time() - start_time
        print(f"✅ [下载成功] {info['name']} 耗时: {cost:.1f} 秒\n")
        return True
    else:
        print(f"❌ [下载失败] {info['name']}\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="edge-tts-arena: PC 端侧主流 TTS 模型一键下载器 (从小到大 82M -> 1.7B)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="一键下载所有 10 款主流模型 (包含 Tokenizer)",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="",
        help="指定要下载的模型 Key，多个用英文逗号分隔，如: --models cosyvoice3,qwen3-tts-0.6b",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="modelscope",
        choices=["modelscope", "huggingface"],
        help="下载源: 'modelscope' (国内阿里极速源，免翻墙，默认推荐) 或 'huggingface'",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default="",
        help="设置 HTTP/HTTPS 代理，如: --proxy http://127.0.0.1:7890",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_CHECKPOINTS_DIR),
        help=f"模型存储目录，默认: {DEFAULT_CHECKPOINTS_DIR}",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用模型及当前本地缓存状态",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新下载（即使本地已存在）",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.getenv("HF_TOKEN", None),
        help="Hugging Face Token (可选)",
    )

    args = parser.parse_args()

    # 处理代理配置
    if args.proxy:
        os.environ["HTTP_PROXY"] = args.proxy
        os.environ["HTTPS_PROXY"] = args.proxy
        os.environ["http_proxy"] = args.proxy
        os.environ["https_proxy"] = args.proxy
        print(f"🔌 [代理已配置] HTTP(S)_PROXY -> {args.proxy}")

    # 如果走 HF 源，默认开启国内镜像
    if args.source == "huggingface" and not os.getenv("HF_ENDPOINT") and not args.proxy:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        print("🌐 [镜像加速] 已启用 HF 国内镜像节点: https://hf-mirror.com")

    out_path = Path(args.output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    if args.list:
        print_model_table()
        return

    targets = []
    if args.all:
        targets = list(MODELS_REGISTRY.keys())
    elif args.models:
        keys = [k.strip() for k in args.models.split(",") if k.strip()]
        for k in keys:
            if k not in MODELS_REGISTRY:
                print(f"⚠️  未知模型 Key: '{k}'，可通过 --list 查看所有支持的 Key。")
            else:
                targets.append(k)
    else:
        print_model_table()
        print("\n💡 提示:")
        print("   1. 🇨🇳 国内极速下载全部 (默认 ModelScope 免翻墙):")
        print("      ./download.sh --all")
        print("   2. 🇨🇳 国内极速下载指定模型:")
        print("      ./download.sh --models cosyvoice3,qwen3-tts-0.6b")
        print("   3. 🌐 切换到 Hugging Face 源下载:")
        print("      ./download.sh --all --source huggingface")
        print("   4. 🔌 本地如果有科学上网代理 (如 7890 端口):")
        print("      ./download.sh --all --source huggingface --proxy http://127.0.0.1:7890\n")
        return

    if not targets:
        print("⚠️ 未指定任何有效模型。退出。")
        return

    print(f"\n📦 计划处理 {len(targets)} 个模型，存放目录: {out_path}")
    print(f"🚀 首选下载渠道: {'ModelScope (魔搭社区·阿里云国内CDN直连)' if args.source == 'modelscope' else 'Hugging Face'}\n" + "=" * 60)

    success_count = 0
    skipped_count = 0
    fail_count = 0

    for key in targets:
        info = MODELS_REGISTRY[key]
        target_dir = out_path / key
        already_have = not args.force and is_model_already_downloaded(target_dir, info["key_patterns"])

        if already_have:
            skipped_count += 1
        ok = download_single_model(
            key,
            info,
            out_path,
            source=args.source,
            force=args.force,
            token=args.token,
        )
        if ok:
            if not already_have:
                success_count += 1
        else:
            fail_count += 1

    print("=" * 60)
    print("🎉 处理完成汇总:")
    print(f"   ├─ 新下载成功: {success_count} 个")
    print(f"   ├─ 本地已存在(已跳过): {skipped_count} 个")
    print(f"   └─ 失败: {fail_count} 个\n")


if __name__ == "__main__":
    main()
