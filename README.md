<div align="center">

# 永雏塔菲.skill

> “他们都叫我小唐人！他们都叫我臭唐氏！说谁是唐氏呢！！！骂谁唐氏！”
> 
> “关注永雏塔菲喵，关注永雏塔菲谢谢喵！”

[![Skill: ace-taffy](https://img.shields.io/badge/Skill-ace--taffy-ff6b81)](#quickstart)
[![Version: v0.2.2](https://img.shields.io/badge/Version-v0.2.2-111827)](./SKILL.md)
[![Persona: Public Figure](https://img.shields.io/badge/Persona-Public%20Figure-0ea5e9)](./meta.json)
[![Sources: Weibo + Bilibili](https://img.shields.io/badge/Sources-Weibo%20%2B%20Bilibili-f59e0b)](#sources)
[![STT: faster-whisper](https://img.shields.io/badge/STT-faster--whisper-10b981)](#workflow)
[![License: MIT](https://img.shields.io/badge/License-MIT-facc15)](./LICENSE)

<br>

<img src="./taffy.gif" alt="taffy.gif" height="180">
<img src="./taffy.png" alt="taffy.png" height="180">


---

**让你的 Codex / Claude Code 一键成为永雏塔菲，**
学会包括经典的喵喵句尾、专注 RP（RolePlay）的 taffy 自称、直播口播里的关键 `喵` 落点，以及“生日歌 / 嗦嗨嗨”触发唱段这种更像真实营业的细节；像塔菲一样聊天、发微博，给视频起标题，给动态写文案。同时，得利于对永雏塔菲用词习惯的蒸馏，我们显著提升了永雏塔菲切片视频中的语音识别正确率。

<br>

[快速开始](#quickstart) · [真实示例](#examples) · [数据来源](#sources) · [STT 工作流](#workflow) · [仓库结构](#structure)

中文（主 README） · [English](./README_EN.md)

</div>

## 走进塔菲的世界

| 模块 | 我们提供什么 | 我们不做什么 |
|---|---|---|
| Persona | 蒸馏永雏塔菲在公开平台上稳定、可复核的人格与表达方式 | 不碰中之人、现实身份、未证实八卦 |
| Sources | 只使用微博 / B 站官方公开内容与直播间元数据 | 不把二创搬运、争议帖、录播站标题当一手事实 |
| Output Protocol | 约束自称、`喵`、句式、唱段触发和公开营业节奏 | 不把角色写成“每句都喵”的机械模板 |
| STT Workflow | 维护公开视频转写、审计、训练候选与样式库 | 不提交大体积媒体、全文转写和训练 JSONL |

## 当前快照

| 项目 | 数值 |
|---|---|
| 更新时间 | `2026-04-09` |
| 一手来源记录 | `941` |
| 转写片段记录 | `2751` |
| 合并语料记录 | `3692` |
| 推荐训练片段 | `1377` |
| 推荐过滤规则 | `large-v3` 且 `quality_score >= 55` |
| 默认 STT 导出 | `json` / `srt` / `vtt` / `tsv` / `txt` |

<a id="quickstart"></a>
## 快速开始

### 安装到 Codex

Codex 默认从 `~/.codex/skills/` 读取 skills。

直接克隆：

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/ly-xxx/ace-taffy-skill.git ~/.codex/skills/ace-taffy
```

如果你希望边改仓库边让 Codex 立即读到最新内容，建议用软链接：

```bash
git clone https://github.com/ly-xxx/ace-taffy-skill.git ~/work/ace-taffy-skill
mkdir -p ~/.codex/skills
ln -s ~/work/ace-taffy-skill ~/.codex/skills/ace-taffy
```

### 安装到 Claude Code

Claude Code 一般会从 `~/.claude/skills/` 或项目内 `.claude/skills/` 读取 skills。

全局安装：

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/ly-xxx/ace-taffy-skill.git ~/.claude/skills/ace-taffy
```

项目内安装：

```bash
mkdir -p .claude/skills
git clone https://github.com/ly-xxx/ace-taffy-skill.git .claude/skills/ace-taffy
```

### 第一次调用

Codex：

```text
请使用 ace-taffy skill，帮我写一条今晚开播《哀鸿》的微博预告。
```

Claude Code：

```text
/ace-taffy 帮我写一条今晚开播《哀鸿》的微博预告，要有塔菲那种先抛情绪再补信息的感觉
```

### 本地 Smoke Test

如果你只是想先确认 skill 已经成功加载，可以跑一条最短 smoke test：

```bash
codex exec --skip-git-repo-check \
  "请使用 ace-taffy skill，只输出最终成稿，不要解释。写一条对粉丝评论“今天怎么这么晚才来”的回复。"
```

只要输出开始明显使用 `taffy` / `塔菲` 的自称，并且没有机械堆 `喵`，基本就说明已经调起成功。长口播场景下，关键句尾通常还会自然保留 `2` 到 `4` 个 `喵` 落点。

`2026-04-09` 的一轮本机实跑输出如下：

```text
被时间乱流绊了一下，taffy这不是火速冲来了嘛。雏草姬先别记小本本，晚到的份补双倍营业喵。
```

## 适合什么，不适合什么

### 更适合

- 公开营业语境下的人格模仿
- 微博 / 动态 / 标题 / 直播预告 / 短口播
- SC 长回复、切片感直播口播
- 基于微博、B 站官方公开内容继续做风格延展
- 中文内容生产、字幕整理、公开转写与训练候选筛选

### 不适合

- 追问未核实八卦、现实身份或中之人信息
- 要求捏造“今天刚发生的事”
- 强行逐字复读某条未经核验的原话
- 把它当成纯口癖生成器，要求每句都堆 `喵`

<a id="examples"></a>
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

### 3. 粉丝互动回复

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

### 4. 短视频封面文案

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

### 5. 长口播 / 生日唱段触发

提示词：

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一段更像录播切片感、高强度碎嘴直播的 SC 回复片段，按顺序回复下面两条：
1. 永雏劳恩堡：[💰30] 最近精神状态不太好有点恍惚，但是看到taffy的直播有种安心感喵。
2. 某言成：[💰30] taffy今天是朋友sheep的生日，可以嗦嗨嗨嘛，爱你喵。
要求：整体像直播切片，不要写成深夜电台；长口播里要保留更明显一点的喵浓度；遇到生日请求时要真的进入唱段，可以用[唱]标记，不要逐字抄整首现成歌词。
```

输出：

```text
永雏劳恩堡，三十，谢谢。等一下，这条有点重。最近精神状态不太好，有点恍惚，嗯，taffy收到。先别急着给自己开庭，别一上来就判自己今天完蛋了，先坐这儿，先挂在直播间里，听taffy碎嘴，听塔菲在这边东一下西一下地播报案发现场，能安心一点就已经很有用了。真的，别小看这个，能在乱糟糟的时候找到一个能落脚的地方，这个就很厉害。今天先别追求一下子变好，先别掉线，先把这一晚混过去，能笑一下算一下，能喘一口气算一下，taffy先把你往这边捞一下，接住了喵。累了就偷偷躺着听，雏草姬先充电，慢慢来喵。

某言成，三十，谢谢。今天这个SC还是带任务来的，朋友sheep生日，还点名要嗦嗨嗨，可以，给寿星整点特别节目。sheep听好了，塔菲现在临时开个生日分会场，音准先放一边，排面不能输，taffy直接开嗓。

[唱]
嗦嗨嗨 嗦嗨嗨 今天sheep最大牌
蛋糕切开 烦恼走开 好运排着队进来
新的一岁要顺顺利利 要开心 要发呆也可爱
朋友替你点歌 taffy替你把祝福端上台
sheep生日快乐呀 生日快乐喵

好，唱完，直播间临时歌会到此结束，耳机没坏的扣个1。替某言成把这份爱送到了，sheep今天就负责开心，负责吃，负责收礼物，负责把愿望许得大一点，能成的都成，不成的过几天再来直播间续愿。生日快乐，亮亮堂堂地过，开开心心地过，爱你喵。
```

<a id="sources"></a>
## 数据来源

当前公开主源只走官方公开入口：

- 微博主页：`https://weibo.com/acetaffy`
- Bilibili 空间：`https://space.bilibili.com/1265680561`
- Bilibili 直播间：`https://live.bilibili.com/22603245`

边界和出处约束集中放在这些文件里：

- `references/boundaries.md`
- `references/sources.md`
- `references/profile.md`

这套 skill 的默认原则是：

- 最新动态、出处核对、时间线问题优先查本地刷新数据
- 本地没有刷新结果时，明确说明需要先抓取微博 / B 站最新内容
- 不把二创、粉丝搬运、争议总结文当成第一手事实

<a id="workflow"></a>
## 刷新公开数据与 STT 工作流

先装依赖：

```bash
pip3 install -r requirements.txt
```

刷新微博、B 站和公共语料清单：

```bash
python3 tools/source_refresh_public.py --target sources/targets/ace-taffy.json
```

这条命令现在会默认把 B 站采集拆成多步落盘，并写出 `sources/raw/bilibili/_collector_state.json`。
如果中途断开，直接重跑同一条命令即可继续利用已落盘结果；需要忽略旧结果时再显式加 `--fresh`。

批量下载并转写公开视频：

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

如果你只想单独补 B 站并调高网络容错，也可以直接这样跑：

```bash
python3 tools/source_refresh_public.py \
  --target sources/targets/ace-taffy.json \
  --steps bilibili,corpus \
  --http-retries 6 \
  --retry-backoff 1.8 \
  --save-every 10
```

### STT 输出兼容性

当前主方案是 `faster-whisper`。默认导出这些格式，主流剪辑、校对和后处理流程都能接：

- `srt`：适配绝大多数剪辑软件和播放器
- `vtt`：适合 Web 和部分在线工作流
- `json`：适合二次切分、校对和训练
- `tsv`：适合表格校对
- `txt`：适合快速浏览和简单检索

更完整的说明见 `references/stt-roadmap.md`。

<a id="structure"></a>
## 仓库结构

```text
taffy.skill/
├── SKILL.md                    # skill 入口与执行规则
├── persona.md                  # 人格基线
├── meta.json                   # 元信息与平台配置
├── prompts/                    # 可复用提示片段
├── references/                 # 风格、边界、来源、输出协议
├── sources/
│   ├── raw/                    # 公开源抓取结果
│   ├── processed/              # 轻量统计、审计与训练候选摘要
│   └── transcripts/            # 转写产物
├── tools/                      # 采集、转写、审计、构建工具
├── submission/                 # Gallery 提交材料
└── README_EN.md                # 英文说明
```

发布前审核时，建议优先看这些文件：

- `SKILL.md`：skill 入口和执行规则
- `persona.md`：人格基线
- `references/expression-dna.md`：表达风格总纲
- `references/meow-pattern.md`：`喵` 的完整输出规则
- `references/self-reference.md`：自称规则，默认不用“我”
- `sources/processed/`：轻量统计、审计和训练候选摘要
- `tools/`：采集、转写、审计和构建工具

## License

MIT，见 `LICENSE`。

## Star History

## Star History

<a href="https://www.star-history.com/?repos=ly-xxx%2Face-taffy-skill&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=ly-xxx/ace-taffy-skill&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=ly-xxx/ace-taffy-skill&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=ly-xxx/ace-taffy-skill&type=date&legend=top-left" />
 </picture>
</a>