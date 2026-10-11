<template>
  <div class="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
    <!-- 顶部状态栏 HUD -->
    <header class="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <AudioLines :size="24" class="text-white" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h1 class="text-lg font-bold bg-gradient-to-r from-white via-slate-200 to-indigo-200 bg-clip-text text-transparent">
                edge-tts-arena
              </h1>
              <span class="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono">
                v1.4.1
              </span>
            </div>
            <p class="text-xs text-slate-400">了解 TTS 特点与能力 · 探索适用场景</p>
          </div>
        </div>

        <!-- 硬件监控状态 -->
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <!-- 芯片型号 -->
          <div class="flex items-center gap-2 bg-slate-800/60 border border-slate-700/50 px-3 py-1.5 rounded-lg">
            <Cpu :size="14" class="text-slate-500" /><span class="text-slate-400">芯片</span>
            <span class="font-medium text-emerald-400 flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              {{ hardware?.chip || '检测中...' }}
            </span>
          </div>

          <!-- 统一内存 -->
          <div class="flex items-center gap-2 bg-slate-800/60 border border-slate-700/50 px-3 py-1.5 rounded-lg">
            <MemoryStick :size="14" class="text-slate-500" /><span class="text-slate-400">系统内存</span>
            <span class="font-mono text-slate-200">
              {{ hardware?.used_memory_gb || '--' }}G / {{ hardware?.total_memory_gb || '--' }}G
            </span>
            <div class="w-12 h-1.5 bg-slate-700 rounded-full overflow-hidden ml-1">
              <div
                class="h-full bg-indigo-500 rounded-full transition-all duration-500"
                :style="{ width: `${hardware?.memory_percent || 0}%` }"
              ></div>
            </div>
          </div>

          <!-- MPS 加速 -->
          <div class="flex items-center gap-2 bg-slate-800/60 border border-slate-700/50 px-3 py-1.5 rounded-lg">
            <Zap :size="14" class="text-slate-500" /><span class="text-slate-400">MPS</span>
            <span class="font-mono" :class="hardware?.mps?.active_device === 'mps' ? 'text-indigo-400' : 'text-amber-400'">
              {{ hardware ? (hardware.mps.mps_available ? '可用' : '不可用') : '检测中...' }}
            </span>
          </div>
        </div>
      </div>
    </header>

    <!-- 主体区域 -->
    <main class="flex-1 max-w-7xl mx-auto px-4 py-6 w-full space-y-6">
      <div v-if="errorMessage" role="alert" class="rounded-xl border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-300">{{ errorMessage }}</div>
      <div v-if="pendingReviewDrafts.length" role="status" class="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
        <p class="flex items-start gap-2 text-xs text-amber-200"><FileText :size="16" class="shrink-0" /> 有 {{ pendingReviewDrafts.length }} 条试听记录未保存。切换页面会保留草稿；刷新或关闭前请保存。</p>
        <div class="flex flex-wrap items-center gap-3 text-xs"><select v-model="pendingDraftKey" aria-label="未保存试听草稿" class="control-input !w-auto max-w-full"><option v-for="draft in pendingReviewDrafts" :key="draft.run.audio_file" :value="draft.run.audio_file">{{ draft.run.model_name }} · {{ draft.run.sample_label || '当前文本' }} · 第 {{ draft.run.repeat_index || 1 }} 次</option></select><button @click="resumeListeningDraft" :disabled="isGenerating" class="text-amber-200 disabled:opacity-50">继续编辑草稿</button></div>
      </div>
      <!-- 模式切换与简介 -->
      <div class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div class="flex flex-wrap items-center gap-2 bg-slate-900 p-1 rounded-xl border border-slate-800">
          <button
            @click="activeTab = 'scenes'" :disabled="isGenerating"
            class="px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50 flex items-center gap-2"
            :class="activeTab === 'scenes' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30' : 'text-slate-400 hover:text-white'"
          ><Compass :size="16" /> 场景选型</button>
          <button
            @click="activeTab = 'single'" :disabled="isGenerating"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2"
            :class="activeTab === 'single' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30' : 'text-slate-400 hover:text-white'"
          >
            <Search :size="16" /><span>能力探索</span>
          </button>
          <button
            @click="activeTab = 'battle'" :disabled="isGenerating"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2"
            :class="activeTab === 'battle' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30' : 'text-slate-400 hover:text-white'"
          >
            <BarChart3 :size="16" /><span>模型评测</span>
          </button>
        </div>

        <div class="text-xs text-slate-400 flex items-center gap-2">
          <span>模型池：可运行 <strong class="text-indigo-400 font-mono">{{ readyCount }}</strong> / {{ models.length }} 款</span>
        </div>
      </div>

      <div class="rounded-xl border border-indigo-500/20 bg-indigo-500/5 px-4 py-3 space-y-1">
        <p class="section-title text-sm"><Compass :size="16" class="text-indigo-300" /> 为 TTS 选型探路：了解特点，试听能力，对比实际表现。</p>
        <p class="text-xs leading-relaxed text-slate-400">先看模型能力与可探索场景，再用你的文本验证。场景建议是探索起点；评测结果对应本轮文本、参数和设备。</p>
      </div>

      <SceneGuide v-show="activeTab === 'scenes'" :models="models" :busy="isGenerating"
        @explore="exploreScenario" @compare="compareScenario" />

      <template v-if="activeTab !== 'scenes'">
      <nav v-if="activeTab === 'battle'" class="flex gap-1 rounded-xl border border-slate-800 bg-slate-900/70 p-1" aria-label="评测工作区">
        <button v-for="view in battleViews" :key="view.key" @click="battleView = view.key" :aria-pressed="battleView === view.key"
          :disabled="isGenerating && view.key !== 'results'" class="flex-1 inline-flex items-center justify-center gap-2 rounded-lg px-2 py-2.5 text-xs sm:text-sm transition disabled:opacity-40"
          :class="battleView === view.key ? 'bg-indigo-500/20 text-indigo-100' : 'text-slate-400 hover:text-white'">
          <component :is="view.icon" :size="16" />{{ view.label }}<span v-if="view.key === 'results' && isGenerating" class="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse"></span>
        </button>
      </nav>
      <div v-show="activeTab === 'single' || battleView === 'setup'" class="space-y-5">
        <div v-if="activeTab === 'battle'" class="space-y-5">
          <div><h2 class="text-lg font-semibold">新建评测</h2><p class="mt-1 text-xs text-slate-400">选择模型和测试文本，检查条件后开始。结果按场景分别比较。</p></div>
        <!-- 模型多选栏 -->
        <div class="glass-panel p-4 rounded-2xl space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span>1. 选择模型</span>
              <span class="text-indigo-400 font-mono">已选 {{ selectedBattleKeys.length }} 个</span>
            </div>
            <div class="flex items-center gap-2">
              <button @click="selectAllBattle(true)" :disabled="isGenerating" class="text-xs text-indigo-400 hover:underline">全选可运行模型</button>
              <span class="text-slate-600">|</span>
              <button @click="selectAllBattle(false)" :disabled="isGenerating" class="text-xs text-slate-400 hover:underline">清空</button>
            </div>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2.5">
            <button type="button"
              v-for="m in models"
              :key="m.key"
              @click="toggleBattleKey(m.key)"
              :aria-pressed="selectedBattleKeys.includes(m.key)" :disabled="isGenerating || !m.is_ready"
              class="p-2.5 rounded-xl border transition cursor-pointer text-left select-none relative group disabled:opacity-50"
              :class="selectedBattleKeys.includes(m.key) ? 'bg-indigo-950/40 border-indigo-500/60 shadow-sm' : 'bg-slate-900/40 border-slate-800 hover:border-slate-700'"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="font-mono text-xs font-bold text-indigo-300">{{ m.param_size }}</span>
                <span class="w-2 h-2 rounded-full" :class="m.is_ready ? 'bg-emerald-400' : 'bg-slate-600'" :title="m.unavailable_reason || '可运行'"></span>
              </div>
              <div class="font-medium text-xs text-slate-200 truncate">{{ m.name }}</div>
              <div class="text-[10px] text-slate-400 truncate" :title="m.unavailable_reason || m.category">{{ m.is_ready ? m.category : m.unavailable_reason }}</div>
            </button>
          </div>
        </div>

          <div class="flex flex-wrap items-center justify-between gap-3">
            <h2 class="section-title text-sm"><FileText :size="17" /> 2. 选择测试文本</h2>
            <div class="inline-flex rounded-lg border border-slate-700 p-1" aria-label="评测文本来源">
              <button @click="chooseEvaluationText('custom')" :disabled="isGenerating" :aria-pressed="evaluationTextMode === 'custom'" class="rounded-md px-3 py-1.5 text-xs" :class="evaluationTextMode === 'custom' ? 'bg-indigo-500/20 text-indigo-200' : 'text-slate-400'">自定义文本</button>
              <button @click="chooseEvaluationText('suite')" :disabled="isGenerating" :aria-pressed="evaluationTextMode === 'suite'" class="rounded-md px-3 py-1.5 text-xs" :class="evaluationTextMode === 'suite' ? 'bg-indigo-500/20 text-indigo-200' : 'text-slate-400'">场景测试集</button>
            </div>
          </div>
        </div>
      <!-- 统一文本输入与预设 -->
      <div v-show="activeTab === 'single' || evaluationTextMode === 'custom'" class="glass-panel p-5 rounded-2xl space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <label class="text-sm font-medium text-slate-200 flex items-center gap-2">
            <FileText :size="16" /><span>{{ activeTab === 'single' ? '体验文本' : '自定义评测文本' }}</span>
            <span class="text-xs text-slate-500 font-normal">({{ inputText.length }} 字符)</span>
          </label>
          <!-- 预设句子 -->
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs text-slate-400">示例文本:</span>
            <button
              v-for="(preset, idx) in presets"
              :key="idx"
              @click="applyPreset(preset.text)" :disabled="isGenerating"
              class="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition"
            >
              {{ preset.label }}
            </button>
          </div>
        </div>

        <div class="relative">
          <textarea
            :aria-label="activeTab === 'single' ? '体验文本' : '自定义评测文本'"
            v-model="inputText" :disabled="isGenerating"
            rows="3"
            class="w-full bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-sm resize-none"
            placeholder="输入想要合成的文本，支持中英文混读、短句或长句..."
          ></textarea>
        </div>

        <!-- 单模型参数控制 -->
        <div v-if="activeTab === 'single'" class="flex flex-wrap items-center justify-between gap-4 pt-2">
          <div class="flex items-center gap-4">
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-400">{{ speedMode === 'output' || currentModel?.profile.speed_kind === 'postprocess' ? '输出音频变速:' : currentModel?.profile.speed_kind === 'discrete' ? '说话速度档位:' : '模型说话速度:' }}</span>
              <input
                type="range"
                min="0.5"
                max="1.5"
                step="0.1"
                v-model.number="displaySpeed" :disabled="isGenerating"
                class="w-24 accent-indigo-500"
              />
              <span class="text-xs font-mono text-indigo-300">{{ displaySpeed.toFixed(1) }}x</span>
            </div>
          </div>

          <select v-if="activeTab === 'single'" v-model="speedMode" :disabled="isGenerating" aria-label="速度方式" class="control-input !w-auto text-xs">
            <option value="model">{{ currentModel?.profile.speed_kind === 'postprocess' ? '该模型使用输出变速' : '模型说话速度' }}</option>
            <option value="output">输出音频变速</option>
          </select>
          <span v-if="isGenerating" role="status" class="text-xs text-indigo-300">已等待 {{ elapsedSeconds }} 秒 · 包含模型加载</span>
          <!-- 执行按钮 -->
          <div class="flex items-center gap-3">
            <button
              v-if="activeTab === 'single'"
              @click="runSingle"
              :disabled="isGenerating || !currentModel?.is_ready || !inputText.trim()"
              class="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition shadow-lg shadow-indigo-600/30 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Loader2 v-if="isGenerating" :size="16" class="animate-spin" /><Play v-else :size="16" />
              <span>{{ isGenerating ? '正在合成中...' : '立即生成音频' }}</span>
            </button>
          </div>
        </div>
      </div>

      <EvaluationPlan v-if="activeTab === 'battle' && evaluationTextMode === 'suite'" v-model:selected-ids="evaluationIds" v-model:repeats="evaluationRepeats" :model-count="selectedBattleKeys.length" :busy="isGenerating" :saved-samples="restoredSamples" @update:selected-ids="restoredSamples = null" />
      <p v-if="activeTab === 'battle' && restoredSamples && evaluationTextMode === 'suite'" class="text-xs text-teal-200">使用历史批次保存的测试文本；重新勾选可改用当前测试集。</p>
      <div v-if="activeTab === 'battle'" class="space-y-5">
      <div class="glass-panel p-5 rounded-2xl space-y-4 text-xs">
        <h2 class="section-title text-sm"><SlidersHorizontal :size="17" /> 3. 检查评测条件</h2>
        <div class="flex flex-wrap items-center gap-3">
          <label for="benchmark-mode" class="text-slate-300">评测方式</label>
          <select id="benchmark-mode" v-model="benchmarkMode" :disabled="isGenerating" class="control-input !w-auto">
            <option value="uniform">统一条件 · 原始速度与默认音色</option>
            <option value="recommended">推荐配置 · 各模型特色预设</option>
          </select>
        </div>
        <p class="text-slate-400">{{ benchmarkMode === 'uniform' ? '使用相同文本与参考音频；模型速度固定 1.0，ChatTTS 关闭台词润色。各模型保留自己的默认算法参数。' : '使用相同文本与参考音频；Qwen 1.7B 使用清晰播报，CosyVoice 使用温暖讲述，ChatTTS 使用自然对话，其余采用默认预设。' }} 输出变速统一处理。每项结果保存实际参数；不同功能与音色的听感需分别判断。</p>
        <label v-if="evaluationTextMode === 'custom'" class="flex items-center gap-3 text-slate-400">每段文本重复
          <select v-model="evaluationRepeats" :disabled="isGenerating" aria-label="重复评测次数" class="control-input !w-auto"><option v-for="count in [1,2,3,5]" :key="count" :value="count">{{ count }} 次</option></select>
        </label>
        <details class="group border-t border-slate-800 pt-3"><summary class="section-title cursor-pointer text-xs"><ChevronRight :size="14" class="group-open:rotate-90" /> 输出变速与评测口径</summary>
          <div class="mt-3 space-y-3"><label class="flex items-center gap-3 text-slate-400">输出音频变速 <input type="range" min="0.5" max="1.5" step="0.1" v-model.number="battleSpeed" :disabled="isGenerating" class="w-24 accent-indigo-500" /><span class="font-mono text-indigo-200">{{ battleSpeed.toFixed(1) }}x</span></label>
          <p class="chart-caption">每次耗时包含进程启动与模型加载。重复生成保持默认种子，用于观察耗时波动；各场景分别比较。</p></div>
        </details>
      </div>
      <details v-if="battleReferenceModels.length" class="glass-panel p-4 rounded-2xl space-y-3 text-xs group">
        <summary class="section-title cursor-pointer"><ChevronRight :size="14" class="group-open:rotate-90" /> 参考声音 <span class="font-normal text-slate-400">{{ refAudioBase64 ? '已上传' : needsReference ? '需要重新提供' : '使用内置参考，可直接运行' }}</span></summary>
        <p class="text-slate-300">{{ battleReferenceModels.map(model => model.name).join('、') }} 未上传参考音频时，自动使用内置中文参考音频和对应文字。</p>
        <div v-if="!refAudioBase64" class="space-y-2">
          <p :class="needsReference ? 'text-amber-300' : 'text-emerald-400'">{{ needsReference ? '历史记录的上传音频尚未恢复，请重新上传或选择默认音频。' : '已启用默认参考音频，可直接开始评测。' }}</p>
          <button v-if="needsReference" @click="resetReference" :disabled="isGenerating" class="text-indigo-400 hover:underline">恢复默认参考音频</button>
          <audio controls preload="none" src="/api/reference/default" class="w-full h-8"></audio>
        </div>
        <input :key="refAudioInputKey" type="file" :disabled="isGenerating" accept="audio/*" @change="handleRefAudioUpload" class="block w-full text-slate-400" />
        <template v-if="refAudioBase64">
          <textarea v-model="refText" :disabled="isGenerating" rows="2" placeholder="请填写上传音频所说的原话（必填）" class="w-full rounded-lg border border-slate-700 bg-slate-900 p-2"></textarea>
          <button @click="resetReference" :disabled="isGenerating" class="text-indigo-400 hover:underline">恢复默认参考音频</button>
        </template>
      </details>
        <div class="rounded-2xl border border-indigo-500/30 bg-indigo-500/5 p-5 flex flex-wrap items-center justify-between gap-4">
          <div><p class="text-sm font-medium text-indigo-100">{{ selectedBattleKeys.length }} 款模型 · {{ plannedSamples.length || (evaluationTextMode === 'custom' ? 1 : 0) }} 段文本 · 每段 {{ evaluationRepeats }} 次</p><p class="mt-1 text-xs text-slate-400">共 {{ plannedGenerations }} 次生成 · {{ benchmarkMode === 'uniform' ? '统一条件' : '推荐配置' }}<span v-if="!hasEvaluationText"> · 请先选择或填写测试文本</span></p></div>
          <button @click="runBattle" :disabled="isGenerating || !selectedBattleKeys.length || !hasEvaluationText" class="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"><Loader2 v-if="isGenerating" :size="16" class="animate-spin" /><Play v-else :size="16" />开始评测 ({{ plannedGenerations }} 次生成)</button>
        </div>
      </div>
      </div>
      <div v-if="activeTab === 'battle'" class="space-y-5">
        <div v-show="battleView === 'history'"><ComparisonHistory :jobs="batchHistory" :busy="isGenerating" :error="batchHistoryError" :loading="batchHistoryLoading" :pagination="batchPagination" :deleted="batchHistoryDeleted" :changing-id="batchChangingId" @page="changeHistoryPage" @page-size="changeHistoryPageSize" @trash="changeHistoryTrash" @delete="deleteBatch" @restore="restoreBatch" @refresh="fetchBatchHistory" @open="openBatch" @prepare="prepareBatch" /></div>
        <div v-show="battleView === 'results'" class="space-y-5">
          <BatchProgress v-if="comparisonJob" :job="comparisonJob" :elapsed="elapsedSeconds" :reconnecting="reconnecting" :stopping="stopping" @stop="stopBatch" />
          <BenchmarkResults v-if="battleResults.length" :results="battleResults" :models="models" :job="comparisonJob" :busy="isGenerating" :active="activeTab === 'battle' && battleView === 'results'" :has-uploaded-reference="!!refAudioBase64" @retry="retryFailed" @review-saved="reviewSaved" @listening="nowPlayingUrl = ''" />
          <div v-else-if="!comparisonJob" class="glass-panel rounded-2xl p-10 text-center space-y-3"><BarChart3 :size="28" class="mx-auto text-indigo-300" /><h2 class="text-base font-medium">还没有打开的评测结果</h2><p class="text-xs text-slate-400">新建一次评测，或从历史批次中查看已有结果。</p><button @click="battleView = 'history'" class="text-sm text-indigo-300">查看历史批次</button></div>
        </div>
      </div>
      <!-- 模式 B: 单模型控制台 (Playground) -->
      <div v-if="activeTab === 'single'" class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- 左侧模型选择与参数 -->
        <div class="md:col-span-1 space-y-4">
          <div class="glass-panel p-4 rounded-2xl space-y-3">
            <label for="studio-model" class="text-xs font-medium text-slate-300">选择体验模型</label>
            <select id="studio-model" v-model="currentModelKey" :disabled="isGenerating" class="control-input text-xs">
              <option v-for="model in models" :key="model.key" :value="model.key">{{ model.name }} · {{ model.param_size }}{{ model.is_ready ? '' : ' · 未就绪' }}</option>
            </select>
            <p class="text-xs leading-relaxed text-slate-400">{{ currentModel?.desc }}</p>
            <div v-if="currentModel" class="space-y-3 border-t border-slate-800 pt-3">
              <div>
                <p class="text-xs font-medium text-slate-300">可探索场景</p>
                <div class="mt-2 flex flex-wrap gap-1.5">
                  <span v-for="scene in currentModel.profile.scenarios" :key="scene" class="rounded-md border border-indigo-500/20 bg-indigo-500/10 px-2 py-1 text-[11px] text-indigo-200">{{ scene }}</span>
                </div>
              </div>
              <p class="text-xs leading-relaxed text-slate-400"><span class="text-slate-300">试听重点：</span>{{ currentModel.profile.listen_for }}</p>
              <a :href="currentModel.profile.source_url" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-xs text-indigo-400 hover:underline">官方能力资料 <ExternalLink :size="12" /></a>
            </div>
            <p v-if="currentModel && !currentModel.is_ready" class="text-xs text-amber-300">{{ currentModel.unavailable_reason }}</p>
          </div>

          <!-- 音色与 Prompt 扩展参数 -->
          <div v-if="currentModel" class="glass-panel p-4 rounded-2xl space-y-3 text-xs">
            <fieldset :disabled="isGenerating" class="space-y-3 disabled:opacity-60">
              <ModelControls :model="currentModel" v-model="modelOptions" :preset-key="selectedPreset"
                v-model:voice="selectedVoice" v-model:prompt="promptText" @preset="applyModelPreset" />
            </fieldset>

            <div v-if="currentModel.supports_clone" class="space-y-3 pt-2 border-t border-slate-800">
              <div class="font-medium text-slate-300">参考声音</div>
              <p v-if="needsReference" class="text-amber-300">这条历史记录使用了上传音频，请重新上传同一素材，或点击恢复默认参考音频。</p>
              <div>
                <label class="text-slate-400 block mb-1">上传参考音频 (wav/mp3，选填):</label>
                <input
                  :key="refAudioInputKey"
                  type="file" :disabled="isGenerating"
                  accept="audio/*"
                  @change="handleRefAudioUpload"
                  class="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-600/20 file:text-indigo-400 hover:file:bg-indigo-600/30"
                />
              </div>
              <div v-if="!refAudioBase64" class="space-y-2">
                <p :class="needsReference ? 'text-amber-300' : 'text-emerald-400'">{{ needsReference ? '等待恢复参考素材。' : currentModel.requires_reference_audio ? '已启用默认参考音频，可直接生成。' : '未上传时使用模型默认音色。' }}</p>
                <button v-if="needsReference" @click="resetReference" :disabled="isGenerating" class="text-indigo-400 hover:underline">恢复默认参考音频</button>
                <audio v-if="currentModel.requires_reference_audio" controls preload="none" src="/api/reference/default" class="w-full h-8"></audio>
              </div>
              <audio v-if="refAudioBase64" :src="refAudioBase64" controls class="w-full h-8"></audio>
              <div v-if="refAudioBase64">
                <label class="text-slate-400 block mb-1">参考音频原文{{ requiresRefText ? '（必填）' : '（当前模式可不填写）' }}:</label>
                <textarea
                  v-model="refText" :disabled="isGenerating"
                  rows="2"
                  class="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 text-slate-200 resize-none"
                  placeholder="请输入上述参考音频所说的原话文字内容..."
                ></textarea>
                <button @click="resetReference" :disabled="isGenerating" class="mt-2 text-indigo-400 hover:underline">{{ currentModel.requires_reference_audio ? '恢复默认参考音频' : '清除参考音频' }}</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧单个生成面板与试听 -->
        <div class="md:col-span-2 space-y-4">
          <div v-if="singleResult" class="glass-panel p-6 rounded-2xl space-y-5">
            <div class="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 class="text-lg font-bold text-slate-100">{{ singleResult.model_name }}</h3>
                <p class="text-xs text-slate-400 font-mono">参数量: {{ singleResult.param_size }} · 采样率: {{ singleResult.sample_rate }}Hz · 推理设备: {{ singleResult.device }}</p>
              </div>
              <div class="text-right">
                <div class="text-xs text-slate-400">实时率 (RTF)</div>
                <div class="text-xl font-bold font-mono" :class="getRTFColor(singleResult.metrics?.rtf)">{{ singleResult.metrics?.rtf }}x</div>
              </div>
            </div>

            <!-- 音频播放卡片 -->
            <div class="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-3">
              <div class="flex items-center justify-between text-xs text-slate-400">
                <span>生成音频试听</span>
                <span>时长: {{ singleResult.metrics?.audio_duration_sec }}s</span>
              </div>
              <audio :src="singleResult.audio_url" controls class="w-full accent-indigo-500"></audio>
              <div class="flex gap-4">
                <a :href="singleResult.audio_url" :download="singleResult.audio_file" class="inline-flex items-center gap-1 text-indigo-300 hover:underline"><Download :size="14" />下载音频</a>
                <a v-if="singleResult.record_url" :href="singleResult.record_url" class="inline-flex items-center gap-1 text-indigo-300 hover:underline"><FileText :size="14" />导出生成参数</a>
              </div>
            </div>

            <p class="text-xs text-slate-400">离线请求耗时包含模型加载；首包延迟尚未测量。采样进程内存峰值：{{ singleResult.metrics?.memory_peak_mb }} MB（包含推理子进程，每 50ms 采样，非显存）。</p>
            <details v-if="singleResult.settings" class="group rounded-xl border border-slate-800 p-3 text-xs text-slate-400">
              <summary class="cursor-pointer flex items-center gap-1"><ChevronRight :size="13" class="group-open:rotate-90 transition" />本次使用：{{ singleResult.settings.preset_label }} · {{ singleResult.voice }} · {{ singleResult.settings.speed }}x {{ singleResult.settings.speed_kind === 'postprocess' ? '输出变速' : '模型速度' }}</summary>
              <p class="mt-3">{{ singleResult.settings.version }} · {{ singleResult.settings.reference.source === 'uploaded' ? '上传参考音频' : singleResult.settings.reference.source === 'default' ? '默认参考音频' : '预置音色' }}</p>
              <p v-if="singleResult.settings.prompt" class="mt-2">表达指令：{{ singleResult.settings.prompt }}</p>
              <pre class="mt-3 whitespace-pre-wrap break-all text-[11px]">{{ JSON.stringify(singleResult.settings.effective_options && Object.keys(singleResult.settings.effective_options).length ? singleResult.settings.effective_options : singleResult.settings.options, null, 2) }}</pre>
            </details>
            <!-- 详细性能指标网格 -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div class="bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                <span class="text-slate-400 block">生成总耗时</span>
                <span class="text-base font-bold font-mono text-slate-200">{{ singleResult.metrics?.elapsed_time_sec }}s</span>
              </div>
              <div class="bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                <span class="text-slate-400 block">首包延迟 (TTFB)</span>
                <span class="text-base font-bold font-mono text-indigo-400">{{ singleResult.metrics?.ttfb_ms || '--' }} ms</span>
              </div>
              <div class="bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                <span class="text-slate-400 block">音频时长</span>
                <span class="text-base font-bold font-mono text-slate-200">{{ singleResult.metrics?.audio_duration_sec }}s</span>
              </div>
              <div class="bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                <span class="text-slate-400 block">实时率 (RTF)</span>
                <span class="text-base font-bold font-mono" :class="getRTFColor(singleResult.metrics?.rtf)">{{ singleResult.metrics?.rtf }}x</span>
              </div>
            </div>
          </div>

          <div v-else class="glass-panel p-12 rounded-2xl text-center text-slate-500 space-y-3">
            <div class="w-12 h-12 rounded-full bg-slate-900 mx-auto flex items-center justify-center text-slate-400"><AudioLines :size="24" /></div>
            <p class="text-sm">在上方输入文本并点击“立即生成音频”开始体验</p>
          </div>
          <ListeningReview v-if="singleResult" id="single-listening-review" :runs="[singleResult]" @saved="reviewSaved" />
          <RunHistory :runs="runHistory" :pagination="runPagination" :deleted="runHistoryDeleted" :loading="runHistoryLoading" :error="runHistoryError" :changing-id="runChangingId" :busy="isGenerating" @refresh="fetchHistory()" @page="fetchHistory" @page-size="size => fetchHistory(1,size)" @trash="changeRunHistoryTrash" @delete="filename => changeRunDeleted(filename,true)" @restore="filename => changeRunDeleted(filename,false)" @play="playAudio" @prepare="restoreRun" />
        </div>
      </div>
      </template>
    </main>

    <!-- 底部全局播放器 -->
    <div v-if="nowPlayingUrl" class="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 glass-panel px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-4 border border-indigo-500/30">
      <AudioLines :size="20" class="text-indigo-300" />
      <audio ref="globalAudio" :src="nowPlayingUrl" autoplay controls class="h-8 accent-indigo-500"></audio>
      <button @click="nowPlayingUrl = ''" aria-label="关闭试听播放器" class="text-slate-400 hover:text-white"><X :size="16" /></button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import ModelControls from './ModelControls.vue'
