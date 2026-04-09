#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


USABILITY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}

MODEL_PRIORITY = {
    "large-v3": 5,
    "distil-large-v3": 4,
    "medium": 3,
    "small": 2,
    "base": 1,
    "tiny": 0,
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def char_mix(text: str) -> dict[str, int]:
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


def usability_at_least(value: str, floor: str) -> bool:
    return USABILITY_ORDER.get(value, -1) >= USABILITY_ORDER.get(floor, -1)


def model_priority(value: str | None) -> int:
    return MODEL_PRIORITY.get((value or "").lower(), -1)


def load_audit_rows(path: Path, *, min_usability: str, best_only: bool) -> list[dict]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        return []

    key = "best_by_bvid" if best_only else "items"
    rows = payload.get(key) or []
    if not isinstance(rows, list):
        return []

    selected = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not usability_at_least(str(row.get("usability") or "low"), min_usability):
            continue
        path_value = row.get("path")
        if not path_value:
            continue
        selected.append(row)
    return selected


def iter_segment_records(
    rows: list[dict],
    *,
    min_chars: int,
    min_cjk_ratio: float,
) -> list[dict]:
    records = []
    skipped = Counter()

    for row in rows:
        transcript_path = Path(str(row["path"])).expanduser()
        try:
            payload = load_json(transcript_path)
        except Exception:
            skipped["transcript_load_error"] += 1
            continue

        segments = payload.get("segments")
        if not isinstance(segments, list):
            skipped["missing_segments"] += 1
            continue

        for segment in segments:
            text = normalize_text(str(segment.get("text") or ""))
            if not text:
                skipped["empty_text"] += 1
                continue

            mix = char_mix(text)
            total = sum(mix.values())
            cjk_ratio = (mix["cjk"] / total) if total else 0.0

            if total < min_chars:
                skipped["too_short"] += 1
                continue
            if cjk_ratio < min_cjk_ratio:
                skipped["low_cjk_ratio"] += 1
                continue

            records.append({
                "source_type": "transcript_segment",
                "selection_mode": "best_by_bvid",
                "usability": row.get("usability"),
                "quality_score": row.get("quality_score"),
                "bvid": row.get("bvid"),
                "title": row.get("title"),
                "model": row.get("model"),
                "vad_filter": row.get("vad_filter"),
                "source_json": str(transcript_path),
                "source_media": payload.get("input"),
                "start": segment.get("start"),
                "end": segment.get("end"),
                "text": text,
                "char_count": total,
                "cjk_ratio": round(cjk_ratio, 4),
            })

    return records, skipped


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_tsv(path: Path, rows: list[dict]) -> None:
    columns = ["usability", "quality_score", "bvid", "title", "model", "segment_count", "char_count", "path"]
    lines = ["\t".join(columns)]
    for row in rows:
        values = [str(row.get(column, "")).replace("\t", " ") for column in columns]
        lines.append("\t".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_records(records: list[dict]) -> dict:
    usage = Counter(record["usability"] for record in records)
    bvids = Counter(record["bvid"] for record in records if record.get("bvid"))
    models = Counter(record["model"] for record in records if record.get("model"))
    return {
        "records": len(records),
        "usability_counts": dict(usage),
        "bvid_count": len(bvids),
        "model_counts": dict(models),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a train-ready transcript dataset from audited transcript files.")
    parser.add_argument("--audit-json", default="sources/processed/transcript-audit.json", help="Audit JSON from audit_transcripts.py")
    parser.add_argument("--output-dir", default="sources/processed/training", help="Output directory")
    parser.add_argument("--min-usability", default="medium", choices=["low", "medium", "high"], help="Minimum usability to include")
    parser.add_argument("--min-chars", type=int, default=6, help="Minimum non-space characters per segment")
    parser.add_argument("--min-cjk-ratio", type=float, default=0.35, help="Minimum CJK ratio per segment")
    parser.add_argument("--recommended-min-score", type=float, default=55.0, help="Minimum transcript quality score for recommended large-v3 export")
    parser.add_argument("--high-only-min-chars", type=int, default=4, help="Minimum chars for high-only export")
    parser.add_argument("--high-only-min-cjk-ratio", type=float, default=0.2, help="Minimum CJK ratio for high-only export")
    args = parser.parse_args()

    audit_path = Path(args.audit_json).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    medium_rows = load_audit_rows(audit_path, min_usability=args.min_usability, best_only=True)
    high_rows = load_audit_rows(audit_path, min_usability="high", best_only=True)
    recommended_rows = [
        row
        for row in medium_rows
        if model_priority(str(row.get("model") or "")) >= MODEL_PRIORITY["large-v3"]
        and float(row.get("quality_score") or 0.0) >= args.recommended_min_score
    ]

    medium_records, medium_skipped = iter_segment_records(
        medium_rows,
        min_chars=args.min_chars,
        min_cjk_ratio=args.min_cjk_ratio,
    )
    high_records, high_skipped = iter_segment_records(
        high_rows,
        min_chars=args.high_only_min_chars,
        min_cjk_ratio=args.high_only_min_cjk_ratio,
    )
    recommended_records, recommended_skipped = iter_segment_records(
        recommended_rows,
        min_chars=args.min_chars,
        min_cjk_ratio=args.min_cjk_ratio,
    )

    train_jsonl = output_dir / "transcript_train_ready.jsonl"
    high_jsonl = output_dir / "transcript_train_high.jsonl"
    recommended_jsonl = output_dir / "transcript_train_recommended.jsonl"
    selected_tsv = output_dir / "selected_transcripts.tsv"
    summary_path = output_dir / "summary.json"

    write_jsonl(train_jsonl, medium_records)
    write_jsonl(high_jsonl, high_records)
    write_jsonl(recommended_jsonl, recommended_records)
    write_tsv(selected_tsv, medium_rows)

    summary = {
        "audit_json": str(audit_path),
        "selection_mode": "best_by_bvid",
        "min_usability": args.min_usability,
        "min_chars": args.min_chars,
        "min_cjk_ratio": args.min_cjk_ratio,
        "train_ready": {
            "path": str(train_jsonl),
            **summarize_records(medium_records),
            "skipped_segment_reasons": dict(medium_skipped),
        },
        "high_only": {
            "path": str(high_jsonl),
            **summarize_records(high_records),
            "skipped_segment_reasons": dict(high_skipped),
        },
        "recommended_large_v3": {
            "path": str(recommended_jsonl),
            "min_quality_score": args.recommended_min_score,
            **summarize_records(recommended_records),
            "skipped_segment_reasons": dict(recommended_skipped),
        },
        "selected_transcripts_tsv": str(selected_tsv),
        "selected_bvids": [
            {
                "bvid": row.get("bvid"),
                "title": row.get("title"),
                "model": row.get("model"),
                "quality_score": row.get("quality_score"),
                "usability": row.get("usability"),
                "path": row.get("path"),
            }
            for row in medium_rows
        ],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] train ready -> {train_jsonl}")
    print(f"[OK] high only   -> {high_jsonl}")
    print(f"[OK] recommended -> {recommended_jsonl}")
    print(f"[OK] selected    -> {selected_tsv}")
    print(f"[OK] summary     -> {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
