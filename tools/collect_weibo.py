#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
    "Mobile/15E148 Safari/604.1"
)
WEIBO_PROFILE_CONTAINER = "100505{uid}"
WEIBO_FEED_CONTAINER = "107603{uid}"
WEIBO_HOT_CONTAINER = "230283{uid}"


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def jsonp_payload(text: str, callback: str) -> dict:
    match = re.search(rf"{re.escape(callback)}\((\{{.*\}})\)", text)
    if not match:
        raise RuntimeError(f"unable to parse jsonp callback: {callback}")
    return json.loads(match.group(1))


def parse_count(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value).strip()
    if not text:
        return None

    units = {"万": 10_000, "亿": 100_000_000}
    for suffix, scale in units.items():
        if text.endswith(suffix):
            try:
                return int(float(text[:-1]) * scale)
            except ValueError:
                return None

    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def picture_urls(mblog: dict) -> list[str]:
    urls: list[str] = []
    for item in mblog.get("pics") or []:
        if not isinstance(item, dict):
            continue
        large = item.get("large") or {}
        if large.get("url"):
            urls.append(large["url"])
        elif item.get("url"):
            urls.append(item["url"])
    return urls


def url_object_urls(mblog: dict) -> list[str]:
    urls: list[str] = []
    for obj in mblog.get("url_objects") or []:
        if not isinstance(obj, dict):
            continue
        for key in ("url_long", "ori_url", "short_url", "url"):
            value = obj.get(key)
            if value and value not in urls:
                urls.append(value)
    return urls


def normalize_user(user: dict | None) -> dict:
    user = user or {}
    return {
        "id": user.get("id"),
        "screen_name": user.get("screen_name"),
        "profile_url": user.get("profile_url"),
        "domain": user.get("domain"),
        "description": html.unescape(user.get("description") or ""),
        "followers_count": parse_count(user.get("followers_count")),
        "followers_count_text": user.get("followers_count_str") or user.get("followers_count"),
        "follow_count": parse_count(user.get("follow_count") or user.get("friends_count")),
        "statuses_count": parse_count(user.get("statuses_count")),
        "video_status_count": parse_count(user.get("video_status_count")),
        "gender": user.get("gender"),
        "verified": bool(user.get("verified")),
        "verified_reason": user.get("verified_reason"),
        "avatar_hd": user.get("avatar_hd"),
        "cover_image_phone": user.get("cover_image_phone"),
    }


def normalize_comment(comment: dict) -> dict:
    return {
        "id": comment.get("id"),
        "root_id": comment.get("rootid") or comment.get("rootidstr"),
        "created_at": comment.get("created_at"),
        "source": comment.get("source"),
        "floor_number": comment.get("floor_number"),
        "like_count": comment.get("like_count"),
        "text_html": comment.get("text"),
        "text_plain": strip_html(comment.get("text", "")),
        "pic_urls": picture_urls(comment),
        "user": normalize_user(comment.get("user")),
    }


def normalize_mblog(mblog: dict) -> dict:
    normalized = {
        "id": mblog.get("id") or mblog.get("idstr"),
        "mid": mblog.get("mid"),
        "bid": mblog.get("bid"),
        "created_at": mblog.get("created_at"),
        "source": mblog.get("source"),
        "region_name": mblog.get("region_name"),
        "text_html": mblog.get("text"),
        "text_plain": strip_html(mblog.get("text", "")),
        "comments_count": parse_count(mblog.get("comments_count")),
        "reposts_count": parse_count(mblog.get("reposts_count")),
        "attitudes_count": parse_count(mblog.get("attitudes_count")),
        "is_long_text": bool(mblog.get("isLongText")),
        "truncated": bool(mblog.get("truncated")),
        "favorited": bool(mblog.get("favorited")),
        "pinned": (mblog.get("title") or {}).get("text") == "置顶",
        "title_text": (mblog.get("title") or {}).get("text"),
        "pic_urls": picture_urls(mblog),
        "url_object_urls": url_object_urls(mblog),
        "scheme": mblog.get("scheme"),
        "user": normalize_user(mblog.get("user")),
    }

    retweeted_status = mblog.get("retweeted_status")
    if isinstance(retweeted_status, dict):
        normalized["retweeted_status"] = {
            "id": retweeted_status.get("id") or retweeted_status.get("idstr"),
            "mid": retweeted_status.get("mid"),
            "created_at": retweeted_status.get("created_at"),
            "text_html": retweeted_status.get("text"),
            "text_plain": strip_html(retweeted_status.get("text", "")),
            "comments_count": parse_count(retweeted_status.get("comments_count")),
            "reposts_count": parse_count(retweeted_status.get("reposts_count")),
            "attitudes_count": parse_count(retweeted_status.get("attitudes_count")),
            "pic_urls": picture_urls(retweeted_status),
            "url_object_urls": url_object_urls(retweeted_status),
            "user": normalize_user(retweeted_status.get("user")),
        }

    return normalized


