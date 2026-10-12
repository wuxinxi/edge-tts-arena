#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import platform
import subprocess
import psutil
from typing import Dict, Any

def get_apple_chip_name() -> str:
    """获取 macOS 芯片具体型号 (如 Apple M4, Apple M1 Pro 等)。"""
    if platform.system() != "Darwin":
        return platform.processor() or "Unknown CPU"

    try:
        cmd = ["sysctl", "-n", "machdep.cpu.brand_string"]
        out = subprocess.check_output(cmd, text=True).strip()
        if out:
            return out
    except Exception:
        pass

    # Fallback to system_profiler
    try:
        cmd = ["system_profiler", "SPHardwareDataType"]
        out = subprocess.check_output(cmd, text=True)
        for line in out.splitlines():
            if "Chip:" in line or "Processor Name:" in line:
                return line.split(":", 1)[1].strip()
    except Exception:
        pass

    return "Apple Silicon"

def check_mps_status() -> Dict[str, Any]:
    """检查 PyTorch MPS (Metal) 加速状态。"""
    try:
        import torch
        has_mps = torch.backends.mps.is_available()
        is_built = torch.backends.mps.is_built()
        device_name = "mps" if has_mps else "cpu"
        return {
            "torch_version": torch.__version__,
            "mps_available": has_mps,
            "mps_built": is_built,
            "active_device": device_name,
        }
    except ImportError:
        return {
            "torch_version": "Not Installed",
            "mps_available": False,
            "mps_built": False,
            "active_device": "cpu",
        }

def get_hardware_info() -> Dict[str, Any]:
    """汇总当前系统硬件信息。"""
    vm = psutil.virtual_memory()
    total_gb = round(vm.total / (1024 ** 3), 2)
    available_gb = round(vm.available / (1024 ** 3), 2)
    # psutil.used is platform-specific (active + wired on macOS), while
    # psutil.percent uses total - available. Keep the number and bar consistent.
    used_bytes = vm.total - vm.available
    used_gb = round(used_bytes / (1024 ** 3), 2)
    percent = round(used_bytes / vm.total * 100, 1) if vm.total else 0.0

    chip_name = get_apple_chip_name()
    mps_info = check_mps_status()

    return {
        "os": f"{platform.system()} {platform.release()}",
        "chip": chip_name,
        "cpu_count": psutil.cpu_count(logical=False),
        "cpu_logical_count": psutil.cpu_count(logical=True),
        "total_memory_gb": total_gb,
        "available_memory_gb": available_gb,
        "used_memory_gb": used_gb,
        "memory_percent": percent,
        "mps": mps_info,
    }

if __name__ == "__main__":
    import json
    print(json.dumps(get_hardware_info(), indent=2, ensure_ascii=False))
