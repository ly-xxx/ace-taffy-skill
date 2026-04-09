#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests


PAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def normalize_proxy_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith("https://"):
        return "http://" + value.split("://", 1)[1]
    return value


def build_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(PAGE_HEADERS)

    proxies = {}
    for scheme in ("http", "https"):
        value = (
            os.environ.get(f"{scheme}_proxy")
            or os.environ.get(f"{scheme.upper()}_PROXY")
            or os.environ.get(f"{scheme.upper()}_proxy")
        )
        normalized = normalize_proxy_url(value)
        if normalized:
            proxies[scheme] = normalized

    if proxies:
        session.proxies.update(proxies)

    return session


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120] or "bilibili_media"


def resolve_bvid(value: str) -> tuple[str, str]:
    if value.startswith("http://") or value.startswith("https://"):
        match = re.search(r"/video/([A-Za-z0-9]+)", value)
        if not match:
            raise SystemExit(f"unable to parse BVID from URL: {value}")
        bvid = match.group(1)
        return bvid, value

    bvid = value.strip()
    if not re.fullmatch(r"BV[0-9A-Za-z]+", bvid):
        raise SystemExit(f"invalid BVID: {value}")
    return bvid, f"https://www.bilibili.com/video/{bvid}/"


def fetch_page_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=40)
    response.raise_for_status()
    return response.text


def extract_embedded_json(html: str, pattern: str) -> dict:
    match = re.search(pattern, html, flags=re.S)
    if not match:
        raise RuntimeError("embedded JSON not found in page")
    return json.loads(match.group(1))


def choose_best_stream(streams: list[dict]) -> dict | None:
    if not streams:
        return None
    return max(streams, key=lambda item: item.get("bandwidth") or 0)


def download_file(session: requests.Session, url: str, dest: Path, referer: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, headers={**PAGE_HEADERS, "Referer": referer}, stream=True, timeout=60) as response:
        response.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    handle.write(chunk)


def run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "ffmpeg failed").strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Download audio or merged media from a public Bilibili video page.")
    parser.add_argument("inputs", nargs="+", help="BVID or full Bilibili video URL")
    parser.add_argument("--output-dir", default="sources/media/bilibili", help="Output directory")
    parser.add_argument("--audio-only", action="store_true", help="Only export an audio file")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files")
    args = parser.parse_args()

    session = build_session()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifests = []
    for raw_input in args.inputs:
        bvid, page_url = resolve_bvid(raw_input)
        page_html = fetch_page_html(session, page_url)
        playinfo = extract_embedded_json(page_html, r"window\.__playinfo__=(\{.*?\})</script>")
        initial_state = extract_embedded_json(page_html, r"window\.__INITIAL_STATE__=(\{.*?\});")

        video_data = (initial_state.get("videoData") or {})
        title = video_data.get("title") or bvid
        safe_title = sanitize_filename(f"{bvid} {title}")
        dash = (playinfo.get("data") or {}).get("dash") or {}
        audio_stream = choose_best_stream(dash.get("audio") or [])
        video_stream = choose_best_stream(dash.get("video") or [])

        if not audio_stream:
            raise SystemExit(f"no audio stream available for {bvid}")

        audio_tmp = output_dir / f"{safe_title}.audio.m4s"
        audio_out = output_dir / f"{safe_title}.m4a"
        video_tmp = output_dir / f"{safe_title}.video.m4s"
        video_out = output_dir / f"{safe_title}.mp4"

        if args.force or not audio_out.exists():
            download_file(session, audio_stream.get("baseUrl") or audio_stream.get("base_url"), audio_tmp, page_url)
            run_ffmpeg([
                "ffmpeg",
                "-y",
                "-i",
                str(audio_tmp),
                "-vn",
                "-c:a",
                "copy",
                str(audio_out),
            ])
            audio_tmp.unlink(missing_ok=True)

        if not args.audio_only and video_stream:
            if args.force or not video_out.exists():
                download_file(session, video_stream.get("baseUrl") or video_stream.get("base_url"), video_tmp, page_url)
                run_ffmpeg([
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(video_tmp),
                    "-i",
                    str(audio_out),
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    str(video_out),
                ])
                video_tmp.unlink(missing_ok=True)

        manifest = {
            "input": raw_input,
            "bvid": bvid,
            "title": title,
            "page_url": page_url,
            "owner": video_data.get("owner"),
            "duration": video_data.get("duration"),
            "pubdate": video_data.get("pubdate"),
            "audio_file": str(audio_out),
            "video_file": str(video_out) if video_out.exists() else None,
            "audio_stream": {
                "id": audio_stream.get("id"),
                "bandwidth": audio_stream.get("bandwidth"),
                "codecs": audio_stream.get("codecs"),
                "host": urlparse(audio_stream.get("baseUrl") or audio_stream.get("base_url") or "").netloc,
            },
            "video_stream": {
                "id": video_stream.get("id"),
                "bandwidth": video_stream.get("bandwidth"),
                "codecs": video_stream.get("codecs"),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "host": urlparse(video_stream.get("baseUrl") or video_stream.get("base_url") or "").netloc,
            } if video_stream else None,
        }
        manifest_path = output_dir / f"{safe_title}.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifests.append(manifest)

        print(f"[OK] audio -> {audio_out}")
        if video_out.exists():
            print(f"[OK] video -> {video_out}")
        print(f"[OK] meta  -> {manifest_path}")

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps({"items": manifests}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] summary -> {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
