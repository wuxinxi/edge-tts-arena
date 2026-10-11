"""当前本地权重的能力探索控制；同一份定义用于界面、校验和运行记录。"""

import math
from copy import deepcopy

from backend.app.core.config import CHECKPOINTS_DIR
from backend.app.workers.worker_settings import PARLER_DEFAULT_DESCRIPTION


def number(key, label, default, minimum, maximum, step=1, help=''):
    return dict(key=key, label=label, type='number', default=default,
                min=minimum, max=maximum, step=step, help=help)


def select(key, label, default, choices, help=''):
    return dict(key=key, label=label, type='select', default=default,
                choices=[dict(value=value, label=title) for value, title in choices], help=help)


def toggle(key, label, default=False, help=''):
    return dict(key=key, label=label, type='boolean', default=default, help=help)


def preset(key, label, options=None, prompt=''):
    return dict(key=key, label=label, options=options or {}, prompt=prompt)


SEED = number('seed', '生成随机种子', 42, 0, 2147483647, help='固定种子有助于复现；不同设备或环境仍可能产生差异。')
LANGUAGES = [('Auto', '自动识别'), ('Chinese', '中文'), ('English', '英语'),
             ('Japanese', '日语'), ('Korean', '韩语'), ('German', '德语'),
             ('French', '法语'), ('Russian', '俄语'), ('Portuguese', '葡萄牙语'),
             ('Spanish', '西班牙语'), ('Italian', '意大利语')]
LANGUAGE = select('language', '目标语言', 'Auto', LANGUAGES,
                  '自动模式保留当前中文／中英混读判断；其他语言建议明确选择。')

