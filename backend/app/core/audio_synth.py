#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
macOS 系统朗读工具，保留供独立演示使用。
此工具不调用项目中的 TTS 模型，不可用于模型推理或性能横评。
"""

import os
import subprocess
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Tuple

# macOS 原生高质量音色映射
VOICE_MAP = {
    # 中文女声 / 甜美
    "female": "Tingting",
    "sweet_female": "Tingting",
    "vivian": "Tingting",
    "bella": "Tingting",
    "zf_xiaobei": "Tingting",
    "中文女声": "Tingting",
    "粤语女声": "Sinji",
    # 中文男声 / 沉稳
    "male": "Sinji",
    "warm_male": "Sinji",
    "eric": "Sinji",
    "alex": "Sinji",
    "zm_yunjian": "Sinji",
    "中文男声": "Sinji",
    "四川话": "Tingting",
    # 英文
    "af_bella": "Samantha",
    "am_adam": "Alex",
    "default": "Tingting",
}

def generate_real_speech(
    text: str,
    voice: str = "default",
    speed: float = 1.0,
    target_sr: int = 24000
) -> Tuple[np.ndarray, int]:
    """生成真实的自然人声朗读音频。"""
    clean_text = text.strip() or "你好，这是端侧语音合成评测。"

    # 选择音色
    chosen_voice = VOICE_MAP.get(voice, "Tingting")

    # 计算语速 (macOS say 默认速率约为 175-190 words/min)
    rate = int(185 * max(0.5, min(2.0, speed)))

    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp_file:
        tmp_aiff = tmp_file.name

    try:
        # 使用本地 say 命令以极高保真度离线渲染出真实人类声音
        cmd = ["say", "-v", chosen_voice, "-r", str(rate), "-o", tmp_aiff, clean_text]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 读取音频并重采样至 24000 Hz
        data, sr = sf.read(tmp_aiff)
        if data.ndim > 1:
            data = data.mean(axis=1)  # 转单声道

        # 简单重采样至 target_sr
        if sr != target_sr:
            num_samples = int(len(data) * target_sr / sr)
            indices = np.linspace(0, len(data) - 1, num_samples)
            data = np.interp(indices, np.arange(len(data)), data)

        data = data.astype(np.float32)
        # 归一化振幅防爆音
        max_val = np.max(np.abs(data))
        if max_val > 0:
            data = data / max_val * 0.85

        return data, target_sr

    except Exception as e:
        # 如果 say 失败，尝试不指定音色的原生兜底
        try:
            cmd = ["say", "-r", str(rate), "-o", tmp_aiff, clean_text]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            data, sr = sf.read(tmp_aiff)
            return data.astype(np.float32), sr
        except Exception as fallback_error:
            raise RuntimeError('macOS 系统朗读失败，未生成音频。') from fallback_error
    finally:
        if os.path.exists(tmp_aiff):
            try:
                os.remove(tmp_aiff)
            except OSError:
                pass

if __name__ == "__main__":
    audio, sr = generate_real_speech("测试语音：你好，世界！", speed=1.0)
    print("生成真实语音成功，采样率:", sr, "样本数:", len(audio), "时长:", len(audio) / sr, "秒")