import SceneGuide from './SceneGuide.vue'
import BenchmarkResults from './BenchmarkResults.vue'
import EvaluationPlan from './EvaluationPlan.vue'
import ComparisonHistory from './ComparisonHistory.vue'
import RunHistory from './RunHistory.vue'
import { evaluationSamples } from './evaluationSamples'
import BatchProgress from './BatchProgress.vue'
import ListeningReview from './ListeningReview.vue'
import { reviewDrafts, pendingReviewDrafts, warnBeforeLeaving } from './listeningReviewDrafts'
import { AudioLines, Compass, Search, BarChart3, FileText, Loader2, Play, Download, ExternalLink, X, ChevronRight, Cpu, MemoryStick, Zap, Info, History, Plus, SlidersHorizontal } from 'lucide-vue-next'
import type { ScenarioExperiment } from './scenarios'
import type { ModelItem, HardwareInfo, GenerationResult, ModelOptions, ComparisonJob, BatchPagination, ListeningReview as Review } from './types'

const hardware = ref<HardwareInfo | null>(null)
const models = ref<ModelItem[]>([])
const activeTab = ref<'battle' | 'single' | 'scenes'>('scenes')
const battleView = ref<'setup' | 'results' | 'history'>('setup')
const battleViews = [{key:'setup',label:'新建评测',icon:Plus},{key:'results',label:'评测结果',icon:BarChart3},{key:'history',label:'历史批次',icon:History}] as const
const evaluationTextMode = ref<'custom' | 'suite'>('custom')
function chooseEvaluationText(mode: 'custom' | 'suite') {
  evaluationTextMode.value = mode
  if (mode === 'custom') { evaluationIds.value = []; restoredSamples.value = null }
}
const inputText = ref('欢迎使用语音助手。您的订单预计明天下午三点送达，请留意通知。')
const speed = ref(1.0)
const battleSpeed = ref(1.0)
const speedMode = ref<'model' | 'output'>('model')
const displaySpeed = computed({ get: () => activeTab.value === 'single' ? speed.value : battleSpeed.value,
  set: value => { if (activeTab.value === 'single') speed.value = value; else battleSpeed.value = value } })
