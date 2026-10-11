"""在模型独立环境中运行真实推理，统一处理启动、超时与错误。"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import soundfile as sf

from backend.app.adapters.base import BaseTTSAdapter
from backend.app.core.config import PROJECT_ROOT
from backend.app.core.reference import resolve_reference


class WorkerTTSAdapter(BaseTTSAdapter):
    implementation_available = True
    environment_name = ''
    worker_name = ''
    runtime_modules = ()
    source_paths = ()
    source_files = ()
    auxiliary_files = ()
    cached_files = ()
    worker_timeout = 300

    def worker_environment(self):
        environment = os.environ.copy()
        environment.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
        environment.setdefault('TOKENIZERS_PARALLELISM', 'false')
        environment['HF_HUB_OFFLINE'] = '1'
        environment['TRANSFORMERS_OFFLINE'] = '1'
        environment.setdefault('HF_HUB_DISABLE_XET', '1')
        paths = [str(PROJECT_ROOT / path) for path in self.source_paths]
        if environment.get('PYTHONPATH'):
            paths.append(environment['PYTHONPATH'])
        if paths:
            environment['PYTHONPATH'] = os.pathsep.join(paths)
        return environment

    def runtime_python(self) -> Path:
        executable = 'Scripts/python.exe' if os.name == 'nt' else 'bin/python'
        return PROJECT_ROOT / '.venvs' / self.environment_name / executable

    def get_status(self):
        status = super().get_status()
        if status['is_ready']:
            worker = 'backend/app/workers/' + self.worker_name
            missing_source = [path for path in (*self.source_files, worker) if not (PROJECT_ROOT / path).is_file()]
            if missing_source:
                status.update(is_ready=False, unavailable_reason='缺少官方推理源码: ' + ', '.join(missing_source))
        if status['is_ready']:
            missing_auxiliary = [pattern for pattern in self.auxiliary_files
                                 if not any(path.is_file() and path.stat().st_size > 0
                                            for path in PROJECT_ROOT.glob(pattern))]
            if missing_auxiliary:
                status.update(is_ready=False, unavailable_reason='缺少辅助模型文件: ' + ', '.join(missing_auxiliary))
        if status['is_ready'] and not self.runtime_python().is_file():
            status.update(is_ready=False, unavailable_reason=f'缺少模型运行环境: .venvs/{self.environment_name}')
        elif status['is_ready']:
            probe = 'import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in sys.argv[1:]) else 1)'
            try:
                result = subprocess.run([str(self.runtime_python()), '-c', probe, *self.runtime_modules],
                                        capture_output=True, text=True, timeout=5, env=self.worker_environment())
                if result.returncode:
                    status.update(is_ready=False, unavailable_reason=f'模型环境缺少必要依赖: {", ".join(self.runtime_modules)}')
                elif self.cached_files:
                    check_cache = ('import json,sys; from huggingface_hub import try_to_load_from_cache; '
                                   'from pathlib import Path; '
                                   'missing=[repo+"/"+name for repo,name in json.loads(sys.argv[1]) '
                                   'if not isinstance(try_to_load_from_cache(repo,name),str)]; '
                                   'print(json.dumps(missing)); sys.exit(bool(missing))')
                    cached = subprocess.run([str(self.runtime_python()), '-c', check_cache, json.dumps(self.cached_files)],
                                            capture_output=True, text=True, timeout=5, env=self.worker_environment())
                    if cached.returncode:
                        status.update(is_ready=False, unavailable_reason='缺少本地辅助模型缓存，请运行 scripts/setup_models.py --assets。')
            except (OSError, subprocess.TimeoutExpired):
                status.update(is_ready=False, unavailable_reason=f'模型环境无法运行: .venvs/{self.environment_name}')
        return status

    def load(self, device: Optional[str] = None):
        self.python_bin = str(self.runtime_python())
        self.worker_script = str(PROJECT_ROOT / 'backend' / 'app' / 'workers' / self.worker_name)
        self.checkpoint_dir = str(self.model_dir)
        if not Path(self.python_bin).is_file():
            raise FileNotFoundError(f'缺少模型运行环境: {self.python_bin}')
        self.device = device or 'auto'
        self.is_loaded = True

    def run_worker(self, arguments: list[str]):
        with tempfile.TemporaryDirectory(prefix=f'{self.metadata.key}_') as directory:
            output = Path(directory) / 'output.wav'
            command = [self.python_bin, self.worker_script, *arguments,
                       '--output', str(output), '--checkpoint_dir', self.checkpoint_dir,
                       '--device', self.device]
            environment = self.worker_environment()
            try:
                result = subprocess.run(command, capture_output=True, text=True, check=False,
                                        cwd=str(PROJECT_ROOT), env=environment, timeout=self.worker_timeout)
            except subprocess.TimeoutExpired as exc:
                self.last_worker_error = f'推理超时（{self.worker_timeout} 秒）'
                raise TimeoutError(f'{self.metadata.name} 推理超过 {self.worker_timeout} 秒。') from exc
            self.last_worker_returncode = result.returncode
            response = None
            for line in reversed(result.stdout.splitlines()):
                try:
                    candidate = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(candidate, dict) and 'status' in candidate:
                    response = candidate
                    break
            if result.returncode != 0 or not response or response.get('status') != 'success':
                message = response.get('message') if response else None
                detail = message or result.stderr[-3000:] or result.stdout[-3000:] or '推理进程没有返回结果'
                if result.returncode < 0:
                    detail = f'推理进程被信号 {-result.returncode} 终止。' + detail
                self.last_worker_error = f'退出码: {result.returncode}\n' + (response.get('traceback', '') if response else result.stderr)
                raise RuntimeError(f'{self.metadata.name}: {detail}')
            if not output.is_file():
                raise RuntimeError(f'{self.metadata.name} 没有生成音频文件。')
            self.last_device = response.get('device', 'unknown')
            self.last_effective_options = response.get('effective_options', {})
            return sf.read(output, dtype='float32')

    def synthesis_arguments(self, text, voice=None, speed=1.0, prompt=None,
                            ref_audio_path=None, ref_text=None, options=None):
        if self.metadata.supports_clone:
            ref_audio_path, ref_text = resolve_reference(
                ref_audio_path, ref_text, required=self.metadata.requires_reference_audio,
                require_text=not (options or {}).get('x_vector_only', False)
                             and (options or {}).get('mode') != 'cross_lingual')
        arguments = ['--text', text, '--speed', str(speed)]
        if options is not None:
            arguments.extend(['--options', json.dumps(options, ensure_ascii=False)])
        if voice:
            arguments.extend(['--voice', voice])
        if prompt:
            arguments.extend(['--prompt', prompt])
        if ref_audio_path:
            arguments.extend(['--ref_audio', str(ref_audio_path)])
        if ref_text:
            arguments.extend(['--ref_text', ref_text])
        return arguments
