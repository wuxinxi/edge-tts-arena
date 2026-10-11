import threading
import time
from pathlib import Path
from typing import Optional

import psutil
import soundfile as sf


class GenerationTracker:
    """记录离线请求耗时，并每 50ms 采样服务及推理子进程的 RSS。"""

    def __init__(self, model_key):
        self.model_key = model_key
        self.start_time = 0.0
        self.end_time = 0.0
        self.first_token_time = None
        self.start_mem_mb = 0.0
        self.memory_peak_mb = 0.0
        self.end_mem_mb = 0.0
        self.process = psutil.Process()
        self._stop = threading.Event()

    def _sample_memory(self):
        total = 0
        try:
            processes = [self.process, *self.process.children(recursive=True)]
        except psutil.Error:
            processes = [self.process]
        for process in processes:
            try:
                total += process.memory_info().rss
            except psutil.Error:
                continue
        self.end_mem_mb = total / (1024 * 1024)
        self.memory_peak_mb = max(self.memory_peak_mb, self.end_mem_mb)

    def _monitor(self):
        while not self._stop.wait(0.05):
            self._sample_memory()

    def __enter__(self):
        self.start_time = time.perf_counter()
        self._sample_memory()
        self.start_mem_mb = self.end_mem_mb
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()
        return self

    def mark_first_token(self):
        """仅供真实流式实现收到首段音频时调用。"""
        if self.first_token_time is None:
            self.first_token_time = time.perf_counter()

    def __exit__(self, exc_type, exc_value, traceback):
        self.end_time = time.perf_counter()
        self._stop.set()
        self._thread.join()
        self._sample_memory()

    def compute_metrics(self, audio_path: Optional[Path] = None, sample_rate=24000, audio_length_samples=0):
        elapsed = max(0.001, self.end_time - self.start_time)
        duration = audio_length_samples / sample_rate if sample_rate > 0 else 0.0
        if audio_path and audio_path.is_file():
            duration = sf.info(str(audio_path)).duration
        ttfb = (self.first_token_time - self.start_time) * 1000 if self.first_token_time is not None else None
        return {
            'model_key': self.model_key,
            'elapsed_time_sec': round(elapsed, 3),
            'audio_duration_sec': round(duration, 2),
            'rtf': round(elapsed / duration, 3) if duration > 0 else None,
            'ttfb_ms': round(ttfb, 1) if ttfb is not None else None,
            'memory_used_mb': round(self.end_mem_mb, 1),
            'memory_diff_mb': round(max(0.0, self.memory_peak_mb - self.start_mem_mb), 1),
            'memory_peak_mb': round(self.memory_peak_mb, 1),
            'memory_scope': 'process_tree_rss_sampled_50ms',
            'timing_scope': 'offline_request_including_worker_startup_and_model_load',
        }