const evaluationIds = ref<string[]>([])
const evaluationRepeats = ref(1)
const restoredSamples = ref<import('./types').EvaluationSample[] | null>(null)
const batchHistory = ref<ComparisonJob[]>([])
const batchHistoryError = ref('')
const batchHistoryLoading = ref(false)
const batchHistoryDeleted = ref(false)
const batchChangingId = ref('')
const batchPagination = ref<BatchPagination>({total:0,page:1,page_size:5,pages:0})
let historyRequest = 0
const plannedSamples = computed(() => evaluationTextMode.value === 'custom' ? [] : restoredSamples.value || evaluationSamples.filter(sample => evaluationIds.value.includes(sample.id)))
const hasEvaluationText = computed(() => evaluationTextMode.value === 'suite' ? plannedSamples.value.length > 0 : !!inputText.value.trim())
const plannedGenerations = computed(() => selectedBattleKeys.value.length * (plannedSamples.value.length || (evaluationTextMode.value === 'custom' ? 1 : 0)) * evaluationRepeats.value)
const benchmarkMode = ref<'uniform' | 'recommended'>('uniform')
const selectedPreset = ref('default')
const modelOptions = ref<ModelOptions>({})
const runHistory = ref<GenerationResult[]>([])
const runPagination = ref<BatchPagination>({total:0,page:1,page_size:5,pages:0})
const runHistoryDeleted = ref(false)
const runHistoryLoading = ref(false)
const runHistoryError = ref('')
const runChangingId = ref('')
let runHistoryRequest = 0
const needsReference = ref(false)
const elapsedSeconds = ref(0)
let startedAt = 0
let clockTimer: ReturnType<typeof setInterval> | undefined
let progressTimer: ReturnType<typeof setTimeout> | undefined
let progressFailures = 0
let disposed = false
const comparisonJob = ref<ComparisonJob | null>(null)
const reconnecting = ref(false)
const stopping = ref(false)
const activeJobStorageKey = 'edge-tts-arena:comparison-job'

