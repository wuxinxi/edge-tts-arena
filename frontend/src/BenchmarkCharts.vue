<template>
  <section class="space-y-4" aria-labelledby="charts-title">
    <div class="flex flex-wrap justify-between items-center gap-3">
      <h2 id="charts-title" class="section-title"><LineChart :size="18" /> 图示对比</h2>
      <span class="text-xs text-slate-500">{{ rows.length }} 款已完成 · 原始数据随结果更新</span>
    </div>
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <div class="chart-card">
        <div class="flex flex-wrap justify-between items-center gap-3">
          <h3 class="section-title text-sm"><Activity :size="16" /> 指标曲线</h3>
          <select v-model="metricKey" aria-label="曲线图指标" class="control-input !w-auto text-xs">
            <option v-for="metric in chartMetrics" :key="metric.key" :value="metric.key">{{ metric.label }}（{{ metric.unit }}）</option>
          </select>
        </div>
        <p class="chart-caption">横轴为模型，按参数量排列；纵轴为原始 {{ selectedMetric.label }}。连线用于比较差异。</p>
        <svg v-if="points.length" viewBox="0 0 620 320" class="w-full chart-svg" role="img" :aria-label="`${selectedMetric.label}模型对比曲线`">
          <defs><linearGradient id="line-area" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#818cf8" stop-opacity=".24" /><stop offset="100%" stop-color="#818cf8" stop-opacity="0" /></linearGradient></defs>
          <g v-for="tick in [0, 1, 2, 3, 4]" :key="tick">
            <line x1="65" x2="594" :y1="250 - tick * 52" :y2="250 - tick * 52" stroke="#263247" stroke-dasharray="3 5" />
            <text x="54" :y="254 - tick * 52" text-anchor="end" fill="#8c9bb2" font-size="11">{{ number(lineMax * tick / 4) }}</text>
          </g>
          <text x="65" y="21" fill="#a9b6ca" font-size="11">{{ selectedMetric.unit }}</text>
          <path v-if="points.length > 1" :d="areaPath" fill="url(#line-area)" />
          <polyline :points="points.map(point => `${point.x},${point.y}`).join(' ')" fill="none" stroke="#a5b4fc" stroke-width="2.5" stroke-linejoin="round" />
          <g v-for="point in points" :key="point.result.model_key" tabindex="0" role="button"
            :aria-label="`${point.result.model_name}，${selectedMetric.label} ${number(point.value)} ${selectedMetric.unit}`"
            @mouseenter="focusKey = point.result.model_key" @focus="focusKey = point.result.model_key"
            @click="focusKey = point.result.model_key" @keydown.enter="focusKey = point.result.model_key" @keydown.space.prevent="focusKey = point.result.model_key">
            <circle :cx="point.x" :cy="point.y" r="12" fill="transparent" />
            <circle :cx="point.x" :cy="point.y" :r="focusKey === point.result.model_key ? 6 : 4" fill="#c7d2fe" stroke="#1e1b4b" stroke-width="2" />
            <text :x="point.x" y="275" text-anchor="middle" fill="#c0cbdc" font-size="10">{{ indexOf(point.result) + 1 }}</text>
            <title>{{ point.result.model_name }}：{{ number(point.value) }} {{ selectedMetric.unit }}</title>
          </g>
          <text x="330" y="307" text-anchor="middle" fill="#8c9bb2" font-size="11">模型编号（按参数量）</text>
        </svg>
        <p v-else class="py-12 text-center text-sm text-slate-500">等待有效指标</p>
        <div class="rounded-lg border border-indigo-500/20 bg-indigo-500/5 px-3 py-2 text-xs text-indigo-200" aria-live="polite">
          {{ focusedPoint?.result.model_name || '选择曲线上的节点' }}<span v-if="focusedPoint"> · {{ number(focusedPoint.value) }} {{ selectedMetric.unit }}</span>
        </div>
        <div class="flex flex-wrap gap-x-4 gap-y-2 text-[11px] text-slate-400">
          <button v-for="(row, index) in rows" :key="row.model_key" @click="focusKey = row.model_key" class="hover:text-indigo-200">{{ index + 1 }} · {{ shortNames[row.model_key] || row.model_name }}</button>
        </div>
        <p class="chart-caption">{{ metricKey === 'audio_duration_sec' ? '音频时长用于核对内容完整度，不是质量分数。' : '同一文本下，耗时与 RTF 越低生成越快；进程内存越低占用越少。' }}</p>
      </div>

      <div class="chart-card">
        <h3 class="section-title text-sm"><Radar :size="16" /> 多维性能雷达</h3>
        <p class="chart-caption">最多叠加 4 款模型。四项指标均越低越好，图形越向外，表示在本轮该维度的相对表现越好。</p>
        <div class="flex flex-wrap gap-2">
          <label v-for="row in radarEligible" :key="row.model_key" class="flex items-center gap-2 rounded-lg border border-slate-700/70 px-2 py-1.5 text-[11px] text-slate-300">
            <input type="checkbox" :checked="chosenKeys.includes(row.model_key)" @change="toggle(row.model_key)"
              :disabled="chosenKeys.length >= 4 && !chosenKeys.includes(row.model_key)" :aria-label="`雷达图显示 ${row.model_name}`" class="accent-indigo-400" />
            <span class="h-2 w-2 rounded-full" :style="{ background: color(row) }"></span>{{ shortNames[row.model_key] || row.model_name }}
          </label>
        </div>
        <svg v-if="radarRows.length >= 2" viewBox="0 0 480 380" class="w-full chart-svg" role="img" aria-label="四维相对性能雷达图">
          <polygon v-for="level in [.25, .5, .75, 1]" :key="level" :points="polygon(radarMetrics.map(() => level))" fill="none" stroke="#2d3a50" />
          <line v-for="(metric, i) in radarMetrics" :key="metric.key" x1="240" y1="190" :x2="radial(1, i)[0]" :y2="radial(1, i)[1]" stroke="#2d3a50" />
          <text v-for="(metric, i) in radarMetrics" :key="metric.key" :x="radial(1.37, i)[0]" :y="radial(1.37, i)[1] + 4" text-anchor="middle" fill="#b9c7da" font-size="12">{{ metric.label }}</text>
          <text x="245" y="185" fill="#65758f" font-size="9">0</text><text x="245" y="78" fill="#65758f" font-size="9">100</text>
          <g v-for="row in radarRows" :key="row.model_key">
            <polygon :points="polygon(scores(row))" :fill="color(row)" fill-opacity=".09" :stroke="color(row)" stroke-width="2" stroke-linejoin="round"><title>{{ radarDescription(row) }}</title></polygon>
            <circle v-for="(score, i) in scores(row)" :key="i" :cx="radial(score, i)[0]" :cy="radial(score, i)[1]" r="3" :fill="color(row)"><title>{{ row.model_name }} · {{ radarMetrics[i].label }}：{{ number(metricValue(row, radarMetrics[i].key)!) }} {{ radarMetrics[i].unit }}</title></circle>
          </g>
        </svg>
        <div v-else class="flex min-h-[230px] items-center justify-center gap-2 text-sm text-slate-500"><Radar :size="20" /> 至少选择两款有完整指标的模型</div>
        <p class="chart-caption">相对值 = 本轮最低值 / 当前值 × 100；最低值为 100，同值并列。当前值为 0 时记 100。基准使用本轮全部有效结果，随生成更新。不是音质或综合评分。</p>
        <details v-if="radarRows.length" class="group text-xs text-slate-400">
          <summary class="flex cursor-pointer items-center gap-1"><ChevronRight :size="14" class="group-open:rotate-90 transition" /> 查看雷达对应的原始数据</summary>
          <div class="mt-3 overflow-x-auto">
            <table class="w-full text-left text-[11px]"><thead><tr><th class="py-2">模型</th><th v-for="metric in radarMetrics" :key="metric.key" class="px-2 py-2 text-right">{{ metric.label }}</th></tr></thead>
              <tbody><tr v-for="row in radarRows" :key="row.model_key" class="border-t border-slate-800"><td class="py-2" :style="{ color: color(row) }">{{ shortNames[row.model_key] }}</td><td v-for="metric in radarMetrics" :key="metric.key" class="px-2 py-2 text-right font-mono">{{ number(metricValue(row, metric.key)!) }} {{ metric.unit }}</td></tr></tbody>
            </table>
          </div>
        </details>
      </div>
    </div>
    <p class="chart-caption flex items-start gap-2"><Info :size="14" class="mt-0.5 shrink-0" /> 耗时包含进程启动和模型加载；进程内存不包含完整的 MPS / CUDA 设备内存。首包延迟与音质未打分，不绘制为零。</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { LineChart, Radar, Activity, Info, ChevronRight } from 'lucide-vue-next'
