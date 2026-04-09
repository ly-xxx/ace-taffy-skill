#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import quickjs


API_LIVE_MASTER = "https://api.live.bilibili.com/live_user/v1/Master/info"
API_LIVE_ROOM = "https://api.live.bilibili.com/room/v1/Room/get_info"
API_VIDEO_REPLIES = "https://api.bilibili.com/x/v2/reply/main"
API_DYNAMIC = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
API_PLAYER_PLAYURL = "https://api.bilibili.com/x/player/playurl"
SEARCH_VIDEO = "https://search.bilibili.com/video"
MOBILE_SPACE = "https://m.bilibili.com/space/{mid}"
MOBILE_VIDEO = "https://m.bilibili.com/video/{bvid}"

DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AceTaffySkill/0.2)",
    "Referer": "https://www.bilibili.com/",
}
MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://m.bilibili.com/",
}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_text(url: str, headers: dict[str, str]) -> str:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def fetch_json(url: str, headers: dict[str, str]) -> dict:
    payload = fetch_text(url, headers)
    return json.loads(payload)


def safe_fetch_json(url: str, headers: dict[str, str]) -> dict | None:
    try:
        return fetch_json(url, headers)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def parse_mobile_state(url: str) -> dict | None:
    try:
        html = fetch_text(url, MOBILE_HEADERS)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None

    marker = "__INITIAL_STATE__="
    start = html.find(marker)
    if start == -1:
        return None

    start += len(marker)
    end = html.find(";(function(){var s;", start)
    if end == -1:
        return None

    try:
        return json.loads(html[start:end])
    except json.JSONDecodeError:
        return None


def parse_search_state(url: str) -> dict | None:
    try:
        html = fetch_text(url, DESKTOP_HEADERS)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None

    start = html.find("window.__pinia=")
    end = html.find("</script>", start)
    if start == -1 or end == -1:
        return None

    code = html[start:end].strip()
    try:
        context = quickjs.Context()
        context.eval("var window = {};")
        context.eval(code)
        return json.loads(context.eval("JSON.stringify(window.__pinia)"))
    except Exception:
        return None


def iter_search_video_items(items: list[dict]) -> list[dict]:
    results: list[dict] = []
    stack = list(items)

    while stack:
        item = stack.pop()
        if not isinstance(item, dict):
            continue
        if item.get("bvid"):
            results.append(item)
        nested = item.get("res")
        if isinstance(nested, list):
            stack.extend(nested)

    return results


def normalize_search_hit(item: dict, keyword: str) -> dict:
    return {
        "aid": item.get("aid"),
        "bvid": item.get("bvid"),
        "title": item.get("title"),
        "description": item.get("description") or item.get("desc"),
        "author": item.get("author") or item.get("uname"),
        "mid": item.get("mid"),
        "pubdate": item.get("pubdate"),
        "duration": item.get("duration"),
        "play": item.get("play"),
        "arcurl": item.get("arcurl"),
        "seed_keyword": keyword,
    }


