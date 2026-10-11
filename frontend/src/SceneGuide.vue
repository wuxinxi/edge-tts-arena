<template>
  <section class="space-y-5" aria-labelledby="scene-heading">
    <div class="glass-panel rounded-2xl p-5 space-y-4">
      <div>
        <h2 id="scene-heading" class="section-title text-lg"><Compass :size="21" class="text-indigo-300" /> 先选场景，再探索模型</h2>
        <p class="mt-2 text-sm leading-relaxed text-slate-400">候选按当前接入能力匹配，按参数量展示。场景适用性是探索建议，需用你的文本和设备验证。</p>
      </div>
      <div class="flex flex-wrap gap-2" aria-label="选择使用场景">
        <button v-for="item in scenarios" :key="item.key" @click="selectedKey = item.key"
          :aria-pressed="selectedKey === item.key"
          class="rounded-xl border px-3 py-2 text-sm transition inline-flex items-center gap-2"
          :class="selectedKey === item.key ? 'border-indigo-400 bg-indigo-500/20 text-indigo-100' : 'border-slate-700 text-slate-400 hover:text-white'">
          <component :is="sceneIcons[item.key]" :size="16" />{{ item.label }}
        </button>
      </div>
      <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-3">
        <h3 class="text-sm font-medium text-indigo-200">{{ selected.question }}</h3>
        <ul class="grid gap-2 text-xs text-slate-400 sm:grid-cols-3">
          <li v-for="check in selected.checks" :key="check" class="leading-relaxed flex items-start gap-2"><Check :size="13" class="mt-0.5 shrink-0 text-teal-400" />{{ check }}</li>
        </ul>
        <details class="group text-xs text-slate-400">
          <summary class="flex items-center gap-1 cursor-pointer"><ChevronRight :size="13" class="group-open:rotate-90 transition" />查看场景示例文本</summary>
          <p class="mt-2 leading-relaxed">{{ selected.text }}</p>
        </details>
      </div>
      <div class="flex flex-wrap justify-between items-center gap-3">
        <label class="flex items-center gap-2 text-xs text-slate-400">
          <input v-model="readyOnly" type="checkbox" class="accent-indigo-500" /> 只看本地资源就绪的模型
        </label>
        <button @click="$emit('compare', { keys: comparableCandidates.map(model => model.key), text: selected.text })"
          :disabled="busy || !comparableCandidates.length"
          class="rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-3 py-2 text-xs text-indigo-200 hover:bg-indigo-500/20 disabled:opacity-40 inline-flex items-center gap-2">
          <ArrowRight :size="14" />前往统一评测（{{ comparableCandidates.length }} 款）
        </button>
      </div>
      <p v-if="comparableCandidates.length < readyCandidates.length" class="text-xs text-amber-300">Parler 仅支持英文，未加入本场景的中文统一评测；可单独使用英文示例探索。</p>
      <p class="text-[11px] leading-relaxed text-slate-500">统一评测使用相同示例文本和基础配置，比较离线耗时与进程内存。特色指令、克隆模式和目标时长需在能力探索页分别验证。此处只准备设置，点击生成后才运行。</p>
    </div>

    <div class="flex flex-wrap justify-between gap-2 text-xs text-slate-400" role="status">
      <span>{{ selected.label }} · {{ visibleModels.length }} 款候选 · {{ readyCandidates.length }} 款本地资源就绪</span>
      <span>资源就绪 ≠ 场景效果已验证</span>
    </div>
    <p v-if="!models.length" class="text-sm text-slate-400">正在读取模型信息…</p>
    <p v-else-if="!visibleModels.length" class="text-sm text-slate-400">当前场景没有本地资源就绪的候选，可取消筛选查看能力资料。</p>
    <div class="grid gap-4 md:grid-cols-2">
      <article v-for="model in visibleModels" :key="model.key" class="glass-panel rounded-2xl p-5 space-y-4">
        <div class="flex flex-wrap justify-between items-start gap-2">
          <div>
            <h3 class="font-semibold text-slate-100">{{ model.name }}</h3>
            <p class="mt-1 text-[11px] text-slate-500">{{ model.profile.version }} · {{ model.param_size }}</p>
          </div>
          <span class="rounded-full border px-2 py-1 text-[10px] inline-flex items-center gap-1"
            :class="model.is_ready ? 'border-emerald-500/20 text-emerald-300' : 'border-amber-500/20 text-amber-300'">
            <CheckCircle2 v-if="model.is_ready" :size="11" /><AlertCircle v-else :size="11" />{{ model.is_ready ? '本地资源就绪' : '本地资源不完整' }}
          </span>
        </div>
        <p class="text-sm leading-relaxed text-indigo-200">{{ selected.candidates[model.key] }}</p>
        <dl class="space-y-3 text-xs leading-relaxed">
          <div><dt class="text-slate-300">使用条件</dt><dd class="mt-1 text-slate-400">{{ referenceCondition(model) }}</dd></div>
          <div><dt class="text-slate-300">当前控制方式</dt><dd class="mt-1 text-slate-400">{{ controlKinds(model) }}</dd></div>
          <div><dt class="text-slate-300">版本 / 接入语言范围</dt><dd class="mt-1 text-slate-400">{{ model.supported_languages.map(languageLabel).join('、') }}</dd></div>
          <div><dt class="text-slate-300">试听重点</dt><dd class="mt-1 text-slate-400">{{ model.profile.listen_for }}</dd></div>
          <div><dt class="text-slate-300">使用边界</dt><dd class="mt-1 text-slate-400">{{ model.profile.tips }}</dd></div>
        </dl>
        <p v-if="!model.is_ready" class="text-xs text-amber-300">{{ model.unavailable_reason }}</p>
        <div class="flex flex-wrap justify-between items-center gap-3 border-t border-slate-800 pt-3">
          <a :href="model.profile.source_url" target="_blank" rel="noopener noreferrer" class="text-xs text-indigo-400 hover:underline inline-flex items-center gap-1">官方能力资料 <ExternalLink :size="12" /></a>
          <button @click="explore(model)" :disabled="busy || !model.is_ready"
            :aria-label="`用示例探索 ${model.name}`"
            class="rounded-lg bg-indigo-600 px-3 py-2 text-xs text-white hover:bg-indigo-500 disabled:opacity-40 inline-flex items-center gap-2">
            <ArrowRight :size="13" />{{ model.is_ready ? '用示例探索' : '暂不可体验' }}
          </button>
        </div>
      </article>
    </div>
    <p class="text-xs leading-relaxed text-slate-500">语言列表与特色能力结合官方资料及当前接入范围整理，尚未逐语言、逐场景验证音质；本项目当前采用离线生成，不能据此判断流式交互延迟。缺失资源仅展示状态，不自动下载。</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Compass, BookOpen, MessageCircle, AudioLines, Languages, SlidersHorizontal, Timer, ExternalLink, ArrowRight, Check, CheckCircle2, AlertCircle, ChevronRight, Info } from 'lucide-vue-next'