const isGenerating = ref(false)

// 擂台模式选中的模型
const selectedBattleKeys = ref<string[]>([])
const battleResults = ref<GenerationResult[]>([])

// 单模型模式
const currentModelKey = ref('')
const selectedVoice = ref('default')
const promptText = ref('')
const refAudioBase64 = ref('')
const refText = ref('')
const refAudioInputKey = ref(0)
const singleResult = ref<GenerationResult | null>(null)

// 全局播放
const nowPlayingUrl = ref('')
const globalAudio = ref<HTMLAudioElement | null>(null)

const currentModel = computed(() => models.value.find(m => m.key === currentModelKey.value))
const battleReferenceModels = computed(() => models.value.filter(model =>
  selectedBattleKeys.value.includes(model.key) && model.requires_reference_audio))
const requiresRefText = computed(() => !modelOptions.value.x_vector_only && modelOptions.value.mode !== 'cross_lingual')
const readyCount = computed(() => models.value.filter(m => m.is_ready).length)
const errorMessage = ref('')
const pendingDraftKey = ref('')
watch(pendingReviewDrafts, drafts => {
  if (!drafts.some(draft => draft.run.audio_file === pendingDraftKey.value)) pendingDraftKey.value = drafts[0]?.run.audio_file || ''
})
watch(() => pendingReviewDrafts.value.length > 0, pending => {
  if (pending) window.addEventListener('beforeunload', warnBeforeLeaving)
  else window.removeEventListener('beforeunload', warnBeforeLeaving)
})
async function resumeListeningDraft() {
  const draft = reviewDrafts[pendingDraftKey.value]
  if (isGenerating.value || !draft) return
  await restoreRun(draft.run)
  await nextTick()
  document.getElementById('single-listening-review')?.scrollIntoView({behavior:'smooth', block:'center'})
}

