#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path


BVID_PATTERN = re.compile(r"(BV[0-9A-Za-z]+)")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def count_chars(text: str) -> dict[str, int]:
    counts = {
        "cjk": 0,
        "latin": 0,
        "digit": 0,
        "other": 0,
    }
    for char in text:
        if "\u4e00" <= char <= "\u9fff":
            counts["cjk"] += 1
        elif "A" <= char <= "Z" or "a" <= char <= "z":
            counts["latin"] += 1
        elif "0" <= char <= "9":
            counts["digit"] += 1
        elif not char.isspace():
            counts["other"] += 1
    return counts


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def model_priority(model: str | None) -> int:
    value = (model or "").lower()
    priorities = {
        "large-v3": 5,
        "distil-large-v3": 4,
        "medium": 3,
        "small": 2,
        "base": 1,
        "tiny": 0,
    }
    return priorities.get(value, -1)


def find_bvid(path: Path, payload: dict) -> str:
    candidates = [
        str(payload.get("input") or ""),
        path.name,
        path.stem,
    ]
    for candidate in candidates:
        match = BVID_PATTERN.search(candidate)
        if match:
            return match.group(1)
    return ""


def compute_score(
    *,
    segment_count: int,
    duration: float,
    char_count: int,
    cjk_ratio: float,
    unique_ratio: float,
    repeated_top_ratio: float,
) -> float:
    if segment_count == 0 or char_count == 0:
        return 0.0

    chars_per_minute = (char_count / duration) * 60.0 if duration > 0 else 0.0
    density_score = 0.0
    if chars_per_minute > 0:
        ideal_low = 120.0
        ideal_high = 420.0
        if chars_per_minute < ideal_low:
            density_score = (chars_per_minute / ideal_low) * 20.0
        elif chars_per_minute <= ideal_high:
            density_score = 20.0
        else:
            density_score = max(0.0, 20.0 - ((chars_per_minute - ideal_high) / ideal_high) * 10.0)

    segment_score = clamp(segment_count / 4.0, 0.0, 25.0)
    cjk_score = clamp(cjk_ratio * 25.0, 0.0, 25.0)
    unique_score = clamp(unique_ratio * 20.0, 0.0, 20.0)
    repetition_penalty = clamp(repeated_top_ratio * 20.0, 0.0, 20.0)
    char_score = clamp(char_count / 50.0, 0.0, 10.0)

    return round(max(0.0, segment_score + cjk_score + unique_score + density_score + char_score - repetition_penalty), 2)


def classify_usability(score: float, segment_count: int, char_count: int) -> str:
    if segment_count == 0 or char_count < 20:
        return "low"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def load_video_lookup(path: Path | None) -> dict[str, dict]:
    if not path or not path.exists():
        return {}
    try:
        payload = load_json(path)
    except Exception:
        return {}
    if not isinstance(payload, list):
        return {}
    lookup = {}
    for item in payload:
        if isinstance(item, dict) and item.get("bvid"):
            lookup[str(item["bvid"])] = item
    return lookup


def audit_transcript(path: Path, video_lookup: dict[str, dict]) -> dict | None:
    try:
        payload = load_json(path)
    except Exception:
        return None

    if not isinstance(payload, dict) or "segments" not in payload:
        return None

    segments = payload.get("segments")
    if not isinstance(segments, list):
        return None

    texts = [str(segment.get("text") or "").strip() for segment in segments]
    nonempty_texts = [text for text in texts if text]
    merged_text = "".join(nonempty_texts)
    char_counts = count_chars(merged_text)
    char_count = sum(char_counts.values())
    segment_count = len(nonempty_texts)
    unique_texts = len(set(nonempty_texts))
    unique_ratio = (unique_texts / segment_count) if segment_count else 0.0
    repeated_top_ratio = 0.0
    if segment_count:
        repeated_top_ratio = max(Counter(nonempty_texts).values()) / segment_count

    duration = float(payload.get("duration") or 0.0)
    if duration <= 0 and nonempty_texts:
        duration = max(float(segment.get("end") or 0.0) for segment in segments)

    cjk_ratio = (char_counts["cjk"] / char_count) if char_count else 0.0
    score = compute_score(
        segment_count=segment_count,
        duration=duration,
        char_count=char_count,
        cjk_ratio=cjk_ratio,
        unique_ratio=unique_ratio,
        repeated_top_ratio=repeated_top_ratio,
    )
    usability = classify_usability(score, segment_count, char_count)

    bvid = find_bvid(path, payload)
    video_meta = video_lookup.get(bvid, {})
    chars_per_minute = round((char_count / duration) * 60.0, 2) if duration > 0 else 0.0
    sample_text = " ".join(nonempty_texts[:5])[:240]

    return {
        "path": str(path),
        "relative_path": str(path),
        "bvid": bvid,
        "title": video_meta.get("title") or path.stem,
        "video_duration": video_meta.get("duration"),
        "transcript_duration": duration,
        "model": payload.get("model"),
        "device": payload.get("device"),
        "compute_type": payload.get("compute_type"),
        "vad_filter": payload.get("vad_filter"),
        "segment_count": segment_count,
        "char_count": char_count,
        "cjk_ratio": round(cjk_ratio, 4),
        "unique_segment_ratio": round(unique_ratio, 4),
        "top_repeat_ratio": round(repeated_top_ratio, 4),
        "chars_per_minute": chars_per_minute,
        "quality_score": score,
        "usability": usability,
        "sample_text": sample_text,
    }


