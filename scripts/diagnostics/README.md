# Qwen 开头发声诊断

这些脚本只用于复现异常并保存对照，不修改默认模型配置，不裁剪音频，不下载资源。生成和解码测试共用项目推理锁，避免与页面评测并发。

在项目根目录、已有 Qwen 环境中运行：

```sh
./.venvs/qwen3/bin/python scripts/diagnostics/qwen_onset_comparison.py \
  --record outputs/qwen3-tts-1.7b_8817182c.run.json \
  --output-dir outputs/qwen-onset-comparison-new

./.venvs/qwen3/bin/python scripts/diagnostics/qwen_decode_comparison.py \
  --record outputs/qwen3-tts-1.7b_8817182c.run.json \
  --output-dir outputs/qwen-decoder-comparison-new

./.venvs/qwen3/bin/python scripts/diagnostics/qwen_generation_comparison.py \
  --record outputs/qwen3-tts-1.7b_8817182c.run.json \
  --output-dir outputs/qwen-generation-comparison-new
```

输出目录必须是新目录，防止覆盖已有证据。解码对照先复现原始音频，要求 WAV 字节完全相同，然后保存这一份生成的 codec，再分别用 MPS float32 和 CPU float32 解码。更换解码器时从同一原始本地权重加载，避免先转为 bfloat16 再转回 float32 的舍入污染。

波形活动段、差异和文件哈希只能定位信号变化，不能自动识别“哦”或证明内容正确。原始异常由用户确认，候选结果需要试听记录。当前没有可以自动判断这个语义症状的回归测试；不要用“非空音频”或“推理成功”代替它。

这些脚本预加载模型后进行诊断，结果不进入正常评测或性能排名。

生成对照分别只使用项目已有新闻播报指令、只关闭主 Talker 的随机采样；保持原文、音色、语言、种子、输入模式、长度上限和解码器不变。语音编码另存为无 pickle 的 NumPy 文件，便于继续定点排查。关闭主 Talker 采样不等于关闭子生成器采样；报告会同时保存解析后的两层配置。候选输出需要检查额外发声和全文完整度，不能仅看开头波形或音频时长决定采用配置。
