#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


MEDIA_EXTENSIONS = {".mp4", ".m4a", ".mp3", ".wav", ".flac", ".mov", ".mkv"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch-transcribe media files with transcribe_audio.py.")
    parser.add_argument("--input-dir", default="sources/media/bilibili", help="Directory containing media files")
    parser.add_argument("--output-dir", default="sources/transcripts", help="Directory for transcript outputs")
    parser.add_argument("--model", default="large-v3", help="Whisper model name")
    parser.add_argument("--language", default="zh", help="Language code")
    parser.add_argument("--limit", type=int, default=0, help="Max files to transcribe; 0 means all")
    parser.add_argument("--initial-prompt-file", help="Prompt file passed through to transcribe_audio.py")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    files = [
        path for path in sorted(input_dir.iterdir())
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    ]
    if args.limit > 0:
        files = files[:args.limit]

    script = Path(__file__).with_name("transcribe_audio.py")
    failures = 0
    for media_path in files:
        output_json = output_dir / f"{media_path.stem}.json"
        if output_json.exists():
            print(f"[SKIP] transcript exists -> {output_json}")
            continue

        command = [
            "python3",
            str(script),
            str(media_path),
            "--output-dir",
            str(output_dir),
            "--model",
            args.model,
            "--language",
            args.language,
        ]
        if args.initial_prompt_file:
            command.extend(["--initial-prompt-file", args.initial_prompt_file])

        print("[RUN]", " ".join(command))
        result = subprocess.run(command, check=False)
        failures += int(result.returncode != 0)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
