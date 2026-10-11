#!/usr/bin/env bash

# 根目录便捷启动入口
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/scripts/start.sh" "$@"
