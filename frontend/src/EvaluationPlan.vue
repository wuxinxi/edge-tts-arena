<template>
  <section class="glass-panel rounded-2xl p-5 space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="section-title text-sm"><ListChecks :size="18" /> 场景测试集</h2>
      <label class="flex items-center gap-2 text-xs text-slate-400">每段文本重复
        <select :value="repeats" @change="$emit('update:repeats', Number(($event.target as HTMLSelectElement).value))" :disabled="busy" aria-label="重复评测次数" class="control-input !w-auto">
          <option v-for="count in [1,2,3,5]" :value="count" :key="count">{{ count }} 次</option>
        </select>
      </label>
    </div>
    <p class="chart-caption">选择需要测试的场景；仅生成所选文本。各场景分别查看，重复次数用于观察耗时波动。</p>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
      <label v-for="sample in evaluationSamples" :key="sample.id" class="rounded-xl border p-3 cursor-pointer" :class="selectedIds.includes(sample.id) ? 'border-indigo-500/50 bg-indigo-500/10' : 'border-slate-800 bg-slate-900/40'">
        <span class="flex items-center gap-2 text-xs text-slate-200"><input type="checkbox" :checked="selectedIds.includes(sample.id)" :disabled="busy" @change="toggle(sample.id)" :aria-label="`测试集：${sample.label}`" class="accent-indigo-400" />{{ sample.label }}</span>
        <span class="block mt-2 text-[11px] leading-relaxed text-slate-500">{{ sample.listen_for }}</span>
      </label>
    </div>
    <details v-if="selectedIds.length || savedSamples?.length" class="group text-xs text-slate-400"><summary class="section-title cursor-pointer"><ChevronRight :size="14" class="group-open:rotate-90" /> 查看本批次测试文本</summary>
      <div v-for="sample in savedSamples || evaluationSamples.filter(item => selectedIds.includes(item.id))" :key="sample.id" class="mt-3 space-y-1"><p class="text-indigo-200">{{ sample.label }}</p><p class="leading-relaxed">{{ sample.text }}</p></div>
    </details>
    <div class="flex items-start gap-2 rounded-lg bg-indigo-500/5 border border-indigo-500/20 p-3 text-xs text-indigo-200"><Layers :size="16" class="shrink-0" /> {{ modelCount }} 款模型 × {{ savedSamples?.length || selectedIds.length }} 段文本 × {{ repeats }} 次 = {{ modelCount * (savedSamples?.length || selectedIds.length) * repeats }} 次生成。每次仍包含进程启动和模型加载；默认种子不变，不作为随机种子敏感性测试。</div>
  </section>
</template>
<script setup lang="ts">
import { ListChecks, Layers, ChevronRight } from 'lucide-vue-next'
import { evaluationSamples } from './evaluationSamples'
import type { EvaluationSample } from './types'
const props = defineProps<{selectedIds:string[]; repeats:number; modelCount:number; busy:boolean; savedSamples?:EvaluationSample[]|null}>()
const emit = defineEmits<{(e:'update:selectedIds', value:string[]):void; (e:'update:repeats', value:number):void}>()
function toggle(id:string) { if (!props.busy) emit('update:selectedIds', props.selectedIds.includes(id) ? props.selectedIds.filter(key => key!==id) : [...props.selectedIds,id]) }
</script>
