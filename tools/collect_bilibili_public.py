#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
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
API_DYNAMIC_OPUS = "https://api.bilibili.com/x/polymer/web-dynamic/v1/opus/feed/space"
API_PLAYER_PLAYURL = "https://api.bilibili.com/x/player/playurl"
SEARCH_VIDEO = "https://search.bilibili.com/video"
MOBILE_SPACE = "https://m.bilibili.com/space/{mid}"
MOBILE_VIDEO = "https://m.bilibili.com/video/{bvid}"

DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AceTaffySkill/0.3)",
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

HTTP_RETRIES = 5
RETRY_BACKOFF = 1.8
HTTP_TIMEOUT = 30
SAVE_EVERY = 20
RETRYABLE_STATUS = {408, 412, 425, 429, 500, 502, 503, 504}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return payload


def load_existing(path: Path, expected_type: type, default: object):
    payload = read_json(path, default)
    return payload if isinstance(payload, expected_type) else default


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values


def load_target_manifest(explicit: str | None) -> tuple[dict | None, Path | None]:
    candidate = Path(explicit or "sources/targets/ace-taffy.json").expanduser()
    if not candidate.exists():
        return None, None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None, candidate
    return payload if isinstance(payload, dict) else None, candidate


def canonical_source(manifest: dict | None, key: str) -> dict:
    if not isinstance(manifest, dict):
        return {}
    sources = manifest.get("canonical_sources")
    if not isinstance(sources, dict):
        return {}
    value = sources.get(key)
    return value if isinstance(value, dict) else {}


def collection_defaults(manifest: dict | None) -> dict:
    if not isinstance(manifest, dict):
        return {}
    defaults = manifest.get("collection_defaults")
    return defaults if isinstance(defaults, dict) else {}


def manifest_search_terms(manifest: dict | None) -> list[str]:
    if not isinstance(manifest, dict):
        return []
    defaults = collection_defaults(manifest)
    values: list[str] = []
    display_name = manifest.get("display_name")
    if isinstance(display_name, str):
        values.append(display_name)
    keywords = defaults.get("bilibili_search_keywords")
    if isinstance(keywords, list):
        values.extend(str(item) for item in keywords)
    return dedupe(values)


def init_state(
    *,
    target_path: Path | None,
    target_slug: str | None,
    mid: str,
    room_id: str | None,
    keywords: list[str],
    args: argparse.Namespace,
) -> dict:
    return {
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "target": str(target_path) if target_path else None,
        "target_slug": target_slug,
        "mid": mid,
        "room_id": room_id,
        "keywords": keywords,
        "resume": bool(args.resume),
        "options": {
            "video_limit": args.video_limit,
            "dynamic_limit": args.dynamic_limit,
            "comment_limit": args.comment_limit,
            "comment_video_limit": args.comment_video_limit,
            "search_pages": args.search_pages,
            "playurl_limit": args.playurl_limit,
            "http_retries": args.http_retries,
            "retry_backoff": args.retry_backoff,
            "save_every": args.save_every,
        },
        "steps": {},
        "errors": {},
    }


def write_state(path: Path, state: dict) -> None:
    state["updated_at"] = now_iso()
    write_json(path, state)


def set_step_state(
    state: dict,
    step: str,
    status: str,
    *,
    output: str | None = None,
    records: int | None = None,
    detail: str | None = None,
) -> None:
    payload = {
        "status": status,
        "updated_at": now_iso(),
    }
    if output:
        payload["output"] = output
    if records is not None:
        payload["records"] = records
    if detail:
        payload["detail"] = detail
    state.setdefault("steps", {})[step] = payload


