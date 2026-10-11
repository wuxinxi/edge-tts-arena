from backend.app.adapters.worker import WorkerTTSAdapter


class KokoroAdapter(WorkerTTSAdapter):
    environment_name = 'kokoro'
    worker_name = 'kokoro_worker.py'
    runtime_modules = ('torch', 'kokoro', 'soundfile')
    source_paths = ()
    source_files = ()
    worker_timeout = 600

    def synthesize(self, text, voice=None, speed=1.0, prompt=None,
                   ref_audio_path=None, ref_text=None, **kwargs):
        arguments = self.synthesis_arguments(text, voice, speed, prompt, ref_audio_path, ref_text, kwargs.get("options"))
        return self.run_worker(arguments)
