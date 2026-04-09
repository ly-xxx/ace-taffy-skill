#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


DEFAULT_COMMAND_CANDIDATES = [
    ["weibo-cli"],
    ["uvx", "--from", "mcp-server-weibo", "weibo-cli"],
]
HTML_HEADERS = {
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
}
SPIDER_USER_AGENTS = [
    "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
    "Mozilla/5.0 (compatible; Sogou web spider/4.0; +http://www.sogou.com/docs/help/webmasters.htm#07)",
]


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_count(text: str) -> int:
    match = re.search(r"(\d+(?:\.\d+)?)(万)?", text.replace(",", ""))
    if not match:
        return 0

    value = float(match.group(1))
    if match.group(2):
        value *= 10_000
    return int(value)


def run_json_command(candidates: Iterable[list[str]], tail_args: list[str]) -> object:
    last_error = None

    for command in candidates:
        try:
            result = subprocess.run(
                [*command, *tail_args],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except FileNotFoundError as exc:
            last_error = exc
            continue

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            lines = [line for line in stderr.splitlines() if line.strip()]
            if len(lines) > 15:
                lines = lines[-15:]
            last_error = RuntimeError("\n".join(lines) or "command failed")
            continue

        stdout = result.stdout.strip()
        if not stdout:
            return {}

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid json from {' '.join(command)}: {exc}") from exc

    raise RuntimeError(f"unable to run weibo cli: {last_error}")


def fetch_public_html(url: str) -> str:
    last_error: Exception | None = None

    for user_agent in SPIDER_USER_AGENTS:
        request = Request(url, headers={**HTML_HEADERS, "User-Agent": user_agent})
        try:
            with urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", "replace")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc

    raise RuntimeError(f"unable to fetch public weibo html: {last_error}")


def pick_text_block(card):
    full = card.select_one("div[node-type='feed_list_content_full']")
    if full:
        return full
    return card.select_one("div[node-type='feed_list_content']")


def build_public_profile(soup: BeautifulSoup, uid: str, domain: str | None) -> dict:
    title = normalize_whitespace((soup.title.string if soup.title else "").replace("_微博", ""))
    description = ""
    keywords = ""
    avatar = None

    meta_description = soup.find("meta", attrs={"name": "description"})
    if meta_description and meta_description.get("content"):
        description = normalize_whitespace(meta_description["content"])

    meta_keywords = soup.find("meta", attrs={"name": "keywords"})
    if meta_keywords and meta_keywords.get("content"):
        keywords = normalize_whitespace(meta_keywords["content"])

    avatar_img = soup.select_one("div.WB_face img")
    if avatar_img:
        avatar = avatar_img.get("src")

    homepage = f"https://weibo.com/{domain}" if domain else f"https://weibo.com/u/{uid}"
    return {
        "uid": uid,
        "domain": domain,
        "homepage": homepage,
        "title": title,
        "description": description,
        "keywords": keywords,
        "avatar": avatar,
        "source": "html-spider",
    }


def parse_public_feed(card) -> dict | None:
    feed_id = str(card.get("mid") or "").strip()
    if not feed_id:
        return None

    text_block = pick_text_block(card)
    reason_block = card.select_one("div[node-type='feed_list_reason']")
    time_link = card.select_one("a[node-type='feed_list_item_date']")

    detail_href = ""
    detail_url = ""
    date_title = None
    date_text = None
    timestamp = None
    if time_link:
        detail_href = time_link.get("href", "")
        detail_url = urljoin("https://weibo.com", detail_href)
        date_title = normalize_whitespace(time_link.get("title", ""))
        date_text = normalize_whitespace(time_link.get_text(" ", strip=True))
        timestamp = time_link.get("date")

    forward_button = card.select_one("[node-type='forward_btn_text']")
    comment_button = card.select_one("[node-type='comment_btn_text']")
    like_button = card.select_one("[node-type='like_status']")

    media_images = card.select(".WB_media_wrap img")
    source_links = [
        normalize_whitespace(link.get_text(" ", strip=True))
        for link in card.select("div.WB_from a")
        if normalize_whitespace(link.get_text(" ", strip=True))
    ]

    text_html = text_block.decode_contents() if text_block else ""
    reason_html = reason_block.decode_contents() if reason_block else ""
    return {
        "id": feed_id,
        "mid": feed_id,
        "url": detail_url,
        "href": detail_href,
        "created_at": date_title or date_text,
        "created_at_display": date_text,
        "timestamp_ms": int(timestamp) if timestamp and timestamp.isdigit() else None,
        "text": text_html,
        "text_plain": strip_html(text_html),
        "repost_text": reason_html,
        "repost_text_plain": strip_html(reason_html),
        "is_top": card.get("feedtype") == "top",
        "source_labels": source_links,
        "forward_count": parse_count(forward_button.get_text(" ", strip=True)) if forward_button else 0,
        "comment_count": parse_count(comment_button.get_text(" ", strip=True)) if comment_button else 0,
        "like_count": parse_count(like_button.get_text(" ", strip=True)) if like_button else 0,
        "image_count": len(media_images),
        "has_video": "WB_video" in str(card),
        "collection_source": "html-spider",
    }


def collect_public_feeds(
    uid: str,
    domain: str | None,
    limit: int,
    max_pages: int,
) -> tuple[dict, list[dict], list[dict]]:
    homepage = f"https://weibo.com/{domain}" if domain else f"https://weibo.com/u/{uid}"
    seen: set[str] = set()
    feeds: list[dict] = []
    pages: list[dict] = []
    repeated_pages = 0
    profile: dict | None = None

    for page in range(1, max_pages + 1):
        page_url = f"{homepage}?is_all=1&page={page}"
        html_text = fetch_public_html(page_url)
        soup = BeautifulSoup(html_text, "html.parser")
        if profile is None:
            profile = build_public_profile(soup, uid, domain)

        page_items = []
        for card in soup.select("div[action-type='feed_list_item'][mid]"):
            parsed = parse_public_feed(card)
            if parsed is not None:
                page_items.append(parsed)

        new_items = 0
        for item in page_items:
            feed_id = item["id"]
            if feed_id in seen:
                continue
            seen.add(feed_id)
            feeds.append(item)
            new_items += 1
            if limit > 0 and len(feeds) >= limit:
                break

        pages.append({
            "page": page,
            "url": page_url,
            "items": len(page_items),
            "new_items": new_items,
        })

        if limit > 0 and len(feeds) >= limit:
            break

        if new_items == 0:
            repeated_pages += 1
            if repeated_pages >= 2:
                break
        else:
            repeated_pages = 0

        time.sleep(0.2)

    return profile or build_public_profile(BeautifulSoup("", "html.parser"), uid, domain), feeds, pages


def enrich_feeds(feeds: list[dict]) -> list[dict]:
    enriched = []

    for item in feeds:
        enriched.append({
            **item,
            "text_plain": strip_html(item.get("text", "")),
        })

    return enriched


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect official Weibo data for public-figure distillation.")
    parser.add_argument("--uid", required=True, help="Weibo UID")
    parser.add_argument("--domain", help="Weibo profile domain, e.g. acetaffy")
    parser.add_argument("--limit", type=int, default=50, help="Number of feeds to fetch; use 0 to collect all visible pages")
    parser.add_argument("--comments-per-post", type=int, default=0, help="Fetch first page of comments for each post when > 0")
    parser.add_argument("--max-pages", type=int, default=20, help="Max public profile pages to scan in HTML fallback")
    parser.add_argument("--force-html-spider", action="store_true", help="Skip CLI and collect from public HTML directly")
    parser.add_argument("--output-dir", default="sources/raw/weibo", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir).expanduser()
    comments_dir = out_dir / "comments"
    collection_method = "weibo-cli"
    pages_scanned: list[dict] = []

    if args.force_html_spider:
        profile, feeds, pages_scanned = collect_public_feeds(args.uid, args.domain, args.limit, args.max_pages)
        collection_method = "html-spider"
    else:
        try:
            profile = run_json_command(DEFAULT_COMMAND_CANDIDATES, ["profile", args.uid])
            feeds_raw = run_json_command(DEFAULT_COMMAND_CANDIDATES, ["feeds", args.uid, "-n", str(args.limit)])
            if not isinstance(feeds_raw, list):
                print("[ERROR] unexpected feeds payload", file=sys.stderr)
                return 1
            feeds = enrich_feeds(feeds_raw)
        except RuntimeError:
            try:
                profile, feeds, pages_scanned = collect_public_feeds(args.uid, args.domain, args.limit, args.max_pages)
                collection_method = "html-spider"
            except RuntimeError as exc:
                print(f"[ERROR] {exc}", file=sys.stderr)
                return 1

    write_json(out_dir / "profile.json", profile)
    write_json(out_dir / "feeds.json", feeds)
    if pages_scanned:
        write_json(out_dir / "pages.json", pages_scanned)

    comments_summary: list[dict] = []
    if args.comments_per_post > 0 and collection_method == "weibo-cli":
        for feed in feeds[:args.limit or None]:
            feed_id = str(feed.get("id", "")).strip()
            if not feed_id:
                continue

            try:
                comments = run_json_command(DEFAULT_COMMAND_CANDIDATES, ["comments", feed_id, "-p", "1"])
            except RuntimeError:
                continue

            if isinstance(comments, list):
                trimmed = comments[:args.comments_per_post]
                write_json(comments_dir / f"{feed_id}.json", trimmed)
                comments_summary.append({
                    "feed_id": feed_id,
                    "count": len(trimmed),
                })

    summary = {
        "uid": args.uid,
        "domain": args.domain,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "method": collection_method,
        "feeds_count": len(feeds),
        "pages_scanned": len(pages_scanned),
        "comments_collected": comments_summary,
    }
    write_json(out_dir / "summary.json", summary)

    print(f"[OK] profile -> {out_dir / 'profile.json'}")
    print(f"[OK] feeds   -> {out_dir / 'feeds.json'}")
    if pages_scanned:
        print(f"[OK] pages   -> {out_dir / 'pages.json'}")
    if comments_summary:
        print(f"[OK] comments -> {comments_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
