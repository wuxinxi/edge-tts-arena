# 模型准备与兼容性

[返回 README](../README.md) · [评测与记录](evaluation.md)

平台使用 `.venv/` 提供 API、下载与指标采集，使用 `.venvs/<环境名>/` 执行各模型真实推理。模型权重默认位于 `checkpoints/<模型 key>/`，部分模型还依赖固定版本的 `third_party/` 源码和辅助资源。

## 准备独立环境

已有环境不必重新创建。以下是手动安装示例，执行时会访问包源；基础环境的初始化见 [README](../README.md#快速启动)。

### 使用准备脚本

```bash
# 只准备所需环境
./.venv/bin/python scripts/setup_models.py --models kokoro
./.venv/bin/python scripts/setup_models.py --models melotts,qwen3
```

`--models` 接受**环境名**，不是模型 key：

| 环境名 | Python | 对应模型 | 主要额外资源 |
| --- | --- | --- | --- |
| `kokoro` | 3.12 | `kokoro-82m` | 本地音色、文本发音资源 |
| `melotts` | 3.11 | `melotts-zh` | MeloTTS 源码、BERT 缓存、NLTK 资源 |
| `qwen3` | 3.12 | 两种 Qwen3-TTS | 本地权重及配套语音 tokenizer |
| `cosyvoice3` | 3.11 | `cosyvoice3` | CosyVoice 源码及 Matcha-TTS 子模块 |
| `fish-speech` | 3.11 | `fish-speech-1.5` | Fish-Speech 固定版本源码、语音编码器 |
| `maskgct` | 3.11 | `maskgct` | Amphion 源码、W2V-BERT、文本与语音资源 |
| `parler` | 3.12 | `parler-tts-mini` | 英文模型权重与 tokenizer |

不带 `--models` 会准备表中全部环境。默认流程会拉取所需源码、安装依赖，并下载需要的辅助资源；它不会替代 `download.sh` 的主权重下载。

```bash
# 环境与源码已经准备好时，只补辅助资源
./.venv/bin/python scripts/setup_models.py --models melotts,maskgct --assets
```

依赖版本见 [model_requirements](../scripts/model_requirements/)，源码 revision 见 [model_sources.json](../scripts/model_sources.json)。已有源码的 revision 不一致时脚本会报错，先保留本地修改再处理；MeloTTS 和 MaskGCT 的本地兼容补丁位于 [vendor_patches](../scripts/vendor_patches/)。

### ChatTTS 与 F5-TTS

这两个环境不在 `setup_models.py` 的环境表中，需单独准备：

```bash
uv venv --python 3.12 .venvs/chattts
uv pip install --python .venvs/chattts/bin/python 'chattts==0.2.5' soundfile

uv venv --python 3.12 .venvs/f5tts
uv pip install --python .venvs/f5tts/bin/python 'f5-tts==1.1.22' soundfile
```

F5-TTS 的参考音频预处理还需系统可用的 FFmpeg。包安装完成不代表全部源码、权重与辅助资源均已就绪，以页面状态检查和实际生成验证为准。

## 主权重与下载入口

```bash
./download.sh --list
./download.sh --models kokoro-82m,melotts-zh

# 明确需要另一来源时手动指定
./download.sh --models qwen3-tts-0.6b --source huggingface
```

下载使用**模型 key**，列表见 [README](../README.md#模型范围)。`--all` 会请求全部注册模型，按需选择通常更容易排查环境问题。

默认下载源为 ModelScope，失败时尝试另一来源。指定 `huggingface` 且未配置 `HF_ENDPOINT` 或代理时，当前下载器会使用 `hf-mirror.com`；需要直连官方源时可显式设置：

```bash
HF_ENDPOINT=https://huggingface.co ./download.sh --models kokoro-82m --source huggingface
```

下载工具检查必要文件存在且非空，不因下载标记、README 或配置文件单独存在就认为主权重完整。文件检查不能发现所有权重损坏，仍需实际生成验证。

F5-TTS 还需要 `checkpoints/f5-tts/vocoder/config.yaml` 与 `pytorch_model.bin`，对应 Vocos 24kHz 声码器。手动下载流程会准备这些文件；其他模型的必要文件规则见 [model_files.py](../backend/app/core/model_files.py)。

推理入口设置离线模式，运行时不会自动补齐资源。模型状态还会检查官方源码、独立解释器、必要模块及辅助缓存，缺少任一项都会显示未就绪。

## 设备与兼容性

下表为当前实现的 **Mac 自动设备策略**，不是同硬件下不同设备的性能排名。实际设备会写入生成记录；CUDA 路径存在不代表已经完成所有模型的 CUDA 验证。

| 模型 | Mac 自动策略 | 说明 |
| --- | --- | --- |
| Kokoro | CPU | 当前入口不自动选 MPS |
| MeloTTS | CPU | 当前 MPS 卷积路径不兼容 |
| ChatTTS | CPU | 自动模式选择 CUDA 或 CPU |
| F5-TTS | MPS 可用时使用 MPS，否则 CPU | 使用旧版 Base 对应架构与 Vocos |
| CosyVoice 3 | CPU | 当前接入 CPU / CUDA，不提供 MPS |
| Qwen3 0.6B Base | CPU / float32 | 本机半精度 MPS 出现无效概率，自动策略回退 CPU |
| Qwen3 1.7B CustomVoice | MPS / bfloat16 | MPS 路径要求 macOS 14 或以上，否则回退 CPU / float32 |
| Fish-Speech 1.5 | MPS + CPU 编码器 | MPS 时语音编码器使用 CPU |
| MaskGCT | CPU | 当前入口不自动选 MPS |
| Parler-TTS Mini | MPS 可用时使用 MPS，否则 CPU | 本机尚缺主权重，未生成验证 |

多数自动设备入口在 CUDA 可用时优先选 CUDA；具体分支见 [workers](../backend/app/workers/)。设备名、精度、源码版本与实际配置应与评测结果一起保存，不能只写一个模型名称。

### F5-TTS 版本匹配

当前权重为旧版 `model_1200000`，使用包内 `F5TTS_Base.yaml`，包含 `text_mask_padding=False`、`pe_attn_head=1`。它不能直接套用新版 DiT 的默认架构配置；当前结果也不能视作新版本 F5-TTS 的表现。

### Qwen 版本与推荐指令

0.6B 是 Base 克隆版，1.7B 是 CustomVoice 预置音色版，能力和调用接口不同。Base 可选择完整参考克隆或仅提取音色；CustomVoice 可选择音色并提供风格指令。

能力探索的 1.7B 默认从「清晰播报 · 推荐」开始，指令为「用清晰、沉稳、专业的新闻播报语气说。」已确认的 Vivian 中文通知样本中，该配置没有开头额外“哦”，正文完整、清楚。这是单一样本的缓解结论，根因未确认，其他文本仍需试听。统一评测保留无指令基础配置，不裁剪音频来掩盖问题。详情见本地 [调查记录](../outputs/qwen-onset-20261009/diagnosis.md)。

### 参考与生成参数

未上传时，克隆模型使用 [内置参考](../backend/assets/reference/SOURCE.md)。Fish-Speech 1.5 的本机无参考长句曾明显提前结束，当前默认使用参考音频、固定种子和已验证采样配置；这不保证所有输入正确。

速度有原生、离散档位与生成后处理三种方式。探索页按模型支持方式展示；评测统一以模型速度 1.0 生成，再按选定输出速度后处理。界面预设是起点，实际参数与有效运行参数见 `.run.json`。定义与校验共享 [model_profiles.py](../backend/app/core/model_profiles.py)。

## 新增模型入口

在 [config.py](../backend/app/core/config.py) 登记模型元数据，在 [model_files.py](../backend/app/core/model_files.py) 配置必要文件，补充独立 worker、适配器及 [factory.py](../backend/app/adapters/factory.py) 注册，并在 [model_profiles.py](../backend/app/core/model_profiles.py) 定义实际支持的控制。

接入后分别验证资源就绪、实际生成、参数记录与失败原因；对语音内容和场景效果做人工试听。不能用系统 TTS 或模拟等待替代目标模型推理。

官方模型与源码链接见项目能力资料；权重、代码和辅助资源许可需要按实际版本分别核对。
