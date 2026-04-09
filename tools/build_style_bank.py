#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


CATEGORY_RULES = {
    "story_openers": [
        r"今天",
        r"前两天",
        r"最近",
        r"刚刚",
        r"早上",
        r"出门前",
        r"那天",
        r"要是",
        r"如果",
    ],
    "incident_broadcast": [
        r"什么情况",
        r"发生",
        r"遭遇",
        r"消息",
        r"新闻",
        r"不小心",
        r"直播间",
        r"事故",
        r"诅咒",
        r"灭亡",
    ],
    "self_reference": [
        r"taffy",
        r"Taffy",
        r"塔菲",
        r"小菲",
    ],
    "fan_address": [
        r"雏草姬",
        r"你们",
        r"大家",
        r"诸位",
    ],
    "reaction_pivots": [
        r"不是",
        r"怎么",
        r"什么",
        r"等一下",
        r"对不起",
        r"真的假的",
        r"看一下",
    ],
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def char_mix(text: str) -> tuple[int, int]:
    cjk = 0
    total = 0
    for char in text:
        if char.isspace():
            continue
        total += 1
        if "\u4e00" <= char <= "\u9fff":
            cjk += 1
    return cjk, total


def classify_text(text: str) -> list[str]:
    matched = []
    for category, patterns in CATEGORY_RULES.items():
        if any(re.search(pattern, text, flags=re.I) for pattern in patterns):
            matched.append(category)
    return matched


def score_text(row: dict, text: str) -> tuple[float, int]:
    cjk, total = char_mix(text)
    cjk_ratio = (cjk / total) if total else 0.0
    quality = float(row.get("quality_score") or 0.0)
    length_bonus = min(total, 45) / 45.0
    score = quality * 0.7 + cjk_ratio * 20.0 + length_bonus * 10.0
    return score, total


def collect_examples(rows: list[dict], *, max_per_category: int) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    seen_texts: set[str] = set()

    sorted_rows = sorted(
        rows,
        key=lambda row: (float(row.get("quality_score") or 0.0), row.get("char_count") or 0),
        reverse=True,
    )

    for row in sorted_rows:
        text = normalize_text(str(row.get("text") or ""))
        if not text:
            continue
        if text in seen_texts:
            continue

        cjk, total = char_mix(text)
        if total < 8:
            continue
        if total > 80:
            continue
        if total and (cjk / total) < 0.35:
            continue

        categories = classify_text(text)
        if not categories:
            continue

        score, char_count = score_text(row, text)
        example = {
            "text": text,
            "bvid": row.get("bvid"),
            "title": row.get("title"),
            "quality_score": row.get("quality_score"),
            "char_count": char_count,
            "score": round(score, 2),
            "source_json": row.get("source_json"),
            "start": row.get("start"),
            "end": row.get("end"),
        }

        accepted = False
        for category in categories:
            if len(buckets[category]) >= max_per_category:
                continue
            buckets[category].append(example)
            accepted = True
        if accepted:
            seen_texts.add(text)

    for category, examples in buckets.items():
        examples.sort(key=lambda item: (item["score"], item["char_count"]), reverse=True)

    return dict(buckets)


def render_markdown(examples: dict[str, list[dict]]) -> str:
    lines = [
        "# Style Bank",
        "",
        "这份风格片段库从 `transcript_train_recommended.jsonl` 自动抽取，优先保留高质量、较短、口播感明显的句段。",
        "",
        "使用方式：",
        "",
        "- 不要整段照抄。",
        "- 重点学习句式推进、事故播报感、自称复现和互动结构。",
        "- 当多个类别同时命中时，优先模仿节奏，不要机械复制字面内容。",
        "",
    ]

    labels = {
        "story_openers": "Story Openers",
        "incident_broadcast": "Incident Broadcast",
        "self_reference": "Self Reference",
        "fan_address": "Fan Address",
        "reaction_pivots": "Reaction Pivots",
    }

    for category in ["story_openers", "incident_broadcast", "self_reference", "fan_address", "reaction_pivots"]:
        rows = examples.get(category) or []
        lines.append(f"## {labels[category]}")
        lines.append("")
        if not rows:
            lines.append("- 暂无样本")
            lines.append("")
            continue
        for row in rows[:10]:
            lines.append(f"- `{row['text']}`")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a style bank from recommended transcript training data.")
    parser.add_argument("--input-jsonl", default="sources/processed/training/transcript_train_recommended.jsonl", help="Recommended transcript JSONL")
    parser.add_argument("--output-json", default="sources/processed/style-bank.json", help="Style bank JSON output")
    parser.add_argument("--output-md", default="references/style-bank.md", help="Style bank Markdown output")
    parser.add_argument("--max-per-category", type=int, default=24, help="Maximum examples per category")
    args = parser.parse_args()

    input_path = Path(args.input_jsonl).expanduser()
    output_json = Path(args.output_json).expanduser()
    output_md = Path(args.output_md).expanduser()

    rows = load_jsonl(input_path)
    examples = collect_examples(rows, max_per_category=args.max_per_category)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_jsonl": str(input_path),
        "category_counts": {key: len(value) for key, value in examples.items()},
        "examples": examples,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(examples), encoding="utf-8")

    print(f"[OK] style bank json -> {output_json}")
    print(f"[OK] style bank md   -> {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
