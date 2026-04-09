# STT 路线

## 主方案

- 主引擎：`faster-whisper`
- 适用场景：公开视频、录播、长音频批处理
- 默认导出：
  - `json`
  - `srt`
  - `vtt`
  - `tsv`
  - `txt`

原因：

- 对中文直播/视频场景足够稳
- 速度和工程可控性比原版 whisper 更适合批量处理
- 输出适合视频制作工具和后续语料清洗

## 备选方案

### WhisperX

- 适合需要更准词级时间戳或说话人分离时使用
- 代价是依赖更重、工程更复杂

### FunASR

- 适合低延迟实时字幕
- 更像流式服务方案，而不是批量离线主链路

## 推荐工作流

1. 从公开视频或直播回放提取音频
2. 用 `tools/transcribe_audio.py` 产出 `json + srt + vtt`
3. 人工抽样校对高价值片段
4. 用 `tools/build_corpus.py` 整理校正后的语料
5. 后续再决定是否做词表增强、热词增强或额外微调

## 中国大陆 + VPN 环境注意事项

- 当前环境下代理如果写成 `https://host:port`，部分 Python 依赖会出现 TLS 握手失败。
- `tools/transcribe_audio.py` 已经内置了代理归一化，会把 `HTTPS_PROXY=https://...` 自动改写成 `http://...` 形式再拉模型。
- `tools/download_bilibili_media.py` 也会按同样规则处理代理，所以在大陆 + VPN 环境里可以直接复用终端里的代理变量。
- 第一次运行 `faster-whisper` 会从 Hugging Face 下载模型；后续同型号模型会走本地缓存。

## VAD 与素材类型

- 游戏解说、闲聊、长段语音：优先保留默认 VAD，噪声更少。
- 短梗、音乐、混合唱跳、压缩过重的二创短视频：优先尝试 `--no-vad`，否则容易整段被判成无语音。
- 如果 `json` 里 `segments` 为空，不要先怀疑代理或模型，先用 `--no-vad` 复跑一遍。

## 批处理入口

- 单条下载：`tools/download_bilibili_media.py`
- 单条转写：`tools/transcribe_audio.py`
- 批量下载并转写：`tools/batch_bilibili_stt.py`
- 转写质量审计：`tools/audit_transcripts.py`

## 更强模型和提示词

- 如果机器有 GPU，优先使用 `large-v3`，比 `small` 更适合中文口播和直播切片。
- `tools/batch_bilibili_stt.py` 现在支持把这些参数直通给 `tools/transcribe_audio.py`：
  - `--device`
  - `--compute-type`
  - `--beam-size`
  - `--initial-prompt`
  - `--initial-prompt-file`
  - `--no-word-timestamps`
- 推荐把 `sources/processed/corpus/stt_initial_prompt.txt` 和 `sources/processed/ace-taffy-hotwords.txt` 一起使用，先提高专有词命中率，再做人工抽样校对。

## 语料筛选建议

- 先用 `tools/audit_transcripts.py` 生成一份质量排序清单，再决定哪些样本值得进下一轮校对。
- 同一条视频如果同时有多个转写版本，优先看审计结果里的 `best_by_bvid`，避免把旧模型和新模型重复算进候选集。
- `quality_score` 高、`cjk_ratio` 高、`top_repeat_ratio` 低、`chars_per_minute` 落在正常口播区间的样本，优先进入训练或精校。
- 对明显是唱跳、混音、MMD、梗视频的条目，不要因为“文件转出来了”就直接进训练集。
- `tools/build_training_set.py` 会基于 `best_by_bvid` 再做一层 segment 级过滤，导出：
  - `transcript_train_ready.jsonl`
  - `transcript_train_high.jsonl`
  - `transcript_train_recommended.jsonl`
  - `selected_transcripts.tsv`
- 如果你希望默认就尽量避开旧的 `small` 转写，优先使用 `transcript_train_recommended.jsonl`。
- `transcript_train_recommended.jsonl` 默认还会加一层质量分门槛，避免把勉强判成 `medium` 的弱样本混进去。

## 对视频工具的兼容性

- `srt`：最广泛
- `vtt`：Web 端和部分播放器更友好
- `json`：便于后续重切字幕和训练
- `tsv`：便于表格校对
