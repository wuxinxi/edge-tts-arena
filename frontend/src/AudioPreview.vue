<template>
  <div class="space-y-2">
    <div class="flex items-center gap-3">
      <button @click="toggle" :aria-label="`${playing ? '暂停' : '播放'}${label}`"
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-500/15 text-indigo-200 transition hover:bg-indigo-500/30">
        <Loader2 v-if="loading" :size="17" class="animate-spin" /><Pause v-else-if="playing" :size="17" /><Play v-else :size="17" class="ml-0.5" />
      </button>
      <input type="range" min="0" :max="duration || 1" step="0.01" :value="position" :disabled="!canSeek"
        @input="seek" :aria-label="`${label}播放进度`" :aria-valuetext="`${clock(position)} / ${clock(duration)}`"
        class="audio-progress min-w-0 flex-1" :style="{ '--audio-progress': `${duration ? position / duration * 100 : 0}%` }" />
      <span class="shrink-0 text-[11px] font-mono tabular-nums text-slate-400">{{ clock(position) }} <span class="text-slate-600">/</span> {{ clock(duration) }}</span>
    </div>
    <p v-if="error" role="alert" class="text-xs text-amber-300">音频未能播放，请重试或下载后试听。</p>
    <audio ref="audio" :src="src" preload="none" :aria-label="label"
      @play="started" @pause="playing = false" @ended="playing = false"
      @waiting="loading = true" @playing="loading = false" @canplay="loading = false"
      @loadedmetadata="update" @durationchange="update" @timeupdate="update" @error="failed"></audio>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Loader2, Pause, Play } from 'lucide-vue-next'
const props = defineProps<{ src: string; label: string; knownDuration: number }>()
const emit = defineEmits<{ (event: 'play'): void; (event: 'playingChange', value: boolean): void; (event: 'loadingChange', value: boolean): void }>()
const audio = ref<HTMLAudioElement | null>(null)
const playing = ref(false), loading = ref(false), error = ref(false)
const position = ref(0), measuredDuration = ref(0)
const duration = computed(() => measuredDuration.value || (Number.isFinite(props.knownDuration) ? Math.max(0, props.knownDuration) : 0))
const canSeek = computed(() => measuredDuration.value > 0)
watch(playing, value => emit('playingChange', value))
watch(loading, value => emit('loadingChange', value))
function clock(seconds: number) {
  const total = Math.floor(Math.max(0, seconds))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}
function update() {
  if (!audio.value) return
  position.value = audio.value.currentTime
  if (Number.isFinite(audio.value.duration)) measuredDuration.value = audio.value.duration
}
function started() { playing.value = true; error.value = false; emit('play') }
function failed() { error.value = true; loading.value = false; playing.value = false }
function pause() { audio.value?.pause(); loading.value = false }
async function toggle() {
  const element = audio.value
  if (!element) return
  if (playing.value || loading.value) { pause(); return }
  await play()
}
async function play() {
  const element = audio.value
  if (!element) return
  error.value = false; loading.value = true
  try { await element.play() }
  catch (reason) {
    // Switching sides can cancel a pending play; that is not a broken audio file.
    if (!(reason instanceof DOMException && reason.name === 'AbortError')) error.value = true
    loading.value = false
  }
}
function seek(event: Event) {
  if (audio.value && canSeek.value) audio.value.currentTime = Number((event.target as HTMLInputElement).value)
}
defineExpose({ pause, play, toggle })
onUnmounted(pause)
</script>
