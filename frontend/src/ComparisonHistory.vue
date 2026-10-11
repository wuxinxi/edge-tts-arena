<template>
  <section class="glass-panel rounded-2xl p-5 space-y-4" :aria-busy="loading">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="section-title"><History :size="18" /> {{ deleted ? '回收站' : '历史批次' }} <span class="text-xs font-normal text-slate-500">共 {{ pagination.total }} 个</span></h2>
      <button @click="$emit('trash', !deleted)" :disabled="locked" class="inline-flex gap-1.5 items-center text-xs text-indigo-300 disabled:opacity-40"><ArchiveRestore v-if="deleted" :size="14" /><Trash2 v-else :size="14" />{{ deleted ? '返回历史批次' : '回收站' }}</button>
    </div>
    <div class="flex justify-between gap-3 items-center"><p class="chart-caption">{{ deleted ? '删除的批次可在这里恢复。生成音频、实际参数和试听记录保留在本机。' : '查看结果保留新建评测的设置；“使用这些条件”才会恢复配置。删除移入回收站，音频与参数文件保留。' }}</p><button @click="$emit('refresh')" :disabled="locked" aria-label="刷新评测批次" class="text-indigo-300 disabled:opacity-40"><RefreshCw :size="16" :class="loading ? 'animate-spin' : ''" /></button></div>
    <p v-if="error" role="alert" class="text-xs text-amber-300">{{ error }}</p>
    <p v-if="loading && !jobs.length" role="status" class="chart-caption">正在读取批次…</p>
    <p v-else-if="!error && !jobs.length" class="chart-caption">{{ deleted ? '回收站为空。' : '暂无批次；首次评测后会自动保存。' }}</p>
    <div v-for="job in jobs" :key="job.job_id" class="rounded-xl border border-slate-800 p-3 space-y-3">
      <div class="flex flex-wrap gap-2 justify-between items-center"><span class="text-xs text-slate-200">{{ new Date(job.created_at).toLocaleString('zh-CN') }} · {{ statusLabels[job.status] }}</span><span class="text-[11px] text-slate-500">{{ job.completed }} / {{ job.total }} 次 · 成功 {{ job.successful }} · 失败 {{ job.failed }}</span></div>
      <p class="text-[11px] text-slate-400">{{ job.samples?.map(sample=>sample.label).join('、') || '当前文本' }} · 每模型每段 {{ job.repeats || 1 }} 次 · {{ job.benchmark_mode==='uniform' ? '统一条件' : '推荐配置' }}</p>
      <div v-if="deleted" class="flex items-center justify-between gap-3"><span class="text-[11px] text-slate-500">删除于 {{ job.deleted_at ? new Date(job.deleted_at).toLocaleString('zh-CN') : '—' }}</span><button @click="$emit('restore',job.job_id)" :disabled="locked" class="inline-flex items-center gap-1 text-xs text-indigo-300 disabled:opacity-40"><ArchiveRestore :size="14" />{{ changingId === job.job_id ? '正在恢复…' : '恢复批次' }}</button></div>
      <div v-else class="flex flex-wrap gap-4 text-xs text-indigo-300">
        <button @click="$emit('open', job.job_id)" :disabled="locked" class="inline-flex items-center gap-1 disabled:opacity-40"><FolderOpen :size="13" /> 查看结果{{ ['running','queued'].includes(job.status) ? '与进度' : '' }}</button>
        <button @click="$emit('prepare',job.job_id)" :disabled="locked" class="inline-flex items-center gap-1 disabled:opacity-40"><Copy :size="13" /> 使用这些条件</button>
        <a :href="`/api/comparisons/${job.job_id}/export`" class="inline-flex items-center gap-1"><Download :size="13" /> 导出</a>
        <button @click="deleteTarget = job.job_id" :disabled="locked || ['queued','running'].includes(job.status)" :aria-label="`删除批次 ${new Date(job.created_at).toLocaleString('zh-CN')}`" class="ml-auto inline-flex items-center gap-1 text-rose-300 disabled:opacity-30"><Trash2 :size="13" /> 删除</button>
      </div>
      <div v-if="deleteTarget === job.job_id && !deleted" class="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3 space-y-3">
        <p class="text-xs text-slate-300">将此批次移入回收站？音频、参数和试听记录保留，可随时恢复。</p>
        <div class="flex gap-4 text-xs"><button @click="$emit('delete',job.job_id)" :disabled="locked" class="inline-flex gap-1 items-center text-rose-300 disabled:opacity-40"><Trash2 :size="13" />{{ changingId === job.job_id ? '正在删除…' : '移入回收站' }}</button><button @click="deleteTarget = ''" :disabled="locked" class="text-slate-400">取消</button></div>
      </div>
    </div>
    <div class="flex flex-wrap justify-between items-center gap-3 border-t border-slate-800 pt-4 text-xs text-slate-400">
      <label class="flex items-center gap-2">每页<select :value="pagination.page_size" @change="$emit('pageSize', Number(($event.target as HTMLSelectElement).value))" :disabled="locked" aria-label="历史批次每页数量" class="control-input !w-auto"><option v-for="size in [5,10,20,50]" :key="size" :value="size">{{ size }} 条</option></select></label>
      <div class="flex items-center gap-3"><button @click="$emit('page',pagination.page-1)" :disabled="locked || pagination.page <= 1" aria-label="上一页历史批次" class="rounded-lg border border-slate-700 p-2 disabled:opacity-30"><ChevronLeft :size="14" /></button><span aria-live="polite">{{ pagination.total ? `第 ${pagination.page} / ${pagination.pages} 页` : '0 条记录' }}</span><button @click="$emit('page',pagination.page+1)" :disabled="locked || pagination.page >= pagination.pages" aria-label="下一页历史批次" class="rounded-lg border border-slate-700 p-2 disabled:opacity-30"><ChevronRight :size="14" /></button></div>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { History, RefreshCw, FolderOpen, Copy, Download, Trash2, ArchiveRestore, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import type { ComparisonJob, BatchPagination } from './types'
const props = defineProps<{jobs:ComparisonJob[];busy:boolean;error:string;loading:boolean;pagination:BatchPagination;deleted:boolean;changingId:string}>()
defineEmits<{(e:'open',id:string):void;(e:'prepare',id:string):void;(e:'refresh'):void;(e:'page',page:number):void;(e:'pageSize',size:number):void;(e:'trash',deleted:boolean):void;(e:'delete',id:string):void;(e:'restore',id:string):void}>()
const locked = computed(() => props.busy || props.loading || !!props.changingId)
const deleteTarget = ref('')
watch(() => props.jobs.map(job=>job.job_id).join('|') + props.deleted, () => { deleteTarget.value = '' })
const statusLabels={queued:'排队中',running:'进行中',completed:'已结束',failed:'已中断',cancelled:'已停止'}
</script>
