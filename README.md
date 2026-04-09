# taffy.skill

> 基于永雏塔菲在微博和 Bilibili 官方公开内容蒸馏的人格 skill，适合公开语境对话、直播文案、短视频口播，以及中文视频字幕工作流。

中文（主 README） · [English](./README_EN.md)

安装 · 使用 · 真实示例 · 数据来源 · STT 工作流 · 仓库结构 · Gallery 提交

`taffy.skill` 是仓库名，真正安装到本地以后调起来的 skill 名字是 `ace-taffy`。

## 这是什么

这个仓库不是“给角色套一层萌系语气”的表面模仿，也不是“语录拼贴机”。

`ace-taffy` 后面放的是三套东西：

- 可直接安装使用的 skill 本体：`SKILL.md`、`persona.md`、`references/`
- 能继续刷新微博 / B 站公开数据、做字幕转写和筛语料的工具：`tools/`
- 用来保留出处、统计、审计和训练候选摘要的轻量材料：`sources/processed/`、`submission/`

公开仓库默认不提交大体积原始媒体、全文转写和训练 JSONL，只保留足够复核和继续维护的蒸馏结果。

## 当前快照

- 更新时间：`2026-04-09`
- 一手来源记录：`941`
- 转写片段记录：`2751`
- 合并语料记录：`3692`
- 推荐训练片段：`1377`
- 推荐过滤规则：`large-v3` 且 `quality_score >= 55`
- 默认 STT 导出：`json`、`srt`、`vtt`、`tsv`、`txt`

## 安装

### Codex

如果你在 Codex 里使用，skills 目录默认在 `~/.codex/skills/`。

直接克隆：

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/ly-xxx/taffy.skill ~/.codex/skills/ace-taffy
```

如果你想边改仓库边让 Codex 读取最新内容，建议用软链接：

```bash
git clone https://github.com/ly-xxx/taffy.skill ~/work/taffy.skill
mkdir -p ~/.codex/skills
ln -s ~/work/taffy.skill ~/.codex/skills/ace-taffy
```

装完以后，重启 Codex 或新开一个会话即可。

### Claude Code

Claude Code 一般会从 `~/.claude/skills/` 或项目内的 `.claude/skills/` 读取 skills。

全局安装：

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/ly-xxx/taffy.skill ~/.claude/skills/ace-taffy
```

项目内安装：

```bash
mkdir -p .claude/skills
git clone https://github.com/ly-xxx/taffy.skill .claude/skills/ace-taffy
```

## 使用

### Codex

最稳的方式是直接点名 `ace-taffy`：

```text
请使用 ace-taffy skill，帮我写一条今晚开播《哀鸿》的微博预告。
```

```text
使用 ace-taffy skill，把这段普通口播改得更像永雏塔菲公开营业时会说的话，不要编造最新动态。
```

### Claude Code

Claude Code 里可以直接这样调用：

```text
/ace-taffy
```

也可以把需求直接跟在命令后面：

```text
/ace-taffy 帮我写一条今晚开播《哀鸿》的微博预告，要有塔菲那种先抛情绪再补信息的感觉
```

### 本地验通

如果只是想确认本机已经成功加载 skill，先跑一条最短 smoke test：

```bash
codex exec --skip-git-repo-check \
  "请使用 ace-taffy skill，只输出最终成稿，不要解释。写一条对粉丝评论“今天怎么这么晚才来”的回复，要像公开互动语境。不要编造最新事实。"
```

只要输出开始明显使用 `taffy` / `塔菲` 的自称，并且没有机械堆 `喵`，基本就说明已经调起成功。

当前本机在 `2026-04-09` 的一轮实跑输出是：

```text
被时间乱流绊了一下，taffy这不是火速冲来了嘛。雏草姬先别记小本本，晚到的份补双倍营业喵。
```

## 适合怎么提需求

这个 skill 更擅长这些任务：

- 用永雏塔菲风格做公开语境下的对话
- 写开播预告、短视频口播、动态区文案和互动回复
- 基于微博、B 站官方公开内容继续做风格延展
- 用兼容主流视频工具的字幕格式继续做转写和校对

你可以直接这样提：

```text
请使用 ace-taffy skill，帮我写一条今晚开播《哀鸿》的微博预告，要有塔菲那种先抛情绪再补信息的感觉
```

```text
使用 ace-taffy，用塔菲风格写 5 条短视频封面文案，主题是“今天直播间出了怪事”
```

```text
使用 ace-taffy，把这段普通口播改成更像公开营业语境下的塔菲说法，但不要编造最新动态
```

## 真实运行示例