class MobileWeiboSession:
    def __init__(self, uid: str) -> None:
        self.uid = uid
        self.profile_url = f"https://m.weibo.cn/u/{uid}"
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPRedirectHandler(),
        )

    def fetch_text(self, url: str, extra_headers: dict[str, str] | None = None, retries: int = 3) -> str:
        headers = {
            "User-Agent": MOBILE_USER_AGENT,
            "Referer": self.profile_url,
        }
        if extra_headers:
            headers.update(extra_headers)

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                request = urllib.request.Request(url, headers=headers)
                with self.opener.open(request, timeout=30) as response:
                    return response.read().decode("utf-8", "ignore")
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(0.5 * attempt)

        raise RuntimeError(f"unable to fetch {url}: {last_error}")

    def fetch_json(self, url: str) -> dict:
        return json.loads(self.fetch_text(url, {"X-Requested-With": "XMLHttpRequest"}))

    def bootstrap(self) -> None:
        genvisitor = self.fetch_text(
            "https://visitor.passport.weibo.cn/visitor/genvisitor?cb=gen_callback&fp={}"
        )
        gen_data = jsonp_payload(genvisitor, "gen_callback")
        payload = gen_data.get("data") or {}

        tid = payload.get("tid")
        if not tid:
            raise RuntimeError("unable to bootstrap mobile weibo visitor session: missing tid")

        confidence = payload.get("confidence", 100)
        where = 2 if not payload.get("new_tid") else 3
        incarnate_url = (
            "https://visitor.passport.weibo.cn/visitor/visitor"
            f"?a=incarnate&t={urllib.parse.quote(str(tid))}"
            f"&w={urllib.parse.quote(str(where))}"
            f"&c={urllib.parse.quote(str(confidence))}"
            "&gc=&cb=cross_domain2&from=weibo&_rand=1"
        )
        incarnate = self.fetch_text(incarnate_url)
        cross_domain_data = jsonp_payload(incarnate, "cross_domain2")
        cross_data = cross_domain_data.get("data") or {}
        sub = cross_data.get("sub")
        subp = cross_data.get("subp")
        if not sub or not subp:
            raise RuntimeError("unable to bootstrap mobile weibo visitor session: missing sub/subp")

        cross_domain_url = (
            "https://login.sina.com.cn/visitor/visitor"
            f"?a=crossdomain&s={urllib.parse.quote(sub)}"
            f"&sp={urllib.parse.quote(subp)}"
            "&from=weibo&_rand=1&entry=sinawap"
            f"&url={urllib.parse.quote(self.profile_url)}"
        )
        self.fetch_text(cross_domain_url)
        self.fetch_text(self.profile_url)

    def profile(self) -> dict:
        profile_data = self.fetch_json(
            "https://m.weibo.cn/api/container/getIndex"
            f"?type=uid&value={urllib.parse.quote(self.uid)}"
            f"&containerid={WEIBO_PROFILE_CONTAINER.format(uid=self.uid)}"
        )
        hot_data = self.fetch_json(
            "https://m.weibo.cn/api/container/getIndex"
            f"?type=uid&value={urllib.parse.quote(self.uid)}"
            f"&containerid={WEIBO_HOT_CONTAINER.format(uid=self.uid)}"
        )

        profile_payload = profile_data.get("data") or {}
        user_info = profile_payload.get("userInfo") or {}
        hot_cards = ((hot_data.get("data") or {}).get("cards") or [])

        hot_posts: list[dict] = []
        for card in hot_cards:
            if card.get("card_type") != 11:
                continue
            for item in card.get("card_group") or []:
                mblog = item.get("mblog")
                if isinstance(mblog, dict):
                    hot_posts.append(normalize_mblog(mblog))

        return {
            "uid": self.uid,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "user": normalize_user(user_info),
            "profile_container_id": WEIBO_PROFILE_CONTAINER.format(uid=self.uid),
            "feed_container_id": WEIBO_FEED_CONTAINER.format(uid=self.uid),
            "hot_container_id": WEIBO_HOT_CONTAINER.format(uid=self.uid),
            "hot_posts": hot_posts,
        }

    def status_detail(self, status_id: str) -> dict | None:
        try:
            payload = self.fetch_json(
                "https://m.weibo.cn/api/statuses/show"
                f"?id={urllib.parse.quote(str(status_id))}"
            )
        except RuntimeError:
            return None

        if payload.get("ok") != 1:
            return None
        return payload

    def feed_page(self, page: int) -> dict:
        return self.fetch_json(
            "https://m.weibo.cn/api/container/getIndex"
            f"?type=uid&value={urllib.parse.quote(self.uid)}"
            f"&containerid={WEIBO_FEED_CONTAINER.format(uid=self.uid)}"
            f"&page={page}"
        )

    def comment_page(self, feed_id: str, max_id: int | None, max_id_type: int) -> dict:
        params = {
            "id": str(feed_id),
            "mid": str(feed_id),
            "max_id_type": str(max_id_type),
        }
        if max_id is not None:
            params["max_id"] = str(max_id)

        query = urllib.parse.urlencode(params)
        return self.fetch_json(f"https://m.weibo.cn/comments/hotflow?{query}")


