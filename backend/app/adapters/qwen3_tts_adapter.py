from backend.app.adapters.worker import WorkerTTSAdapter


class Qwen3TTSAdapter(WorkerTTSAdapter):
    environment_name = 'qwen3'
    worker_name = 'qwen3_worker.py'
    runtime_modules = ('torch', 'qwen_tts', 'soundfile')
    source_paths = ()
    source_files = ()
    worker_timeout = 600

    def synthesize(self, text, voice=None, speed=1.0, prompt=None,
                   ref_audio_path=None, ref_text=None, **kwargs):
        arguments = self.synthesis_arguments(text, voice, speed, prompt, ref_audio_path, ref_text, kwargs.get("options"))
        arguments.extend(['--model_key', self.metadata.key])
        return self.run_worker(arguments)
