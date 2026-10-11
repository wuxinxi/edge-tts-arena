import type { GenerationResult } from './types'
import { chartMetrics, metricValue } from './chartMetrics'
export function quantile(values: number[], fraction: number): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((a,b) => a-b)
  const index = (sorted.length-1)*fraction, low = Math.floor(index), high = Math.ceil(index)
  return sorted[low] + (sorted[high]-sorted[low])*(index-low)
}
export function modelStatistics(results: GenerationResult[], expectedRepeats: number | Record<string,number>) {
  const keys = [...new Set(results.map(result => result.model_key))]
  return keys.map(key => {
    const attempts = results.filter(result => result.model_key === key)
    const successes = attempts.filter(result => result.success && result.metrics)
    const metricStats = Object.fromEntries(chartMetrics.map(metric => {
      const values = successes.map(result => metricValue(result, metric.key)).filter((value): value is number => value !== null)
      return [metric.key, { median: quantile(values, .5), p90: quantile(values, .9), min: values.length ? Math.min(...values) : null, max: values.length ? Math.max(...values) : null, count: values.length }]
    })) as Record<typeof chartMetrics[number]['key'], {median:number|null; p90:number|null; min:number|null; max:number|null; count:number}>
    // 合成的图表行只包含各指标中位数，不指向任何一次实际音频。
    const representative = successes[0]
    const aggregate = representative ? { ...representative, metrics: { ...representative.metrics,
      ...Object.fromEntries(chartMetrics.map(metric => [metric.key, metricStats[metric.key].median])) } } as GenerationResult : null
    return { key, name: attempts[0].model_name, attempts: attempts.length, success: successes.length,
      failed: attempts.length-successes.length, expected: typeof expectedRepeats==='number' ? expectedRepeats : expectedRepeats[key] ?? attempts.length, metricStats, aggregate }
  })
}