def collect_search_seeds(mid: str, keywords: list[str], pages_per_keyword: int) -> tuple[list[dict], list[dict]]:
    target_mid = int(mid)
    seeds: dict[str, dict] = {}
    search_pages: list[dict] = []

    for keyword in keywords:
        stagnant_pages = 0
        for page in range(1, pages_per_keyword + 1):
            url = (
                f"{SEARCH_VIDEO}?keyword={urllib.parse.quote(keyword)}"
                f"&page={page}"
            )
            payload = parse_search_state(url)
            if not payload:
                search_pages.append({
                    "keyword": keyword,
                    "page": page,
                    "url": url,
                    "hits": 0,
                    "new_hits": 0,
                    "status": "parse_failed",
                })
                stagnant_pages += 1
                if stagnant_pages >= 2:
                    break
                continue

            response = payload.get("searchResponse", {}).get("searchAllResponse", {})
            page_hits = 0
            new_hits = 0

            for group in response.get("result", []):
                for item in iter_search_video_items(group.get("data", [])):
                    if item.get("mid") != target_mid:
                        continue
                    bvid = str(item.get("bvid") or "").strip()
                    if not bvid:
                        continue
                    page_hits += 1
                    if bvid not in seeds:
                        seeds[bvid] = normalize_search_hit(item, keyword)
                        new_hits += 1

            search_pages.append({
                "keyword": keyword,
                "page": page,
                "url": url,
                "hits": page_hits,
                "new_hits": new_hits,
                "num_pages": response.get("numPages"),
                "num_results": response.get("numResults"),
                "status": "ok",
            })

            if new_hits == 0:
                stagnant_pages += 1
                if stagnant_pages >= 3:
                    break
            else:
                stagnant_pages = 0

            time.sleep(0.15)

    ordered = sorted(
        seeds.values(),
        key=lambda item: (item.get("pubdate") or 0, item.get("bvid") or ""),
        reverse=True,
    )
    return ordered, search_pages


def collect_dynamic(mid: str, limit: int) -> list[dict]:
    url = f"{API_DYNAMIC}?host_mid={urllib.parse.quote(mid)}"
    payload = safe_fetch_json(url, DESKTOP_HEADERS)
    if not payload or payload.get("code") != 0:
        return []

    items = payload.get("data", {}).get("items") or []
    results: list[dict] = []
    for item in items[:limit]:
        modules = item.get("modules") or {}
        author = modules.get("module_author") or {}
        dynamic = modules.get("module_dynamic") or {}
        desc = dynamic.get("desc") or {}
        results.append({
            "id_str": item.get("id_str"),
            "type": item.get("type"),
            "author": author.get("name"),
            "pub_ts": author.get("pub_ts"),
            "text": desc.get("text"),
        })

    return results


def collect_live(mid: str, room_id: str | None) -> dict:
    data: dict = {}

    payload = safe_fetch_json(f"{API_LIVE_MASTER}?uid={urllib.parse.quote(mid)}", DESKTOP_HEADERS)
    if payload and payload.get("code") == 0:
        data["master_info"] = payload.get("data", {})

    if room_id:
        room_payload = safe_fetch_json(f"{API_LIVE_ROOM}?room_id={urllib.parse.quote(room_id)}", DESKTOP_HEADERS)
        if room_payload and room_payload.get("code") == 0:
            data["room_info"] = room_payload.get("data", {})

    return data


def collect_playurl(bvid: str, cid: int | None) -> dict | None:
    if not cid:
        return None

    url = (
        f"{API_PLAYER_PLAYURL}?bvid={urllib.parse.quote(bvid)}"
        f"&cid={cid}&qn=80&fnval=0&platform=html5&high_quality=1"
    )
    headers = {**DESKTOP_HEADERS, "Referer": f"https://m.bilibili.com/video/{bvid}"}
    payload = safe_fetch_json(url, headers)
    if not payload or payload.get("code") != 0:
        return None

    data = payload.get("data", {})
    durl = data.get("durl") or []
    if not durl:
        return None

    first = durl[0]
    return {
        "bvid": bvid,
        "cid": cid,
        "quality": data.get("quality"),
        "format": data.get("format"),
        "timelength": data.get("timelength"),
        "accept_description": data.get("accept_description"),
        "play_url": first.get("url"),
        "size": first.get("size"),
        "length": first.get("length"),
    }