async function exploreScenario(experiment: ScenarioExperiment) {
  const model = models.value.find(item => item.key === experiment.modelKey)
  if (isGenerating.value || !model?.is_ready) return
  currentModelKey.value = model.key
  activeTab.value = 'single'
  await nextTick()
  applyModelPreset(experiment.preset)
  selectedVoice.value = model.profile.voices[0]?.value || 'default'
  modelOptions.value = { ...modelOptions.value, ...experiment.options }
  inputText.value = experiment.text
  speed.value = 1
  speedMode.value = 'model'
  singleResult.value = null
  nowPlayingUrl.value = ''
  errorMessage.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function compareScenario(selection: { keys: string[]; text: string }) {
  if (isGenerating.value) return
  const ready = selection.keys.filter(key => models.value.some(model => model.key === key && model.is_ready))
  if (!ready.length) return
  selectedBattleKeys.value = ready
  inputText.value = selection.text
  battleSpeed.value = 1
  benchmarkMode.value = 'uniform'
  battleResults.value = []
  comparisonJob.value = null
  evaluationIds.value = []
  restoredSamples.value = null
  evaluationRepeats.value = 1
  errorMessage.value = ''
  activeTab.value = 'battle'
  battleView.value = 'setup'
  evaluationTextMode.value = 'custom'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function validMemory(value?: number): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

function formatMemory(value?: number): string {
  if (!validMemory(value)) return '--'
  return value >= 1024 ? `${(value / 1024).toFixed(2)} GB` : `${value.toFixed(1)} MB`
}

// 预设评测文本库
const presets = [
  {
    label: '英文朗读',
    text: 'Hello, this is a test of speech synthesis. Have a wonderful day.'
  },
  {
    label: '日常对话',
    text: '小爱同学，今天天气怎么样？'
  },
  {
    label: '中英混读',
    text: '今天的代码已经 push 到 GitHub 仓库了，请用 Vite 和 Docker 重新构建我们的 TTS 项目。'
  },
  {
    label: '长句与多音字',
    text: '重阳节的重复练习非常重要，随着大语言模型和流匹配技术的发展，端侧语音合成的自然度已经无限逼近真人。'
  }
]

function handleRefAudioUpload(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) {
    refAudioBase64.value = ''
    return
  }
  const reader = new FileReader()
  reader.onload = (e) => {
    if (e.target?.result) {
      refAudioBase64.value = e.target.result as string
      needsReference.value = false
    }
  }
  reader.readAsDataURL(file)
}

function applyPreset(text: string) {
  inputText.value = text
}

function toggleBattleKey(key: string) {
  if (isGenerating.value) return
  if (!models.value.find(model => model.key === key)?.is_ready) return
  const idx = selectedBattleKeys.value.indexOf(key)
  if (idx > -1) {
    selectedBattleKeys.value.splice(idx, 1)
  } else {
    selectedBattleKeys.value.push(key)
  }
}

function selectAllBattle(select: boolean) {
  if (isGenerating.value) return
  if (select) {
    selectedBattleKeys.value = models.value.filter(m => m.is_ready).map(m => m.key)
  } else {
    selectedBattleKeys.value = []
  }
}

function getRTFColor(rtf?: number) {
  if (!rtf) return 'text-slate-300'
  if (rtf < 0.2) return 'text-emerald-400'
  if (rtf < 0.5) return 'text-indigo-400'
  return 'text-amber-400'
}

function playAudio(url: string) {
  nowPlayingUrl.value = url
  if (globalAudio.value) {
    globalAudio.value.play().catch(() => {})
  }
}

// 获取系统与模型列表
async function fetchData() {
  try {
    const sysRes = await fetch('/api/system')
    const sysData = await sysRes.json()
    if (sysData.success) hardware.value = sysData.data

    const modelsRes = await fetch('/api/models')
    const modelsData = await modelsRes.json()
    if (modelsData.success) {
      models.value = modelsData.data
      const ready = models.value.filter(model => model.is_ready)
      selectedBattleKeys.value = ready.map(model => model.key)
      currentModelKey.value = ready[0]?.key || models.value[0]?.key || ''
    }
  } catch (e) {
    errorMessage.value = '获取模型和系统信息失败: ' + e
  }
}

// 运行擂台多模型对决
function rememberJob(id: string | null) {
  try { if (id) localStorage.setItem(activeJobStorageKey, id); else localStorage.removeItem(activeJobStorageKey) } catch { /* 浏览器禁用本地存储时仍可正常评测。 */ }
}

function acceptProgress(job: ComparisonJob) {
  comparisonJob.value = job
  battleResults.value = job.results
  const active = job.status === 'queued' || job.status === 'running'
  isGenerating.value = active
  startedAt = Date.parse(job.created_at) || Date.now()
  elapsedSeconds.value = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
  if (active) rememberJob(job.job_id)
  else {
    rememberJob(null)
    if (job.error) errorMessage.value = job.error
    fetchHistory()
    fetchBatchHistory()
  }
}

async function pollComparison(id: string) {
  if (disposed) return
  try {
    const response = await fetch(`/api/tts/compare/jobs/${id}`)
    const data = await response.json()
    if (!response.ok) {
      if (response.status === 404) {
        errorMessage.value = apiError(data)
        isGenerating.value = false
        reconnecting.value = false
        rememberJob(null)
        return
      }
      throw new Error(apiError(data))
    }
    if (disposed) return
    progressFailures = 0
    reconnecting.value = false
    acceptProgress(data.data)
  } catch {
    progressFailures += 1
    reconnecting.value = true
  }
  if (!disposed && isGenerating.value) progressTimer = setTimeout(() => pollComparison(id), Math.min(5000, 1000 * (1 + progressFailures)))
}

async function stopBatch() {
  const job = comparisonJob.value
  if (!job || !['queued','running'].includes(job.status) || stopping.value || job.stop_requested) return
  stopping.value = true
  try {
    const response = await fetch(`/api/tts/compare/jobs/${job.job_id}/stop`, {method:'POST'})
    const data = await response.json()
    if (!response.ok || !data.success) throw new Error(apiError(data))
    if (comparisonJob.value?.job_id===job.job_id) {
      if (data.data.completed >= comparisonJob.value.completed) acceptProgress(data.data)
      else comparisonJob.value.stop_requested = true
    }
  } catch (error) { errorMessage.value = '停止请求失败，评测仍继续：' + error }
  finally { stopping.value = false }
}

async function retryFailed(useDefault: boolean) {
  const previous = comparisonJob.value
  if (!previous || isGenerating.value || !previous.failed) return
  if (previous.reference_source==='uploaded' && !useDefault && refAudioBase64.value && !refText.value.trim()) {
    errorMessage.value = '请填写当前上传参考音频的原话，或明确选择使用默认参考。'
    return
  }
  errorMessage.value = ''
  isGenerating.value = true
  try {
    const response = await fetch(`/api/comparisons/${previous.job_id}/retry`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({use_default_reference:useDefault,
        ref_audio:previous.reference_source==='uploaded' && !useDefault ? refAudioBase64.value || undefined : undefined,
        ref_text:previous.reference_source==='uploaded' && !useDefault ? refText.value || undefined : undefined})
    })
    const data = await response.json()
    if (!response.ok || !data.success) throw new Error(apiError(data))
    battleView.value = 'results'
    reconnecting.value = false; progressFailures = 0
    acceptProgress(data.data)
    if (isGenerating.value) pollComparison(data.data.job_id)
  } catch (error) { isGenerating.value = false; errorMessage.value = '失败项重试未启动：' + error }
}