import type { GenerationResult, ModelItem } from './types'
import { chartMetrics, radarMetrics, metricValue, relativePerformance, niceMaximum, shortNames, type MetricKey } from './chartMetrics'
const props = defineProps<{ results: GenerationResult[]; models: ModelItem[] }>()
const rows = computed(() => props.results.filter(row => row.success && row.metrics).slice()
  .sort((a, b) => (props.models.find(model => model.key === a.model_key)?.order || 0) - (props.models.find(model => model.key === b.model_key)?.order || 0)))
const metricKey = ref<MetricKey>('rtf'), focusKey = ref(''), chosenKeys = ref<string[]>([])
let selectionTouched = false
const selectedMetric = computed(() => chartMetrics.find(metric => metric.key === metricKey.value)!)
const validRows = computed(() => rows.value.filter(row => metricValue(row, metricKey.value) !== null))
const lineMax = computed(() => niceMaximum(Math.max(0, ...validRows.value.map(row => metricValue(row, metricKey.value)!)) * 1.1))
const points = computed(() => validRows.value.map((result, index) => ({ result, value: metricValue(result, metricKey.value)!,
  x: validRows.value.length === 1 ? 330 : 65 + index / (validRows.value.length - 1) * 529,
  y: 250 - metricValue(result, metricKey.value)! / lineMax.value * 208 })))
