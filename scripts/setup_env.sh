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
PLATFORM_PYTHON_VERSION="3.12"

echo "=========================================================="
echo "  🛠️  edge-tts-arena: 虚拟环境初始化 (.venv)"
echo "=========================================================="

# 系统默认 Python 可以不同；新建平台环境统一使用已验证的版本。
if [ -d "${VENV_DIR}" ]; then
    if [ ! -x "${VENV_PYTHON}" ]; then
        echo "错误: 已有 .venv 缺少可用解释器，请先保留并检查该目录，不会自动覆盖。"
        exit 1
    fi
    EXISTING_PYTHON_VERSION="$("${VENV_PYTHON}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [ "${EXISTING_PYTHON_VERSION}" != "${PLATFORM_PYTHON_VERSION}" ]; then
        echo "提示: 保留已有 Python ${EXISTING_PYTHON_VERSION} 平台环境；当前已验证版本为 ${PLATFORM_PYTHON_VERSION}。"
        echo "      如需复现已验证配置，请另行准备 3.12 环境；模型环境仍按各自版本独立创建。"
    fi
fi

# 创建环境时不自动下载解释器，缺少指定版本则提示手动准备。
if command -v uv >/dev/null 2>&1; then
    echo "⚡ 检测到 uv，极速创建虚拟环境..."
    if [ ! -d "${VENV_DIR}" ]; then
        if ! uv venv --python "${PLATFORM_PYTHON_VERSION}" --no-python-downloads "${VENV_DIR}"; then
            echo "创建环境失败。若缺少 Python 3.12，可手动运行 uv python install 3.12 后重试。"
            exit 1
        fi
    fi
    echo "📦 安装基础下载依赖..."
    uv pip install -r "${SCRIPT_DIR}/requirements-download.txt" --python "${VENV_PYTHON}"
    uv pip install -r "${PROJECT_ROOT}/backend/requirements.txt" --python "${VENV_PYTHON}"
else
    if [ ! -d "${VENV_DIR}" ]; then
        if ! command -v python3.12 >/dev/null 2>&1; then
            echo "错误: 未找到 uv 或 python3.12；系统 python3 不会作为其他版本的替代。"
            echo "      请准备 Python 3.12，或安装 uv 后手动运行 uv python install 3.12。"
            exit 1
        fi
        echo "使用 Python 3.12 创建虚拟环境..."
        python3.12 -m venv "${VENV_DIR}"
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
