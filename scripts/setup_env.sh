#!/usr/bin/env bash

# ==============================================================================
# edge-tts-arena: 虚拟环境一键初始化脚本
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

VENV_DIR="${PROJECT_ROOT}/.venv"
VENV_PYTHON="${VENV_DIR}/bin/python"

echo "=========================================================="
echo "  🛠️  edge-tts-arena: 虚拟环境初始化 (.venv)"
echo "=========================================================="

# 检查系统是否有 uv
if command -v uv >/dev/null 2>&1; then
    echo "⚡ 检测到 uv，极速创建虚拟环境..."
    if [ ! -d "${VENV_DIR}" ]; then
        uv venv "${VENV_DIR}"
    fi
    echo "📦 安装基础下载依赖..."
    uv pip install -r "${SCRIPT_DIR}/requirements-download.txt" --python "${VENV_PYTHON}"
    uv pip install -r "${PROJECT_ROOT}/backend/requirements.txt" --python "${VENV_PYTHON}"
else
    echo "🐍 使用标准 python3 创建虚拟环境..."
    if [ ! -d "${VENV_DIR}" ]; then
        python3 -m venv "${VENV_DIR}"
    fi
    echo "📦 升级 pip 并安装基础下载依赖..."
    "${VENV_PYTHON}" -m pip install --upgrade pip
    "${VENV_PYTHON}" -m pip install -r "${SCRIPT_DIR}/requirements-download.txt"
    "${VENV_PYTHON}" -m pip install -r "${PROJECT_ROOT}/backend/requirements.txt"
fi

echo "----------------------------------------------------------"
echo "✅ 虚拟环境就绪！"
echo "   解释器路径: ${VENV_PYTHON}"
echo "   激活命令:   source .venv/bin/activate"
echo "=========================================================="
