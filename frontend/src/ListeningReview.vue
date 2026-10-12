<template>
  <section class="rounded-xl border border-slate-800 bg-slate-950/20 p-3">
    <button @click="expanded = !expanded" :aria-expanded="expanded" aria-label="展开或收起听感记录" class="flex w-full flex-wrap items-center gap-2 text-left">
      <ClipboardCheck :size="15" class="text-slate-400" /><span class="text-xs font-medium text-slate-300">听感记录<span class="ml-1 font-normal text-slate-500">（可选）</span></span>
      <span v-if="selectedRun" class="min-w-0 truncate text-[11px] text-slate-500">{{ selectedRun.model_name }} · 第 {{ selectedRun.repeat_index || 1 }} 次</span>
      <span class="ml-auto text-[11px]" :class="state?.dirty ? 'text-amber-300' : 'text-slate-500'">{{ state?.dirty ? '有未保存草稿' : state?.value.updated_at ? '已记录' : '未记录' }}</span>
      <ChevronRight :size="13" class="text-slate-500 transition" :class="expanded ? 'rotate-90' : ''" />
    </button>
    <div v-show="expanded" class="mt-4 space-y-4">
    <p class="chart-caption">人工记录对应这一次音频，不计入性能排名。</p>
    <label v-if="eligible.length > 1" class="flex flex-wrap items-center gap-2 text-xs text-slate-400">记录音频
      <select v-model="selectedKey" aria-label="试听记录音频" class="control-input !w-auto max-w-full"><option v-for="run in eligible" :key="run.audio_file" :value="run.audio_file">{{ run.model_name }} · {{ run.sample_label || '当前文本' }} · 第 {{ run.repeat_index || 1 }} 次</option></select>
    </label>
    <p v-if="!selectedRun" class="chart-caption">等待成功生成的音频</p>
    <template v-else>
      <details class="group text-xs text-slate-400"><summary class="flex items-center gap-1 cursor-pointer"><ChevronRight :size="12" class="group-open:rotate-90" />查看正文</summary><p class="mt-2 leading-relaxed">{{ selectedRun.text }}</p></details>
      <p v-if="state?.loading" class="chart-caption" role="status">正在读取试听记录…</p>
      <p v-if="state?.error" class="text-xs text-amber-300" role="alert">{{ state.error }} <button v-if="!state.loaded" @click="load(selectedRun)" class="text-indigo-300 underline">重新读取</button></p>
      <fieldset v-if="state" :disabled="!state.loaded || state.saving" class="space-y-4 disabled:opacity-50" @change="state.dirty = true">
        <div class="grid sm:grid-cols-3 gap-3 text-xs">
          <label class="space-y-2 block"><span class="text-slate-400">当前场景可用性</span><select v-model="state.value.verdict" aria-label="场景可用性" class="control-input"><option value="unreviewed">尚未判断</option><option value="acceptable">当前场景可用</option><option value="needs_work">需要调整或核对</option><option value="unusable">当前场景不可用</option></select></label>
          <label class="space-y-2 block"><span class="text-slate-400">自然度</span><select v-model="state.value.naturalness" aria-label="人工自然度" class="control-input"><option value="unreviewed">尚未判断</option><option value="natural">自然</option><option value="ordinary">一般</option><option value="mechanical">机械感明显</option></select></label>
          <label class="space-y-2 block"><span class="text-slate-400">表达是否合适</span><select v-model="state.value.expression" aria-label="人工表达表现" class="control-input"><option value="unreviewed">尚未判断</option><option value="appropriate">符合场景</option><option value="flat">偏平淡</option><option value="exaggerated">偏夸张</option></select></label>
        </div>
        <div class="flex flex-wrap gap-2"><label v-for="issue in reviewIssues" :key="issue.key" class="flex items-center gap-2 rounded-lg border border-slate-700/60 px-3 py-2 text-xs text-slate-300"><input v-model="state.value.issues" :value="issue.key" type="checkbox" :aria-label="`试听问题：${issue.label}`" class="accent-teal-400" />{{ issue.label }}</label></div>
        <label class="block text-xs text-slate-400 space-y-2"><span>具体片段与选型备注</span><textarea v-model="state.value.notes" @input="state.dirty = true" aria-label="试听备注" maxlength="2000" rows="3" class="control-input resize-y" placeholder="例如：第三句有重复；适合产品提示，长段落还需验证。"></textarea></label>
      </fieldset>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span class="text-[11px] text-slate-500" role="status">{{ state?.dirty ? '有未保存修改；切换页面或音频会保留草稿，刷新或关闭前请保存。' : state?.value.updated_at ? `已保存 · ${new Date(state.value.updated_at).toLocaleString('zh-CN')}` : '尚无保存记录；未勾选问题不代表内容已确认正确。' }}</span>
        <button @click="save" :disabled="!state?.loaded || state.saving || !state.dirty" class="inline-flex items-center gap-2 rounded-lg bg-teal-500/10 border border-teal-500/30 px-3 py-2 text-xs text-teal-200 disabled:opacity-40"><Loader2 v-if="state?.saving" :size="14" class="animate-spin" /><Save v-else :size="14" /> 保存试听记录</button>
      </div>
    </template>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ClipboardCheck, Loader2, Save, ChevronRight } from 'lucide-vue-next'
