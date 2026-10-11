import { computed, reactive } from 'vue'
import type { GenerationResult, ListeningReview } from './types'

export type ReviewDraft = {
  run: GenerationResult
  value: ListeningReview
  loading: boolean
  loaded: boolean
  saving: boolean
  dirty: boolean
  error: string
}

// 页面级共享，组件卸载或切换批次不会清除未保存的内容；不写入评测记录。
export const reviewDrafts = reactive<Record<string, ReviewDraft>>({})
export const pendingReviewDrafts = computed(() => Object.values(reviewDrafts).filter(draft => draft.dirty))
export const emptyReview = (): ListeningReview => ({
  verdict: 'unreviewed', naturalness: 'unreviewed', expression: 'unreviewed', issues: [], notes: '',
})

export function warnBeforeLeaving(event: BeforeUnloadEvent) {
  if (!pendingReviewDrafts.value.length) return
  event.preventDefault()
  event.returnValue = ''
}
