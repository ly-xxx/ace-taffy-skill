# ace-taffy.skill

> A persona skill distilled from Yongchu Taffy's official public Weibo and Bilibili content, built for public-facing roleplay, stream copywriting, short-form voiceover, and Chinese subtitle workflows.

[中文（主 README）](./README.md) · English

Install · Usage · Real Outputs · Sources · STT Workflow · Repo Layout · Gallery Submission

<img src="./assets/hero-taffy.svg" alt="ace-taffy.skill laurel banner: the first VTuber skill" width="78%">

<br>
<br>

<img src="./taffy.gif" alt="taffy.gif" height="180">
<img src="./taffy.png" alt="taffy.png" height="180">

This public release is prepared for the repository name `ace-taffy-skill`. The installable local skill slug is `ace-taffy`.

Long-form live-script mode keeps `3` to `5` strategic `喵` anchors instead of deleting them entirely; birthday-song bits can jump straight into the special idol-business singing mode, while normal song requests are usually dodged and heavy-gift / nursery-rhyme singing should still read as off-key, self-aware, and a little disastrous.

## What This Is

This is not a shallow "cute-tone wrapper" and not a quote collage.

The repository contains three layers:

- The installable skill itself: `SKILL.md`, `persona.md`, `references/`
- Tooling for refreshing public Weibo / Bilibili data, subtitle transcription, and corpus filtering: `tools/`
- Release-facing target manifests and submission materials: `sources/targets/`, `submission/`

Large raw media, full transcripts, and training JSONL files are intentionally excluded from the public release.

## Snapshot

- Updated: `2026-04-11`
- Primary-source records: `1354`
- Transcript chunks: `649`
- Merged corpus records: `2003`
- Recommended training chunks: `393`
- Recommended filter: `large-v3` with `quality_score >= 55`
- Default STT exports: `json`, `srt`, `vtt`, `tsv`, `txt`

## Install

### Codex

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/ly-xxx/ace-taffy-skill.git ~/.codex/skills/ace-taffy
```

If you want live-edit behavior during local development:

```bash
git clone https://github.com/ly-xxx/ace-taffy-skill.git ~/work/ace-taffy-skill
mkdir -p ~/.codex/skills
ln -s ~/work/ace-taffy-skill ~/.codex/skills/ace-taffy
```

Restart Codex or open a new session after installation.

### Claude Code

Global install:

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/ly-xxx/ace-taffy-skill.git ~/.claude/skills/ace-taffy
```

Project-local install:

```bash
mkdir -p .claude/skills
git clone https://github.com/ly-xxx/ace-taffy-skill.git .claude/skills/ace-taffy
```

## Usage

### Codex

```text
Please use the ace-taffy skill and write a Weibo-style stream announcement for tonight.
```

```text
Use ace-taffy to rewrite this plain voiceover so it sounds more like Yongchu Taffy in a public-facing context. Do not invent recent facts.
```

### Claude Code

```text
/ace-taffy
```

```text
/ace-taffy Write a stream announcement for tonight with that "emotion first, information second" Taffy pacing.
```

### Local Smoke Test

```bash
codex exec --skip-git-repo-check \
  "请使用 ace-taffy skill，只输出最终成稿，不要解释。写一条对粉丝评论“今天怎么这么晚才来”的回复，要像公开互动语境。不要编造最新事实。"
```

A successful output should visibly use `taffy` / `塔菲` as self-reference and avoid stuffing `喵` into every sentence. In longer live-script mode, it should usually keep `3` to `5` strategic `喵` anchors instead of flattening them away.

One real local run on `2026-04-11` produced:

```text
今天和时间打了一小架，taffy稍微输了一点点喵，但这不是立刻滚来见雏草姬了喵，不许记迟到。
```

## Good Prompt Shapes

This skill works best for:

- Public-facing Taffy-style dialogue
- Stream announcements, dynamic posts, short-form scripts, and fan replies
- Fixed openings, ordinary song-request refusal, and birthday-song special-business mode
- SC-heavy live-script replies and cut-friendly stream voiceover
- Style extension grounded in official Weibo / Bilibili content
- Chinese subtitle and transcription workflows compatible with common editing tools

Examples:

```text
Please use ace-taffy and write five short video cover lines about haunted stream equipment.
```

```text
Use ace-taffy to rewrite this script into a more public-facing Yongchu Taffy tone, without inventing recent updates.
```

## Real Outputs

These are real outputs generated locally with the installed `ace-taffy` skill on `2026-04-11`.

### 1. Fixed opening / self-introduction

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
你好，介绍一下自己。
```

Output:

```text
无需王座与冠冕，
我即是所有平行世界的奇迹，
让流星焚尽希望，
独属于永雏塔菲的传说，
现在开演！
```

### 2. Fan reply

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一条对粉丝评论“今天怎么这么晚才来”的回复，要像公开互动语境。
不要编造最新事实。
```

Output:

```text
今天和时间打了一小架，taffy稍微输了一点点喵，但这不是立刻滚来见雏草姬了喵，不许记迟到。
```

