"""保守检测长文本生成明显提前结束的音频，不代替内容或音质评审。"""

import re


def validate_audio_duration(text, duration, speed=1.0):
    characters = len(re.findall(r'[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]', text))
    words = len(re.findall(r'[A-Za-z]+', text))
    if characters + words < 10:
        return
    # 阈值刻意低于正常朗读时长，仅拦截明显提前结束的长句。
    minimum = (characters * 0.04 + words * 0.08) / max(float(speed), 0.1)
    if duration < minimum:
        raise RuntimeError(f'音频明显过短（{duration:.2f} 秒），可能提前停止，未计入成功结果。请重试或更换推理设备。')
