import type { ModelOptions } from './types'
import { englishExample } from './textCompatibility'

export interface Scenario {
  key: string
  label: string
  question: string
  text: string
  checks: string[]
  candidates: Record<string, string>
  preset?: string
  modelPresets?: Record<string, string>
  modelTexts?: Record<string, string>
  modelVoices?: Record<string, string>
  options?: ModelOptions
}

// 候选是能力匹配，不是质量排名；版本与本地接入范围来自服务端 profile。
export const scenarios: Scenario[] = [
  {
    key: 'reading', label: '朗读与语音提示',
    question: '不提供参考声音，能否直接把文章或产品提示读清楚？',
    text: '欢迎使用语音助手。您的订单预计明天下午三点送达，请留意通知。',
    checks: ['人名、数字和时间是否读对', '句间停顿是否合理', '你的设备能否满足耗时与内存要求'],
    modelPresets: { 'qwen3-tts-1.7b': 'news' },
    candidates: {
      'kokoro-82m': '预置音色可直接朗读，适合先考察小模型的发音与资源占用。',
      'melotts-zh': '当前中文权重无需参考音频，可测试中文提示与中英词语衔接。',
      'qwen3-tts-1.7b': 'CustomVoice 提供预置音色，可对比同一段提示的声音与表达方式。',
    },
  },
  {
    key: 'english', label: '英文朗读与声音描述',
    question: '英文内容需要现成音色，还是通过描述控制声音特征？',
    text: englishExample,
    modelVoices: { 'kokoro-82m': 'af_heart', 'qwen3-tts-1.7b': 'ryan' },
    checks: ['英文正文是否完整，专有名词是否读对', '改变声音描述后，节奏与音色是否有变化', '同一设备上的耗时与内存是否可接受'],
    candidates: {
      'kokoro-82m': '选择本地英文音色，考察小模型朗读与资源占用。',
      'qwen3-tts-1.7b': '选择预置音色并使用表达指令；英文建议采用对应母语音色。',
      'parler-tts-mini': '英文描述控制声音特征、语速与录音感，也可指定命名说话人；无需参考音频。',
    },
  },
  {
    key: 'dialogue', label: '聊天与口语对话',
    question: '声音能否像日常交流一样，有合适的语气与停顿？',
    text: '你今天忙不忙？我刚发现一家不错的小店，等你有空，我们一起去看看吧。',
    checks: ['口语节奏与停顿是否自然', '是否改写、漏读或增加内容', '情绪是否合适，重复生成是否稳定'],
    candidates: {
      'chattts': '对话专用模型，可探索口语润色、笑声与停顿标记。',
      'cosyvoice3': '参考声音与风格指令可组合，用于探索同一声音的口语表达。',
      'qwen3-tts-1.7b': '预置音色支持表达指令，可尝试亲切、轻松等对话语气。',
    },
  },
  {
    key: 'clone', label: '参考声音克隆',
    question: '提供一段声音后，能否用相近音色说出新的内容？',
    text: '今天阳光很好，让我们用清晰自然的声音，讲述一个新的故事。',
    checks: ['与参考声音是否相似', '新文本是否完整准确', '换参考音频后是否仍稳定'],
    candidates: {
      'f5-tts': '当前接入中英文参考克隆，可对比参考素材与生成步数的影响。',
      'cosyvoice3': '提供参考克隆与跨语言音色迁移两种路径。',
      'qwen3-tts-0.6b': 'Base 支持完整克隆与仅音色模式，可直接比较两种方式。',
      'fish-speech-1.5': '当前 1.5 版本使用参考音频与文字，可考察音色和采样稳定性。',
      'maskgct': '当前接入参考克隆，可同时探索生成步数和目标时长。',
    },
  },
  {
    key: 'languages', label: '中英与多语言',
    question: '换语言或混合中英文后，发音和音色还能保持稳定吗？',
    text: '今天的会议主题是 artificial intelligence。请在下午三点前提交报告，thank you。',
    checks: ['中英文衔接与专有名词发音', '显式语言与自动模式的差别', '每种目标语言分别试听，检查内容与音色'],
    candidates: {
      'kokoro-82m': '本地开放中英音色，需选择与文本语言相符的声音；混读效果待试听。',
      'melotts-zh': '中文权重支持中英混读，可用同一段文本验证衔接。',
      'f5-tts': '当前接入中英文参考克隆，可尝试换语言后的音色保留。',
      'chattts': '提供中英文对话生成，可考察混合文本的发音与节奏。',
      'cosyvoice3': '提供跨语言音色迁移；各语言的效果仍需单独验证。',
      'qwen3-tts-0.6b': 'Base 提供多语言克隆和显式语言选择。',
      'qwen3-tts-1.7b': 'CustomVoice 提供多语言生成和预置音色。',
      'fish-speech-1.5': '1.5 版本提供多语言生成，需按目标语言检查内容与参考音色。',
      'maskgct': '当前项目接入中文与英文；不把模型其他语言能力视为已开放。',
    },
  },
  {
    key: 'style', label: '情绪与风格指令',
    question: '修改表达指令后，同一段文本的声音会发生怎样的变化？',
    text: '终于等到你了！这个好消息，我一直想亲口告诉你。',
    checks: ['指令是否产生可听见的变化', '情绪变化是否影响内容准确性', '同一音色能否保留一致性'],
    preset: 'warm',
    modelTexts: { 'parler-tts-mini': 'You are finally here! I have been waiting to share this wonderful news with you.' },
    candidates: {
      'cosyvoice3': '提供自然语言风格和方言指令，需结合参考声音试听。',
      'qwen3-tts-1.7b': 'CustomVoice 支持对预置音色施加表达指令。',
      'parler-tts-mini': '通过英文描述控制声音特征；单独探索使用英文示例，中文统一评测不包含它。',
    },
  },
  {
    key: 'duration', label: '目标时长控制',
    question: '给定目标时长后，能否兼顾完整内容、自然节奏与音色？',
    text: '今天阳光很好，让我们用清晰自然的声音，讲述一个新的故事。',
    checks: ['实际时长与目标的差距', '是否挤字、漏字或出现长静音', '改变目标时长后，内容与音质是否稳定'],
    options: { target_duration: 5 },
    candidates: {
      'maskgct': '当前开放模型目标时长参数，可与生成后的音频变速分别验证。',
    },
  },
]

export interface ScenarioExperiment {
  modelKey: string
  voice?: string
  text: string
  preset: string
  options: ModelOptions
}