PROFILES = {
    'kokoro-82m': dict(version='Kokoro v1.0', purpose='轻量朗读与音色组合', speed_kind='native',
        prompt_kind='none', tips='仅列出已有音色；新增语言需先验证本地发音资源。混合音色需属于同一语言。',
        controls=[number('blend_ratio', '第二音色比例', 0.5, 0, 1, 0.05)],
        presets=[preset('default', '自然朗读')]),
    'melotts-zh': dict(version='MeloTTS Chinese', purpose='中文与中英混读', speed_kind='native',
        prompt_kind='none', tips='当前权重为中文版本，支持中英混读。音色保持原有说话人。',
        controls=[SEED, number('noise_scale', '声音变化', 0.6, 0.1, 1, 0.05),
                  number('noise_scale_w', '节奏变化', 0.8, 0.1, 1, 0.05)],
        presets=[preset('default', '自然朗读'), preset('steady', '平稳节奏', {'noise_scale': 0.4, 'noise_scale_w': 0.5})]),
    'f5-tts': dict(version='F5TTS_Base · 1200000 · Vocos', purpose='中英文声音克隆', speed_kind='native',
        prompt_kind='none', tips='参考音频建议少于 12 秒，原文准确，并保留自然句尾。质量档位需要结合试听选择。',
        controls=[SEED, select('nfe_step', '生成步数', 32, [(16, '16 步'), (32, '32 步'), (48, '48 步')]),
                  number('cfg_strength', '参考引导强度', 2.0, 1, 3, 0.1)],
        presets=[preset('default', '均衡 · 32 步'), preset('fast', '快速 · 16 步', {'nfe_step': 16}),
                 preset('fine', '精细 · 48 步', {'nfe_step': 48})]),
    'chattts': dict(version='ChatTTS · 0.2.5', purpose='有停顿和笑声的对话', speed_kind='discrete',
        prompt_kind='tokens', tips='口语化润色可能改写台词；逐字朗读可关闭润色。音色与生成随机种子分别保存。',
        controls=[SEED, toggle('refine_text', '启用对话润色', True),
                  number('oral', '口语程度', 2, 0, 9), number('laugh', '笑声程度', 0, 0, 2),
                  number('break', '停顿程度', 4, 0, 7), number('temperature', '表达随机性', 0.3, 0.1, 0.7, 0.05)],
        presets=[preset('default', '自然对话'), preset('verbatim', '逐字朗读', {'refine_text': False}),
                 preset('lively', '活泼对话', {'oral': 4, 'laugh': 1, 'break': 3}),
                 preset('calm', '舒缓对话', {'oral': 1, 'laugh': 0, 'break': 6})]),
    'cosyvoice3': dict(version='Fun-CosyVoice3-0.5B-2512', purpose='声音克隆、方言与风格指令', speed_kind='native',
        prompt_kind='instruction', tips='默认参考音频可直接使用；方言和情绪通过指令控制，效果需要试听。',
        controls=[SEED, select('mode', '生成模式', 'auto', [('auto', '自动（有指令时使用风格控制）'),
                    ('zero_shot', '参考声音克隆'), ('cross_lingual', '跨语言音色迁移')])],
        presets=[preset('default', '保留参考风格'), preset('warm', '温暖讲述', prompt='用温暖、自然、亲切的语气说。'),
                 preset('news', '新闻播报', prompt='用清晰、平稳的新闻播报语气说。'),
                 preset('sichuan', '四川话', prompt='用四川话说。'), preset('cantonese', '粤语', prompt='用粤语说。')]),
    'qwen3-tts-0.6b': dict(version='Qwen3-TTS-12Hz-0.6B-Base', purpose='多语言声音克隆', speed_kind='postprocess',
        prompt_kind='none', tips='当前是 Base 克隆版。仅音色模式不需要参考原文，但可能降低克隆质量。',
        controls=[SEED, LANGUAGE, toggle('x_vector_only', '仅提取音色（无需参考原文）')],
        presets=[preset('default', '完整声音克隆'), preset('timbre', '仅提取音色', {'x_vector_only': True})]),
    'qwen3-tts-1.7b': dict(version='Qwen3-TTS-12Hz-1.7B-CustomVoice', purpose='预置音色与情绪表达', speed_kind='postprocess',
        prompt_kind='instruction', exploration_preset='news',
        tips='当前是 CustomVoice，提供 9 种音色。建议从清晰播报开始：Vivian 中文通知样本中，该指令经试听消除了开头额外“哦”声，其他文本仍需验证。自然表达保留无指令输出；统一评测继续使用该原始配置。',
        controls=[SEED, LANGUAGE],
        presets=[preset('default', '自然表达'), preset('warm', '温暖讲述', prompt='用温暖、亲切、自然的语气说。'),
                 preset('energetic', '精神饱满', prompt='用精神饱满、有活力、清晰自然的语气说。'),
                 preset('story', '故事讲述', prompt='用富有感情、节奏自然的故事讲述语气说。'),
                 preset('news', '清晰播报 · 推荐', prompt='用清晰、沉稳、专业的新闻播报语气说。')]),
    'fish-speech-1.5': dict(version='Fish-Speech 1.5 · code v1.5.1', purpose='参考音色与多语言生成', speed_kind='postprocess',
        prompt_kind='none', tips='未上传时使用已验证的默认参考音频。上传素材可尝试清晰的 10–30 秒单人语音。',
        controls=[SEED, number('temperature', '表达随机性', 0.7, 0.3, 0.9, 0.05),
                  number('top_p', '采样范围', 0.7, 0.5, 0.95, 0.05),
                  number('repetition_penalty', '重复抑制', 1.2, 1, 1.5, 0.05),
                  number('chunk_length', '文本分段长度', 100, 50, 200, 10)],
        presets=[preset('default', '当前稳定配置'), preset('expressive', '增加表达变化', {'temperature': 0.8, 'top_p': 0.8})]),
    'maskgct': dict(version='MaskGCT · 两阶段本地权重', purpose='声音克隆与目标时长控制', speed_kind='postprocess',
        prompt_kind='none', tips='当前接入中文与英文。指定时长仅控制目标语音；过短时长可能影响完整度。',
        controls=[SEED, select('language', '目标语言', 'auto', [('auto', '自动'), ('zh', '中文'), ('en', '英语')]),
                  number('target_duration', '目标时长（秒，0 为自动）', 0, 0, 30, 0.5),
                  select('n_timesteps', '语义生成步数', 25, [(16, '16 步'), (25, '25 步'), (50, '50 步')]),
                  number('cfg', '参考引导强度', 2.5, 1, 4, 0.1)],
        presets=[preset('default', '均衡 · 25 步'), preset('fast', '快速 · 16 步', {'n_timesteps': 16}),
                 preset('fine', '精细 · 50 步', {'n_timesteps': 50})]),
    'parler-tts-mini': dict(version='Parler-TTS Mini v1', purpose='英文声音描述与命名说话人', speed_kind='postprocess',
        prompt_kind='description', tips='仅支持英文正文；用英文描述音高、语速与录音感。当前提供官方示例中的 6 个命名说话人；选定后会在描述前附上名字。不是参考声音克隆，音色一致性和描述效果仍需试听。',
        controls=[SEED],
        presets=[preset('default', '清晰英文', prompt=PARLER_DEFAULT_DESCRIPTION),
                 preset('warm', '温暖讲述', prompt='A speaker delivers warm, gentle and expressive speech at a moderate speed, with very clear audio and almost no background noise.'),
                 preset('news', '平稳播报', prompt='A speaker delivers clear, steady and measured speech at a moderate speed and pitch, with very clear audio and almost no background noise.'),
                 preset('lively', '活泼表达', prompt='A speaker delivers lively, expressive and animated speech at a slightly fast pace, with very clear audio and almost no background noise.')]),
}