function reviewSaved(run:GenerationResult, review:Review) {
  for (const result of [...battleResults.value,...runHistory.value]) {
    if (result.audio_file===run.audio_file) result.listening_review = review
  }
  if (singleResult.value?.audio_file===run.audio_file) singleResult.value.listening_review = review
}

async function runBattle() {
  if (isGenerating.value || selectedBattleKeys.value.length === 0 || !hasEvaluationText.value) return
  errorMessage.value = ''
  if (needsReference.value && battleReferenceModels.value.length) {
    errorMessage.value = '请重新上传参考音频，或明确恢复默认参考音频。'
    return
  }
  if (refAudioBase64.value && !refText.value.trim() && models.value.some(model =>
    selectedBattleKeys.value.includes(model.key) && model.supports_clone)) {
    errorMessage.value = '请填写上传参考音频所说的原话，或恢复默认参考音频。'
    return
  }
  isGenerating.value = true
  startedAt = Date.now()
  elapsedSeconds.value = 0
  battleResults.value = []
  comparisonJob.value = null
  reconnecting.value = false
  progressFailures = 0
  try {
    const response = await fetch('/api/tts/compare/jobs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_keys: [...selectedBattleKeys.value], text: inputText.value,
        speed: battleSpeed.value, speed_mode: 'output', benchmark_mode: benchmarkMode.value,
        samples: plannedSamples.value, repeats: evaluationRepeats.value,
        ref_audio: refAudioBase64.value || undefined, ref_text: refText.value || undefined })
    })
    const data = await response.json()
    if (!response.ok || !data.success) throw new Error(apiError(data))
    acceptProgress(data.data)
    battleView.value = 'results'
    window.scrollTo({ top: 0, behavior: 'smooth' })
    if (isGenerating.value) pollComparison(data.data.job_id)
  } catch (error) {
    isGenerating.value = false
    errorMessage.value = '评测提交失败：' + error
  }
}

