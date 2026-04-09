# taffy.skill

> A persona skill distilled from Yongchu Taffy's official public Weibo and Bilibili content, built for public-facing roleplay, stream copywriting, short-form voiceover, and Chinese subtitle workflows.

[中文（主 README）](./README.md) · English

Install · Usage · Real Outputs · Sources · STT Workflow · Repo Layout · Gallery Submission

`taffy.skill` is the repository name. The actual local skill slug is `ace-taffy`.

## What This Is

This is not a shallow "cute-tone wrapper" and not a quote collage.

The repository contains three layers:

- The installable skill itself: `SKILL.md`, `persona.md`, `references/`
- Tooling for refreshing public Weibo / Bilibili data, subtitle transcription, and corpus filtering: `tools/`
- Lightweight audit, summary, and submission materials: `sources/processed/`, `submission/`

Large raw media, full transcripts, and training JSONL files are intentionally excluded from the public repo.

## Snapshot

- Updated: `2026-04-09`
- Primary-source records: `941`
- Transcript chunks: `2751`
- Merged corpus records: `3692`
- Recommended training chunks: `1377`
- Recommended filter: `large-v3` with `quality_score >= 55`
- Default STT exports: `json`, `srt`, `vtt`, `tsv`, `txt`

## Install

### Codex

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/ly-xxx/taffy.skill ~/.codex/skills/ace-taffy
```

If you want live-edit behavior during local development:

```bash
git clone https://github.com/ly-xxx/taffy.skill ~/work/taffy.skill
mkdir -p ~/.codex/skills
ln -s ~/work/taffy.skill ~/.codex/skills/ace-taffy
```

Restart Codex or open a new session after installation.

### Claude Code

Global install:

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/ly-xxx/taffy.skill ~/.claude/skills/ace-taffy
```

Project-local install:

```bash
mkdir -p .claude/skills
git clone https://github.com/ly-xxx/taffy.skill .claude/skills/ace-taffy
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

A successful output should visibly use `taffy` / `塔菲` as self-reference and avoid stuffing `喵` into every sentence.

One real local run on `2026-04-09` produced:

```text
被时间乱流绊了一下，taffy这不是火速冲来了嘛。雏草姬先别记小本本，晚到的份补双倍营业喵。
```

## Good Prompt Shapes

This skill works best for:

- Public-facing Taffy-style dialogue
- Stream announcements, dynamic posts, short-form scripts, and fan replies
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

These are real outputs generated locally with the installed `ace-taffy` skill on `2026-04-09`.

### 1. Weibo-style stream announcement

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一条微博风格的开播预告，30到50字，主题是今晚播恐怖游戏。
不要编造最新事实。
```

Output:

```text
今晚塔菲要去恐怖游戏里查案了，雏草姬来直播间当护身符，不然主播真的要出事故喵👁️
```

### 2. Post-stream dynamic

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一段4句左右的下播后动态，主题是今天玩游戏玩得很累但很满足。
不要编造最新事实。
```

Output:

```text
今天玩游戏，taffy不是在打流程，是在和体力还有脑细胞正面对决。
手也酸了，脑子也转得冒烟了，但一关一关啃过去的时候，塔菲又会觉得，嗯，这种累很值。
累是真的累，满足也是真的满足，属于下播以后瘫着都还想回味一下的程度。
雏草姬今天也辛苦了，taffy先去充电，今天这份成就感先抱走喵。
```

### 3. Short video cover copy

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写3条短视频封面文案，每条一行，主题是“直播间设备又闹鬼了”。
不要编造最新事实。
```

Output:

```text
不是，taffy直播间设备又闹鬼了？
今日事故播报：麦克风摄像头集体中邪
这直播间到底住了几个电子幽灵喵
```

### 4. Fan reply

Prompt:

```text
请使用 ace-taffy skill，只输出最终成稿，不要解释。
写一条对粉丝评论“今天怎么这么晚才来”的回复，要像公开互动语境。
不要编造最新事实。
```

Output:

```text
不是晚，是taffy今天走压轴路线，雏草姬一催，主角这不就到场了喵。
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
- Skill file URL: `https://github.com/ly-xxx/taffy.skill/blob/main/SKILL.md`

## License

MIT. See `LICENSE`.
