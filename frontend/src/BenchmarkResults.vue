<template>
  <section class="glass-panel rounded-2xl p-5 space-y-5">
    <div class="flex flex-wrap justify-between items-center gap-3">
      <h2 class="section-title"><BarChart3 :size="18" /> 本批次评测结果</h2>
      <a v-if="job" :href="`/api/comparisons/${job.job_id}/export`" class="inline-flex items-center gap-1 text-xs text-indigo-300"><Download :size="14" /> 导出完整批次</a>
    </div>
    <div v-if="job" class="flex flex-wrap gap-2 text-[11px] text-slate-300">
      <span class="rounded-lg border border-slate-700 px-2 py-1">{{ job.benchmark_mode === 'uniform' ? '统一条件' : '推荐配置' }}</span>
      <span class="rounded-lg border border-slate-700 px-2 py-1">{{ new Date(job.created_at).toLocaleString('zh-CN') }}</span>
      <span class="rounded-lg border border-slate-700 px-2 py-1">输出 {{ job.speed }}x · {{ job.reference_source === 'uploaded' ? '上传参考' : '内置参考 / 无需参考' }}</span>
    </div>
    <div class="flex flex-wrap items-center gap-3 text-xs">
      <label for="result-sample" class="text-slate-400">查看场景</label>
      <select id="result-sample" v-model="sampleId" class="control-input !w-auto"><option v-for="sample in samples" :key="sample.id" :value="sample.id">{{ sample.label }}</option></select>
      <span class="text-slate-500">本场景计划 {{ plannedTotal }} 次生成 · 已返回 {{ scoped.length }} 项</span>
    </div>
    <p v-if="job?.retry_of" class="chart-caption">这是失败项重试批次，只包含原失败场景与轮次。<a :href="`/api/comparisons/${job.retry_of}/export`" class="text-indigo-300">查看原批次记录</a>。</p>
    <BatchActions v-if="job" :job="job" :busy="busy" :has-uploaded-reference="hasUploadedReference" @retry="$emit('retry',$event)" />
    <details class="group rounded-xl bg-slate-900/50 border border-slate-800 p-3"><summary class="section-title text-xs cursor-pointer"><ChevronRight :size="14" class="group-open:rotate-90" /> 测试文本与试听重点</summary><p class="mt-3 text-xs leading-relaxed text-slate-300">{{ selectedSample?.text }}</p><p v-if="selectedSample?.listen_for" class="mt-2 text-[11px] text-teal-300">试听重点：{{ selectedSample.listen_for }}</p></details>
    <nav class="flex gap-1 rounded-xl bg-slate-950/50 p-1 border border-slate-800" aria-label="结果视图">
      <button v-for="view in resultViews" :key="view.key" @click="resultView = view.key" :aria-pressed="resultView === view.key" class="flex-1 flex items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs transition" :class="resultView === view.key ? 'bg-indigo-500/20 text-indigo-100' : 'text-slate-400 hover:text-white'"><component :is="view.icon" :size="14" />{{ view.label }}</button>
    </nav>



    <div v-show="resultView === 'overview'" class="space-y-4">
      <h3 class="section-title text-sm"><Activity :size="16" /> 核心对比</h3>
      <p class="chart-caption">同一场景比较成功结果的中位数。速度与内存越低越好；听感需要逐次人工确认。</p>
      <div class="space-y-3 sm:hidden">
        <article v-for="row in stats" :key="row.key" class="rounded-xl border border-slate-700/60 p-4 space-y-3">
          <div class="flex justify-between gap-2"><h4 class="text-sm text-slate-100">{{ row.name }}</h4><span class="text-xs text-teal-300">{{ row.success }} / {{ row.attempts }} 成功</span></div>
          <dl class="grid grid-cols-2 gap-3 text-xs"><div><dt class="text-slate-500">实时率 RTF</dt><dd class="mt-1 font-mono text-indigo-200">{{ format(row.metricStats.rtf.median) }}x</dd></div><div><dt class="text-slate-500">生成耗时</dt><dd class="mt-1 font-mono text-slate-200">{{ format(row.metricStats.elapsed_time_sec.median) }} 秒</dd></div><div><dt class="text-slate-500">进程内存峰值</dt><dd class="mt-1 font-mono text-slate-200">{{ memory(row.metricStats.memory_peak_mb.median) }}</dd></div><div><dt class="text-slate-500">内容与听感</dt><dd class="mt-1 text-slate-200">{{ reviewSummary(row.key) }}</dd></div></dl>
          <button @click="listenModel(row.key)" :disabled="!row.success" :aria-label="`试听与记录 ${row.name}`" class="inline-flex items-center gap-1 text-xs text-indigo-300 disabled:opacity-40"><Headphones :size="13" />试听与记录</button>
        </article>
      </div>
      <div class="hidden sm:block overflow-x-auto"><table class="w-full min-w-[760px] text-xs text-left"><thead class="text-slate-500"><tr><th class="py-3">模型</th><th>成功 / 已返回</th><th>RTF</th><th>耗时中位数</th><th>内存峰值</th><th>内容与听感</th><th>试听</th></tr></thead><tbody>
        <tr v-for="row in stats" :key="row.key" class="border-t border-slate-800"><td class="py-4 text-slate-200">{{ row.name }}<span class="block mt-1 text-[10px] text-slate-500">计划 {{ row.expected }} 次</span></td><td class="text-teal-300">{{ row.success }} / {{ row.attempts }}</td><td class="font-mono text-indigo-200">{{ format(row.metricStats.rtf.median) }}x</td><td class="font-mono">{{ format(row.metricStats.elapsed_time_sec.median) }} 秒</td><td class="font-mono">{{ memory(row.metricStats.memory_peak_mb.median) }}</td><td>{{ reviewSummary(row.key) }}</td><td><button @click="listenModel(row.key)" :disabled="!row.success" :aria-label="`试听与记录 ${row.name}`" class="text-indigo-300 disabled:opacity-40"><Headphones :size="15" /></button></td></tr>
      </tbody></table></div>
      <details class="group"><summary class="section-title text-xs cursor-pointer"><ChevronRight :size="14" class="group-open:rotate-90" /> 耗时波动与内存增量</summary><div class="overflow-x-auto mt-3"><table class="w-full min-w-[500px] text-xs text-left"><thead class="text-slate-500"><tr><th class="py-2">模型</th><th>耗时范围</th><th>RSS 增量中位数</th></tr></thead><tbody><tr v-for="row in stats" :key="row.key" class="border-t border-slate-800"><td class="py-3">{{ row.name }}</td><td>{{ row.metricStats.elapsed_time_sec.count < 2 ? '样本不足' : `${format(row.metricStats.elapsed_time_sec.min)} – ${format(row.metricStats.elapsed_time_sec.max)} 秒` }}</td><td>{{ memory(row.metricStats.memory_diff_mb.median) }}</td></tr></tbody></table></div><p class="chart-caption mt-2">只有一次成功结果时无法判断耗时波动。未完成项不计入成功率分母。</p></details>
    </div>
    <div v-show="resultView === 'charts'" class="space-y-5">
    <div class="chart-card">
      <div class="flex flex-wrap items-center justify-between gap-3"><h3 class="section-title text-sm"><BarChart3 :size="16" /> 模型差异</h3>
        <select v-model="barMetric" aria-label="柱状图指标" class="control-input !w-auto text-xs"><option v-for="metric in chartMetrics.slice(0,4)" :key="metric.key" :value="metric.key">{{ metric.label }}（{{ metric.unit }}）</option></select>
      </div>
      <p class="chart-caption">同一场景按中位数比较，越低越好；横条从零开始。未成功或缺失指标不绘制。</p>
      <div v-for="row in barRows" :key="row.key" class="grid grid-cols-[95px_1fr_85px] gap-3 items-center text-xs">
        <span class="truncate text-slate-300" :title="row.name">{{ shortNames[row.key] || row.name }}</span><div class="h-4 bg-slate-800 rounded"><div class="h-full bg-gradient-to-r from-indigo-500 to-teal-400 rounded" :style="{width:`${barMax ? row.value/barMax*100 : 0}%`}"></div></div><span class="font-mono text-right text-indigo-200">{{ format(row.value) }} {{ barUnit }}</span>
      </div><p v-if="!barRows.length" class="chart-caption">等待有效结果</p>
    </div>
    <div class="space-y-3"><h3 class="section-title text-sm"><Activity :size="16" /> 曲线与四维雷达</h3>
      <p class="chart-caption mt-3 mb-3">重复评测时图中每项为该场景的中位数。耗时与 RTF、内存峰值与增量有相关性，四轴不代表四项独立能力，也不提供综合评分。</p>
      <BenchmarkCharts :results="aggregates" :models="models" />
    </div>

    </div>
    <div v-show="resultView === 'listening'" class="space-y-5">
    <div class="space-y-3">
      <h3 class="section-title text-sm"><Headphones :size="16" /> 并排试听</h3>
      <p class="chart-caption">A、B 使用同一段测试文本。可选择不同模型或同一模型的不同轮次，播放一边会暂停另一边。</p>
      <div class="grid md:grid-cols-2 gap-3">
        <div v-for="(side,index) in sides" :key="side" class="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4 space-y-3">
          <div class="flex items-center gap-3"><span class="rounded-lg px-2 py-1 bg-indigo-500/10 text-indigo-200 font-semibold">{{ side }}</span>
            <select v-model="audioKeys[index]" @change="audioSelectionTouched = true" :aria-label="`试听 ${side} 结果`" class="control-input text-xs"><option v-for="(run,i) in successful" :key="runKey(run)" :value="runKey(run)">{{ run.model_name }} · 第 {{ run.repeat_index || 1 }} 次</option></select></div>
          <template v-if="audioRuns[index]">
            <audio :ref="element => setAudioRef(element, index)" :src="audioRuns[index].audio_url" :aria-label="`试听 ${side} 音频`" controls preload="none" class="w-full h-9" @play="onPlay(index)"></audio>
            <p class="text-[11px] text-slate-400">{{ audioRuns[index].settings?.preset_label }} · {{ audioRuns[index].device }} · {{ audioRuns[index].metrics.audio_duration_sec }} 秒</p>
            <div class="flex gap-4 text-[11px] text-indigo-300"><a :href="audioRuns[index].audio_url" :download="audioRuns[index].audio_file" class="inline-flex gap-1 items-center"><Download :size="12" /> 下载音频</a><a v-if="audioRuns[index].record_url" :href="audioRuns[index].record_url" class="inline-flex gap-1 items-center"><FileText :size="12" /> 实际参数</a></div>
          </template><p v-else class="chart-caption">等待该场景的成功音频</p>
        </div>
      </div>
    </div>
    <ListeningReview :key="reviewFocus" :runs="reviewRuns" @saved="(run, review) => $emit('reviewSaved',run,review)" />
    </div>
    <details v-show="resultView === 'records'" open class="group"><summary class="section-title text-sm cursor-pointer"><ChevronRight :size="15" class="group-open:rotate-90" /> 查看逐次原始记录（{{ scoped.length }}）</summary>
      <div class="overflow-x-auto mt-3"><table class="w-full min-w-[850px] text-xs text-left"><thead class="text-slate-500"><tr><th class="py-2">模型 / 轮次</th><th>参数量 / 架构</th><th>耗时</th><th>音频时长</th><th>RTF</th><th>RSS 峰值 / 增量</th><th>记录</th></tr></thead><tbody>
        <tr v-for="(run,i) in scoped" :key="runKey(run) || i" class="border-t border-slate-800"><td class="py-3 text-slate-200">{{ run.model_name }} · {{ run.repeat_index || 1 }}</td><td class="text-slate-400">{{ run.param_size }}<span class="block text-[10px]">{{ models.find(model => model.key===run.model_key)?.architecture || '—' }}</span></td>
          <td v-if="!run.success" colspan="5" class="text-rose-300">{{ run.error }}</td><template v-else><td>{{ format(run.metrics.elapsed_time_sec) }}s</td><td>{{ format(run.metrics.audio_duration_sec) }}s</td><td>{{ format(run.metrics.rtf) }}x</td><td>{{ format(run.metrics.memory_peak_mb) }} / {{ format(run.metrics.memory_diff_mb) }} MB</td><td><a :href="run.record_url" class="text-indigo-300">实际参数</a></td></template>
        </tr></tbody></table></div>
    </details>
    <p class="chart-caption">{{ job?.benchmark_mode==='recommended' ? '推荐配置' : '统一条件' }} · 离线冷启动，耗时包含进程启动与模型加载；内存为进程 RSS，不含完整 MPS / CUDA 设备内存。首包延迟未测量；图表不代表整体音质。</p>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { BarChart3, Activity, ChevronRight, Download, Headphones, FileText, List } from 'lucide-vue-next'
