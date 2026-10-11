import type { GenerationResult } from './types'

// 只汇总已保存的人工记录，生成成功不能代替内容确认。
export function listeningSummary(results: GenerationResult[], key: string): string {
  const runs = results.filter(run => run.model_key === key && run.success)
  if (!runs.length) return '无可试听音频'
  if (runs.some(run => run.listening_review_error)) return '记录读取失败'
  const reviewed = runs.filter(run => run.listening_review && run.listening_review.verdict !== 'unreviewed')
  const issues = runs.filter(run => run.listening_review?.issues.length ||
    ['needs_work', 'unusable'].includes(run.listening_review?.verdict || ''))
  if (issues.length) return `${issues.length} 次需核对 · 已评 ${reviewed.length}/${runs.length}`
  return reviewed.length ? `${reviewed.length}/${runs.length} 已评可用` : '待试听确认'
}
