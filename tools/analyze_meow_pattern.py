#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


EMOJI_RANGES = (
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B50"
    "\uFE0F"
)

EMOJI_RE = re.compile(fr"[{EMOJI_RANGES}]")
MENTION_OR_HASHTAG_LEFT_RE = re.compile(r"(?:@[^@\s]{0,20}|#[^#\n]{0,50})$")
VOCATIVE_RE = re.compile(r"(?:雏草姬|taffy|塔菲|小菲)$", re.I)
SOFT_TAIL_CHARS = set(" ，,。；;：:、…~～)]}））》」』\t")


def load_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --text, --file, or stdin.")


def is_emoji(ch: str) -> bool:
    return bool(ch) and bool(EMOJI_RE.match(ch))


def classify_meow(text: str, index: int, run_length: int) -> str:
    prev = text[max(0, index - 12):index]
    next_text = text[index + run_length:index + run_length + 4]

    if run_length >= 2:
        if next_text.startswith("叫"):
            return "lexical_or_mimetic"
        return "redup_emphasis"

    if MENTION_OR_HASHTAG_LEFT_RE.search(prev):
        return "lexical_or_mimetic"

    if VOCATIVE_RE.search(prev):
        if not next_text:
            return "vocative_suffix"
        if next_text[0] in SOFT_TAIL_CHARS or next_text[0] in "!?！？" or is_emoji(next_text[0]):
            return "vocative_suffix"

    if next_text.startswith(("？", "?")):
        return "question_tail"

    if next_text.startswith(("！", "!")):
        return "exclaim_tail"

    if next_text and is_emoji(next_text[0]):
        return "emoji_tail"

    if not next_text or next_text[0] in SOFT_TAIL_CHARS:
        return "soft_tail"

    return "mid_clause_tail"


def iter_meow_tokens(text: str):
    i = 0
    while i < len(text):
        if text[i] != "喵":
            i += 1
            continue

        run_match = re.match(r"喵+", text[i:])
        run_length = len(run_match.group(0)) if run_match else 1
        end = i + run_length
        category = classify_meow(text, i, run_length)

        yield {
            "start": i,
            "end": end,
            "token": text[i:end],
            "category": category,
            "prefix": text[max(0, i - 18):i],
            "suffix": text[end:min(len(text), end + 18)],
        }
        i = end


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify the occurrence pattern of '喵' in text.")
    parser.add_argument("--text", help="Inline text to analyze")
    parser.add_argument("--file", help="Path to a UTF-8 text file to analyze")
    parser.add_argument("--summary-only", action="store_true", help="Only output summary counts")
    args = parser.parse_args()

    text = load_text(args)
    items = list(iter_meow_tokens(text))
    summary = Counter(item["category"] for item in items)

    payload = {
        "total_tokens": len(items),
        "summary": dict(summary),
    }
    if not args.summary_only:
        payload["items"] = items

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