import type { ModelItem } from './types'
import { scenarios, type ScenarioExperiment } from './scenarios'
import { textCompatibilityError } from './textCompatibility'

const props = defineProps<{ models: ModelItem[]; busy: boolean }>()
const emit = defineEmits<{
  (event: 'explore', value: ScenarioExperiment): void
  (event: 'compare', value: { keys: string[]; text: string }): void
}>()
const sceneIcons = { reading: BookOpen, english: Languages, dialogue: MessageCircle, clone: AudioLines, languages: Languages, style: SlidersHorizontal, duration: Timer }
const selectedKey = ref('reading')
const readyOnly = ref(true)
const selected = computed(() => scenarios.find(scene => scene.key === selectedKey.value) || scenarios[0])
const candidates = computed(() => props.models.filter(model => Object.prototype.hasOwnProperty.call(selected.value.candidates, model.key))
  .slice().sort((a, b) => a.order - b.order))
const readyCandidates = computed(() => candidates.value.filter(model => model.is_ready))
const comparableCandidates = computed(() => readyCandidates.value.filter(model => !textCompatibilityError([model.key], [selected.value.text])))
const visibleModels = computed(() => readyOnly.value ? readyCandidates.value : candidates.value)
const languages: Record<string, string> = { zh: '中文', en: '英语', ja: '日语', ko: '韩语', de: '德语', fr: '法语',
  ru: '俄语', pt: '葡萄牙语', es: '西班牙语', it: '意大利语', ar: '阿拉伯语', nl: '荷兰语', pl: '波兰语' }
function languageLabel(code: string) { return languages[code] || code }
function referenceCondition(model: ModelItem) {
  if (model.requires_reference_audio) return '需要参考声音，未上传时使用内置中文参考与原文；上传参考的原文要求因生成模式而异。'
  if (model.key === 'chattts') return '无需参考音频；通过音色种子选择声音。'
  if (model.profile.prompt_kind === 'description') return '无需参考音频；通过英文描述指定声音特征。'
  return '无需参考音频；使用该版本的预置音色。'
}
function controlKinds(model: ModelItem) {
  const parts = [model.supports_clone ? '参考音色生成' : model.profile.prompt_kind === 'description' ? '描述式声音生成' : model.key === 'chattts' ? '种子音色生成' : '预置音色生成']
  const prompts = { none: '无风格指令入口', tokens: '专用对话标记', instruction: '自然语言风格指令', description: '英文声音描述' }
  parts.push(prompts[model.profile.prompt_kind])
  if (model.profile.controls.some(control => control.key === 'target_duration')) parts.push('模型目标时长')
  if (model.key === 'parler-tts-mini') parts.push('6 个命名说话人快捷选项，也可自行描述')
  else if (model.profile.voices.length > 1) parts.push(`${model.profile.voices.length} 个本地音色选项`)
  return parts.join(' · ')
}
function explore(model: ModelItem) {
  const requestedPreset = selected.value.modelPresets?.[model.key] || selected.value.preset
  const preset = model.profile.presets.some(item => item.key === requestedPreset) ? requestedPreset! : 'default'
  emit('explore', { modelKey: model.key, voice: selected.value.modelVoices?.[model.key], text: selected.value.modelTexts?.[model.key] || selected.value.text, preset, options: selected.value.options || {} })
}
</script>
