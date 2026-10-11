from backend.app.adapters.worker import WorkerTTSAdapter


class FishSpeechAdapter(WorkerTTSAdapter):
    environment_name = 'fish-speech'
    worker_name = 'fish_speech_worker.py'
    runtime_modules = ('torch', 'fish_speech', 'hydra', 'soundfile', 'click', 'natsort', 'rich')
    source_paths = ('third_party/fish-speech',)
    source_files = ('third_party/fish-speech/fish_speech/models/text2semantic/inference.py',)
    worker_timeout = 600

    def synthesize(self, text, voice=None, speed=1.0, prompt=None,
                   ref_audio_path=None, ref_text=None, **kwargs):
        arguments = self.synthesis_arguments(text, voice, speed, prompt, ref_audio_path, ref_text, kwargs.get("options"))
        return self.run_worker(arguments)


class MaskGCTAdapter(WorkerTTSAdapter):
    environment_name = 'maskgct'
    worker_name = 'maskgct_worker.py'
    runtime_modules = ('torch', 'transformers', 'phonemizer', 'soundfile', 'accelerate', 'safetensors', 'espeakng_loader')
    source_paths = ('third_party/Amphion',)
    source_files = ('third_party/Amphion/models/tts/maskgct/maskgct_utils.py',)
    worker_timeout = 600
    auxiliary_files = ('checkpoints/support/w2v-bert-2.0/model.safetensors',
                       'checkpoints/support/w2v-bert-2.0/config.json',
                       'checkpoints/support/w2v-bert-2.0/preprocessor_config.json',
                       'third_party/Amphion/models/tts/maskgct/g2p/sources/g2p_chinese_model/poly_bert_model.onnx')

    def synthesize(self, text, voice=None, speed=1.0, prompt=None,
                   ref_audio_path=None, ref_text=None, **kwargs):
        arguments = self.synthesis_arguments(text, voice, speed, prompt, ref_audio_path, ref_text, kwargs.get("options"))
        return self.run_worker(arguments)
