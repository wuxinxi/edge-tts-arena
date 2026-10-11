#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, List, Optional

# 项目根目录与各个子目录绝对路径
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"

# 确保输出目录存在
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

class ModelMetadata(BaseModel):
    key: str
    name: str
    param_size: str
    category: str
    architecture: str
    desc: str
    repo_id: str
    supported_languages: List[str]
    default_voices: List[str]
    supports_prompt: bool = False
    supports_clone: bool = False
    requires_reference_audio: bool = False
    order: int

# 10 款主流模型元数据注册表（从小到大排序）
MODELS_CATALOG: Dict[str, ModelMetadata] = {
    "kokoro-82m": ModelMetadata(
        key="kokoro-82m",
        name="Kokoro-82M",
        param_size="82M",
        category="极致轻量",
        architecture="StyleTTS2 + ISTFTNet",
        desc="轻量预置音色朗读，支持中英发音与音色组合；速度和内存以本机实测为准。",
        repo_id="hexgrad/Kokoro-82M",
        supported_languages=["zh", "en"],
        default_voices=["zf_xiaobei", "zm_yunjian", "af_bella", "am_adam"],
        supports_prompt=False,
        supports_clone=False,
        order=1,
    ),
    "melotts-zh": ModelMetadata(
        key="melotts-zh",
        name="MeloTTS (Chinese)",
        param_size="130M",
        category="实用双语",
        architecture="改良 VITS",
        desc="当前为中文权重，支持中英混读，默认使用本地 CPU 推理。",
        repo_id="myshell-ai/MeloTTS-Chinese",
        supported_languages=["zh", "en"],
        default_voices=["default"],
        supports_prompt=False,
        supports_clone=False,
        order=2,
    ),
    "f5-tts": ModelMetadata(
        key="f5-tts",
        name="F5-TTS",
        param_size="380M",
        category="流匹配前沿",
        architecture="Flow Matching (非自回归)",
        desc="旧版 F5TTS_Base + Vocos，中英文参考音频声音克隆。",
        repo_id="SWivid/F5-TTS",
        supported_languages=["zh", "en"],
        default_voices=["reference"],
        supports_prompt=False,
        supports_clone=True,
        requires_reference_audio=True,
        order=3,
    ),
    "chattts": ModelMetadata(
        key="chattts",
        name="ChatTTS",
        param_size="400M",
        category="拟真会话",
        architecture="自回归会话模型",
        desc="中英文对话语音，可通过专用标记控制口语化、笑声与停顿。",
        repo_id="2noise/ChatTTS",
        supported_languages=["zh", "en"],
        default_voices=["seed_2222", "seed_6666", "seed_8888"],
        supports_prompt=True,
        supports_clone=False,
        order=4,
    ),
    "cosyvoice3": ModelMetadata(
        key="cosyvoice3",
        name="CosyVoice 3.0",
        param_size="500M",
        category="克隆与指令",
        architecture="LLM + 条件流匹配 (CFM)",
        desc="2512 版本，支持参考声音克隆、跨语言迁移与方言、情绪指令。",
        repo_id="FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
        supported_languages=["zh", "en", "ja", "ko", "de", "es", "fr", "it", "ru"],
        default_voices=["reference"],
        supports_prompt=True,
        supports_clone=True,
        requires_reference_audio=True,
        order=5,
    ),
    "qwen3-tts-0.6b": ModelMetadata(
        key="qwen3-tts-0.6b",
        name="Qwen3-TTS 0.6B Base",
        param_size="600M",
        category="千问双轨LM",
        architecture="双轨离散 LM + 12Hz Codec",
        desc="Base 声音克隆版，支持多语言；当前项目采用离线生成。",
        repo_id="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        supported_languages=["zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"],
        default_voices=["reference"],
        supports_prompt=False,
        supports_clone=True,
        requires_reference_audio=True,
        order=6,
    ),
    "parler-tts-mini": ModelMetadata(
        key="parler-tts-mini",
        name="Parler-TTS Mini",
        param_size="880M",
        category="Prompt控制",
        architecture="Prompt-Conditioned 自回归",
        desc="通过英文描述控制声音特征、语速和录音感，也可指定命名说话人；不提供参考声音克隆。",
        repo_id="parler-tts/parler-tts-mini-v1",
        supported_languages=["en"],
        default_voices=["default", "Jon", "Lea", "Gary", "Jenna", "Mike", "Laura"],
        supports_prompt=True,
        supports_clone=False,
        order=7,
    ),
    "fish-speech-1.5": ModelMetadata(
        key="fish-speech-1.5",
        name="Fish-Speech 1.5",
        param_size="1B",
        category="双流自回归",
        architecture="Dual-AR 大模型架构",
        desc="1.5 版本的多语言参考音色合成，使用本地默认参考音频和稳定采样配置。",
        repo_id="fishaudio/fish-speech-1.5",
        supported_languages=["zh", "en", "ja", "de", "fr", "es", "ko", "ar", "ru", "nl", "it", "pl", "pt"],
        default_voices=["default"],
        supports_prompt=False,
        supports_clone=True,
        requires_reference_audio=True,
        order=8,
    ),
    "maskgct": ModelMetadata(
        key="maskgct",
        name="MaskGCT",
        param_size="1B",
        category="掩码扩散",
        architecture="两阶段掩码声学扩散 (Masked Codec)",
        desc="上海 AI Lab / CUHK，非自回归两阶段掩码声学生成",
        repo_id="amphion/MaskGCT",
        supported_languages=["zh", "en"],
        default_voices=["default"],
        supports_prompt=False,
        supports_clone=True,
        requires_reference_audio=True,
        order=9,
    ),
    "qwen3-tts-1.7b": ModelMetadata(
        key="qwen3-tts-1.7b",
        name="Qwen3-TTS 1.7B CustomVoice",
        param_size="1.7B",
        category="音色与情绪",
        architecture="双轨离散 LM + 12Hz Codec",
        desc="CustomVoice 预置音色版，提供 9 种声音和自然语言风格指令。",
        repo_id="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        supported_languages=["zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"],
        default_voices=["vivian", "serena", "uncle_fu", "dylan", "eric", "ryan", "aiden", "ono_anna", "sohee"],
        supports_prompt=True,
        supports_clone=False,
        order=10,
    ),
}