async function resumeComparison() {
  let id: string | null = null
  try { id = localStorage.getItem(activeJobStorageKey) } catch { return }
  if (!id) return
  activeTab.value = 'battle'
  battleView.value = 'results'
  isGenerating.value = true
  await pollComparison(id)
  const job = comparisonJob.value
  if (job) restoreBatchPlan(job)
}

// 运行单个模型生成
async function runSingle() {
  if (!currentModelKey.value || !inputText.value || !currentModel.value?.is_ready) return
  errorMessage.value = ''
  singleResult.value = null
  nowPlayingUrl.value = ''
  if (currentModel.value.supports_clone && needsReference.value) {
    errorMessage.value = '请重新上传历史记录的参考音频，或明确恢复默认参考音频。'
    return
  }
  if (currentModel.value?.supports_clone && requiresRefText.value && refAudioBase64.value && !refText.value.trim()) {
    errorMessage.value = '请填写上传参考音频所说的原话，或恢复默认参考音频。'
    return
  }
  isGenerating.value = true
  startedAt = Date.now()
  elapsedSeconds.value = 0

  try {
    const res = await fetch('/api/tts/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_key: currentModelKey.value,
        text: inputText.value,
        voice: selectedVoice.value,
        speed: speed.value,
        prompt: promptText.value,
        preset: selectedPreset.value,
        options: modelOptions.value,
        speed_mode: speedMode.value,
        ref_audio: currentModel.value?.supports_clone ? refAudioBase64.value : undefined,
        ref_text: currentModel.value?.supports_clone ? refText.value : undefined
      })
    })
    const data = await res.json()
    if (data.success) {
      singleResult.value = data.data
      playAudio(data.data.audio_url)
      runHistoryDeleted.value = false
      await fetchHistory(1)
    } else {
      errorMessage.value = apiError(data)
    }
  } catch (e) {
    errorMessage.value = '生成失败: ' + e
  } finally {
    isGenerating.value = false
  }
}

function apiError(data: { detail?: unknown; error?: string }): string {
  return typeof data.detail === 'string' ? data.detail : data.error || JSON.stringify(data.detail || '请求失败')
}

function resetReference() {
  refAudioBase64.value = ''
  refText.value = ''
  needsReference.value = false
  refAudioInputKey.value += 1
  errorMessage.value = ''
}

watch(currentModel, model => {
  selectedVoice.value = model?.default_voices[0] || 'default'
  singleResult.value = null
  nowPlayingUrl.value = ''
  applyModelPreset(model?.profile.exploration_preset || 'default')
})

watch(selectedVoice, voice => {
  const blend = modelOptions.value.blend_voice
  if (typeof blend === 'string' && blend && blend[0] !== voice[0]) modelOptions.value = { ...modelOptions.value, blend_voice: '' }
})


function applyModelPreset(key: string) {
  const model = currentModel.value
  const preset = model?.profile.presets.find(item => item.key === key)
  if (!model || !preset) return
  selectedPreset.value = key
  modelOptions.value = Object.fromEntries(model.profile.controls.map(control => [control.key, control.default]))
  modelOptions.value = { ...modelOptions.value, ...preset.options }
  promptText.value = preset.prompt
}