def fetch_video_detail(target_mid: str, bvid: str) -> dict | None:
    payload = parse_mobile_state(MOBILE_VIDEO.format(bvid=bvid))
    if not payload:
        return None

    video = payload.get("video", {})
    view = video.get("viewInfo", {})
    owner = view.get("owner") or {}
    owner_mid = int(owner.get("mid") or 0)
    if owner_mid != int(target_mid):
        return None

    season = view.get("ugc_season") or {}
    related_bvids: list[str] = []
    for section in season.get("sections", []):
        for episode in section.get("episodes", []):
            episode_bvid = str(episode.get("bvid") or "").strip()
            if episode_bvid and episode_bvid not in related_bvids:
                related_bvids.append(episode_bvid)

    return {
        "aid": view.get("aid"),
        "bvid": view.get("bvid"),
        "cid": view.get("cid"),
        "title": view.get("title"),
        "desc": view.get("desc"),
        "pubdate": view.get("pubdate"),
        "ctime": view.get("ctime"),
        "duration": view.get("duration"),
        "owner": owner,
        "stat": view.get("stat") or {},
        "pages": view.get("pages") or [],
        "tname": view.get("tname"),
        "copyright": view.get("copyright"),
        "subtitle": view.get("subtitle") or {},
        "ugc_season": season,
        "related_bvids": related_bvids,
        "source_url": MOBILE_VIDEO.format(bvid=bvid),
    }


def collect_video_details(target_mid: str, seeds: list[dict], limit: int) -> list[dict]:
    seed_map = {item["bvid"]: item for item in seeds if item.get("bvid")}
    queue = deque(seed_map.keys())
    seen: set[str] = set()
    details: list[dict] = []

    while queue and len(details) < limit:
        bvid = queue.popleft()
        if bvid in seen:
            continue
        seen.add(bvid)

        detail = fetch_video_detail(target_mid, bvid)
        if not detail:
            continue

        detail["seed_hit"] = seed_map.get(bvid)
        details.append(detail)

        for related_bvid in detail.get("related_bvids", []):
            if related_bvid not in seen:
                queue.append(related_bvid)

        time.sleep(0.15)

    return sorted(
        details,
        key=lambda item: (item.get("pubdate") or 0, item.get("bvid") or ""),
        reverse=True,
    )


def flatten_videos(details: list[dict]) -> list[dict]:
    videos: list[dict] = []
    for item in details:
        stat = item.get("stat") or {}
        videos.append({
            "aid": item.get("aid"),
            "bvid": item.get("bvid"),
            "title": item.get("title"),
            "description": item.get("desc"),
            "duration": item.get("duration"),
            "created": item.get("pubdate"),
            "play": stat.get("view"),
            "comment": stat.get("reply"),
            "coin": stat.get("coin"),
            "like": stat.get("like"),
        })
    return videos


def collect_comments(video_details: list[dict], per_video_limit: int, video_limit: int) -> list[dict]:
    comments: list[dict] = []

    for detail in video_details[:video_limit]:
        aid = detail.get("aid")
        if not aid:
            continue

        url = f"{API_VIDEO_REPLIES}?oid={aid}&type=1&mode=3&next=0&ps={max(per_video_limit, 1)}"
        payload = safe_fetch_json(url, DESKTOP_HEADERS)
        if not payload or payload.get("code") != 0:
            continue

        replies = payload.get("data", {}).get("replies") or []
        for reply in replies[:per_video_limit]:
            comments.append({
                "aid": aid,
                "bvid": detail.get("bvid"),
                "video_title": detail.get("title"),
                "reply_id": reply.get("rpid"),
                "user": (reply.get("member") or {}).get("uname"),
                "message": (reply.get("content") or {}).get("message"),
                "like": reply.get("like"),
                "ctime": reply.get("ctime"),
            })

        time.sleep(0.2)

    return comments