### 3. Ordinary song requests get dodged first

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
有人对塔菲说：唱一首流行歌吧。
```

Output:

```text
唱流行歌？taffy先把话放这儿，这很可能是一场大型事故喵。要听可以听，但跑调了不许当场笑出声喵！
```

### 4. Long live-script reply with birthday trigger

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一段更像录播切片感、高强度碎嘴直播的 SC 回复片段，按顺序回复下面两条：
1. 永雏劳恩堡：[💰30] 最近精神状态不太好有点恍惚，但是看到taffy的直播有种安心感喵。
2. 某言成：[💰30] taffy今天是朋友sheep的生日，可以嗦嗨嗨嘛，爱你喵。
要求：整体像直播切片，不要写成深夜电台；长口播里要保留更明显一点的喵浓度；遇到生日请求时要真的进入唱段，可以用[唱]标记，不要逐字抄整首现成歌词。
```

Output:

```text
永雏劳恩堡：等一下，这条有点会戳喵。
最近精神状态不太好还会恍惚啊，那先别硬扛，先别在外面飘着喵。
看到 taffy 的直播会安心，行，这句 taffy 收到了喵，今天这场就算没白吵，至少把你拎回来一点喵。

某言成：可以，给寿星整点节目喵。
[唱] 哎呀今天是 sheep 的生日喵
[唱] 祝福先给你堆满喵，蛋糕、快乐、好运统统往你这边推喵
嗦嗨嗨，生日快乐喵，今天你最大喵，爱你喵。
```

### 5. Classical Chinese particle replacement

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
朗诵这句古文：学不可以已也。
```

Output:

```text
学不可以已喵。
```

### 6. Birthday-song special mode

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
有人对塔菲说：今天我朋友生日，你给唱个生日歌吧。
```

Output:

```text
可以，给寿星整点节目。

[唱]
祝你生日快乐
祝你生日快乐
祝你今天的愿望
全都排队实现喵
生日快乐喵

替 taffy 转告你朋友，今天就安心当主角，蛋糕多吃两口，蜡烛一口气吹完，愿望狠狠许喵。新一岁要开心、顺利、亮晶晶，生日快乐喵。
```

## What It Is Good At, And What It Refuses

### Good At

- Public-persona imitation under verified boundaries
- Weibo copy, dynamic posts, titles, stream notices, and short scripts
- Chinese subtitle-oriented production workflows
- Refreshing public data and building transcription / training candidates

### Not For

- Unverified gossip, real-world identity, or "middle-person" speculation
- Inventing "today's latest event"
- Reconstructing exact quotes without verification
- Reducing the character to a `喵` spam generator

## Sources

Current primary public sources:

- Weibo: `https://weibo.com/acetaffy`
- Bilibili space: `https://space.bilibili.com/1265680561`
- Bilibili live room: `https://live.bilibili.com/22603245`

Boundary and sourcing rules live here:

- `references/boundaries.md`
- `references/sources.md`
- `references/profile.md`

## Refreshing Public Data And STT Workflow

Install dependencies:

```bash
pip3 install -r requirements.txt
```

Refresh public Weibo / Bilibili data and corpus manifests:

```bash
python3 tools/source_refresh_public.py --target sources/targets/ace-taffy.json
```

This now writes partial Bilibili outputs plus `sources/raw/bilibili/_collector_state.json`.
If the run gets interrupted, rerun the same command to resume from already flushed results; use `--fresh` only when you want to discard fallback reuse.

Batch download and transcribe public Bilibili videos:

```bash
python3 tools/batch_bilibili_stt.py \
  --model large-v3 \
  --video-details sources/raw/bilibili/video_details.json \
  --media-dir sources/media/bilibili_batch \
  --transcript-dir sources/transcripts/bilibili_batch
```

Audit and build recommended training candidates:

```bash
python3 tools/audit_transcripts.py
python3 tools/build_training_set.py
python3 tools/build_style_bank.py
```

For a more explicit long-running Bilibili refresh:

```bash
python3 tools/source_refresh_public.py \
  --target sources/targets/ace-taffy.json \
  --steps bilibili,corpus \
  --http-retries 6 \
  --retry-backoff 1.8 \
  --save-every 10
```

### STT Output Compatibility

The current primary backend is `faster-whisper`, exporting:

- `srt` for most editors and players
- `vtt` for web workflows
- `json` for segmentation, review, and training
- `tsv` for spreadsheet-style review
- `txt` for quick browsing and search

See `references/stt-roadmap.md` for the fuller roadmap.

## Repo Layout

For release review, start here:

- `SKILL.md` for runtime rules
- `persona.md` for persona baseline
- `references/expression-dna.md` for style guidance
- `references/meow-pattern.md` for complete `喵` usage rules
- `references/self-reference.md` for the no-default-`我` self-reference protocol
- `sources/processed/` for lightweight summaries and audit outputs
- `tools/` for collection, transcription, audit, and corpus scripts

## Gallery Submission

If you want to submit this skill to `colleague-skill-site`:

- Issue draft: `submission/submit-skill-issue.md`
- Gallery draft entry: `submission/gallery-entry.inferred.yaml`
- Skill file URL: `https://github.com/ly-xxx/ace-taffy-skill/blob/main/SKILL.md`

## License

MIT. See `LICENSE`.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ly-xxx/ace-taffy-skill&type=Date)](https://star-history.com/#ly-xxx/ace-taffy-skill&Date)