# 场景标签是根据官方能力与当前接入路径提出的探索方向，不代表场景质量已实测。
EXPLORATION = {
    'kokoro-82m': dict(scenarios=['文章朗读', '通知播报', '轻量本地应用'],
        listen_for='发音与断句、不同音色的差别，以及在你的设备上的耗时和内存。',
        source_url='https://github.com/hexgrad/kokoro'),
    'melotts-zh': dict(scenarios=['中文朗读', '中英混读', '产品语音提示'],
        listen_for='英文词与中文之间的衔接、数字读法，以及语速变化后的清晰度。',
        source_url='https://github.com/myshell-ai/MeloTTS'),
    'f5-tts': dict(scenarios=['参考音色复现', '同音色新文本', '中英文声音克隆'],
        listen_for='音色相似度、参考原文准确性对结果的影响，以及不同步数下的完整度。',
        source_url='https://github.com/SWivid/F5-TTS'),
    'chattts': dict(scenarios=['聊天助手', '口语对话', '笑声与停顿实验'],
        listen_for='口语节奏、笑声与停顿是否自然；启用润色后是否改写、漏读或增加内容。',
        source_url='https://github.com/2noise/ChatTTS'),
    'cosyvoice3': dict(scenarios=['参考声音克隆', '方言表达', '风格指令实验'],
        listen_for='参考音色保留程度、指令是否生效，以及方言表达和文字内容是否准确。',
        source_url='https://github.com/QwenAudio/CosyVoice'),
    'qwen3-tts-0.6b': dict(scenarios=['声音克隆', '多语言音色迁移', '完整克隆与仅音色对比'],
        listen_for='两种克隆模式的音色相似度与内容完整度；多语言效果需逐语种验证。',
        source_url='https://github.com/QwenLM/Qwen3-TTS'),
    'qwen3-tts-1.7b': dict(scenarios=['预置音色朗读', '故事表达', '情绪指令实验'],
        listen_for='同一音色对不同指令的响应、情绪与内容的匹配，以及开头和结尾的发音。',
        source_url='https://github.com/QwenLM/Qwen3-TTS'),
    'fish-speech-1.5': dict(scenarios=['参考音色生成', '多语言文本实验', '采样参数对比'],
        listen_for='参考声音相似度、内容完整度，以及随机性变化带来的重复或异常声音。',
        source_url='https://huggingface.co/fishaudio/fish-speech-1.5'),
    'maskgct': dict(scenarios=['声音克隆', '目标时长实验', '不同生成步数对比'],
        listen_for='指定时长下是否漏字或挤字、音色相似度，以及步数对音质与耗时的影响。',
        source_url='https://huggingface.co/amphion/MaskGCT'),
    'parler-tts-mini': dict(scenarios=['英文朗读', '声音描述', '命名说话人'],
        listen_for='正文是否完整、声音是否随描述改变，以及命名说话人在不同文本中的一致性。',
        source_url='https://huggingface.co/parler-tts/parler-tts-mini-v1'),
}

