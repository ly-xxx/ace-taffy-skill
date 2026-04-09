#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests


API_SPACE_INFO = "https://api.bilibili.com/x/space/acc/info"
API_RELATION = "https://api.bilibili.com/x/relation/stat"
API_SEARCH = "https://api.bilibili.com/x/web-interface/search/type"
API_VIDEO_DETAIL = "https://api.bilibili.com/x/web-interface/view/detail"
API_VIDEO_REPLIES = "https://api.bilibili.com/x/v2/reply/main"
API_SPI = "https://api.bilibili.com/x/frontend/finger/spi"
API_LIVE_MASTER = "https://api.live.bilibili.com/live_user/v1/Master/info"
API_LIVE_ROOM = "https://api.live.bilibili.com/room/v1/Room/get_info"
MOBILE_SPACE = "https://m.bilibili.com/space/{mid}"
RSSHUB_INSTANCES = [
    "https://rsshub.bili.ren",
]
BVID_RE = re.compile(r"BV[0-9A-Za-z]{10}")
MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://m.bilibili.com/",
}
API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
    session.headers.update(API_HEADERS)

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


SESSION = build_session()


def bootstrap_api_session() -> None:
    try:
        response = SESSION.get(API_SPI, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return

    data = payload.get("data") or {}
    if data.get("b_3"):
        SESSION.cookies.set("buvid3", data["b_3"], domain=".bilibili.com", path="/")
    if data.get("b_4"):
        SESSION.cookies.set("buvid4", data["b_4"], domain=".bilibili.com", path="/")
    SESSION.cookies.set("b_nut", str(int(time.time())), domain=".bilibili.com", path="/")


bootstrap_api_session()


def fetch_text(url: str, headers: dict[str, str], retries: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = SESSION.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(0.5 * attempt)
    raise RuntimeError(f"unable to fetch {url}: {last_error}")


def safe_fetch_json(url: str, headers: dict[str, str]) -> dict | None:
    try:
        return json.loads(fetch_text(url, headers=headers))
    except (RuntimeError, json.JSONDecodeError):
        return None


def search_fetch_json(keyword: str, page: int) -> dict | None:
    try:
        response = SESSION.get(
            API_SEARCH,
            headers={
                **API_HEADERS,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://search.bilibili.com/all?keyword=" + urllib.parse.quote(keyword),
            },
            params={
                "search_type": "video",
                "keyword": keyword,
                "order": "pubdate",
                "page": page,
                "page_size": 20,
            },
            timeout=20,
        )
        return response.json()
    except Exception:
        return None


def extract_mobile_initial_state(html: str) -> dict | None:
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;\s*\(function", html, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def normalize_space_profile(mid: str) -> dict:
    payload = safe_fetch_json(f"{API_SPACE_INFO}?mid={urllib.parse.quote(mid)}", {**API_HEADERS, "Referer": f"https://space.bilibili.com/{mid}"})
    if payload and payload.get("code") == 0:
        info = payload.get("data") or {}
        return {
            "mid": mid,
            "space_url": f"https://space.bilibili.com/{mid}",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "name": info.get("name"),
            "sex": info.get("sex"),
            "face": info.get("face"),
            "sign": info.get("sign"),
            "official": info.get("official") or {},
            "fans_medal": info.get("fans_medal") or {},
            "live_room": info.get("live_room") or {},
            "top_photo": info.get("top_photo"),
            "avatar_pendant": info.get("pendant") or {},
            "vip": info.get("vip") or {},
            "raw_space_info": info,
        }

    profile_url = MOBILE_SPACE.format(mid=mid)
    html = fetch_text(profile_url, headers=MOBILE_HEADERS)
    state = extract_mobile_initial_state(html) or {}
    space = state.get("space") or {}
    info = space.get("info") or {}

    return {
        "mid": mid,
        "space_url": profile_url,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "name": info.get("name"),
        "sex": info.get("sex"),
        "face": info.get("face"),
        "sign": info.get("sign"),
        "official": info.get("official") or {},
        "fans_medal": info.get("fans_medal") or {},
        "live_room": info.get("live_room") or {},
        "top_photo": info.get("top_photo"),
        "avatar_pendant": info.get("pendant") or {},
        "vip": info.get("vip") or {},
        "raw_space_info": info,
    }


def get_relation(mid: str) -> dict:
    payload = safe_fetch_json(f"{API_RELATION}?vmid={urllib.parse.quote(mid)}", API_HEADERS)
    return payload or {}


def collect_live(mid: str, room_id: str | None) -> dict:
    data: dict = {}

    payload = safe_fetch_json(f"{API_LIVE_MASTER}?uid={urllib.parse.quote(mid)}", API_HEADERS)
    if payload and payload.get("code") == 0:
        data["master_info"] = payload.get("data", {})

    if room_id:
        room_payload = safe_fetch_json(f"{API_LIVE_ROOM}?room_id={urllib.parse.quote(room_id)}", API_HEADERS)
        if room_payload and room_payload.get("code") == 0:
            data["room_info"] = room_payload.get("data", {})

    return data


def parse_seed_bvids(seed_path: Path) -> list[dict]:
    if not seed_path.exists():
        return []

    try:
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    results: list[dict] = []
    for item in ((payload.get("bilibili") or {}).get("samples") or []):
        bvid = item.get("bvid")
        if not bvid:
            match = BVID_RE.search(item.get("url", ""))
            bvid = match.group(0) if match else None
        if not bvid:
            continue
        results.append(
            {
                "bvid": bvid,
                "source": "seed",
                "label": item.get("label"),
                "url": item.get("url"),
            }
        )
    return results


def parse_weibo_bvids(feeds_path: Path) -> list[dict]:
    if not feeds_path.exists():
        return []

    try:
        feeds = json.loads(feeds_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    results: list[dict] = []
    for feed in feeds:
        if not isinstance(feed, dict):
            continue

        parts: list[str] = []
        for key in ("text_plain", "text_html", "text", "url", "href", "repost_text_plain", "repost_text"):
            value = feed.get(key)
            if value:
                parts.append(str(value))

        for url_value in feed.get("url_object_urls", []) or []:
            if url_value:
                parts.append(str(url_value))

        retweeted = feed.get("retweeted_status") or {}
        if isinstance(retweeted, dict):
            for key in ("text_plain", "text_html", "text"):
                value = retweeted.get(key)
                if value:
                    parts.append(str(value))
            for url_value in retweeted.get("url_object_urls", []) or []:
                if url_value:
                    parts.append(str(url_value))

        text_blob = " ".join(parts)
        for bvid in sorted(set(BVID_RE.findall(text_blob))):
            results.append(
                {
                    "bvid": bvid,
                    "source": "weibo",
                    "feed_id": feed.get("id"),
                }
            )
    return results


def rsshub_text(url: str) -> str | None:
    for instance in RSSHUB_INSTANCES:
        target = f"{instance}{url}"
        text = None
        try:
            text = fetch_text(target, headers=API_HEADERS, retries=1)
        except RuntimeError:
            continue

        if text:
            return text
    return None


def parse_rsshub_items(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items: list[dict] = []
    for item in root.findall("./channel/item"):
        description = item.findtext("description") or ""
        link = item.findtext("link") or ""
        title = item.findtext("title") or ""
        pub_date = item.findtext("pubDate")
        text_blob = " ".join([title, link, description])
        match = BVID_RE.search(text_blob)
        items.append(
            {
                "title": title,
                "link": link,
                "description_html": description,
                "description_plain": re.sub(r"<[^>]+>", "", description).strip(),
                "published_at": pub_date,
                "bvid": match.group(0) if match else None,
            }
        )
    return items


def collect_rsshub_video_refs(mid: str) -> tuple[list[dict], list[dict], str | None]:
    xml_text = rsshub_text(f"/bilibili/user/video/{mid}")
    if not xml_text:
        return [], [], None

    try:
        items = parse_rsshub_items(xml_text)
    except ET.ParseError:
        return [], [], None
    refs: list[dict] = []
    for item in items:
        if not item.get("bvid"):
            continue
        refs.append(
            {
                "bvid": item["bvid"],
                "source": "rsshub-video",
                "url": item.get("link"),
                "title_hint": item.get("title"),
                "published_at": item.get("published_at"),
            }
        )
    return refs, items, "rsshub"


def collect_rsshub_dynamics(mid: str, limit: int) -> tuple[list[dict], str | None]:
    xml_text = rsshub_text(f"/bilibili/user/dynamic/{mid}")
    if not xml_text:
        return [], None

    try:
        items = parse_rsshub_items(xml_text)
    except ET.ParseError:
        return [], None
    results: list[dict] = []
    for item in items[:limit]:
        results.append(
            {
                "published_at": item.get("published_at"),
                "title": item.get("title"),
                "text": item.get("description_plain"),
                "link": item.get("link"),
                "bvid": item.get("bvid"),
                "source": "rsshub",
            }
        )
    return results, "rsshub"


def collect_search_video_refs(mid: str, keywords: list[str], max_pages: int, limit: int) -> list[dict]:
    if max_pages <= 0 or not keywords:
        return []

    refs: dict[str, dict] = {}
    for keyword in keywords:
        page = 1
        consecutive_misses = 0

        while page <= max_pages and len(refs) < limit:
            payload = search_fetch_json(keyword, page)
            if not payload or payload.get("code") != 0:
                consecutive_misses += 1
                page += 1
                if consecutive_misses >= 4:
                    break
                time.sleep(0.3)
                continue

            items = ((payload.get("data") or {}).get("result") or [])
            if not items:
                break

            page_hits = 0
            for item in items:
                if str(item.get("mid")) != str(mid):
                    continue
                bvid = item.get("bvid")
                if not bvid:
                    continue
                page_hits += 1
                refs.setdefault(
                    bvid,
                    {
                        "bvid": bvid,
                        "source": "search",
                        "url": f"https://www.bilibili.com/video/{bvid}/",
                        "title_hint": re.sub(r"<[^>]+>", "", item.get("title", "")).strip(),
                        "published_at": item.get("pubdate"),
                    },
                )
                if len(refs) >= limit:
                    break

            consecutive_misses = 0 if page_hits else consecutive_misses + 1
            if consecutive_misses >= 4:
                break

            page += 1
            time.sleep(0.3)

    return list(refs.values())


def dedupe_video_refs(refs: list[dict], limit: int) -> list[dict]:
    by_bvid: dict[str, dict] = {}
    for ref in refs:
        bvid = ref.get("bvid")
        if not bvid:
            continue
        existing = by_bvid.get(bvid)
        if not existing:
            by_bvid[bvid] = ref
            continue

        sources = sorted({*(existing.get("sources") or [existing.get("source")]), ref.get("source")})
        merged = dict(existing)
        merged["sources"] = [source for source in sources if source]
        for key in ("url", "title_hint", "published_at", "label", "feed_id"):
            if not merged.get(key) and ref.get(key):
                merged[key] = ref[key]
        by_bvid[bvid] = merged

    results = list(by_bvid.values())
    results.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    if limit > 0:
        results = results[:limit]
    return results


def collect_video_details(video_refs: list[dict]) -> list[dict]:
    details: list[dict] = []
    for item in video_refs:
        bvid = item.get("bvid")
        if not bvid:
            continue

        payload = safe_fetch_json(f"{API_VIDEO_DETAIL}?bvid={urllib.parse.quote(bvid)}", API_HEADERS)
        if not payload or payload.get("code") != 0:
            continue

        data = payload.get("data", {})
        view = data.get("View") or {}
        details.append(
            {
                "aid": view.get("aid"),
                "bvid": view.get("bvid"),
                "title": view.get("title"),
                "desc": view.get("desc"),
                "pubdate": view.get("pubdate"),
                "duration": view.get("duration"),
                "owner": view.get("owner", {}),
                "stat": view.get("stat", {}),
                "pages": view.get("pages", []),
                "rights": view.get("rights", {}),
                "pic": view.get("pic"),
                "discovered_from": item.get("sources") or [item.get("source")],
                "seed_url": item.get("url"),
                "title_hint": item.get("title_hint"),
            }
        )
        time.sleep(0.1)

    return details


def collect_comments(video_details: list[dict], per_video_limit: int, video_limit: int) -> list[dict]:
    comments: list[dict] = []
    if per_video_limit <= 0:
        return comments

    scoped_details = video_details[:video_limit] if video_limit > 0 else video_details
    for detail in scoped_details:
        aid = detail.get("aid")
        if not aid:
            continue

        url = f"{API_VIDEO_REPLIES}?oid={aid}&type=1&mode=3&next=0&ps={max(per_video_limit, 1)}"
        payload = safe_fetch_json(url, API_HEADERS)
        if not payload or payload.get("code") != 0:
            continue

        replies = payload.get("data", {}).get("replies") or []
        for reply in replies[:per_video_limit]:
            comments.append(
                {
                    "aid": aid,
                    "bvid": detail.get("bvid"),
                    "video_title": detail.get("title"),
                    "reply_id": reply.get("rpid"),
                    "user": (reply.get("member") or {}).get("uname"),
                    "message": (reply.get("content") or {}).get("message"),
                    "like": reply.get("like"),
                    "ctime": reply.get("ctime"),
                }
            )
        time.sleep(0.1)

    return comments


def collect_playinfo_samples(video_details: list[dict], limit: int) -> list[dict]:
    if limit <= 0:
        return []

    samples: list[dict] = []
    for detail in video_details[:limit]:
        bvid = detail.get("bvid")
        if not bvid:
            continue

        try:
            html = fetch_text(f"https://www.bilibili.com/video/{bvid}/", headers={**API_HEADERS, "Referer": f"https://www.bilibili.com/video/{bvid}/"}, retries=2)
        except RuntimeError:
            continue

        match = re.search(r"window\.__playinfo__=(\{.*?\})</script>", html, re.S)
        if not match:
            continue

        try:
            playinfo = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

        dash = ((playinfo.get("data") or {}).get("dash")) or {}
        audio_streams = []
        for item in dash.get("audio") or []:
            audio_streams.append(
                {
                    "id": item.get("id"),
                    "codecs": item.get("codecs"),
                    "bandwidth": item.get("bandwidth"),
                    "base_url": item.get("baseUrl") or item.get("base_url"),
                }
            )
        video_streams = []
        for item in dash.get("video") or []:
            video_streams.append(
                {
                    "id": item.get("id"),
                    "codecs": item.get("codecs"),
                    "bandwidth": item.get("bandwidth"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "base_url": item.get("baseUrl") or item.get("base_url"),
                }
            )

        samples.append(
            {
                "bvid": bvid,
                "title": detail.get("title"),
                "duration": detail.get("duration"),
                "cid": (detail.get("pages") or [{}])[0].get("cid") if detail.get("pages") else None,
                "audio_streams": audio_streams,
                "video_streams": video_streams,
            }
        )
        time.sleep(0.1)

    return samples


def default_seed_path(output_dir: Path) -> Path:
    root = output_dir.parent.parent
    return root / "processed" / "seed-official-links.json"


def default_weibo_feeds_path(output_dir: Path) -> Path:
    root = output_dir.parent.parent
    return root / "raw" / "weibo" / "feeds.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public Bilibili metadata with resilient fallbacks.")
    parser.add_argument("--mid", required=True, help="Bilibili mid / uid")
    parser.add_argument("--room-id", help="Live room id")
    parser.add_argument("--video-limit", type=int, default=30, help="Max videos to keep")
    parser.add_argument("--dynamic-limit", type=int, default=20, help="Max dynamics to keep")
    parser.add_argument("--comment-limit", type=int, default=0, help="Top comments per video")
    parser.add_argument("--comment-video-limit", type=int, default=0, help="How many videos should receive comment sampling")
    parser.add_argument("--keywords", help="Optional comma-separated keywords; accepted for manifest compatibility")
    parser.add_argument("--search-pages", type=int, default=0, help="Optional search pages hint; accepted for compatibility")
    parser.add_argument("--playurl-limit", type=int, default=0, help="Optional playurl hint; accepted for compatibility")
    parser.add_argument("--output-dir", default="sources/raw/bilibili", help="Output directory")
    parser.add_argument("--seed-file", help="Seed links json file")
    parser.add_argument("--weibo-feeds", help="Weibo feeds json used to discover linked BVIDs")
    args = parser.parse_args()

    out_dir = Path(args.output_dir).expanduser()
    seed_file = Path(args.seed_file).expanduser() if args.seed_file else default_seed_path(out_dir)
    weibo_feeds = Path(args.weibo_feeds).expanduser() if args.weibo_feeds else default_weibo_feeds_path(out_dir)
    keywords = [item.strip() for item in (args.keywords or "").split(",") if item.strip()]

    profile = normalize_space_profile(args.mid)
    relation = get_relation(args.mid)
    live = collect_live(args.mid, args.room_id)

    seed_refs = parse_seed_bvids(seed_file)
    weibo_refs = parse_weibo_bvids(weibo_feeds)
    search_refs = collect_search_video_refs(args.mid, keywords, args.search_pages, args.video_limit)
    rss_video_refs, rss_video_items, video_feed_source = collect_rsshub_video_refs(args.mid)
    dynamics, dynamic_feed_source = collect_rsshub_dynamics(args.mid, args.dynamic_limit)

    video_refs = dedupe_video_refs(
        [*search_refs, *rss_video_refs, *seed_refs, *weibo_refs],
        args.video_limit,
    )
    video_details = collect_video_details(video_refs)
    comments = collect_comments(
        video_details,
        args.comment_limit,
        args.comment_video_limit,
    )
    playinfo_samples = collect_playinfo_samples(video_details, args.playurl_limit)

    write_json(out_dir / "profile.json", profile)
    write_json(out_dir / "relation.json", relation)
    write_json(out_dir / "videos.json", video_refs)
    write_json(out_dir / "video_details.json", video_details)
    write_json(out_dir / "dynamics.json", dynamics)
    write_json(out_dir / "live.json", live)
    if rss_video_items:
        write_json(out_dir / "videos_feed.json", rss_video_items)
    if comments:
        write_json(out_dir / "comments.json", comments)
    if playinfo_samples:
        write_json(out_dir / "playinfo_samples.json", playinfo_samples)

    summary = {
        "mid": args.mid,
        "room_id": args.room_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "videos_count": len(video_refs),
        "video_details_count": len(video_details),
        "dynamics_count": len(dynamics),
        "comments_count": len(comments),
        "playinfo_samples_count": len(playinfo_samples),
        "comment_video_limit": args.comment_video_limit,
        "seed_refs_count": len(seed_refs),
        "weibo_refs_count": len(weibo_refs),
        "search_refs_count": len(search_refs),
        "rss_video_refs_count": len(rss_video_refs),
        "video_feed_source": video_feed_source,
        "dynamic_feed_source": dynamic_feed_source,
        "seed_file": str(seed_file) if seed_file.exists() else None,
        "weibo_feeds": str(weibo_feeds) if weibo_feeds.exists() else None,
    }
    write_json(out_dir / "summary.json", summary)

    print(f"[OK] bilibili profile  -> {out_dir / 'profile.json'}")
    print(f"[OK] bilibili videos   -> {out_dir / 'videos.json'}")
    print(f"[OK] bilibili details  -> {out_dir / 'video_details.json'}")
    print(f"[OK] bilibili dynamics -> {out_dir / 'dynamics.json'}")
    print(f"[OK] bilibili live     -> {out_dir / 'live.json'}")
    if comments:
        print(f"[OK] bilibili comments -> {out_dir / 'comments.json'}")
    if playinfo_samples:
        print(f"[OK] bilibili playinfo -> {out_dir / 'playinfo_samples.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
