"""为需要声音克隆的模型提供配套的本地默认参考音频与文字。"""

from backend.app.core.config import PROJECT_ROOT

DEFAULT_REFERENCE_AUDIO = PROJECT_ROOT / 'backend/assets/reference/default.wav'
DEFAULT_REFERENCE_TEXT_FILE = DEFAULT_REFERENCE_AUDIO.with_suffix('.txt')


def default_reference():
    if not DEFAULT_REFERENCE_AUDIO.is_file() or not DEFAULT_REFERENCE_TEXT_FILE.is_file():
        raise FileNotFoundError('缺少内置参考音频或对应文字，请恢复 backend/assets/reference 中的文件。')
    text = DEFAULT_REFERENCE_TEXT_FILE.read_text(encoding='utf-8').strip()
    if not text:
        raise ValueError('内置参考音频的对应文字为空。')
    return str(DEFAULT_REFERENCE_AUDIO), text


def resolve_reference(audio_path, text, required=False, require_text=True):
    if audio_path:
        if require_text and (not text or not text.strip()):
            raise ValueError('上传参考音频后，请填写音频所说的原话。')
        return str(audio_path), (text or '').strip()
    # 未上传时，孤立的文字不能替换默认音频配套的原文。
    return default_reference() if required else (None, None)
