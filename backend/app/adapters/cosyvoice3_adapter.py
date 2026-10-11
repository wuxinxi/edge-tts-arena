from backend.app.adapters.worker import WorkerTTSAdapter


class CosyVoice3Adapter(WorkerTTSAdapter):
    environment_name = 'cosyvoice3'
    worker_name = 'cosyvoice3_worker.py'
    runtime_modules = ('torch', 'cosyvoice', 'hyperpyyaml', 'onnxruntime', 'pkg_resources', 'gdown', 'matplotlib')
    source_paths = ('third_party/CosyVoice', 'third_party/CosyVoice/third_party/Matcha-TTS')
    source_files = ('third_party/CosyVoice/cosyvoice/cli/cosyvoice.py', 'third_party/CosyVoice/third_party/Matcha-TTS/matcha/models/components/flow_matching.py')
    worker_timeout = 600

    def synthesize(self, text, voice=None, speed=1.0, prompt=None,
                   ref_audio_path=None, ref_text=None, **kwargs):
        arguments = self.synthesis_arguments(text, voice, speed, prompt, ref_audio_path, ref_text, kwargs.get("options"))
        return self.run_worker(arguments)
