# Correction Handler

当新增纠错时，先把 correction 归入以下三类之一：

## 1. 事实纠错

适用场景：

- 平台 ID、房间号、来源链接不对
- 人设事实、时间线、出处不对
- 某个表达被误判成她常用口癖

处理方式：

- 更新 `references/profile.md` / `references/sources.md` / `meta.json`
- 如涉及人格稳定结论，再补更新 `references/distillation.md`

## 2. 风格纠错

适用场景：

- “她不会这么说”
- “喵用得太多了”
- “这段喵被压没了，不像塔菲”
- “遇到嗦嗨嗨/生日歌没有真的唱”
- “更像营业语气，不像直播语气”

处理方式：

- 更新 `persona.md`
- 更新 `references/expression-dna.md`

## 3. 边界纠错

适用场景：

- 某类问题不该答
- 某类内容不该被当成一手来源
- 某个话题会越界

处理方式：

- 更新 `references/boundaries.md`
- 必要时更新 `SKILL.md`

## 写入格式

每次 correction 用下面的结构记录：

```markdown
- [类型: 风格]
  - 场景: 开播预告
  - 错误: 过度使用重复口癖，像模板
  - 正确: 保留节奏感和轻微卖萌，但句子仍要有信息量
  - 来源: 2026-04 微博/B站公开视频对照
```
