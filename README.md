# taffy.skill

你们现在看到的这个 `taffy.skill`，先讲结论，它不是那种套一层萌系语气就说自己是塔菲的东西。`ace-taffy` 这个调用名后面，放的是从永雏塔菲微博和 Bilibili 官方公开内容里，一点一点蒸出来的可复用 persona、能持续刷新的数据管线，还有一套适合中文视频工作流继续做转写的 STT 工具链。

仓库名是 `taffy.skill`，真正安装到本地以后调起来的 skill 名字是 `ace-taffy`。

你们别看这个仓库表面上像个小 skill，它里面其实分得还挺清楚，主要就是三块：

- 可以直接装上去开用的 skill 主体：`SKILL.md`、`persona.md`、`references/`
- 继续往下刷公开数据、做转写、做整理的工具：`tools/`
- 用来兜住出处、审计和证据链的轻量材料：目标源配置、审计表、统计摘要、热词和提示词

然后有些很大的原始媒体、整仓转写文件和训练 JSONL，taffy 是故意没直接往里塞的。不是漏了，是公开仓库就该把体积收一收，别让 Git 平白无故背 400MB 以上的构建产物喵。

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

如果你是 Codex 这边用，skills 目录默认就在 `~/.codex/skills/`。安装方式我给你们分两种，一个是装了就跑，一个是边改边调。

直接克隆：

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/ly-xxx/taffy.skill ~/.codex/skills/ace-taffy
```

如果你是那种会一边改仓库、一边想让 Codex 立刻读到最新内容的人，那就先 clone 到工作目录，再做一个软链接：

```bash
git clone https://github.com/ly-xxx/taffy.skill ~/work/taffy.skill
mkdir -p ~/.codex/skills
ln -s ~/work/taffy.skill ~/.codex/skills/ace-taffy
```

装完之后，重启 Codex，或者新开一个 Codex 会话，基本就能读到了。

### Claude Code

如果你用的是 Claude Code，它一般会从 `~/.claude/skills/`，或者当前项目里的 `.claude/skills/` 去读 skills。

想全局装就这样：

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/ly-xxx/taffy.skill ~/.claude/skills/ace-taffy
```

想装到项目里就这样：

```bash
mkdir -p .claude/skills
git clone https://github.com/ly-xxx/taffy.skill .claude/skills/ace-taffy
```

## 使用

### Codex

Codex 这边最稳的用法，其实就是直接点名 `ace-taffy`。你把名字叫清楚，它比较知道自己该往哪个频道切，不容易串味。

```text
请使用 ace-taffy 这个 skill，帮我写一条今晚开播《哀鸿》的微博预告。
```

```text
使用 ace-taffy skill，把这段普通口播改得更像永雏塔菲公开营业时会说的话，不要编造最新动态。
```

### Claude Code

Claude Code 这边就更直接一点，命令调就行：

```text
/ace-taffy
```

你也可以命令后面直接把需求接上：

```text
/ace-taffy 帮我写一条今晚开播《哀鸿》的微博预告，要有塔菲那种先抛情绪再补信息的感觉
```

### 本地验通

如果你只是想确认本机已经把 skill 读进去了，先跑一个最短 smoke test 就够了：

```bash
codex exec --skip-git-repo-check \
  "请使用 ace-taffy skill，只输出最终成稿，不要解释。写一条对粉丝评论“今天怎么这么晚才来”的回复，要像公开互动语境。不要编造最新事实。"
```

只要输出开始明显使用 `taffy` / `塔菲` 的自称，并且没有机械堆 `喵`，基本就说明已经调起成功。

当前本机在 `2026-04-09` 的一轮实跑输出是：

```text
被时间乱流绊了一下，taffy这不是火速冲来了嘛。雏草姬先别记小本本，晚到的份补双倍营业喵。
```

### 适合怎么提需求

这个 skill 比较擅长接的，基本是这些：

- 用永雏塔菲风格做公开语境下的对话
- 写开播预告、短视频口播、动态区文案和互动回复
- 基于微博、B 站官方公开内容继续做风格延展
- 用兼容主流视频工具的字幕格式继续做转写和校对

所以你们如果要提需求，直接这么讲就行，不用绕：

```text
请使用 ace-taffy skill，帮我写一条今晚开播《哀鸿》的微博预告，要有塔菲那种先抛情绪再补信息的感觉
```

```text
使用 ace-taffy，用塔菲风格写 5 条短视频封面文案，主题是“今天直播间出了怪事”
```

```text
使用 ace-taffy，把这段普通口播改成更像公开营业语境下的塔菲说法，但不要编造最新动态
```

### 真实运行示例