const areaPath = computed(() => points.value.length ? `M ${points.value[0].x} 250 L ${points.value.map(point => `${point.x} ${point.y}`).join(' L ')} L ${points.value[points.value.length - 1].x} 250 Z` : '')
const focusedPoint = computed(() => points.value.find(point => point.result.model_key === focusKey.value) || points.value[0])
const radarEligible = computed(() => rows.value.filter(row => radarMetrics.every(metric => metricValue(row, metric.key) !== null)))
const radarRows = computed(() => radarEligible.value.filter(row => chosenKeys.value.includes(row.model_key)))
watch(() => radarEligible.value.map(row => row.model_key).join(','), () => {
  chosenKeys.value = selectionTouched ? chosenKeys.value.filter(key => radarEligible.value.some(row => row.model_key === key)) : radarEligible.value.slice(0, 4).map(row => row.model_key)
}, { immediate: true })
function toggle(key: string) {
  selectionTouched = true
  chosenKeys.value = chosenKeys.value.includes(key) ? chosenKeys.value.filter(item => item !== key) : [...chosenKeys.value, key].slice(0, 4)
}
const palette = ['#a5b4fc', '#5eead4', '#fbbf24', '#fb7185', '#c4b5fd', '#38bdf8', '#f0abfc', '#a3e635', '#fdba74']
function indexOf(row: GenerationResult) { return rows.value.findIndex(item => item.model_key === row.model_key) }
function color(row: GenerationResult) { return palette[indexOf(row) % palette.length] }
function number(value: number) { return value >= 100 ? value.toFixed(0) : value >= 10 ? value.toFixed(1) : value.toFixed(2) }
function scores(row: GenerationResult) {
  return radarMetrics.map(metric => relativePerformance(metricValue(row, metric.key)!, radarEligible.value.map(result => metricValue(result, metric.key)!)))
}
function radial(value: number, index: number) { const angle = -Math.PI / 2 + index * Math.PI / 2; return [240 + Math.cos(angle) * 110 * value, 190 + Math.sin(angle) * 110 * value] }
function polygon(values: number[]) { return values.map((value, index) => radial(value, index).join(',')).join(' ') }
function radarDescription(row: GenerationResult) { return `${row.model_name}：${radarMetrics.map(metric => `${metric.label} ${number(metricValue(row, metric.key)!)} ${metric.unit}`).join('，')}` }
</script>
