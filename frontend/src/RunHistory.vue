<template>
  <section class="glass-panel rounded-2xl p-5 space-y-4" :aria-busy="loading" aria-label="能力探索生成历史">
    <div class="flex flex-wrap justify-between items-center gap-3">
      <h3 class="section-title"><History :size="18" />{{ deleted ? '生成回收站' : '生成历史' }}<span class="text-xs font-normal text-slate-500">共 {{ pagination.total }} 条</span></h3>
      <button @click="$emit('trash',!deleted)" :disabled="locked" class="inline-flex items-center gap-1.5 text-xs text-indigo-300 disabled:opacity-40"><ArchiveRestore v-if="deleted" :size="14" /><Trash2 v-else :size="14" />{{ deleted ? '返回生成历史' : '回收站' }}</button>
    </div>
    <div class="flex justify-between items-center gap-3"><p class="chart-caption">{{ deleted ? '可恢复到生成历史。音频、参数、试听记录和原评测批次均保留。' : '试听、下载或恢复生成设置。删除仅将这条生成历史移入回收站，保留音频与原评测结果。' }}</p><button @click="$emit('refresh')" :disabled="locked" aria-label="刷新生成历史" class="text-indigo-300 disabled:opacity-40"><RefreshCw :size="16" :class="loading ? 'animate-spin' : ''" /></button></div>
    <p v-if="error" role="alert" class="text-xs text-amber-300">{{ error }}</p>
    <p v-if="loading && !runs.length" role="status" class="chart-caption">正在读取生成历史…</p>
    <p v-else-if="!error && !runs.length" class="chart-caption">{{ deleted ? '生成回收站为空。' : '暂无生成记录，生成音频后会自动保存。' }}</p>
    <div v-for="run in runs" :key="run.audio_file" class="rounded-xl border border-slate-800 bg-slate-900/40 p-3 space-y-3">
      <div class="flex flex-wrap justify-between gap-2 text-xs"><span class="font-medium text-slate-200">{{ run.model_name }}<template v-if="run.settings?.preset_label"> · {{ run.settings.preset_label }}</template></span><span class="text-slate-500">{{ run.created_at ? new Date(run.created_at).toLocaleString('zh-CN') : '' }}</span></div>
      <p class="line-clamp-2 text-xs leading-relaxed text-slate-400">{{ run.text }}</p>
      <div class="flex flex-wrap gap-4 items-center text-xs">
        <span class="text-slate-500">{{ run.metrics.audio_duration_sec }} 秒 · {{ run.evaluation ? '评测结果' : '探索结果' }}</span>
        <template v-if="!deleted">
          <button @click="$emit('play',run.audio_url)" :disabled="locked" class="inline-flex items-center gap-1 text-indigo-300 disabled:opacity-40"><Play :size="13" />试听</button>
          <button @click="$emit('prepare',run)" :disabled="locked || !run.settings" class="inline-flex items-center gap-1 text-indigo-300 disabled:opacity-40"><Copy :size="13" />恢复设置</button>
          <a :href="run.audio_url" :download="run.audio_file" class="inline-flex items-center gap-1 text-indigo-300"><Download :size="13" />下载</a>
          <button @click="deleteTarget=filename(run)" :disabled="locked" :aria-label="`删除生成记录 ${run.model_name} ${run.created_at || run.audio_file}`" class="ml-auto inline-flex items-center gap-1 text-rose-300 disabled:opacity-40"><Trash2 :size="13" />删除</button>
        </template>
        <template v-else>
          <span class="text-slate-500">删除于 {{ run.history_deleted_at ? new Date(run.history_deleted_at).toLocaleString('zh-CN') : '—' }}</span>
          <button @click="$emit('restore',filename(run))" :disabled="locked" class="inline-flex items-center gap-1 text-indigo-300 disabled:opacity-40"><ArchiveRestore :size="13" />{{ changingId===filename(run) ? '正在恢复…' : '恢复记录' }}</button>
        </template>
      </div>
      <div v-if="!deleted && deleteTarget===filename(run)" class="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3 space-y-3">
        <p class="text-xs text-slate-300">将这条生成历史移入回收站？音频、参数、试听记录和原评测结果保留，可随时恢复。</p>
        <div class="flex gap-4 text-xs"><button @click="$emit('delete',filename(run))" :disabled="locked" class="inline-flex items-center gap-1 text-rose-300 disabled:opacity-40"><Trash2 :size="13" />{{ changingId===filename(run) ? '正在删除…' : '移入回收站' }}</button><button @click="deleteTarget=''" :disabled="locked" class="text-slate-400">取消</button></div>
      </div>
    </div>
    <div class="flex flex-wrap justify-between items-center gap-3 border-t border-slate-800 pt-4 text-xs text-slate-400">
      <label class="flex gap-2 items-center">每页<select :value="pagination.page_size" @change="$emit('pageSize',Number(($event.target as HTMLSelectElement).value))" :disabled="locked" aria-label="生成历史每页数量" class="control-input !w-auto"><option v-for="size in [5,10,20,50]" :key="size" :value="size">{{ size }} 条</option></select></label>
      <div class="flex items-center gap-3"><button @click="$emit('page',pagination.page-1)" :disabled="locked || pagination.page<=1" aria-label="上一页生成历史" class="rounded-lg border border-slate-700 p-2 disabled:opacity-30"><ChevronLeft :size="14" /></button><span aria-live="polite">{{ pagination.total ? `第 ${pagination.page} / ${pagination.pages} 页` : '0 条记录' }}</span><button @click="$emit('page',pagination.page+1)" :disabled="locked || pagination.page>=pagination.pages" aria-label="下一页生成历史" class="rounded-lg border border-slate-700 p-2 disabled:opacity-30"><ChevronRight :size="14" /></button></div>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { History, Trash2, ArchiveRestore, RefreshCw, Play, Copy, Download, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import type { GenerationResult, BatchPagination } from './types'
const props=defineProps<{runs:GenerationResult[];pagination:BatchPagination;deleted:boolean;loading:boolean;error:string;changingId:string;busy:boolean}>()
defineEmits<{(e:'refresh'):void;(e:'trash',deleted:boolean):void;(e:'page',page:number):void;(e:'pageSize',size:number):void;(e:'delete',filename:string):void;(e:'restore',filename:string):void;(e:'play',url:string):void;(e:'prepare',run:GenerationResult):void}>()
const locked=computed(()=>props.busy || props.loading || !!props.changingId)
const deleteTarget=ref('')
const filename=(run:GenerationResult)=>run.audio_file.replace(/\.wav$/,'.run.json')
watch(()=>props.runs.map(run=>run.audio_file).join('|')+props.deleted,()=>{deleteTarget.value=''})
</script>
