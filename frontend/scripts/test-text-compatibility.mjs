import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'

function moduleUrl(file) {
  const source = ts.transpileModule(fs.readFileSync(new URL(file, import.meta.url), 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText
  return 'data:text/javascript;base64,' + Buffer.from(source).toString('base64')
}
const compatibilityUrl = moduleUrl('../src/textCompatibility.ts')
const { textCompatibilityError, compatibleModelKeys, englishExample } = await import(compatibilityUrl)
for (const text of ['Hello.', '“Café!” 9:30, $12.50', englishExample]) {
  assert.equal(textCompatibilityError(['parler-tts-mini'], [text]), '')
}
for (const text of ['你好', 'Hello 世界', 'こんにちは', '안녕하세요', 'Привет']) {
  assert.ok(textCompatibilityError(['parler-tts-mini'], [text]))
}
assert.equal(textCompatibilityError(['chattts', 'qwen3-tts-1.7b'], ['Hello 世界']), '')
assert.ok(textCompatibilityError(['kokoro-82m', 'parler-tts-mini'], [englishExample, '你好']))
const selected = ['kokoro-82m', 'parler-tts-mini', 'chattts']
for (const texts of [['你好'], ['Hello 世界'], [englishExample, '你好']]) {
  assert.deepEqual(compatibleModelKeys(selected, texts), ['kokoro-82m', 'chattts'])
}
assert.deepEqual(compatibleModelKeys(selected, [englishExample]), selected)
assert.deepEqual(compatibleModelKeys(selected, []), selected)
assert.deepEqual(compatibleModelKeys(['kokoro-82m', 'chattts'], [englishExample]), ['kokoro-82m', 'chattts'])
assert.deepEqual(selected, ['kokoro-82m', 'parler-tts-mini', 'chattts'])
const source = ts.transpileModule(fs.readFileSync(new URL('../src/scenarios.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText
  .replace("'./textCompatibility'", JSON.stringify(compatibilityUrl))
const { scenarios } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
for (const scenario of scenarios.filter(scene => 'parler-tts-mini' in scene.candidates)) {
  assert.equal(textCompatibilityError(['parler-tts-mini'], [scenario.modelTexts?.['parler-tts-mini'] || scenario.text]), '')
}
assert.equal(scenarios.find(scene => scene.key === 'english').modelVoices['qwen3-tts-1.7b'], 'ryan')
console.log('语言兼容性、混合测试集与 Parler 场景示例检查通过。')
