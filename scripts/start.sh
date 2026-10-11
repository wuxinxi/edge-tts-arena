#!/usr/bin/env bash

# ==============================================================================
# edge-tts-arena: 一键启动前后端全套服务脚本
# 强制约定：必须使用项目根目录下的 .venv 虚拟环境
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

VENV_DIR="${PROJECT_ROOT}/.venv"
VENV_PYTHON="${VENV_DIR}/bin/python"

if [ ! -f "${VENV_PYTHON}" ]; then
    echo "❌ 错误: 未找到本地虚拟环境 ${VENV_DIR}，请先运行 ./scripts/setup_env.sh 初始化环境！"
    exit 1
fi

echo "=========================================================="
echo "  🎙️  正在启动 edge-tts-arena 竞技场服务..."
echo "  💻 运行环境: $("${VENV_PYTHON}" --version)"
echo "=========================================================="

# 检查是否传入了 --dev 模式
DEV_MODE=false
for arg in "$@"; do
    if [ "$arg" == "--dev" ]; then
        DEV_MODE=true
        break
    fi
done

if [ "$DEV_MODE" = true ]; then
    echo "⚡ 启动模式: [双进程开发热重载模式 (FastAPI:8081 + Vite:5173)]"

    # 后台启动 FastAPI
    "${VENV_PYTHON}" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8081 --reload &
    BACKEND_PID=$!

    # 启动 Vite 前端
    cd "${PROJECT_ROOT}/frontend"
    pnpm run dev &
    FRONTEND_PID=$!

    echo ""
    echo "🎉 服务启动成功！"
    echo "   🔗 前端界面 (热重载): http://localhost:5173"
    echo "   🔗 后端接口 (FastAPI): http://localhost:8081"
    echo "   📖 交互式 API 文档:    http://localhost:8081/docs"
    echo ""
    echo "按 Ctrl+C 即可退出所有服务..."

    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
    wait
else
    echo "🚀 启动模式: [单端口一体化托管模式 (FastAPI 直出 Vue3 产物)]"
    echo ""
    echo "🎉 服务已启动！请在浏览器中打开:"
    echo "   👉 http://127.0.0.1:8081"
    echo "   📖 API 文档: http://127.0.0.1:8081/docs"
    echo ""
    echo "（提示: 如需前端热重载开发，可运行: ./start.sh --dev）"
    echo "按 Ctrl+C 停止服务..."

    exec "${VENV_PYTHON}" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8081 --reload
fi
