#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, List, Optional
from backend.app.core.config import MODELS_CATALOG
from backend.app.core.model_profiles import profile_for, local_voices
from backend.app.adapters.base import BaseTTSAdapter
from backend.app.adapters.kokoro_adapter import KokoroAdapter
from backend.app.adapters.melotts_adapter import MeloTTSAdapter
from backend.app.adapters.f5tts_adapter import F5TTSAdapter
from backend.app.adapters.chattts_adapter import ChatTTSAdapter
from backend.app.adapters.cosyvoice3_adapter import CosyVoice3Adapter
from backend.app.adapters.qwen3_tts_adapter import Qwen3TTSAdapter
from backend.app.adapters.parler_adapter import ParlerAdapter
from backend.app.adapters.fish_speech_adapter import FishSpeechAdapter, MaskGCTAdapter

class AdapterFactory:
    """TTS 适配器工厂：按需实例化并提供统一接口。"""

    _instances: Dict[str, BaseTTSAdapter] = {}

    @classmethod
    def get_adapter(cls, model_key: str) -> Optional[BaseTTSAdapter]:
        if model_key in cls._instances:
            return cls._instances[model_key]

        if model_key not in MODELS_CATALOG:
            return None

        metadata = MODELS_CATALOG[model_key]

        if model_key == "kokoro-82m":
            adapter = KokoroAdapter(metadata)
        elif model_key == "melotts-zh":
            adapter = MeloTTSAdapter(metadata)
        elif model_key == "f5-tts":
            adapter = F5TTSAdapter(metadata)
        elif model_key == "chattts":
            adapter = ChatTTSAdapter(metadata)
        elif model_key == "cosyvoice3":
            adapter = CosyVoice3Adapter(metadata)
        elif "qwen3-tts" in model_key:
            adapter = Qwen3TTSAdapter(metadata)
        elif model_key == "parler-tts-mini":
            adapter = ParlerAdapter(metadata)
        elif model_key == "fish-speech-1.5":
            adapter = FishSpeechAdapter(metadata)
        elif model_key == "maskgct":
            adapter = MaskGCTAdapter(metadata)
        else:
            return None

        cls._instances[model_key] = adapter
        return adapter

    @classmethod
    def get_all_models_status(cls) -> List[dict]:
        """按参数量从小到大返回所有模型状态。"""
        results = []
        for key, meta in sorted(MODELS_CATALOG.items(), key=lambda x: x[1].order):
            adapter = cls.get_adapter(key)
            info = meta.model_dump()
            info['default_voices'] = local_voices(meta)
            info['profile'] = profile_for(meta)
            info.update(adapter.get_status())
            results.append(info)
        return results
