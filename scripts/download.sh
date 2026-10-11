#!/usr/bin/env bash

# ==============================================================================
# edge-tts-arena: PC 端侧主流 TTS 模型一键下载脚本
# 严格约束：强制使用项目本地虚拟环境 (.venv)
# ==============================================================================

set -e

# 定位脚本所在目录与项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

VENV_DIR="${PROJECT_ROOT}/.venv"
VENV_PYTHON="${VENV_DIR}/bin/python"

echo "=========================================================="
echo "  🎙️  edge-tts-arena: PC 端侧主流 TTS 模型下载工具"
echo "  📁 项目根目录: ${PROJECT_ROOT}"
echo "=========================================================="

# 1. 严格检查虚拟环境
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "⚠️  未检测到虚拟环境: ${VENV_DIR}"
    echo "🛠️  正在为你自动创建虚拟环境 (.venv)..."
    if command -v uv >/dev/null 2>&1; then
        uv venv "${VENV_DIR}"
        uv pip install -r "${SCRIPT_DIR}/requirements-download.txt" --python "${VENV_PYTHON}"
    else
        python3 -m venv "${VENV_DIR}"
        "${VENV_PYTHON}" -m pip install --upgrade pip
        "${VENV_PYTHON}" -m pip install -r "${SCRIPT_DIR}/requirements-download.txt"
    fi
    echo "✅ 虚拟环境创建并初始化完成！"
fi

# 2. 验证虚拟环境依赖
if ! "${VENV_PYTHON}" -c "import huggingface_hub, rich, tqdm" >/dev/null 2>&1; then
    echo "📦 正在补全虚拟环境下载依赖..."
    if command -v uv >/dev/null 2>&1; then
        uv pip install -r "${SCRIPT_DIR}/requirements-download.txt" --python "${VENV_PYTHON}"
    else
        "${VENV_PYTHON}" -m pip install -r "${SCRIPT_DIR}/requirements-download.txt"
    fi
fi

echo "🐍 运行环境: $("${VENV_PYTHON}" --version) (${VENV_PYTHON})"
echo "----------------------------------------------------------"

# 3. 强制在虚拟环境中运行 Python 下载脚本
exec "${VENV_PYTHON}" "${SCRIPT_DIR}/download_models.py" "$@"
