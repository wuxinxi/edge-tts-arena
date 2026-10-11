<template>
  <div v-if="job.failed>0 && !['queued','running'].includes(job.status)" class="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-3"><h3 class="section-title text-sm text-amber-200"><RotateCcw :size="16" /> 重试失败项（{{ job.failed }}）</h3><button @click="$emit('retry',useDefault)" :disabled="busy || (job.reference_source==='uploaded' && !hasUploadedReference && !useDefault)" class="inline-flex items-center gap-2 rounded-lg border border-amber-500/30 px-3 py-2 text-xs text-amber-200 disabled:opacity-40"><RotateCcw :size="13" /> 开始重试失败项</button></div>
    <p class="chart-caption">只重试失败的场景与原轮次，沿用原文本、评测方式和输出速度；新批次保留与原批次的关联，成功音频不重复生成。实际参数另存。</p>
    <template v-if="job.reference_source==='uploaded'"><p class="text-xs text-amber-200">原批次使用上传参考。{{ hasUploadedReference ? '将使用新建评测中当前上传的参考音频，请核对素材和原文。' : '请先在新建评测中重新上传参考音频，或明确选择使用默认参考。' }}</p><label class="inline-flex gap-2 items-center text-xs text-slate-300"><input v-model="useDefault" type="checkbox" aria-label="失败重试使用默认参考音频" class="accent-amber-400" /> 本次重试改用默认参考音频（条件会改变）</label></template>
  </div>
</template>
<script setup lang="ts">
import {ref,watch} from 'vue'
import {RotateCcw} from 'lucide-vue-next'
import type {ComparisonJob} from './types'
const props=defineProps<{job:ComparisonJob;busy:boolean;hasUploadedReference:boolean}>()
defineEmits<{(e:'retry',useDefault:boolean):void}>()
const useDefault=ref(false)
watch(()=>props.job.job_id,()=>{useDefault.value=false})
</script>
