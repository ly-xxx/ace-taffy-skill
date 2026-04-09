#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def format_timestamp(seconds: float, decimal_marker: str = ",") -> str:
    if seconds < 0:
        seconds = 0

    milliseconds = round(seconds * 1000.0)
    hours = milliseconds // 3_600_000
    milliseconds -= hours * 3_600_000
    minutes = milliseconds // 60_000
    milliseconds -= minutes * 60_000
    secs = milliseconds // 1000
    milliseconds -= secs * 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal_marker}{milliseconds:03d}"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_txt(path: Path, segments: list[dict]) -> None:
    lines = [segment["text"].strip() for segment in segments if segment["text"].strip()]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_srt(path: Path, segments: list[dict]) -> None:
    lines: list[str] = []
    for index, segment in enumerate(segments, start=1):
        lines.append(str(index))
        lines.append(f"{format_timestamp(segment['start'])} --> {format_timestamp(segment['end'])}")
        lines.append(segment["text"].strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_vtt(path: Path, segments: list[dict]) -> None:
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.append(f"{format_timestamp(segment['start'], '.')} --> {format_timestamp(segment['end'], '.')}")
        lines.append(segment["text"].strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_tsv(path: Path, segments: list[dict]) -> None:
    lines = ["start\tend\ttext"]
    for segment in segments:
        lines.append(f"{segment['start']:.3f}\t{segment['end']:.3f}\t{segment['text'].strip()}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def detect_device(device: str) -> str:
    if device != "auto":
        return device
    return "cuda" if shutil.which("nvidia-smi") else "cpu"


def normalize_proxy_env() -> None:
    for key in ("HTTPS_PROXY", "https_proxy"):
        value = os.environ.get(key)
        if value and value.startswith("https://"):
            os.environ[key] = "http://" + value.split("://", 1)[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe media into json/srt/vtt/tsv/txt using faster-whisper.")
    parser.add_argument("input", help="Audio or video file")
    parser.add_argument("--output-dir", default="sources/transcripts", help="Output directory")
    parser.add_argument("--model", default="large-v3", help="faster-whisper model size")
    parser.add_argument("--language", default="zh", help="Language code")
    parser.add_argument("--device", default="auto", help="cpu / cuda / auto")
    parser.add_argument("--compute-type", default="auto", help="Compute type passed to faster-whisper")
    parser.add_argument("--beam-size", type=int, default=5, help="Beam size")
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD filtering")
    parser.add_argument("--no-word-timestamps", action="store_true", help="Disable word timestamps")
    parser.add_argument("--initial-prompt", help="Optional prompt to bias transcription vocabulary")
    parser.add_argument("--initial-prompt-file", help="Path to a UTF-8 prompt file")
    parser.add_argument("--hotwords-file", help="Path to a newline-delimited hotwords file")
    parser.add_argument("--formats", default="json,srt,vtt,tsv,txt", help="Comma-separated output formats")
    args = parser.parse_args()

    normalize_proxy_env()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("faster-whisper is required. Install dependencies from requirements.txt first.")

    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        raise SystemExit(f"input file not found: {input_path}")

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    device = detect_device(args.device)
    compute_type = args.compute_type
    initial_prompt = args.initial_prompt

    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    if args.initial_prompt_file:
        prompt_path = Path(args.initial_prompt_file).expanduser()
        initial_prompt = prompt_path.read_text(encoding="utf-8").strip()

    if args.hotwords_file:
        hotwords_path = Path(args.hotwords_file).expanduser()
        hotwords = [
            line.strip()
            for line in hotwords_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if hotwords:
            hotwords_prompt = "；".join(hotwords)
            initial_prompt = f"{initial_prompt or ''}；{hotwords_prompt}".strip("；")

    model = WhisperModel(args.model, device=device, compute_type=compute_type)
    segments_iter, info = model.transcribe(
        str(input_path),
        language=args.language,
        beam_size=args.beam_size,
        vad_filter=not args.no_vad,
        word_timestamps=not args.no_word_timestamps,
        initial_prompt=initial_prompt or None,
    )

    segments: list[dict] = []
    for index, segment in enumerate(segments_iter):
        words = []
        if segment.words:
            for word in segment.words:
                words.append({
                    "start": word.start,
                    "end": word.end,
                    "word": word.word,
                    "probability": word.probability,
                })

        segments.append({
            "id": index,
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "avg_logprob": segment.avg_logprob,
            "no_speech_prob": segment.no_speech_prob,
            "words": words,
        })

    formats = {fmt.strip().lower() for fmt in args.formats.split(",") if fmt.strip()}
    transcript_payload = {
        "input": str(input_path),
        "model": args.model,
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": getattr(info, "duration", None),
        "backend": "faster-whisper",
        "initial_prompt": initial_prompt or "",
        "device": device,
        "compute_type": compute_type,
        "vad_filter": not args.no_vad,
        "word_timestamps": not args.no_word_timestamps,
        "segments": segments,
    }

    if "json" in formats:
        write_json(output_dir / f"{stem}.json", transcript_payload)
    if "txt" in formats:
        write_txt(output_dir / f"{stem}.txt", segments)
    if "srt" in formats:
        write_srt(output_dir / f"{stem}.srt", segments)
    if "vtt" in formats:
        write_vtt(output_dir / f"{stem}.vtt", segments)
    if "tsv" in formats:
        write_tsv(output_dir / f"{stem}.tsv", segments)

    print(f"[OK] transcript -> {output_dir / f'{stem}.json'}")
    if "srt" in formats:
        print(f"[OK] srt        -> {output_dir / f'{stem}.srt'}")
    if "vtt" in formats:
        print(f"[OK] vtt        -> {output_dir / f'{stem}.vtt'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