def record_error(state: dict, step: str, error: Exception) -> None:
    state.setdefault("errors", {})[step] = f"{type(error).__name__}: {error}"


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def fetch_text(url: str, headers: dict[str, str]) -> str:
    last_error: Exception | None = None
    for attempt in range(1, max(HTTP_RETRIES, 1) + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in RETRYABLE_STATUS or attempt >= HTTP_RETRIES:
                raise
        except (urllib.error.URLError, http.client.IncompleteRead, http.client.RemoteDisconnected, ConnectionResetError, TimeoutError, ValueError) as exc:
            last_error = exc
            if attempt >= HTTP_RETRIES:
                raise
        time.sleep(RETRY_BACKOFF * attempt)
    if last_error:
        raise last_error
    raise RuntimeError(f"unable to fetch {url}")


def fetch_json(url: str, headers: dict[str, str]) -> dict:
    payload = fetch_text(url, headers)
    return json.loads(payload)


def safe_fetch_json(url: str, headers: dict[str, str]) -> dict | None:
    try:
        return fetch_json(url, headers)
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        http.client.IncompleteRead,
        http.client.RemoteDisconnected,
        ConnectionResetError,
        TimeoutError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None


def parse_mobile_state(url: str) -> dict | None:
    try:
        html = fetch_text(url, MOBILE_HEADERS)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
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
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
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


def nested_get(payload: object, *keys: str) -> object:
    cursor = payload
    for key in keys:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def pick_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
    return ""


def normalize_jump_url(url: object) -> str:
    text = pick_text(url)
    if text.startswith("//"):
        return "https:" + text
    return text


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


def normalize_legacy_dynamic(item: dict, page: int) -> dict | None:
    modules = item.get("modules") or {}
    author = modules.get("module_author") or {}
    dynamic = modules.get("module_dynamic") or {}
    desc = dynamic.get("desc") or {}
    text = pick_text(
        desc.get("text"),
        nested_get(dynamic, "major", "opus", "summary", "text"),
        nested_get(dynamic, "major", "archive", "desc"),
        nested_get(dynamic, "major", "archive", "title"),
        item.get("desc"),
        item.get("content"),
    )
    if not text:
        return None

    return {
        "opus_id": pick_text(
            item.get("id_str"),
            nested_get(item, "basic", "rid_str"),
            nested_get(item, "basic", "comment_id_str"),
        ) or None,
        "url": normalize_jump_url(
            nested_get(dynamic, "major", "opus", "jump_url")
            or nested_get(item, "basic", "jump_url")
            or item.get("jump_url")
        ),
        "text": text,
        "like": nested_get(modules, "module_stat", "like", "count"),
        "author": author.get("name"),
        "pub_ts": author.get("pub_ts"),
        "page": page,
        "source_endpoint": "legacy_feed_space",
    }


def collect_dynamic(
    mid: str,
    limit: int,
    *,
    on_progress=None,
) -> list[dict]:
    if limit <= 0:
        return []

    headers = {**DESKTOP_HEADERS, "Referer": f"https://space.bilibili.com/{mid}/dynamic"}
    results: list[dict] = []
    offset = ""
    page = 1

    while len(results) < limit:
        url = (
            f"{API_DYNAMIC_OPUS}?host_mid={urllib.parse.quote(mid)}"
            f"&page={page}&offset={urllib.parse.quote(offset)}&type=all"
        )
        payload = safe_fetch_json(url, headers)
        if not payload or payload.get("code") != 0:
            break

        data = payload.get("data") or {}
        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            break

        for item in items:
            content = pick_text(item.get("content"))
            if not content:
                continue
            stat = item.get("stat") or {}
            results.append({
                "opus_id": item.get("opus_id"),
                "url": normalize_jump_url(item.get("jump_url")),
                "text": content,
                "like": stat.get("like"),
                "page": page,
                "source_endpoint": "opus_feed_space",
            })
            if len(results) >= limit:
                break

        if on_progress and (page % max(SAVE_EVERY, 1) == 0 or len(results) >= limit):
            on_progress(results[:limit], page, "opus_feed_space")

        offset = str(data.get("offset") or "").strip()
        if not data.get("has_more") or not offset or len(results) >= limit:
            return results[:limit]
        page += 1
        time.sleep(0.15)

    if results:
        return results[:limit]

    offset = ""
    page = 1
    legacy_results: list[dict] = []
    while len(legacy_results) < limit:
        url = (
            f"{API_DYNAMIC}?host_mid={urllib.parse.quote(mid)}"
            f"&offset={urllib.parse.quote(offset)}"
        )
        payload = safe_fetch_json(url, headers)
        if not payload or payload.get("code") != 0:
            break

        data = payload.get("data") or {}
        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            break

        for item in items:
            normalized = normalize_legacy_dynamic(item, page)
            if not normalized:
                continue
            legacy_results.append(normalized)
            if len(legacy_results) >= limit:
                break

        if on_progress and (page % max(SAVE_EVERY, 1) == 0 or len(legacy_results) >= limit):
            on_progress(legacy_results[:limit], page, "legacy_feed_space")

        offset = str(data.get("offset") or "").strip()
        if not data.get("has_more") or not offset or len(legacy_results) >= limit:
            break
        page += 1
        time.sleep(0.15)

    return legacy_results[:limit]


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


def sort_video_details(details: list[dict]) -> list[dict]:
    return sorted(
        details,
        key=lambda item: (item.get("pubdate") or 0, item.get("bvid") or ""),
        reverse=True,
    )


def collect_video_details(
    target_mid: str,
    seeds: list[dict],
    limit: int,
    *,
    on_progress=None,
) -> list[dict]:
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

        if on_progress and (len(details) % max(SAVE_EVERY, 1) == 0 or len(details) >= limit):
            on_progress(sort_video_details(details)[:limit], len(details))

        for related_bvid in detail.get("related_bvids", []):
            if related_bvid not in seen:
                queue.append(related_bvid)

        time.sleep(0.15)

    return sort_video_details(details)[:limit]


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


def collect_comments(
    video_details: list[dict],
    per_video_limit: int,
    video_limit: int,
    *,
    on_progress=None,
) -> list[dict]:
    comments: list[dict] = []

    for index, detail in enumerate(video_details[:video_limit], start=1):
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

        if on_progress and (index % max(SAVE_EVERY, 1) == 0 or index >= min(video_limit, len(video_details))):
            on_progress(comments, index)

        time.sleep(0.2)

    return comments


def collect_playurls(
    video_details: list[dict],
    limit: int,
    *,
    on_progress=None,
) -> list[dict]:
    playurls: list[dict] = []

    for index, detail in enumerate(video_details[:limit], start=1):
        cid = detail.get("cid")
        if not cid:
            pages = detail.get("pages") or []
            if pages:
                cid = pages[0].get("cid")

        record = collect_playurl(str(detail.get("bvid") or ""), cid)
        if record:
            playurls.append(record)

        if on_progress and (index % max(SAVE_EVERY, 1) == 0 or index >= min(limit, len(video_details))):
            on_progress(playurls, index)
        time.sleep(0.15)

    return playurls


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public Bilibili metadata for distillation.")
    parser.add_argument("--target", default="sources/targets/ace-taffy.json", help="Optional target manifest path")
    parser.add_argument("--mid", help="Bilibili mid / uid")
    parser.add_argument("--room-id", help="Live room id")
    parser.add_argument("--video-limit", type=int, default=60, help="Max official videos to keep")
    parser.add_argument("--dynamic-limit", type=int, default=20, help="Max dynamics to keep")
    parser.add_argument("--comment-limit", type=int, default=0, help="Top comments per video")
    parser.add_argument("--comment-video-limit", type=int, default=20, help="Videos to probe for comments")
    parser.add_argument("--keywords", help="Comma-separated search keywords for seed discovery")
    parser.add_argument("--search-pages", type=int, default=8, help="Search pages per keyword")
    parser.add_argument("--playurl-limit", type=int, default=0, help="Generate direct play URLs for latest N videos")
    parser.add_argument("--output-dir", default="sources/raw/bilibili", help="Output directory")
    parser.add_argument("--state-file", help="Optional collector state path")
    parser.add_argument("--http-retries", type=int, default=5, help="HTTP retry attempts for transient failures")
    parser.add_argument("--retry-backoff", type=float, default=1.8, help="Base retry backoff in seconds")
    parser.add_argument("--save-every", type=int, default=20, help="Flush partial long-running results every N units")
    parser.add_argument("--resume", dest="resume", action="store_true", default=True, help="Reuse existing step outputs as fallback")
    parser.add_argument("--fresh", dest="resume", action="store_false", help="Ignore existing outputs when a step fails")
    args = parser.parse_args()

    global HTTP_RETRIES, RETRY_BACKOFF, SAVE_EVERY
    HTTP_RETRIES = max(args.http_retries, 1)
    RETRY_BACKOFF = max(args.retry_backoff, 0.1)
    SAVE_EVERY = max(args.save_every, 1)

    manifest, target_path = load_target_manifest(args.target)
    defaults = collection_defaults(manifest)
    bili = canonical_source(manifest, "bilibili")

    mid = str(args.mid or bili.get("mid") or "").strip()
    if not mid:
        raise SystemExit("missing --mid and no bilibili.mid found in target manifest")
    room_id = str(args.room_id or bili.get("room_id") or bili.get("short_id") or "").strip() or None

    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.state_file).expanduser() if args.state_file else out_dir / "_collector_state.json"

    raw_keywords = args.keywords
    if raw_keywords is None:
        raw_keywords = ",".join(defaults.get("bilibili_search_keywords") or manifest_search_terms(manifest))
    keywords = [item.strip() for item in (raw_keywords or "").split(",") if item.strip()]
    if not keywords:
        keywords = ["永雏塔菲", "AceTaffy", "雏草姬", "塔菲", "永雛タフィー"]

    state = init_state(
        target_path=target_path,
        target_slug=(manifest or {}).get("slug") if isinstance(manifest, dict) else None,
        mid=mid,
        room_id=room_id,
        keywords=keywords,
        args=args,
    )
    write_state(state_path, state)

    profile_path = out_dir / "profile.json"
    space_state_path = out_dir / "space_state.json"
    relation_path = out_dir / "relation.json"
    search_hits_path = out_dir / "search_hits.json"
    search_pages_path = out_dir / "search_pages.json"
    videos_path = out_dir / "videos.json"
    video_details_path = out_dir / "video_details.json"
    dynamics_path = out_dir / "dynamics.json"
    live_path = out_dir / "live.json"
    comments_path = out_dir / "comments.json"
    playurls_path = out_dir / "playurls.json"
    summary_path = out_dir / "summary.json"

    existing_profile = load_existing(profile_path, dict, {}) if args.resume else {}
    existing_space_state = load_existing(space_state_path, dict, {}) if args.resume else {}
    existing_relation = load_existing(relation_path, dict, {}) if args.resume else {}
    existing_search_hits = load_existing(search_hits_path, list, []) if args.resume else []
    existing_search_pages = load_existing(search_pages_path, list, []) if args.resume else []
    existing_video_details = load_existing(video_details_path, list, []) if args.resume else []
    existing_videos = load_existing(videos_path, list, []) if args.resume else []
    existing_dynamics = load_existing(dynamics_path, list, []) if args.resume else []
    existing_live = load_existing(live_path, dict, {}) if args.resume else {}
    existing_comments = load_existing(comments_path, list, []) if args.resume else []
    existing_playurls = load_existing(playurls_path, list, []) if args.resume else []

    space_state: dict = {}
    profile: dict = {}
    set_step_state(state, "profile", "running", output=str(profile_path))
    write_state(state_path, state)
    try:
        space_state = parse_mobile_state(MOBILE_SPACE.format(mid=mid)) or {}
        profile = {
            "source": "mobile-space",
            "mid": mid,
            "space_url": MOBILE_SPACE.format(mid=mid),
            "info": (space_state.get("space") or {}).get("info") or {},
            "feed_list": (space_state.get("space") or {}).get("feedList") or {},
        }
        write_json(space_state_path, space_state)
        write_json(profile_path, profile)
        set_step_state(state, "profile", "completed", output=str(profile_path), records=1)
    except Exception as exc:
        record_error(state, "profile", exc)
        space_state = load_existing(space_state_path, dict, existing_space_state)
        profile = load_existing(profile_path, dict, existing_profile)
        if profile or space_state:
            warn(f"profile fetch failed, reuse existing snapshot: {exc}")
            set_step_state(state, "profile", "fallback", output=str(profile_path), records=1, detail=str(exc))
        else:
            warn(f"profile fetch failed without fallback: {exc}")
            set_step_state(state, "profile", "failed", output=str(profile_path), detail=str(exc))
    write_state(state_path, state)

    search_hits: list[dict] = []
    search_pages: list[dict] = []
    set_step_state(state, "search", "running", output=str(search_hits_path))
    write_state(state_path, state)
    try:
        search_hits, search_pages = collect_search_seeds(mid, keywords, args.search_pages)
        write_json(search_hits_path, search_hits)
        write_json(search_pages_path, search_pages)
        set_step_state(state, "search", "completed", output=str(search_hits_path), records=len(search_hits))
    except Exception as exc:
        record_error(state, "search", exc)
        search_hits = load_existing(search_hits_path, list, existing_search_hits)
        search_pages = load_existing(search_pages_path, list, existing_search_pages)
        if search_hits or search_pages:
            warn(f"search fetch failed, reuse existing snapshot: {exc}")
            set_step_state(state, "search", "fallback", output=str(search_hits_path), records=len(search_hits), detail=str(exc))
        else:
            warn(f"search fetch failed without fallback: {exc}")
            set_step_state(state, "search", "failed", output=str(search_hits_path), detail=str(exc))
    write_state(state_path, state)

    video_details: list[dict] = []
    videos: list[dict] = []
    set_step_state(state, "video_details", "running", output=str(video_details_path), records=len(existing_video_details))
    write_state(state_path, state)

    def flush_video_details(rows: list[dict], scanned: int) -> None:
        write_json(video_details_path, rows)
        write_json(videos_path, flatten_videos(rows))
        set_step_state(
            state,
            "video_details",
            "running",
            output=str(video_details_path),
            records=len(rows),
            detail=f"partial flush after {scanned} details",
        )
        write_state(state_path, state)

    try:
        video_details = collect_video_details(
            mid,
            search_hits,
            args.video_limit,
            on_progress=flush_video_details,
        )
        videos = flatten_videos(video_details)
        write_json(video_details_path, video_details)
        write_json(videos_path, videos)
        set_step_state(state, "video_details", "completed", output=str(video_details_path), records=len(video_details))
    except Exception as exc:
        record_error(state, "video_details", exc)
        video_details = load_existing(video_details_path, list, existing_video_details)
        videos = load_existing(videos_path, list, existing_videos) or flatten_videos(video_details)
        if video_details or videos:
            warn(f"video detail fetch failed, reuse existing snapshot: {exc}")
            if video_details:
                write_json(video_details_path, video_details)
            if videos:
                write_json(videos_path, videos)
            set_step_state(state, "video_details", "fallback", output=str(video_details_path), records=len(video_details), detail=str(exc))
        else:
            warn(f"video detail fetch failed without fallback: {exc}")
            set_step_state(state, "video_details", "failed", output=str(video_details_path), detail=str(exc))
    write_state(state_path, state)

    dynamics: list[dict] = []
    set_step_state(state, "dynamics", "running", output=str(dynamics_path), records=len(existing_dynamics))
    write_state(state_path, state)

    def flush_dynamics(rows: list[dict], page: int, endpoint: str) -> None:
        write_json(dynamics_path, rows)
        set_step_state(
            state,
            "dynamics",
            "running",
            output=str(dynamics_path),
            records=len(rows),
            detail=f"partial flush page={page} endpoint={endpoint}",
        )
        write_state(state_path, state)

    try:
        dynamics = collect_dynamic(mid, args.dynamic_limit, on_progress=flush_dynamics)
        write_json(dynamics_path, dynamics)
        set_step_state(state, "dynamics", "completed", output=str(dynamics_path), records=len(dynamics))
    except Exception as exc:
        record_error(state, "dynamics", exc)
        dynamics = load_existing(dynamics_path, list, existing_dynamics)
        if dynamics:
            warn(f"dynamics fetch failed, reuse existing snapshot: {exc}")
            write_json(dynamics_path, dynamics)
            set_step_state(state, "dynamics", "fallback", output=str(dynamics_path), records=len(dynamics), detail=str(exc))
        else:
            warn(f"dynamics fetch failed without fallback: {exc}")
            set_step_state(state, "dynamics", "failed", output=str(dynamics_path), detail=str(exc))
    write_state(state_path, state)

    live: dict = {}
    relation: dict = {}
    set_step_state(state, "live", "running", output=str(live_path))
    write_state(state_path, state)
    try:
        live = collect_live(mid, room_id)
        relation = {
            "source": "live-master",
            "mid": mid,
            "follower_num": ((live.get("master_info") or {}).get("follower_num")),
        }
        write_json(live_path, live)
        write_json(relation_path, relation)
        set_step_state(state, "live", "completed", output=str(live_path), records=1)
    except Exception as exc:
        record_error(state, "live", exc)
        live = load_existing(live_path, dict, existing_live)
        relation = load_existing(relation_path, dict, existing_relation)
        if live or relation:
            warn(f"live fetch failed, reuse existing snapshot: {exc}")
            if live:
                write_json(live_path, live)
            if relation:
                write_json(relation_path, relation)
            set_step_state(state, "live", "fallback", output=str(live_path), records=1, detail=str(exc))
        else:
            warn(f"live fetch failed without fallback: {exc}")
            set_step_state(state, "live", "failed", output=str(live_path), detail=str(exc))
    write_state(state_path, state)

    comments: list[dict] = []
    if args.comment_limit > 0:
        set_step_state(state, "comments", "running", output=str(comments_path), records=len(existing_comments))
        write_state(state_path, state)

        def flush_comments(rows: list[dict], scanned: int) -> None:
            write_json(comments_path, rows)
            set_step_state(
                state,
                "comments",
                "running",
                output=str(comments_path),
                records=len(rows),
                detail=f"partial flush after {scanned} videos",
            )
            write_state(state_path, state)

        try:
            comments = collect_comments(
                video_details,
                args.comment_limit,
                args.comment_video_limit,
                on_progress=flush_comments,
            )
            write_json(comments_path, comments)
            set_step_state(state, "comments", "completed", output=str(comments_path), records=len(comments))
        except Exception as exc:
            record_error(state, "comments", exc)
            comments = load_existing(comments_path, list, existing_comments)
            if comments:
                warn(f"comment fetch failed, reuse existing snapshot: {exc}")
                write_json(comments_path, comments)
                set_step_state(state, "comments", "fallback", output=str(comments_path), records=len(comments), detail=str(exc))
            else:
                warn(f"comment fetch failed without fallback: {exc}")
                set_step_state(state, "comments", "failed", output=str(comments_path), detail=str(exc))
        write_state(state_path, state)
    else:
        comments = []

    playurls: list[dict] = []
    if args.playurl_limit > 0:
        set_step_state(state, "playurls", "running", output=str(playurls_path), records=len(existing_playurls))
        write_state(state_path, state)

        def flush_playurls(rows: list[dict], scanned: int) -> None:
            write_json(playurls_path, rows)
            set_step_state(
                state,
                "playurls",
                "running",
                output=str(playurls_path),
                records=len(rows),
                detail=f"partial flush after {scanned} videos",
            )
            write_state(state_path, state)

        try:
            playurls = collect_playurls(video_details, args.playurl_limit, on_progress=flush_playurls)
            write_json(playurls_path, playurls)
            set_step_state(state, "playurls", "completed", output=str(playurls_path), records=len(playurls))
        except Exception as exc:
            record_error(state, "playurls", exc)
            playurls = load_existing(playurls_path, list, existing_playurls)
            if playurls:
                warn(f"playurl fetch failed, reuse existing snapshot: {exc}")
                write_json(playurls_path, playurls)
                set_step_state(state, "playurls", "fallback", output=str(playurls_path), records=len(playurls), detail=str(exc))
            else:
                warn(f"playurl fetch failed without fallback: {exc}")
                set_step_state(state, "playurls", "failed", output=str(playurls_path), detail=str(exc))
        write_state(state_path, state)
    else:
        playurls = []

    summary = {
        "target": str(target_path) if target_path else None,
        "target_slug": (manifest or {}).get("slug") if isinstance(manifest, dict) else None,
        "mid": mid,
        "room_id": room_id,
        "collected_at": now_iso(),
        "keywords": keywords,
        "search_seed_count": len(search_hits),
        "videos_count": len(videos),
        "video_details_count": len(video_details),
        "dynamics_count": len(dynamics),
        "comments_count": len(comments),
        "playurl_count": len(playurls),
        "resume_mode": bool(args.resume),
        "state_file": str(state_path),
        "errors": state.get("errors", {}),
    }
    write_json(summary_path, summary)
    set_step_state(state, "summary", "completed", output=str(summary_path), records=1)
    write_state(state_path, state)

    print(f"[OK] bilibili profile      -> {profile_path}")
    print(f"[OK] bilibili search hits  -> {search_hits_path}")
    print(f"[OK] bilibili videos       -> {videos_path}")
    print(f"[OK] bilibili details      -> {video_details_path}")
    print(f"[OK] bilibili dynamics     -> {dynamics_path}")
    print(f"[OK] bilibili live         -> {live_path}")
    if args.comment_limit > 0:
        print(f"[OK] bilibili comments     -> {comments_path}")
    if args.playurl_limit > 0:
        print(f"[OK] bilibili playurls     -> {playurls_path}")
    print(f"[OK] bilibili summary      -> {summary_path}")
    print(f"[OK] collector state       -> {state_path}")

    hard_failures = [
        name for name in ("profile", "search", "video_details", "dynamics", "live")
        if state.get("steps", {}).get(name, {}).get("status") == "failed"
    ]
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
