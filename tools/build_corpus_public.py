#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


KEY_PHRASES = [
    "永雏塔菲",
    "AceTaffy",
    "雏草姬",
    "喵",
    "虚拟偶像",
    "单机游戏",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_transcript_records(root: Path):
    for path in sorted(root.rglob("*.json")):
        try:
            payload = load_json(path)
        except Exception:
            continue

        if not isinstance(payload, dict) or "segments" not in payload:
            continue

        source_file = payload.get("input")
        for segment in payload.get("segments", []):
            text = normalize_text(segment.get("text") or "")
            if not text:
                continue

            yield {
                "source_type": "transcript_segment",
                "source_json": str(path),
                "source_media": source_file,
                "start": segment.get("start"),
                "end": segment.get("end"),
                "text": text,
                "words": segment.get("words") or [],
            }


def iter_weibo_records(root: Path):
    feeds_path = root / "weibo" / "feeds.json"
    if not feeds_path.exists():
        return

    try:
        payload = load_json(feeds_path)
    except Exception:
        return

    if not isinstance(payload, list):
        return

    for item in payload:
        text = normalize_text(item.get("text_plain") or "")
        if not text:
            continue

        yield {
            "source_type": "weibo_feed",
            "source_id": item.get("mid") or item.get("id"),
            "url": item.get("url"),
            "created_at": item.get("created_at"),
            "text": text,
        }

        repost_text = normalize_text(item.get("repost_text_plain") or "")
        if repost_text:
            yield {
                "source_type": "weibo_repost_text",
                "source_id": item.get("mid") or item.get("id"),
                "url": item.get("url"),
                "created_at": item.get("created_at"),
                "text": repost_text,
            }


def iter_bilibili_records(root: Path):
    details_path = root / "bilibili" / "video_details.json"
    if details_path.exists():
        try:
            payload = load_json(details_path)
        except Exception:
            payload = []

        if isinstance(payload, list):
            for item in payload:
                title = normalize_text(item.get("title") or "")
                desc = normalize_text(item.get("desc") or "")
                text = "\n".join(part for part in [title, desc] if part).strip()
                if not text:
                    continue

                yield {
                    "source_type": "bilibili_video",
                    "source_id": item.get("bvid"),
                    "url": item.get("source_url"),
                    "created_at": item.get("pubdate"),
                    "text": text,
                }

    live_path = root / "bilibili" / "live.json"
    if live_path.exists():
        try:
            payload = load_json(live_path)
        except Exception:
            payload = {}

        room_info = (payload.get("room_info") or {}) if isinstance(payload, dict) else {}
        chunks = [
            normalize_text(room_info.get("title") or ""),
            normalize_text(room_info.get("description") or ""),
            normalize_text(room_info.get("tags") or ""),
        ]
        text = "\n".join(part for part in chunks if part).strip()
        if text:
            yield {
                "source_type": "bilibili_live_room",
                "source_id": room_info.get("room_id"),
                "url": f"https://live.bilibili.com/{room_info.get('room_id')}" if room_info.get("room_id") else "",
                "created_at": None,
                "text": text,
            }


def build_phrase_counts(records: list[dict]) -> Counter:
    phrases = Counter()
    for record in records:
        text = record["text"]
        for needle in KEY_PHRASES:
            if needle in text:
                phrases[needle] += 1
    return phrases


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build transcript and source corpora for ace-taffy.skill.")
    parser.add_argument("--raw-dir", default="sources/raw", help="Directory containing raw platform captures")
    parser.add_argument("--transcript-dir", default="sources/transcripts", help="Directory containing transcript JSON files")
    parser.add_argument("--output-dir", default="sources/processed/corpus", help="Directory for corpus output")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).expanduser()
    transcript_dir = Path(args.transcript_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    transcript_records = list(iter_transcript_records(transcript_dir))
    source_records = list(iter_weibo_records(raw_dir)) + list(iter_bilibili_records(raw_dir))
    combined_records = source_records + transcript_records

    transcript_jsonl = output_dir / "transcript_corpus.jsonl"
    source_jsonl = output_dir / "source_text_corpus.jsonl"
    combined_jsonl = output_dir / "combined_corpus.jsonl"
    phrases_path = output_dir / "hot_phrases.txt"
    prompt_path = output_dir / "stt_initial_prompt.txt"

    write_jsonl(transcript_jsonl, transcript_records)
    write_jsonl(source_jsonl, source_records)
    write_jsonl(combined_jsonl, combined_records)

    phrases = build_phrase_counts(combined_records)
    phrase_lines = [f"{term}\t{count}" for term, count in phrases.most_common()]
    phrases_path.write_text("\n".join(phrase_lines) + ("\n" if phrase_lines else ""), encoding="utf-8")

    prompt_terms = [term for term in KEY_PHRASES if phrases.get(term) or term in {"永雏塔菲", "AceTaffy", "雏草姬", "喵"}]
    prompt_path.write_text("，".join(prompt_terms) + "\n", encoding="utf-8")

    summary = {
        "source_records": len(source_records),
        "transcript_records": len(transcript_records),
        "combined_records": len(combined_records),
        "transcript_jsonl": str(transcript_jsonl),
        "source_jsonl": str(source_jsonl),
        "combined_jsonl": str(combined_jsonl),
        "hot_phrases": str(phrases_path),
        "stt_initial_prompt": str(prompt_path),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] transcripts -> {transcript_jsonl}")
    print(f"[OK] sources     -> {source_jsonl}")
    print(f"[OK] combined    -> {combined_jsonl}")
    print(f"[OK] prompt      -> {prompt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
