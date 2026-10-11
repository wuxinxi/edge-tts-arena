import type { GenerationResult } from './types'

export const chartMetrics = [
  { key: 'rtf', label: '实时率 RTF', unit: 'x' },
  { key: 'elapsed_time_sec', label: '生成耗时', unit: '秒' },
  { key: 'memory_peak_mb', label: '进程内存峰值', unit: 'MB' },
  { key: 'memory_diff_mb', label: '进程内存增量', unit: 'MB' },
  { key: 'audio_duration_sec', label: '音频时长', unit: '秒' },
] as const
export type MetricKey = typeof chartMetrics[number]['key']
export const radarMetrics = chartMetrics.slice(0, 4)

export function metricValue(result: GenerationResult, key: MetricKey): number | null {
  const value = result.metrics?.[key]
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

export function relativePerformance(value: number, values: number[]): number {
  const best = Math.min(...values)
  return value === 0 ? 1 : best / value
}

export function niceMaximum(value: number): number {
  if (value <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(value))
  return ([1, 2, 5, 10].find(step => step * power >= value) || 10) * power
}

export const shortNames: Record<string, string> = { 'kokoro-82m': 'Kokoro', 'melotts-zh': 'MeloTTS',
  'f5-tts': 'F5-TTS', chattts: 'ChatTTS', cosyvoice3: 'CosyVoice 3', 'qwen3-tts-0.6b': 'Qwen 0.6B',
  'qwen3-tts-1.7b': 'Qwen 1.7B', 'fish-speech-1.5': 'Fish 1.5', maskgct: 'MaskGCT', 'parler-tts-mini': 'Parler' }
