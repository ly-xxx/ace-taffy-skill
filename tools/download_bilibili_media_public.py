#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_PLAYER_PLAYURL = "https://api.bilibili.com/x/player/playurl"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AceTaffySkill/0.2)",
    "Referer": "https://m.bilibili.com/",
}


def sanitize_filename(text: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:120] or "untitled"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_json(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_playurl(bvid: str, cid: int) -> dict | None:
    url = (
        f"{API_PLAYER_PLAYURL}?bvid={urllib.parse.quote(bvid)}"
        f"&cid={cid}&qn=80&fnval=0&platform=html5&high_quality=1"
    )
    headers = {**HEADERS, "Referer": f"https://m.bilibili.com/video/{bvid}"}
    try:
        payload = fetch_json(url, headers)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None

    if payload.get("code") != 0:
        return None

    data = payload.get("data", {})
    durl = data.get("durl") or []
    if not durl:
        return None

    first = durl[0]
    return {
        "quality": data.get("quality"),
        "format": data.get("format"),
        "timelength": data.get("timelength"),
        "url": first.get("url"),
        "size": first.get("size"),
        "length": first.get("length"),
    }


def choose_cid(item: dict) -> int | None:
    cid = item.get("cid")
    if cid:
        return int(cid)

    pages = item.get("pages") or []
    if not pages:
        return None

    page_cid = pages[0].get("cid")
    return int(page_cid) if page_cid else None


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Bilibili media from collected video detail JSON.")
    parser.add_argument("--input-json", default="sources/raw/bilibili/video_details.json", help="Collected video_details.json path")
    parser.add_argument("--output-dir", default="sources/media/bilibili", help="Output directory for downloaded media")
    parser.add_argument("--limit", type=int, default=3, help="Max videos to download")
    parser.add_argument("--max-duration", type=int, default=900, help="Skip videos longer than N seconds")
    parser.add_argument("--min-pubdate", type=int, default=0, help="Skip videos older than this Unix timestamp")
    parser.add_argument("--sleep", type=float, default=0.3, help="Seconds to sleep between downloads")
    args = parser.parse_args()

    input_path = Path(args.input_json).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    items = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise SystemExit(f"expected a list in {input_path}")

    ordered = sorted(
        items,
        key=lambda item: (item.get("pubdate") or 0, item.get("bvid") or ""),
        reverse=True,
    )

    downloads: list[dict] = []
    for item in ordered:
        if len(downloads) >= args.limit:
            break

        pubdate = int(item.get("pubdate") or 0)
        duration = int(item.get("duration") or 0)
        if pubdate < args.min_pubdate or duration > args.max_duration:
            continue

        bvid = str(item.get("bvid") or "").strip()
        cid = choose_cid(item)
        if not bvid or not cid:
            continue

        playurl = collect_playurl(bvid, cid)
        if not playurl or not playurl.get("url"):
            continue

        title = sanitize_filename(str(item.get("title") or bvid))
        target_path = output_dir / f"{pubdate or 0}_{bvid}_{title}.mp4"
        if not target_path.exists():
            download_file(playurl["url"], target_path)

        downloads.append({
            "bvid": bvid,
            "aid": item.get("aid"),
            "cid": cid,
            "title": item.get("title"),
            "pubdate": pubdate,
            "duration": duration,
            "path": str(target_path),
            "playurl": playurl,
        })
        print(f"[OK] downloaded -> {target_path}")
        time.sleep(args.sleep)

    write_json(output_dir / "manifest.json", downloads)
    print(f"[OK] manifest   -> {output_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
