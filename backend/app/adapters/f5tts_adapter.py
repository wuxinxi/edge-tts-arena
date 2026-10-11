from backend.app.adapters.worker import WorkerTTSAdapter


class F5TTSAdapter(WorkerTTSAdapter):
    """F5-TTS 真实声音克隆推理。"""
    environment_name = 'f5tts'
    worker_name = 'f5tts_worker.py'
    runtime_modules = ('torch', 'f5_tts', 'soundfile')

    def synthesize(self, text, voice=None, speed=1.0, prompt=None,
                   ref_audio_path=None, ref_text=None, **kwargs):
        arguments = self.synthesis_arguments(text, speed=speed,
                                            ref_audio_path=ref_audio_path, ref_text=ref_text, options=kwargs.get("options"))
        return self.run_worker(arguments)