def collect_playurls(video_details: list[dict], limit: int) -> list[dict]:
    playurls: list[dict] = []

    for detail in video_details[:limit]:
        cid = detail.get("cid")
        if not cid:
            pages = detail.get("pages") or []
            if pages:
                cid = pages[0].get("cid")

        record = collect_playurl(str(detail.get("bvid") or ""), cid)
        if record:
            playurls.append(record)
        time.sleep(0.15)

    return playurls


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public Bilibili metadata for distillation.")
    parser.add_argument("--mid", required=True, help="Bilibili mid / uid")
    parser.add_argument("--room-id", help="Live room id")
    parser.add_argument("--video-limit", type=int, default=60, help="Max official videos to keep")
    parser.add_argument("--dynamic-limit", type=int, default=20, help="Max dynamics to keep")
    parser.add_argument("--comment-limit", type=int, default=0, help="Top comments per video")
    parser.add_argument("--comment-video-limit", type=int, default=20, help="Videos to probe for comments")
    parser.add_argument(
        "--keywords",
        default="永雏塔菲,AceTaffy,雏草姬,塔菲,永雛タフィー",
        help="Comma-separated search keywords for seed discovery",
    )
    parser.add_argument("--search-pages", type=int, default=8, help="Search pages per keyword")
    parser.add_argument("--playurl-limit", type=int, default=0, help="Generate direct play URLs for latest N videos")
    parser.add_argument("--output-dir", default="sources/raw/bilibili", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir).expanduser()
    keywords = [item.strip() for item in args.keywords.split(",") if item.strip()]

    space_state = parse_mobile_state(MOBILE_SPACE.format(mid=args.mid)) or {}
    profile = {
        "source": "mobile-space",
        "mid": args.mid,
        "space_url": MOBILE_SPACE.format(mid=args.mid),
        "info": (space_state.get("space") or {}).get("info") or {},
        "feed_list": (space_state.get("space") or {}).get("feedList") or {},
    }

    search_hits, search_pages = collect_search_seeds(args.mid, keywords, args.search_pages)
    video_details = collect_video_details(args.mid, search_hits, args.video_limit)
    videos = flatten_videos(video_details)
    dynamics = collect_dynamic(args.mid, args.dynamic_limit)
    live = collect_live(args.mid, args.room_id)
    comments = (
        collect_comments(video_details, args.comment_limit, args.comment_video_limit)
        if args.comment_limit > 0
        else []
    )
    playurls = collect_playurls(video_details, args.playurl_limit) if args.playurl_limit > 0 else []

    relation = {
        "source": "live-master",
        "mid": args.mid,
        "follower_num": ((live.get("master_info") or {}).get("follower_num")),
    }

    write_json(out_dir / "profile.json", profile)
    write_json(out_dir / "space_state.json", space_state)
    write_json(out_dir / "relation.json", relation)
    write_json(out_dir / "search_hits.json", search_hits)
    write_json(out_dir / "search_pages.json", search_pages)
    write_json(out_dir / "videos.json", videos)
    write_json(out_dir / "video_details.json", video_details)
    write_json(out_dir / "dynamics.json", dynamics)
    write_json(out_dir / "live.json", live)
    if comments:
        write_json(out_dir / "comments.json", comments)
    if playurls:
        write_json(out_dir / "playurls.json", playurls)

    summary = {
        "mid": args.mid,
        "room_id": args.room_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "keywords": keywords,
        "search_seed_count": len(search_hits),
        "videos_count": len(videos),
        "video_details_count": len(video_details),
        "dynamics_count": len(dynamics),
        "comments_count": len(comments),
        "playurl_count": len(playurls),
    }
    write_json(out_dir / "summary.json", summary)

    print(f"[OK] bilibili profile      -> {out_dir / 'profile.json'}")
    print(f"[OK] bilibili search hits  -> {out_dir / 'search_hits.json'}")
    print(f"[OK] bilibili videos       -> {out_dir / 'videos.json'}")
    print(f"[OK] bilibili details      -> {out_dir / 'video_details.json'}")
    print(f"[OK] bilibili dynamics     -> {out_dir / 'dynamics.json'}")
    print(f"[OK] bilibili live         -> {out_dir / 'live.json'}")
    if comments:
        print(f"[OK] bilibili comments     -> {out_dir / 'comments.json'}")
    if playurls:
        print(f"[OK] bilibili playurls     -> {out_dir / 'playurls.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