def write_tsv(path: Path, rows: list[dict]) -> None:
    columns = [
        "usability",
        "quality_score",
        "bvid",
        "title",
        "model",
        "vad_filter",
        "segment_count",
        "char_count",
        "cjk_ratio",
        "unique_segment_ratio",
        "top_repeat_ratio",
        "chars_per_minute",
        "path",
    ]
    lines = ["\t".join(columns)]
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                value = f"{value:.4f}" if not math.isclose(value, round(value, 2)) else f"{value:.2f}"
            values.append(str(value).replace("\t", " "))
        lines.append("\t".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def choose_best_by_bvid(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        key = row["bvid"] or row["path"]
        grouped.setdefault(key, []).append(row)

    best_rows = []
    for group in grouped.values():
        selected = max(
            group,
            key=lambda row: (
                round(float(row["quality_score"])),
                model_priority(row.get("model")),
                float(row["quality_score"]),
                row["segment_count"],
                row["char_count"],
            ),
        )
        best_rows.append(selected)

    best_rows.sort(key=lambda item: (item["quality_score"], model_priority(item.get("model")), item["segment_count"]), reverse=True)
    return best_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transcript JSON files and rank likely usable samples.")
    parser.add_argument("--input-dir", default="sources/transcripts", help="Directory containing transcript JSON files")
    parser.add_argument("--video-details", default="sources/raw/bilibili/video_details.json", help="Optional Bilibili video details JSON")
    parser.add_argument("--output-json", default="sources/processed/transcript-audit.json", help="Audit JSON output path")
    parser.add_argument("--output-tsv", default="sources/processed/transcript-audit.tsv", help="Audit TSV output path")
    parser.add_argument("--output-best-tsv", help="Optional TSV containing only best_by_bvid rows")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser()
    output_json = Path(args.output_json).expanduser()
    output_tsv = Path(args.output_tsv).expanduser()
    output_best_tsv = Path(args.output_best_tsv).expanduser() if args.output_best_tsv else output_tsv.with_name(f"{output_tsv.stem}-best-by-bvid{output_tsv.suffix}")
    video_lookup = load_video_lookup(Path(args.video_details).expanduser())

    rows = []
    for path in sorted(input_dir.rglob("*.json")):
        row = audit_transcript(path, video_lookup)
        if row:
            rows.append(row)

    rows.sort(key=lambda item: (item["quality_score"], item["segment_count"], item["char_count"]), reverse=True)
    best_rows = choose_best_by_bvid(rows)
    summary = {
        "transcript_count": len(rows),
        "usability_counts": dict(Counter(row["usability"] for row in rows)),
        "top_candidates": rows[:20],
        "best_by_bvid": best_rows[:20],
        "items": rows,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(output_tsv, rows)
    write_tsv(output_best_tsv, best_rows)

    print(f"[OK] audit json -> {output_json}")
    print(f"[OK] audit tsv  -> {output_tsv}")
    print(f"[OK] best tsv   -> {output_best_tsv}")
    print(f"[OK] transcripts -> {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
