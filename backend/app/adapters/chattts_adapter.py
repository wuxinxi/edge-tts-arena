import hashlib
import json

from backend.app.adapters.worker import WorkerTTSAdapter


class ChatTTSAdapter(WorkerTTSAdapter):
    """ChatTTS 真实对话语音推理。"""
    environment_name = 'chattts'
    worker_name = 'chattts_worker.py'
    runtime_modules = ('torch', 'ChatTTS', 'soundfile')

    def synthesize(self, text, voice=None, speed=1.0, prompt=None, **kwargs):
        voice = voice or 'seed_2222'
        seed_text = voice.removeprefix('seed_')
        seed = int(seed_text) if seed_text.isdigit() else int(hashlib.md5(voice.encode()).hexdigest(), 16) % 10000
        arguments = ['--text', text, '--voice_seed', str(seed), '--speed', str(speed)]
        if kwargs.get('options') is not None:
            arguments.extend(['--options', json.dumps(kwargs['options'])])
        if prompt:
            arguments.extend(['--prompt', prompt])
        return self.run_worker(arguments)
