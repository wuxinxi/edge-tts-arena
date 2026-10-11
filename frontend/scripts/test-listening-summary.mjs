import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'

const source = ts.transpileModule(fs.readFileSync(new URL('../src/listeningSummary.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
const { listeningSummary } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
const run = (review, success = true) => ({ model_key: 'a', success, listening_review: review })
assert.equal(listeningSummary([run(undefined)], 'a'), '待试听确认')
assert.equal(listeningSummary([run(undefined, false)], 'a'), '无可试听音频')
assert.equal(listeningSummary([run({ verdict: 'acceptable', issues: [] }), run(undefined)], 'a'), '1/2 已评可用')
assert.equal(listeningSummary([run({ verdict: 'needs_work', issues: [] })], 'a'), '1 次需核对 · 已评 1/1')
// 只勾选异常、尚未判断可用性时，也必须显示问题。
assert.equal(listeningSummary([run({ verdict: 'unreviewed', issues: ['omission'] })], 'a'), '1 次需核对 · 已评 0/1')
assert.equal(listeningSummary([{ ...run(undefined), listening_review_error: '读取失败' }], 'a'), '记录读取失败')
assert.equal(listeningSummary([run({ verdict: 'acceptable', issues: [] }), { model_key: 'b', success: true }], 'a'), '1/1 已评可用')
console.log('7 项人工试听摘要检查通过。')
