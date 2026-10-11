<template>
  <div class="space-y-4">
    <div>
      <p class="font-medium text-indigo-200">{{ model.profile.purpose }}</p>
      <p class="mt-1 text-[11px] text-slate-500">{{ model.profile.version }}</p>
    </div>
    <div class="flex flex-wrap gap-2">
      <button v-for="item in model.profile.presets" :key="item.key" @click="$emit('preset', item.key)"
        class="rounded-lg border px-2.5 py-1.5 transition"
        :class="presetKey === item.key ? 'border-indigo-400 bg-indigo-500/20 text-indigo-200' : 'border-slate-700 text-slate-400 hover:text-white'">
        {{ item.label }}
      </button>
    </div>
    <label v-if="model.profile.voices.length > 1" class="block space-y-1.5 text-slate-400">
      <span>说话人音色</span>
      <select :value="voice" @change="$emit('update:voice', ($event.target as HTMLSelectElement).value)" class="control-input">
        <option v-for="item in model.profile.voices" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </label>
    <label v-if="['instruction', 'description'].includes(model.profile.prompt_kind) && (model.key !== 'cosyvoice3' || modelValue.mode === 'auto')" class="block space-y-1.5 text-slate-400">
      <span>{{ model.profile.prompt_kind === 'description' ? '英文声音描述' : '表达方式（可自行修改）' }}</span>
      <textarea :value="prompt" @input="$emit('update:prompt', ($event.target as HTMLTextAreaElement).value)"
        rows="2" class="control-input" :placeholder="model.profile.prompt_kind === 'description' ? 'A clear, warm female voice…' : '例如：清晰自然、精神饱满，带轻微笑意。'"></textarea>
    </label>
    <template v-for="advanced in [false, true]" :key="String(advanced)">
      <component :is="advanced ? 'details' : 'div'" class="group space-y-3" v-if="controlsFor(advanced).length">
        <summary v-if="advanced" class="cursor-pointer text-slate-400 flex items-center gap-1"><ChevronRight :size="13" class="group-open:rotate-90 transition" />高级设置 · 随机性与生成参数</summary>
        <label v-for="control in controlsFor(advanced)" :key="control.key" class="block space-y-1.5 text-slate-400">
          <span class="flex items-center justify-between gap-2">
            <span>{{ control.label }}</span>
            <input v-if="control.type === 'boolean'" type="checkbox" :checked="Boolean(modelValue[control.key])"
              @change="update(control.key, ($event.target as HTMLInputElement).checked)" class="accent-indigo-500" />
            <span v-if="control.type === 'number'" class="font-mono text-indigo-300">{{ modelValue[control.key] }}</span>
          </span>
          <select v-if="control.type === 'select'" :value="modelValue[control.key] as string | number"
            @change="selectValue(control, $event)" class="control-input">
            <option v-for="choice in choicesFor(control)" :key="String(choice.value)" :value="choice.value">{{ choice.label }}</option>
          </select>
          <input v-if="control.type === 'number'" :type="control.key === 'seed' ? 'number' : 'range'"
            :min="control.min" :max="control.max" :step="control.step" :value="modelValue[control.key] as number"
            @input="update(control.key, Number(($event.target as HTMLInputElement).value))"
            :class="control.key === 'seed' ? 'control-input' : 'w-full accent-indigo-500'" />
          <span v-if="control.help" class="block text-[11px] leading-relaxed text-slate-500">{{ control.help }}</span>
        </label>
      </component>
    </template>
    <p class="rounded-lg border border-slate-800 bg-slate-900/70 p-3 text-[11px] leading-relaxed text-slate-400">{{ model.profile.tips }}</p>
  </div>
</template>

<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'
import type { ModelItem, ModelOptions, ModelControl } from './types'
const props = defineProps<{ model: ModelItem; modelValue: ModelOptions; presetKey: string; voice: string; prompt: string }>()
const emit = defineEmits<{
  (event: 'update:modelValue', value: ModelOptions): void
  (event: 'update:voice', value: string): void
  (event: 'update:prompt', value: string): void
  (event: 'preset', value: string): void
}>()
const basic = new Set(['language', 'mode', 'refine_text', 'oral', 'laugh', 'break', 'nfe_step', 'target_duration', 'x_vector_only', 'blend_voice', 'blend_ratio'])
function controlsFor(advanced: boolean) {
  return props.model.profile.controls.filter(control => basic.has(control.key) !== advanced)
}
function update(key: string, value: string | number | boolean) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
  if (key === 'mode' && value !== 'auto') emit('update:prompt', '')
}
function choicesFor(control: ModelControl) {
  return control.key === 'blend_voice' ? control.choices?.filter(choice => !choice.value || String(choice.value)[0] === props.voice[0]) : control.choices
}
function selectValue(control: ModelControl, event: Event) {
  const selected = (event.target as HTMLSelectElement).value
  const choice = control.choices?.find(item => String(item.value) === selected)
  if (choice) update(control.key, choice.value)
}
</script>
