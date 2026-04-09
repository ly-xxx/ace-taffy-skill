#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run_step(command: list[str]) -> int:
    print("[RUN]", " ".join(command))
    result = subprocess.run(command, check=False)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh ace-taffy public sources using stable collectors.")
    parser.add_argument(
        "--target",
        default="sources/targets/ace-taffy.json",
        help="Target manifest path",
    )
    parser.add_argument(
        "--steps",
        default="weibo,bilibili,corpus",
        help="Comma-separated steps: weibo,bilibili,corpus",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore existing bilibili outputs and avoid fallback reuse",
    )
    parser.add_argument(
        "--http-retries",
        type=int,
        default=6,
        help="HTTP retry attempts passed to bilibili collector",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=1.8,
        help="Base retry backoff passed to bilibili collector",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=20,
        help="Partial flush cadence passed to long-running bilibili steps",
    )
    args = parser.parse_args()

    target_path = Path(args.target).expanduser()
    manifest = json.loads(target_path.read_text(encoding="utf-8"))
    root = target_path.parent.parent.parent
    steps = {item.strip() for item in args.steps.split(",") if item.strip()}
    failures = 0

    if "weibo" in steps:
        weibo = manifest["canonical_sources"]["weibo"]
        rc = run_step([
            "python3",
            str(root / "tools" / "collect_weibo_public.py"),
            "--uid",
            weibo["uid"],
            "--domain",
            weibo["domain"],
            "--force-html-spider",
            "--limit",
            str(manifest["collection_defaults"]["weibo_limit"]),
            "--comments-per-post",
            str(manifest["collection_defaults"]["weibo_comments_per_post"]),
            "--max-pages",
            str(manifest["collection_defaults"]["weibo_max_pages"]),
            "--output-dir",
            str(root / "sources" / "raw" / "weibo"),
        ])
        failures += int(rc != 0)

    if "bilibili" in steps:
        bili = manifest["canonical_sources"]["bilibili"]
        keywords = ",".join(manifest["collection_defaults"]["bilibili_search_keywords"])
        command = [
            "python3",
            str(root / "tools" / "collect_bilibili_public.py"),
            "--target",
            str(target_path),
            "--mid",
            bili["mid"],
            "--room-id",
            bili["room_id"],
            "--video-limit",
            str(manifest["collection_defaults"]["bilibili_video_limit"]),
            "--dynamic-limit",
            str(manifest["collection_defaults"]["bilibili_dynamic_limit"]),
            "--comment-limit",
            str(manifest["collection_defaults"]["bilibili_comment_limit"]),
            "--comment-video-limit",
            str(manifest["collection_defaults"]["bilibili_comment_video_limit"]),
            "--keywords",
            keywords,
            "--search-pages",
            str(manifest["collection_defaults"]["bilibili_search_pages"]),
            "--playurl-limit",
            str(manifest["collection_defaults"]["bilibili_playurl_limit"]),
            "--http-retries",
            str(args.http_retries),
            "--retry-backoff",
            str(args.retry_backoff),
            "--save-every",
            str(args.save_every),
            "--output-dir",
            str(root / "sources" / "raw" / "bilibili"),
        ]
        command.append("--fresh" if args.fresh else "--resume")
        rc = run_step(command)
        failures += int(rc != 0)

    if "corpus" in steps:
        rc = run_step([
            "python3",
            str(root / "tools" / "build_corpus_public.py"),
            "--raw-dir",
            str(root / "sources" / "raw"),
            "--transcript-dir",
            str(root / "sources" / "transcripts"),
            "--output-dir",
            str(root / "sources" / "processed" / "corpus"),
        ])
        failures += int(rc != 0)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
