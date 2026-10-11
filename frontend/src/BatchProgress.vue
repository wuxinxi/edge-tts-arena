<template>
  <section class="glass-panel rounded-2xl p-5 space-y-4" aria-labelledby="progress-title">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div class="rounded-xl border border-indigo-500/20 bg-indigo-500/10 p-2.5 text-indigo-300">
          <Loader2 v-if="active" :size="20" class="animate-spin" /><CheckCircle2 v-else-if="job.status === 'completed'" :size="20" /><AlertCircle v-else :size="20" />
        </div>
        <div>
          <h2 id="progress-title" class="text-sm font-semibold">{{ job.status === 'queued' ? '评测已排队' : active ? '批量评测进行中' : job.status === 'completed' ? '本轮评测已结束' : job.status === 'cancelled' ? '已停止后续生成' : '评测未能继续' }}</h2>
          <p class="mt-1 text-xs text-slate-400">完成 {{ job.completed }} / {{ job.total }} 次生成 · 成功 {{ job.successful }} · 失败 {{ job.failed }}<span v-if="active"> · 已等待 {{ elapsed }} 秒</span></p>
        </div>
      </div>
      <span v-if="active" class="text-2xl font-semibold font-mono text-indigo-200">{{ percent }}<span class="text-sm text-slate-500">%</span></span>
    </div>
    <div v-if="active" class="flex flex-wrap items-center justify-between gap-3"><p class="text-[11px] text-slate-500">当前生成会正常结束并保存，停止后不再启动后续项。</p><button @click="$emit('stop')" :disabled="stopping || job.stop_requested" class="inline-flex items-center gap-2 rounded-lg border border-amber-500/30 px-3 py-2 text-xs text-amber-200 disabled:opacity-40"><Square :size="13" /> {{ stopping ? '正在提交停止请求…' : job.stop_requested ? '已请求停止' : '停止后续生成' }}</button></div>
    <div v-if="active" role="progressbar" aria-label="已完成生成次数" :aria-valuenow="job.completed" :aria-valuemax="job.total" aria-valuemin="0" class="h-2 overflow-hidden rounded-full bg-slate-800">
      <div class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-teal-400 transition-all duration-500" :style="{ width: `${percent}%` }"></div>
    </div>
    <p v-if="reconnecting" class="text-xs text-amber-300" role="status">正在重新连接进度；评测仍在服务端继续，请勿重复提交。</p>
    <p v-else-if="active" class="text-xs text-slate-400" role="status">{{ job.stop_requested ? '停止请求已收到，等待当前生成结束。' : job.status === 'queued' ? '等待已有批次结束。' : currentName ? `正在处理 ${currentName}，包含等待资源、进程启动与模型加载。` : '准备下一项…' }} 每次完成即更新结果。</p>
    <p v-if="job.status === 'cancelled'" class="text-xs text-amber-200">已保留 {{ job.completed }} 项返回结果，{{ skipped }} 项未运行；未运行项不算失败，也不计入完成百分比。</p>
    <p v-if="job.error" class="text-xs text-red-300">{{ job.error }}</p>
    <details class="group" :open="active"><summary class="section-title text-xs cursor-pointer"><ChevronRight :size="14" class="group-open:rotate-90" /> {{ active ? '各项进度' : '查看完成与未运行项' }}</summary>
    <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 max-h-64 overflow-y-auto mt-3">
      <div v-for="model in job.models" :key="model.key" class="flex items-center gap-2.5 rounded-lg border p-2.5 text-xs"
        :class="model.status === 'running' ? 'border-indigo-500/40 bg-indigo-500/10' : 'border-slate-800 bg-slate-900/40'" :title="model.error">
        <Loader2 v-if="model.status === 'running'" :size="15" class="shrink-0 animate-spin text-indigo-300" />
        <CheckCircle2 v-else-if="model.status === 'succeeded'" :size="15" class="shrink-0 text-teal-300" />
        <XCircle v-else-if="model.status === 'failed'" :size="15" class="shrink-0 text-rose-300" />
        <MinusCircle v-else-if="model.status === 'skipped'" :size="15" class="shrink-0 text-slate-500" />
        <Circle v-else :size="15" class="shrink-0 text-slate-600" />
        <span class="min-w-0 flex-1 truncate text-slate-300">{{ model.name }}<span v-if="model.sample_label" class="block mt-1 text-[10px] text-slate-500">{{ model.sample_label }} · 第 {{ model.repeat_index || 1 }} 次</span></span>
        <span class="shrink-0 text-[10px] text-slate-500">{{ labels[model.status] }}</span>
      </div>
    </div>
    </details>
    <p v-if="active" class="text-[11px] text-slate-500">进度按已返回的生成次数计算，失败也计入完成数；不估算模型内部进度。刷新可恢复当前任务；服务重启后保留已完成结果。</p>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { Loader2, CheckCircle2, AlertCircle, XCircle, MinusCircle, Circle, Square, ChevronRight } from 'lucide-vue-next'
import type { ComparisonJob } from './types'
const props = defineProps<{ job: ComparisonJob; elapsed: number; reconnecting: boolean; stopping:boolean }>()
defineEmits<{(e:'stop'):void}>()
const active = computed(() => ['queued', 'running'].includes(props.job.status))
const percent = computed(() => props.job.total ? Math.round(props.job.completed / props.job.total * 100) : 0)
const skipped = computed(() => props.job.models.filter(model=>model.status==='skipped').length)
const currentName = computed(() => { const model = props.job.models.find(model => model.key === props.job.current_model); return model ? `${model.name}${model.sample_label ? ` · ${model.sample_label} · 第 ${model.repeat_index || 1} 次` : ''}` : '' })
const labels = { pending: '待运行', running: '处理中', succeeded: '完成', failed: '失败', skipped: '未运行' }
</script>