async function fetchBatchHistory(page=batchPagination.value.page, pageSize=batchPagination.value.page_size) {
  const request = ++historyRequest
  batchHistoryLoading.value = true
  try {
    const response = await fetch(`/api/comparisons?page=${page}&limit=${pageSize}&deleted=${batchHistoryDeleted.value}`)
    const data = await response.json()
    if (request !== historyRequest || disposed) return
    if (!response.ok || !data.success) throw new Error(apiError(data))
    batchHistory.value = data.data
    batchPagination.value = data.pagination
    batchHistoryError.value = ''
  } catch { if (request === historyRequest) batchHistoryError.value = '读取评测批次失败，请点击刷新重试。' }
  finally { if (request === historyRequest) batchHistoryLoading.value = false }
}
function changeHistoryPage(page:number) { fetchBatchHistory(page) }
function changeHistoryPageSize(size:number) { fetchBatchHistory(1,size) }
function changeHistoryTrash(deleted:boolean) { batchHistoryDeleted.value=deleted; batchHistory.value=[]; batchPagination.value={...batchPagination.value,total:0,page:1,pages:0}; changeHistoryPage(1) }
async function changeBatchDeleted(id:string, deleted:boolean) {
  if (isGenerating.value || batchChangingId.value) return
  batchChangingId.value=id
  batchHistoryError.value=''
  try {
    const response=await fetch(`/api/comparisons/${id}${deleted ? '' : '/restore'}`, {method:deleted ? 'DELETE' : 'POST'})
    const data=await response.json()
    if (!response.ok || !data.success) throw new Error(apiError(data))
    if (deleted && comparisonJob.value?.job_id === id) {
      comparisonJob.value=null; battleResults.value=[]
    }
    await fetchBatchHistory()
  } catch (error) { batchHistoryError.value=(deleted ? '删除' : '恢复')+'批次失败：'+error }
  finally { batchChangingId.value='' }
}
function deleteBatch(id:string) { return changeBatchDeleted(id, true) }
function restoreBatch(id:string) { return changeBatchDeleted(id, false) }

async function loadBatch(id: string) {
  const response = await fetch(`/api/tts/compare/jobs/${id}`)
  const data = await response.json()
  if (!response.ok || !data.success) throw new Error(apiError(data))
  return data.data as ComparisonJob
}

function restoreBatchPlan(job: ComparisonJob) {
  selectedBattleKeys.value = (job.model_keys || [...new Set(job.models.map(model => model.model_key || model.key))])
    .filter(key => models.value.some(model => model.key === key && model.is_ready))
  inputText.value = job.text
  battleSpeed.value = job.speed
  benchmarkMode.value = job.benchmark_mode
  evaluationRepeats.value = job.repeats || 1
  evaluationIds.value = (job.samples || []).filter(sample => evaluationSamples.some(item => item.id === sample.id)).map(sample => sample.id)
  evaluationTextMode.value = job.samples?.some(sample => sample.id !== 'custom') ? 'suite' : 'custom'
  restoredSamples.value = job.samples?.some(sample => sample.id !== 'custom') ? job.samples : null
  resetReference()
  if (job.reference_source === 'uploaded') {
    needsReference.value = true
    refText.value = job.ref_text || job.results.find(run => run.settings?.reference.source === 'uploaded')?.settings?.reference.text || ''
  }
}

async function openBatch(id: string) {
  if (isGenerating.value) return
  try {
    const job = await loadBatch(id)
    errorMessage.value = ''
    activeTab.value = 'battle'
    battleView.value = 'results'
    acceptProgress(job)
    window.scrollTo({ top: 0, behavior: 'smooth' })
    if (isGenerating.value) pollComparison(id)
  } catch (error) { errorMessage.value = '读取批次失败：' + error }
}

async function prepareBatch(id: string) {
  if (isGenerating.value) return
  try {
    const job = await loadBatch(id)
    restoreBatchPlan(job)
    battleView.value = 'setup'
    errorMessage.value = selectedBattleKeys.value.length ? '' : '该批次模型当前均未就绪，请选择已有模型。'
    activeTab.value = 'battle'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (error) { errorMessage.value = '恢复设置失败：' + error }
}

async function fetchHistory(page=runPagination.value.page, pageSize=runPagination.value.page_size) {
  const request=++runHistoryRequest
  runHistoryLoading.value=true
  try {
    const response=await fetch(`/api/runs?page=${page}&limit=${pageSize}&deleted=${runHistoryDeleted.value}`)
    const data=await response.json()
    if (request!==runHistoryRequest || disposed) return
    if (!response.ok || !data.success) throw new Error(apiError(data))
    runHistory.value=data.data
    runPagination.value=data.pagination
    runHistoryError.value=''
  } catch (error) { if (request===runHistoryRequest && !disposed) runHistoryError.value='读取生成历史失败：'+error }
  finally { if (request===runHistoryRequest) runHistoryLoading.value=false }
}
function changeRunHistoryTrash(deleted:boolean) {
  runHistoryDeleted.value=deleted
  runHistory.value=[]
  runPagination.value={...runPagination.value,total:0,page:1,pages:0}
  fetchHistory(1)
}
async function changeRunDeleted(filename:string, deleted:boolean) {
  if (isGenerating.value || runChangingId.value) return
  runChangingId.value=filename
  runHistoryError.value=''
  try {
    const response=await fetch(`/api/runs/${encodeURIComponent(filename)}${deleted ? '' : '/restore'}`, {method:deleted ? 'DELETE' : 'POST'})
    const data=await response.json()
    if (!response.ok || !data.success) throw new Error(apiError(data))
    const audioUrl=runHistory.value.find(run=>run.audio_file.replace(/\.wav$/,'.run.json')===filename)?.audio_url
    if (deleted && nowPlayingUrl.value===audioUrl) nowPlayingUrl.value=''
    await fetchHistory()
  } catch (error) { runHistoryError.value=(deleted ? '删除' : '恢复')+'生成历史失败：'+error }
  finally { runChangingId.value='' }
}

async function restoreRun(run: GenerationResult) {
  if (isGenerating.value || !run.settings) return
  activeTab.value = 'single'
  currentModelKey.value = run.model_key
  await nextTick()
  selectedVoice.value = run.voice
  selectedPreset.value = run.settings.preset
  modelOptions.value = { ...run.settings.options }
  promptText.value = run.settings.prompt
  speed.value = run.settings.speed
  speedMode.value = run.settings.speed_mode
  inputText.value = run.text
  resetReference()
  if (run.settings.reference.source === 'uploaded') {
    refText.value = run.settings.reference.text || ''
    needsReference.value = true
  }
  singleResult.value = run
}

onMounted(async () => {
  await fetchData()
  fetchHistory()
  fetchBatchHistory()
  await resumeComparison()
  clockTimer = setInterval(() => { if (isGenerating.value) elapsedSeconds.value = Math.floor((Date.now() - startedAt) / 1000) }, 1000)
})
onUnmounted(() => { disposed = true; window.removeEventListener('beforeunload', warnBeforeLeaving); if (clockTimer) clearInterval(clockTimer); if (progressTimer) clearTimeout(progressTimer) })
</script>
