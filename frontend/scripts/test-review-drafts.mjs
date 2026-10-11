import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'

const source=ts.transpileModule(fs.readFileSync(new URL('../src/listeningReviewDrafts.ts',import.meta.url),'utf8'),
  {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText
  .replace("'vue'",JSON.stringify(import.meta.resolve('vue')))
const moduleUrl='data:text/javascript;base64,'+Buffer.from(source).toString('base64')
const {reviewDrafts,pendingReviewDrafts,emptyReview,warnBeforeLeaving}=await import(moduleUrl)
const event=()=>({prevented:false,returnValue:undefined,preventDefault(){this.prevented=true}})
let leaving=event()
warnBeforeLeaving(leaving)
assert.equal(leaving.prevented,false)
reviewDrafts['one.wav']={run:{audio_file:'one.wav'},value:emptyReview(),dirty:true}
reviewDrafts['one.wav'].value.notes='尚未保存的片段'
assert.equal(pendingReviewDrafts.value.length,1)
leaving=event(); warnBeforeLeaving(leaving)
assert.equal(leaving.prevented,true)
assert.equal(leaving.returnValue,'')
// 两个消费方读取同一模块，组件重建不会重新初始化草稿。
const secondConsumer=await import(moduleUrl)
assert.equal(secondConsumer.reviewDrafts['one.wav'].value.notes,'尚未保存的片段')
reviewDrafts['two.wav']={run:{audio_file:'two.wav'},value:emptyReview(),dirty:true}
assert.equal(pendingReviewDrafts.value.length,2)
reviewDrafts['one.wav'].dirty=false
assert.equal(pendingReviewDrafts.value.length,1)
leaving=event(); warnBeforeLeaving(leaving)
assert.equal(leaving.prevented,true)
reviewDrafts['two.wav'].dirty=false
leaving=event(); warnBeforeLeaving(leaving)
assert.equal(leaving.prevented,false)
assert.equal(pendingReviewDrafts.value.length,0)
assert.equal(emptyReview().notes,'')
assert.deepEqual(emptyReview().issues,[])
console.log('12 项草稿共享与离开提醒检查通过。')
