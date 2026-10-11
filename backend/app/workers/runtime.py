"""独立推理进程的参数、设备选择、音频保存与 JSON 结果。"""

import argparse
import json
import traceback
try:
    from worker_settings import load_options
except ModuleNotFoundError:
    from backend.app.workers.worker_settings import load_options


def parser():
    args = argparse.ArgumentParser()
    args.add_argument('--text', required=True)
    args.add_argument('--output', required=True)
    args.add_argument('--checkpoint_dir', required=True)
    args.add_argument('--device', choices=['auto', 'cpu', 'mps', 'cuda'], default='auto')
    args.add_argument('--speed', type=float, default=1.0)
    args.add_argument('--voice', default='default')
    args.add_argument('--prompt', default='')
    args.add_argument('--ref_audio')
    args.add_argument('--ref_text')
    args.add_argument('--options', type=load_options, default={})
    return args


def device(requested, mps=True):
    import torch
    if requested != 'auto':
        return requested
    if torch.cuda.is_available():
        return 'cuda'
    return 'mps' if mps and torch.backends.mps.is_available() else 'cpu'


def finish(audio, sample_rate, output, selected_device, speed=1.0, effective_options=None):
    import numpy as np
    import soundfile as sf
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not audio.size or not np.isfinite(audio).all():
        raise RuntimeError('模型没有生成有效音频。')
    if speed != 1.0:
        import librosa
        audio = librosa.effects.time_stretch(audio, rate=speed)
    sf.write(output, audio, sample_rate)
    print(json.dumps({'status': 'success', 'output': output, 'sample_rate': sample_rate,
                      'device': selected_device, 'effective_options': effective_options or {}}), flush=True)


def run(main, fast_exit=False):
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'error', 'message': str(error), 'traceback': traceback.format_exc()}), flush=True)
        if fast_exit:
            import os
            import sys
            sys.stderr.flush()
            os._exit(1)
        raise SystemExit(1)
    if fast_exit:
        # 音频与 JSON 已写入；避开 macOS / Torch 2.8 的原生模块退出互斥锁崩溃。
        import os
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
