#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
edge-tts-arena: 后端 FastAPI 服务主入口
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import FRONTEND_DIST_DIR
from backend.app.api.routes import router as api_router

app = FastAPI(
    title="edge-tts-arena 能力探索与评测 API",
    description="TTS 能力探索、场景选型参考与离线性能评测",
    version="1.4.1",
)

# 允许跨域（方便前端 Vite 本地开发模式 5173 联调）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载核心 API
app.include_router(api_router, prefix="/api")

# 如果存在打包后的前端静态资源，直接挂载到根路径
if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {
            "name": "edge-tts-arena API",
            "status": "online",
            "docs": "/docs",
            "message": "前端正在通过 Vite 开发服务器运行或待编译构建。"
        }

if __name__ == "__main__":
    import uvicorn
    print("🚀 启动 edge-tts-arena 后端服务: http://127.0.0.1:8081")
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8081, reload=True)