import type { GenerationResult, ListeningReview as Review } from './types'
import { reviewDrafts as drafts, emptyReview as empty } from './listeningReviewDrafts'
const props = defineProps<{runs:GenerationResult[]; preferredKey?:string}>()
const emit = defineEmits<{(e:'saved',run:GenerationResult,review:Review):void}>()
const reviewIssues=[{key:'omission',label:'漏字'},{key:'repetition',label:'重复'},{key:'cutoff',label:'提前结束'},{key:'pronunciation',label:'异常发音'},{key:'noise',label:'杂音'}] as const
const eligible=computed(() => props.runs.filter(run=>run.success && run.record_url))
const selectedKey=ref('')
const expanded=ref(false)
const selectedRun=computed(() => eligible.value.find(run=>run.audio_file===selectedKey.value))
const state=computed(() => drafts[selectedKey.value])
watch(() => eligible.value.map(run=>run.audio_file).join('|'), () => {
  if (!eligible.value.some(run=>run.audio_file===selectedKey.value)) selectedKey.value=eligible.value.find(run=>run.audio_file===props.preferredKey)?.audio_file || eligible.value[0]?.audio_file || ''
}, {immediate:true})
watch(() => props.preferredKey, key => { if (eligible.value.some(run=>run.audio_file===key)) selectedKey.value=key! }, {immediate:true})
watch(selectedRun, run => {
  if (run && !drafts[run.audio_file]) load(run)
  if (run && drafts[run.audio_file]?.dirty) expanded.value=true
}, {immediate:true})
watch(() => state.value?.dirty, dirty => { if (dirty) expanded.value=true })
async function load(run:GenerationResult) {
  const key=run.audio_file
  // 保存被拒绝后重新读取也不能抹掉已经输入的草稿。
  if (!drafts[key]) drafts[key]={run,value:empty(),loading:false,loaded:false,saving:false,dirty:false,error:''}
  const draft=drafts[key]
  draft.loading=true; draft.loaded=false; draft.error=''
  try {
    const response=await fetch(run.record_url+'/review'), data=await response.json()
    if (!response.ok || !data.success) throw new Error(typeof data.detail==='string' ? data.detail : '读取失败')
    if (!draft.dirty) draft.value={...empty(),...(data.data || {}),issues:[...(data.data?.issues || [])]}
    draft.loaded=true
  } catch (error) { draft.error='读取试听记录失败：'+error }
  finally { draft.loading=false }
}
async function save() {
  const run=selectedRun.value, draft=state.value
  if (!run || !draft?.loaded || draft.saving) return
  draft.saving=true; draft.error=''
  try {
    const {verdict,naturalness,expression,issues,notes}=draft.value
    const response=await fetch(run.record_url+'/review',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({verdict,naturalness,expression,issues,notes})})
    const data=await response.json()
    if (response.status===409) draft.loaded=false
    if (!response.ok || !data.success) throw new Error(typeof data.detail==='string' ? data.detail : '保存失败')
    draft.value=data.data; draft.dirty=false
    emit('saved',run,data.data)
  } catch (error) { draft.error='保存试听记录失败，草稿仍保留：'+error }
  finally { draft.saving=false }
}
</script>
