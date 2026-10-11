from backend.app.adapters.worker import WorkerTTSAdapter


class MeloTTSAdapter(WorkerTTSAdapter):
    environment_name = 'melotts'
    worker_name = 'melotts_worker.py'
    runtime_modules = ('torch', 'melo', 'soundfile')
    source_paths = ('third_party/MeloTTS',)
    source_files = ('third_party/MeloTTS/melo/api.py',)
    worker_timeout = 600
    cached_files = (('bert-base-multilingual-uncased', 'model.safetensors'),
                    ('bert-base-multilingual-uncased', 'vocab.txt'), ('bert-base-uncased', 'vocab.txt'))

    def synthesize(self, text, voice=None, speed=1.0, prompt=None,
                   ref_audio_path=None, ref_text=None, **kwargs):
        arguments = self.synthesis_arguments(text, voice, speed, prompt, ref_audio_path, ref_text, kwargs.get("options"))
        return self.run_worker(arguments)
