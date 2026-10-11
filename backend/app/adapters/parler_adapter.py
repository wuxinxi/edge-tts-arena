from backend.app.adapters.worker import WorkerTTSAdapter


class ParlerAdapter(WorkerTTSAdapter):
    environment_name = 'parler'
    worker_name = 'parler_worker.py'
    runtime_modules = ('torch', 'parler_tts', 'soundfile')
    source_paths = ()
    source_files = ()
    worker_timeout = 600

    def synthesize(self, text, voice=None, speed=1.0, prompt=None,
                   ref_audio_path=None, ref_text=None, **kwargs):
        arguments = self.synthesis_arguments(text, voice, speed, prompt, ref_audio_path, ref_text, kwargs.get("options"))
        return self.run_worker(arguments)
