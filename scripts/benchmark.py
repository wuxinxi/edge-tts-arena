#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
edge-tts-arena: 终端离线批量 Benchmark 跑分工具
- 强制使用项目本地 .venv 虚拟环境
- 针对 10 款模型进行阶梯式跑分横评
- 自动计算并输出标准 Markdown 报表，方便直接复制到公众号文章！
"""

import os
import sys
import argparse
import time
from pathlib import Path

# 虚拟环境自动守护
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _PROJECT_ROOT / ".venv" / "bin" / "python"

if _VENV_PYTHON.exists() and Path(sys.executable).resolve() != _VENV_PYTHON.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON)] + sys.argv)

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.app.core.config import MODELS_CATALOG
from backend.app.core.hardware import get_hardware_info
from backend.app.adapters.factory import AdapterFactory

BENCHMARK_PROMPTS = {
    "english": "Hello, this is a test of speech synthesis. Have a wonderful day.",
    "short": "你好，小爱同学！",
    "bilingual": "今天的代码已经 push 到 GitHub 仓库了，请用 Vite 和 Docker 重新构建我们的端侧 TTS 项目。",
    "prosody": "重阳节的重复练习非常重要，随着大语言模型和流匹配技术的发展，端侧语音合成的自然度已经无限逼近真人。"
}

def run_benchmark(test_type="bilingual", model_keys=None, ref_audio=None, ref_text=None, report_path=None):
    test_text = BENCHMARK_PROMPTS[test_type]
    hw = get_hardware_info()
    keys = model_keys or [key for key, meta in sorted(MODELS_CATALOG.items(), key=lambda item: item[1].order)]
    rows = []
    successes = 0
    for key in keys:
        adapter = AdapterFactory.get_adapter(key)
        print(f"正在评测: {key}", flush=True)
        try:
            if not adapter:
                raise ValueError(f"未知模型: {key}")
            status = adapter.get_status()
            if not status['is_ready']:
                raise RuntimeError(status['unavailable_reason'])
            result = adapter.generate(text=test_text, speed=1.0, speed_mode='output',
                                      options={'refine_text': False} if key == 'chattts' else {},
                                      ref_audio_path=ref_audio, ref_text=ref_text,
                                      evaluation={'mode': 'uniform', 'scope': 'cold_worker_offline',
                                                  'model_speed': 1.0, 'output_speed': 1.0})
            metrics = result['metrics']
            successes += 1
            rows.append(f"| {adapter.metadata.name} | 成功 | {metrics['elapsed_time_sec']}s | {metrics['audio_duration_sec']}s | {metrics['rtf']} | -- | {metrics['memory_peak_mb']} MB |")
        except Exception as exc:
            reason = str(exc).replace('|', '/').replace('\n', ' ')
            name = adapter.metadata.name if adapter else key
            rows.append(f"| {name} | 失败 / 不可用：{reason} | -- | -- | -- | -- | -- |")
            print(f"  {reason}", flush=True)
    table = '\n'.join([
        '| 模型 | 状态 | 离线总耗时 | 音频时长 | RTF | 首包延迟 | 采样内存峰值 |',
        '| :--- | :--- | ---: | ---: | ---: | ---: | ---: |',
        *rows,
    ])
    report = f"# edge-tts-arena 离线基准测试\n\n- 设备: {hw['chip']} ({hw['total_memory_gb']}GB)\n- 文本: {test_text}\n- 成功: {successes} / {len(keys)}\n\n总耗时包含进程启动与模型加载，属于冷启动离线评测；当前未实现流式首包测量。\n内存峰值为服务及推理子进程 RSS 每 50ms 采样估计，不代表显存，可能漏过短时峰值。\n不可用模型不会生成替代音频，也不会参与性能排序。\n\n{table}\n"
    report_file = Path(report_path) if report_path else _PROJECT_ROOT / 'outputs' / 'benchmark_report.md'
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report, encoding='utf-8')
    print(table)
    print(f"报告已保存: {report_file}")
    return successes


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', choices=list(BENCHMARK_PROMPTS), default='bilingual')
    parser.add_argument('--models', help='模型 key，多个用逗号分隔；默认检查全部模型')
    parser.add_argument('--ref-audio', help='声音克隆模型共用的参考音频路径')
    parser.add_argument('--ref-text', help='参考音频对应文字')
    args = parser.parse_args()
    keys = args.models.split(',') if args.models else None
    successes = run_benchmark(args.type, keys, args.ref_audio, args.ref_text)
    sys.exit(0 if successes else 1)