import BenchmarkCharts from './BenchmarkCharts.vue'
import ListeningReview from './ListeningReview.vue'
import BatchActions from './BatchActions.vue'
import { chartMetrics, shortNames, type MetricKey } from './chartMetrics'
import { modelStatistics } from './benchmarkStatistics'
import { listeningSummary } from './listeningSummary'
import type { ComparisonJob, ModelItem, GenerationResult, EvaluationSample, ListeningReview as Review } from './types'
const props = defineProps<{results:GenerationResult[]; models:ModelItem[]; job:ComparisonJob|null; busy:boolean; hasUploadedReference:boolean; active:boolean}>()
const emit = defineEmits<{(e:'listening'):void;(e:'retry',useDefault:boolean):void;(e:'reviewSaved',run:GenerationResult,review:Review):void}>()
const resultView=ref<'overview'|'charts'|'listening'|'records'>('overview')
const resultViews=[{key:'overview',label:'对比总览',icon:List},{key:'charts',label:'图示分析',icon:BarChart3},{key:'listening',label:'试听与记录',icon:Headphones},{key:'records',label:'原始记录',icon:FileText}] as const
const reviewFocus=ref('')
const sampleId=ref(''), barMetric=ref<MetricKey>('rtf')
const samples=computed<EvaluationSample[]>(() => props.job?.samples?.length ? props.job.samples : [{id:'custom',label:'当前文本',text:props.results[0]?.text || '',listen_for:''}])
watch(() => samples.value.map(sample => sample.id).join(',')+'|'+(props.job?.job_id || ''), () => {sampleId.value=samples.value[0]?.id || 'custom'; resultView.value='overview'; reviewFocus.value=''}, {immediate:true})
const selectedSample=computed(() => samples.value.find(sample => sample.id===sampleId.value))
const scoped=computed(() => props.results.filter(run => (run.sample_id || 'custom')===sampleId.value))
const plannedCounts=computed(() => {const counts:Record<string,number>={}; for(const task of props.job?.models || []) {if((task.sample_id || 'custom')===sampleId.value){const key=task.model_key || task.key; counts[key]=(counts[key] || 0)+1}} return counts})
const plannedTotal=computed(() => Object.values(plannedCounts.value).reduce((sum,value)=>sum+value,0))
const stats=computed(() => modelStatistics(scoped.value,props.job ? plannedCounts.value : 1).sort((a,b) => (props.models.find(m=>m.key===a.key)?.order || 0)-(props.models.find(m=>m.key===b.key)?.order || 0)))
const aggregates=computed(() => stats.value.map(row=>row.aggregate).filter((run):run is GenerationResult => !!run))
const barRows=computed(() => stats.value.map(row=>({key:row.key,name:row.name,value:row.metricStats[barMetric.value].median})).filter((row):row is {key:string;name:string;value:number}=>row.value!==null).sort((a,b)=>a.value-b.value))
const barMax=computed(() => Math.max(0,...barRows.value.map(row=>row.value)))
const barUnit=computed(() => chartMetrics.find(metric=>metric.key===barMetric.value)?.unit || '')
function format(value:number|null|undefined) { return value==null || !Number.isFinite(value) ? '—' : value>=100 ? value.toFixed(1) : value.toFixed(3).replace(/\.?0+$/,'') }
const successful=computed(() => scoped.value.filter(run=>run.success && run.audio_url))
const sides=['A','B'], audioKeys=ref<string[]>(['','']), audioElements:(HTMLAudioElement|null)[]=[null,null]
let audioSelectionTouched = false
watch(sampleId, () => { audioSelectionTouched = false; reviewFocus.value='' })
function runKey(run:GenerationResult) { return run.audio_file || run.task_key || '' }
const audioRuns=computed(() => audioKeys.value.map(key=>successful.value.find(run=>runKey(run)===key)))
watch(() => successful.value.map(runKey).join('|'), () => {
  const keys=successful.value.map(runKey)
  audioKeys.value=audioKeys.value.map((key,index) => keys.includes(key) ? key : keys[index] || keys[0] || '')
  // 初次只有一个模型时两边相同；第二个模型返回后优先展示不同模型。
  if (!audioSelectionTouched && audioKeys.value[0]===audioKeys.value[1] && successful.value.length>1) {
    const other=successful.value.find(run=>run.model_key!==audioRuns.value[0]?.model_key)
    if (other) audioKeys.value[1]=runKey(other)
  }
}, {immediate:true})
function setAudioRef(element:unknown,index:number) { audioElements[index]=element as HTMLAudioElement|null }
watch([resultView, () => props.active], () => { if (resultView.value !== 'listening' || !props.active) audioElements.forEach(audio=>audio?.pause()) })
const reviewRuns=computed(() => reviewFocus.value ? [...successful.value.filter(run=>run.model_key===reviewFocus.value),...successful.value.filter(run=>run.model_key!==reviewFocus.value)] : successful.value)
function listenModel(key:string) {
  const run=successful.value.find(item=>item.model_key===key)
  if (!run) return
  audioKeys.value[0]=runKey(run); audioSelectionTouched=true; reviewFocus.value=key; resultView.value='listening'
}
function memory(value:number|null) { return value==null ? '—' : value >= 1024 ? `${(value/1024).toFixed(2)} GB` : `${value.toFixed(1)} MB` }
function reviewSummary(key:string) { return listeningSummary(scoped.value, key) }
function onPlay(index:number) { audioElements[1-index]?.pause(); emit('listening') }
onUnmounted(() => audioElements.forEach(audio=>audio?.pause()))
</script>