def collect_feeds(session: MobileWeiboSession, limit: int, max_pages: int) -> list[dict]:
    feeds: list[dict] = []
    seen_ids: set[str] = set()
    page = 1

    while True:
        if max_pages > 0 and page > max_pages:
            break
        payload = session.feed_page(page)
        cards = ((payload.get("data") or {}).get("cards") or [])
        page_items = 0

        for card in cards:
            if card.get("card_type") != 9:
                continue
            mblog = card.get("mblog")
            if not isinstance(mblog, dict):
                continue

            feed_id = str(mblog.get("id") or mblog.get("idstr") or "").strip()
            if not feed_id or feed_id in seen_ids:
                continue

            if mblog.get("isLongText") or mblog.get("truncated"):
                detail = session.status_detail(feed_id)
                if detail and isinstance(detail.get("data"), dict):
                    mblog = detail["data"]

            normalized = normalize_mblog(mblog)
            feeds.append(normalized)
            seen_ids.add(feed_id)
            page_items += 1

            if limit > 0 and len(feeds) >= limit:
                return feeds

        if page_items == 0:
            break

        page += 1
        time.sleep(0.15)

    return feeds


def collect_comments(session: MobileWeiboSession, feed_id: str, limit: int) -> list[dict]:
    if limit <= 0:
        return []

    comments: list[dict] = []
    max_id: int | None = None
    max_id_type = 0

    while len(comments) < limit:
        payload = session.comment_page(feed_id, max_id, max_id_type)
        if payload.get("ok") != 1:
            break

        data = payload.get("data") or {}
        batch = data.get("data") or []
        if not batch:
            break

        for comment in batch:
            comments.append(normalize_comment(comment))
            if len(comments) >= limit:
                break

        next_max_id = data.get("max_id")
        next_max_id_type = data.get("max_id_type", 0)
        if not next_max_id or next_max_id == max_id:
            break

        max_id = int(next_max_id)
        max_id_type = int(next_max_id_type)
        time.sleep(0.15)

    return comments[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect official Weibo data from the mobile visitor flow.")
    parser.add_argument("--uid", required=True, help="Weibo UID")
    parser.add_argument("--domain", help="Optional Weibo domain; kept for manifest compatibility")
    parser.add_argument("--limit", type=int, default=200, help="Number of feeds to fetch; use 0 for all visible pages")
    parser.add_argument("--max-pages", type=int, default=0, help="Maximum feed pages to request; use 0 for no explicit cap")
    parser.add_argument("--comments-per-post", type=int, default=0, help="Top hot comments per post")
    parser.add_argument("--output-dir", default="sources/raw/weibo", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir).expanduser()
    comments_dir = out_dir / "comments"

    session = MobileWeiboSession(args.uid)
    session.bootstrap()
    profile = session.profile()
    feeds = collect_feeds(session, args.limit, args.max_pages)

    write_json(out_dir / "profile.json", profile)
    write_json(out_dir / "feeds.json", feeds)

    comments_summary: list[dict] = []
    if args.comments_per_post > 0:
        for feed in feeds:
            feed_id = str(feed.get("id") or "").strip()
            if not feed_id:
                continue
            comments = collect_comments(session, feed_id, args.comments_per_post)
            if not comments:
                continue
            write_json(comments_dir / f"{feed_id}.json", comments)
            comments_summary.append(
                {
                    "feed_id": feed_id,
                    "count": len(comments),
                }
            )

    summary = {
        "uid": args.uid,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "feeds_count": len(feeds),
        "comments_collected": comments_summary,
        "limit_requested": args.limit,
        "max_pages_requested": args.max_pages,
    }
    write_json(out_dir / "summary.json", summary)

    print(f"[OK] profile -> {out_dir / 'profile.json'}")
    print(f"[OK] feeds   -> {out_dir / 'feeds.json'}")
    if comments_summary:
        print(f"[OK] comments -> {comments_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