VOICE_LABELS = {'vivian': 'Vivian · 明亮女声', 'serena': 'Serena · 温柔女声',
    'uncle_fu': '傅叔 · 低沉男声', 'dylan': 'Dylan · 北京男声', 'eric': 'Eric · 成都男声',
    'ryan': 'Ryan · 英语男声', 'aiden': 'Aiden · 美式男声', 'ono_anna': 'Anna · 日语女声',
    'sohee': 'Sohee · 韩语女声', 'reference': '参考音频的声音', 'default': '默认声音',
    'zf_xiaobei': '小北 · 中文女声', 'zf_xiaoni': '小妮 · 中文女声', 'zf_xiaoxiao': '小小 · 中文女声',
    'zf_xiaoyi': '小伊 · 中文女声', 'zm_yunjian': '云健 · 中文男声', 'zm_yunxi': '云希 · 中文男声',
    'zm_yunxia': '云夏 · 中文男声', 'zm_yunyang': '云扬 · 中文男声'}


def voice_label(voice):
    if voice in VOICE_LABELS:
        return VOICE_LABELS[voice]
    if voice.startswith('seed_'):
        return '对话音色 ' + voice.removeprefix('seed_')
    prefix = {'af': '美式女声', 'am': '美式男声', 'bf': '英式女声', 'bm': '英式男声'}
    if voice[:2] in prefix:
        return voice[3:].replace('_', ' ').title() + ' · ' + prefix[voice[:2]]
    return voice


def local_voices(metadata):
    if metadata.key != 'kokoro-82m':
        return list(metadata.default_voices)
    # 先开放已有中英发音路径；其他语言的音色文件存在不等于发音资源就绪。
    voices = sorted(path.stem for path in (CHECKPOINTS_DIR / metadata.key / 'voices').glob('*.pt')
                    if path.stem.startswith(('zf_', 'zm_', 'af_', 'am_', 'bf_', 'bm_')))
    return list(dict.fromkeys([v for v in metadata.default_voices if v in voices] + voices))


def profile_for(metadata):
    profile = deepcopy(PROFILES[metadata.key])
    profile.update(deepcopy(EXPLORATION[metadata.key]))
    voices = local_voices(metadata)
    profile['voices'] = [dict(value=v, label=voice_label(v)) for v in voices]
    if metadata.key == 'parler-tts-mini':
        profile['voices'] = [dict(value=v, label='按声音描述生成' if v == 'default' else f'{v} · 命名说话人') for v in voices]
    profile['language_note'] = '语言列表表示当前版本能力范围；本机尚未逐语种验证音质。'
    if metadata.key == 'kokoro-82m':
        profile['controls'].insert(0, select('blend_voice', '混合第二音色', '',
                                            [('', '不混合')] + [(v, voice_label(v)) for v in voices]))
    return profile


def resolve_options(metadata, options=None, preset_key='default'):
    profile = profile_for(metadata)
    chosen = next((p for p in profile['presets'] if p['key'] == preset_key), None)
    if chosen is None:
        raise ValueError('未找到该模型的探索预设。')
    options = options or {}
    controls = {c['key']: c for c in profile['controls']}
    unknown = set(options) - controls.keys()
    if unknown:
        raise ValueError('该模型不支持参数: ' + ', '.join(sorted(unknown)))
    values = {c['key']: c['default'] for c in profile['controls']}
    values.update(chosen['options'])
    values.update(options)
    for key, value in values.items():
        control = controls[key]
        valid = False
        if control['type'] == 'boolean':
            valid = isinstance(value, bool)
        elif control['type'] == 'select':
            valid = not isinstance(value, bool) and value in [v['value'] for v in control['choices']]
            if valid:
                values[key] = next(v['value'] for v in control['choices'] if v['value'] == value)
        elif control['type'] == 'number':
            valid = (isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value) and control['min'] <= value <= control['max'])
            if valid and isinstance(control['default'], int) and control['step'] >= 1:
                valid = int(value) == value
                if valid:
                    values[key] = int(value)
        if not valid:
            raise ValueError(f'{control["label"]}的值无效。')
    return values, chosen
