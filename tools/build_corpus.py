#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def iter_transcript_records(root: Path):
    for path in sorted(root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(payload, dict) or "segments" not in payload:
            continue

        source_file = payload.get("input")
        for segment in payload.get("segments", []):
            text = (segment.get("text") or "").strip()
            if not text:
                continue

            yield {
                "source_kind": "transcript",
                "source_json": str(path),
                "source_media": source_file,
                "start": segment.get("start"),
                "end": segment.get("end"),
                "text": text,
                "words": segment.get("words") or [],
            }


def iter_weibo_records(path: Path):
    if not path.exists():
        return

    try:
        feeds = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return

    for item in feeds:
        if not isinstance(item, dict):
            continue
        text = (
            item.get("text_plain")
            or item.get("text")
            or item.get("text_html")
            or ""
        ).strip()
        if not text:
            continue

        yield {
            "source_kind": "weibo-feed",
            "source_id": item.get("id"),
            "created_at": item.get("created_at"),
            "text": text,
        }

        retweeted = item.get("retweeted_status") or {}
        retweeted_text = (
            (retweeted.get("text_plain") if isinstance(retweeted, dict) else None)
            or item.get("repost_text_plain")
            or item.get("repost_text")
            or ""
        ).strip()
        if retweeted_text:
            yield {
                "source_kind": "weibo-retweet",
                "source_id": retweeted.get("id") if isinstance(retweeted, dict) else None,
                "created_at": retweeted.get("created_at") if isinstance(retweeted, dict) else None,
                "text": retweeted_text,
            }


def iter_bilibili_video_records(path: Path):
    if not path.exists():
        return

    try:
        details = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return

    for item in details:
        if not isinstance(item, dict):
            continue
        if item.get("title"):
            yield {
                "source_kind": "bilibili-video-title",
                "source_id": item.get("bvid"),
                "created_at": item.get("pubdate"),
                "text": item["title"].strip(),
            }
        if item.get("desc"):
            yield {
                "source_kind": "bilibili-video-desc",
                "source_id": item.get("bvid"),
                "created_at": item.get("pubdate"),
                "text": item["desc"].strip(),
            }


def iter_bilibili_dynamic_records(path: Path):
    if not path.exists():
        return

    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return

    for item in items:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        yield {
            "source_kind": "bilibili-dynamic",
            "source_id": item.get("link") or item.get("title"),
            "created_at": item.get("published_at"),
            "text": text,
        }


def iter_bilibili_live_records(path: Path):
    if not path.exists():
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return

    room_info = payload.get("room_info") or {}
    for label, value in [
        ("bilibili-live-title", room_info.get("title")),
        ("bilibili-live-description", room_info.get("description")),
        ("bilibili-live-tags", room_info.get("tags")),
    ]:
        text = (value or "").strip()
        if not text:
            continue
        yield {
            "source_kind": label,
            "source_id": room_info.get("room_id"),
            "created_at": room_info.get("live_time"),
            "text": text,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a JSONL corpus from transcripts and public text sources.")
    parser.add_argument("--input-dir", default="sources/transcripts", help="Directory containing transcript json files")
    parser.add_argument("--weibo-feeds", default="sources/raw/weibo/feeds.json", help="Weibo feeds json")
    parser.add_argument("--bilibili-details", default="sources/raw/bilibili/video_details.json", help="Bilibili video details json")
    parser.add_argument("--bilibili-dynamics", default="sources/raw/bilibili/dynamics.json", help="Bilibili dynamics json")
    parser.add_argument("--bilibili-live", default="sources/raw/bilibili/live.json", help="Bilibili live info json")
    parser.add_argument("--output-dir", default="sources/processed/corpus", help="Directory for corpus output")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    records = [
        *list(iter_transcript_records(input_dir)),
        *list(iter_weibo_records(Path(args.weibo_feeds).expanduser())),
        *list(iter_bilibili_video_records(Path(args.bilibili_details).expanduser())),
        *list(iter_bilibili_dynamic_records(Path(args.bilibili_dynamics).expanduser())),
        *list(iter_bilibili_live_records(Path(args.bilibili_live).expanduser())),
    ]

    jsonl_path = output_dir / "transcript_corpus.jsonl"
    phrases_path = output_dir / "hot_phrases.txt"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    phrases = Counter()
    for record in records:
        text = record["text"]
        for needle in ("taffy", "塔菲", "雏草姬", "喵"):
            if needle in text:
                phrases[needle] += 1

    phrase_lines = [f"{term}\t{count}" for term, count in phrases.most_common()]
    phrases_path.write_text("\n".join(phrase_lines) + ("\n" if phrase_lines else ""), encoding="utf-8")

    source_kind_counts = Counter(record["source_kind"] for record in records)
    summary = {
        "records": len(records),
        "source_kind_counts": dict(source_kind_counts),
        "jsonl": str(jsonl_path),
        "hot_phrases": str(phrases_path),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] corpus -> {jsonl_path}")
    print(f"[OK] hot phrases -> {phrases_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