下面这几条不是手写示意，是 `2026-04-09` 在本机用已安装的 `ace-taffy` skill 实际跑出来的结果。

#### 1. 微博风格开播预告

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

#### 2. 下播后动态

提示词：

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一段4句左右的下播后动态，主题是今天玩游戏玩得很累但很满足。
不要编造最新事实。
```

输出：

```text
今天玩游戏，taffy不是在打流程，是在和体力还有脑细胞正面对决。
手也酸了，脑子也转得冒烟了，但一关一关啃过去的时候，塔菲又会觉得，嗯，这种累很值。
累是真的累，满足也是真的满足，属于下播以后瘫着都还想回味一下的程度。
雏草姬今天也辛苦了，taffy先去充电，今天这份成就感先抱走喵。
```

#### 3. 短视频封面文案

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

#### 4. 粉丝互动回复

提示词：

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一条对粉丝评论“今天怎么这么晚才来”的回复，要像公开互动语境。
不要编造最新事实。
```

输出：

```text
不是晚，是taffy今天走压轴路线，雏草姬一催，主角这不就到场了喵。
```

### 它不适合什么

但是有些东西，taffy 就是不接。不是听不懂，是边界得先讲在前面：
- 追问未核实八卦、现实身份或中之人信息
- 要求捏造“今天刚发生的事”
- 强行逐字复读某条未经核验的原话
- 把它当成纯口癖生成器，要求每句都堆 `喵`

### 如果你是想继续做数据和转写

还有一个事情你们要知道，这个仓库不只是拿来聊天的。它本身就是一套公开数据维护仓库。你如果后面想继续往下做数据、做转写、做整理，它也接得住：

- 刷新微博/B 站官方公开数据
- 下载公开视频音频
- 导出 `json + srt + vtt + tsv + txt`
- 审计转写质量并筛选训练候选

## 数据来源

现在公开主源只走官方公开入口。这个事情看着简单，其实很重要，来源干净一点，后面很多事都比较站得住：

- 微博主页：`https://weibo.com/acetaffy`
- Bilibili 空间：`https://space.bilibili.com/1265680561`
- Bilibili 直播间：`https://live.bilibili.com/22603245`

边界和出处约束我也放在这些文件里了，你们要查就直接看：

- `references/boundaries.md`
- `references/sources.md`
- `references/profile.md`

## 刷新公开数据

你如果是准备自己刷新公开数据，先装依赖：

```bash
pip3 install -r requirements.txt
```

然后微博、B 站和公共语料清单一起刷：

```bash
python3 tools/source_refresh_public.py --target sources/targets/ace-taffy.json
```

如果你接下来是要批量下载并转写公开视频，就跑这个：

```bash
python3 tools/batch_bilibili_stt.py \
  --model large-v3 \
  --video-details sources/raw/bilibili/video_details.json \
  --media-dir sources/media/bilibili_batch \
  --transcript-dir sources/transcripts/bilibili_batch
```

转写完你还想做质量审计，顺手把训练候选导出来，那就接着跑：

```bash
python3 tools/audit_transcripts.py
python3 tools/build_training_set.py
python3 tools/build_style_bank.py
```

## STT 输出兼容性

当前主方案是 `faster-whisper`。它默认会导出这些格式，主流剪辑、校对和后处理流程，基本都能接上：

- `srt`：适配绝大多数剪辑软件和播放器
- `vtt`：适合 Web 和部分在线工作流
- `json`：适合二次切分、校对和训练
- `tsv`：适合表格校对
- `txt`：适合快速浏览和简单检索

更完整的说明在 `references/stt-roadmap.md`。你要往深了做，就继续往下看。

## 提交到 Gallery

如果你是想把这个东西往 `colleague-skill` 的社区 gallery 提，材料这边也已经先给你备好了：

- `submission/submit-skill-issue.md`
- `submission/gallery-entry.inferred.yaml`

这里顺手补几句：

- `submission/submit-skill-issue.md` 现在已经按 GitHub issue 表单的真实字段改写，可以直接复制。
- `submission/gallery-entry.inferred.yaml` 仍然保留，作为 gallery 字段的结构化备份。
- 我已经尽量对齐这些已验证字段：标题、身份副标题、文化标签、分类标签、traits、repo 链接、作者 GitHub 用户名、创建日期和 Skill 文件存在性。
- 如果你推到 GitHub 后发现 issue 表单字段名略有差异，直接把对应答案粘进去即可。

## 许可证

本仓库里的代码、脚本、蒸馏说明和仓库结构，按 MIT 发布。微博和 Bilibili 上那些原始公开内容、媒体文件和平台素材，权利还是归各自权利方所有；这个仓库默认也不会直接分发那些大体积源文件。该讲清楚的地方，还是要讲清楚喵。
