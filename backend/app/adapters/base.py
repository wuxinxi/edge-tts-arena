#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import uuid
import threading
import numpy as np
import soundfile as sf

from backend.app.core.config import ModelMetadata, CHECKPOINTS_DIR, OUTPUTS_DIR
from backend.app.core.metrics import GenerationTracker
from backend.app.core.model_files import missing_model_files
from backend.app.core.inference_lock import exclusive_inference
from backend.app.core.audio_validation import validate_audio_duration
from backend.app.core.model_profiles import resolve_options, profile_for, local_voices
from backend.app.core.run_records import save_run, reference_record
from backend.app.core.audio_effects import stretch_audio

class BaseTTSAdapter(ABC):
    """所有端侧 TTS 模型的统一抽象适配器。"""

    implementation_available = False
    # 端侧设备串行推理，避免同时加载多个模型耗尽统一内存。
    _generation_lock = threading.Lock()

    def __init__(self, metadata: ModelMetadata):
        self.metadata = metadata
        self.model_dir = CHECKPOINTS_DIR / metadata.key
        self.is_loaded = False
        self.device = "cpu"

    def is_available(self) -> bool:
        """检查模型权重是否已下载就绪。"""
        return not missing_model_files(self.metadata.key, self.model_dir)

    def get_status(self) -> Dict[str, Any]:
        missing = missing_model_files(self.metadata.key, self.model_dir)
        reason = None
        if not self.implementation_available:
            reason = '该模型尚未接入真实推理，不能生成音频或参加跑分。'
        elif missing:
            reason = '缺少必要文件: ' + ', '.join(missing)
        return {
            'is_downloaded': not missing,
            'implementation_available': self.implementation_available,
            'is_ready': reason is None,
            'unavailable_reason': reason,
            'missing_files': missing,
        }

    @abstractmethod
    def load(self, device: Optional[str] = None):
        """将模型加载至指定设备 (mps / cpu)。"""
        pass

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        prompt: Optional[str] = None,
        **kwargs
    ) -> Tuple[np.ndarray, int]:
        """执行实际语音合成推理，返回 (audio_array_float32, sample_rate)。"""
        pass

    def generate(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """统一对外调用接口：包含性能计时、保存音频文件、计算指标。"""
        if not text or not text.strip():
            raise ValueError('合成文本不能为空。')
        if not self.implementation_available:
            raise NotImplementedError(f'{self.metadata.name} 尚未接入真实推理。')
        if not self.is_available():
            raise FileNotFoundError('缺少必要模型文件: ' + ', '.join(missing_model_files(self.metadata.key, self.model_dir)))
        options, chosen = resolve_options(self.metadata, kwargs.pop('options', None), kwargs.pop('preset', 'default'))
        speed_mode = kwargs.pop('speed_mode', 'model')
        if speed_mode not in ('model', 'output'):
            raise ValueError('速度模式无效。')
        if not np.isfinite(speed) or not 0.5 <= speed <= 2:
            raise ValueError('速度必须在 0.5 到 2 之间。')
        if voice is None and self.metadata.key == 'kokoro-82m':
            import re
            if re.search('[A-Za-z]', text) and not re.search('[\u4e00-\u9fff]', text) and 'af_heart' in local_voices(self.metadata):
                voice = 'af_heart'
        voice = voice or (self.metadata.default_voices[0] if self.metadata.default_voices else "default")
        if voice not in local_voices(self.metadata):
            raise ValueError('该模型没有指定的本地音色。')
        if options.get('blend_voice') and options['blend_voice'][0] != voice[0]:
            raise ValueError('混合音色必须属于同一语言。')
        prompt = chosen['prompt'] if prompt is None else prompt.strip()
        if self.metadata.key == 'chattts' and prompt:
            from backend.app.workers.worker_settings import chat_refine_prompt
            chat_refine_prompt(options, prompt)
        if prompt and not self.metadata.supports_prompt:
            raise ValueError('当前模型版本不支持风格指令。')
        if self.metadata.key == 'cosyvoice3' and options['mode'] != 'auto' and prompt:
            raise ValueError('风格指令请使用自动模式；参考克隆和跨语言模式不接受指令。')
        reference = reference_record(self.metadata, kwargs.get('ref_audio_path'), kwargs.get('ref_text'))
        profile = profile_for(self.metadata)
        settings = dict(preset=chosen['key'], preset_label=chosen['label'], options=options,
                        prompt=prompt or '', speed=speed, speed_mode=speed_mode,
                        speed_kind='postprocess' if speed_mode == 'output' else profile['speed_kind'],
                        worker_speed=1.0 if speed_mode == 'output' else speed,
                        reference=reference, version=profile['version'], repo_id=self.metadata.repo_id)
        evaluation = kwargs.pop('evaluation', None)
        tracker = GenerationTracker(model_key=self.metadata.key)

        with self._generation_lock, exclusive_inference(OUTPUTS_DIR / '.inference.lock'):
            if not self.is_loaded:
                self.load()
            with tracker:
                audio_array, sample_rate = self.synthesize(
                    text=text,
                    voice=voice,
                    speed=settings['worker_speed'],
                    prompt=prompt,
                    options=options,
                    tracker=tracker,
                    **kwargs
                )
                if speed_mode == 'output' and speed != 1.0:
                    audio_array = stretch_audio(audio_array, speed)
                actual_device = getattr(self, 'last_device', self.device)
                settings['effective_options'] = getattr(self, 'last_effective_options', {})

        # 确保音频数组格式正确
        if not isinstance(audio_array, np.ndarray):
            audio_array = np.array(audio_array, dtype=np.float32)
        if audio_array.dtype != np.float32:
            audio_array = audio_array.astype(np.float32)

        if sample_rate <= 0 or audio_array.size == 0 or not np.isfinite(audio_array).all():
            raise RuntimeError('模型返回了无效的音频。')
        validate_audio_duration(text, len(audio_array) / sample_rate, speed)

        # 写入 outputs 目录
        file_id = f"{self.metadata.key}_{uuid.uuid4().hex[:8]}.wav"
        output_file = OUTPUTS_DIR / file_id
        sf.write(str(output_file), audio_array, sample_rate)

        # 计算指标
        metrics = tracker.compute_metrics(
            audio_path=output_file,
            sample_rate=sample_rate,
            audio_length_samples=len(audio_array)
        )

        result = {
            "success": True,
            "model_key": self.metadata.key,
            "model_name": self.metadata.name,
            "param_size": self.metadata.param_size,
            "audio_file": file_id,
            "audio_url": f"/api/audio/{file_id}",
            "sample_rate": sample_rate,
            "text": text,
            "voice": voice,
            "metrics": metrics,
            "inference_mode": "offline",
            "device": actual_device,
            "settings": settings,
            "evaluation": evaluation,
        }
        save_run(result, OUTPUTS_DIR)
        return result