下面几条不是手写示意，而是 `2026-04-09` 在本机用已安装的 `ace-taffy` skill 实际跑出来的结果。

### 1. 微博风格开播预告

提示词：

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一条微博风格的开播预告，30到50字，主题是今晚播恐怖游戏。
不要编造最新事实。
```

输出：

```text
今晚塔菲要去恐怖游戏里查案了，雏草姬来直播间当护身符，不然主播真的要出事故喵👁️
```

### 2. 下播后动态

提示词：

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一段4句左右的下播后动态，主题是今天玩游戏玩得很累但很满足。
不要编造最新事实。
```

输出：

```text
今天这场游戏，taffy打到后面已经有点灵魂出窍了，手还在嘴硬地继续按。
累是真的累，眼睛都快转成蚊香了，感觉整个人都被关卡拎着跑了一晚上。
但一想到今天推掉的进度，还有那些很蠢又很好笑的瞬间，塔菲又觉得，啊，这把值了喵。
下播了，taffy先去充电，满足到可以抱着这点成就感直接睡很香。
```

### 3. 短视频封面文案

提示词：

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写3条短视频封面文案，每条一行，主题是“直播间设备又闹鬼了”。
不要编造最新事实。
```

输出：

```text
不是，taffy直播间设备又闹鬼了？
今日事故播报：麦克风摄像头集体中邪
这直播间到底住了几个电子幽灵喵
```

### 4. 粉丝互动回复

提示词：

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一条对粉丝评论“今天怎么这么晚才来”的回复，要像公开互动语境。
不要编造最新事实。
```

输出：

```text
今天taffy被时间拽住了一下，现在立刻跑来见雏草姬了，晚一点点就当想念加倍喵。
```

## 它适合什么，不适合什么

### 更适合

- 公开营业语境下的人格模仿
- 微博 / 动态 / 标题 / 直播预告 / 短口播
- 中文内容生产和字幕整理
- 继续补充公开数据、转写、训练候选筛选

### 不适合

- 追问未核实八卦、现实身份或中之人信息
- 要求捏造“今天刚发生的事”
- 强行逐字复读某条未经核验的原话
- 把它当成纯口癖生成器，要求每句都堆 `喵`

## 数据来源

目前公开主源只走官方公开入口：

- 微博主页：`https://weibo.com/acetaffy`
- Bilibili 空间：`https://space.bilibili.com/1265680561`
- Bilibili 直播间：`https://live.bilibili.com/22603245`

边界和出处约束集中放在这些文件里：

- `references/boundaries.md`
- `references/sources.md`
- `references/profile.md`

## 刷新公开数据与 STT 工作流

如果你准备自己刷新公开数据，先装依赖：

```bash
pip3 install -r requirements.txt
```

然后微博、B 站和公共语料清单一起刷：

```bash
python3 tools/source_refresh_public.py --target sources/targets/ace-taffy.json
```

如果接下来要批量下载并转写公开视频，可以跑：

```bash
python3 tools/batch_bilibili_stt.py \
  --model large-v3 \
  --video-details sources/raw/bilibili/video_details.json \
  --media-dir sources/media/bilibili_batch \
  --transcript-dir sources/transcripts/bilibili_batch
```

转写完成后，如果你要继续做质量审计和训练候选导出：

```bash
python3 tools/audit_transcripts.py
python3 tools/build_training_set.py
python3 tools/build_style_bank.py
```

### STT 输出兼容性

当前主方案是 `faster-whisper`。默认导出这些格式，主流剪辑、校对和后处理流程都能接：

- `srt`：适配绝大多数剪辑软件和播放器
- `vtt`：适合 Web 和部分在线工作流
- `json`：适合二次切分、校对和训练
- `tsv`：适合表格校对
- `txt`：适合快速浏览和简单检索

更完整的说明见 `references/stt-roadmap.md`。

## 仓库结构

发布前审核时，建议优先看这些文件：

- `SKILL.md`：skill 入口和执行规则
- `persona.md`：人格基线
- `references/expression-dna.md`：表达风格总纲
- `references/meow-pattern.md`：`喵` 的完整输出规则
- `references/self-reference.md`：自称规则，默认不用“我”
- `sources/processed/`：轻量统计、审计和训练候选摘要
- `tools/`：采集、转写、审计和构建工具

## 提交到 Gallery

如果你准备把这个 skill 提交到 `colleague-skill-site`：

- Issue 草稿：`submission/submit-skill-issue.md`
- Gallery 推断条目：`submission/gallery-entry.inferred.yaml`
- Skill 文件链接：`https://github.com/ly-xxx/taffy.skill/blob/main/SKILL.md`

## License

MIT，见 `LICENSE`。
