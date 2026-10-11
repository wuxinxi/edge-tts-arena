"""独立推理进程的语言和精度选择。"""

import re
import json
import random


def load_options(value):
    options = json.loads(value)
    if not isinstance(options, dict):
        raise ValueError('模型参数必须是对象。')
    return options


def seed_generation(options):
    import numpy as np
    import torch
    seed = options.get('seed', 42)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    return seed


def chat_refine_prompt(options, legacy_prompt=''):
    if legacy_prompt:
        # 兼容已有专用标记接口，不将自然语言当作标记。
        if not re.fullmatch(r'(\[(?:oral_[0-9]|laugh_[0-2]|break_[0-7])\])+', legacy_prompt):
            raise ValueError('ChatTTS 请使用口语、笑声和停顿控制，或输入合法的专用标记。')
        return legacy_prompt
    return f'[oral_{options.get("oral", 2)}][laugh_{options.get("laugh", 0)}][break_{options.get("break", 4)}]'


def qwen_language(text):
    # 中英混读保持中文主语言；日文假名避免被汉字误判为中文。
    if re.search(r'[\u4e00-\u9fff]', text) and not re.search(r'[\u3040-\u30ff]', text):
        return 'Chinese'
    return 'Auto'


def qwen_precision(device):
    # 本地 Qwen 原权重为 BF16，MPS 使用该精度，不转换成 FP16。
    return 'bfloat16' if device == 'mps' else 'float32' if device == 'cpu' else 'float16'
