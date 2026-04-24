from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from googleapiclient.errors import HttpError


BASE_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
sys.path.insert(0, str(VENDOR_DIR))

from upload_to_youtube import get_authenticated_service  # noqa: E402
from google_oauth_service import build_authenticated_service  # noqa: E402


STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "business", "by", "close", "daily", "english", "for",
    "from", "how", "in", "into", "is", "it", "learn", "lesson", "lessons", "of", "on", "or",
    "pod", "podcast", "practice", "real", "sales", "speak", "speaking", "that", "the", "this",
    "to", "up", "with", "work", "your", "bbc", "bel",
}

NICHE_KEYWORDS = {
    "business", "english", "pod", "podcast", "conversation", "conversations", "work", "workplace",
    "professional", "sales", "pronunciation", "vocabulary", "phrases", "listening", "speaking",
    "learn", "learning", "communication", "meeting", "meetings", "interview", "job", "fluent",
}

FOCUS_KEYWORDS = {
    "business", "work", "workplace", "professional", "sales", "conversation", "conversations",
    "meeting", "meetings", "interview", "interviews", "phrases", "vocabulary", "pronunciation",
    "speaking", "communication", "manager", "managers", "leader", "leaders", "delegate",
}


@dataclass
class VideoMetric:
    video_id: str
    title: str
    published_at: str
    views: int
    likes: int
    comments: int
    duration_seconds: int
    views_per_day: float
    url: str
    analytics: dict[str, Any] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a daily YouTube improvement report.")
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--client-secrets", required=True)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent / "channel_improvement_config.json"))
    parser.add_argument("--output-root", default=str(BASE_DIR / "reports" / "channel-improvement"))
    parser.add_argument("--channel-title", default="The English Pod Club")
    parser.add_argument("--analytics-token-file")
    parser.add_argument("--analytics-client-secrets")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def auth(token_file: str, client_secrets: str):
    return get_authenticated_service(token_file=token_file, client_secrets_file=client_secrets)


def auth_analytics(token_file: str, client_secrets: str):
    return build_authenticated_service(
        token_file=token_file,
        client_secrets_file=client_secrets,
        api_service_name="youtubeAnalytics",
        api_version="v2",
        scopes=[
            "https://www.googleapis.com/auth/yt-analytics.readonly",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
        port=8080,
    )


def batched(items: list[str], size: int) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def parse_duration_seconds(value: str) -> int:
    pattern = re.compile(
        r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
    )
    match = pattern.match(value or "")
    if not match:
        return 0
    parts = {name: safe_int(number) for name, number in match.groupdict(default="0").items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def views_per_day(published_at: str, views: int) -> float:
    published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    age_days = max((now_utc() - published).total_seconds() / 86400, 0.25)
    return round(views / age_days, 2)


def get_own_channel(youtube, own_channel_id: str | None = None) -> dict[str, Any]:
    response = youtube.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
    items = response.get("items", [])
    if not items:
        raise RuntimeError("Unable to load authenticated channel.")
    channel = items[0]
    if own_channel_id and channel.get("id") != own_channel_id:
        raise RuntimeError(f"Authenticated channel mismatch: expected {own_channel_id}, got {channel.get('id')}")
    return channel


def search_channels(youtube, query: str, max_results: int) -> list[dict[str, Any]]:
    response = youtube.search().list(
        part="snippet",
        q=query,
        type="channel",
        maxResults=max_results,
    ).execute()
    return response.get("items", [])


def fetch_channels(youtube, channel_ids: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for chunk in batched(channel_ids, 50):
        response = youtube.channels().list(
            part="snippet,statistics,contentDetails",
            id=",".join(chunk),
        ).execute()
        items.extend(response.get("items", []))
    return items


def fetch_playlist_video_ids(youtube, playlist_id: str, limit: int) -> list[str]:
    video_ids: list[str] = []
    next_page_token = None
    while len(video_ids) < limit:
        response = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=min(50, limit - len(video_ids)),
            pageToken=next_page_token,
        ).execute()
        for item in response.get("items", []):
            video_id = item.get("contentDetails", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    return video_ids


def fetch_videos(youtube, video_ids: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for chunk in batched(video_ids, 50):
        response = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(chunk),
        ).execute()
        items.extend(response.get("items", []))
    return items


def simplify_video(video: dict[str, Any]) -> VideoMetric:
    snippet = video.get("snippet", {})
    stats = video.get("statistics", {})
    duration = parse_duration_seconds(video.get("contentDetails", {}).get("duration", ""))
    views = safe_int(stats.get("viewCount"))
    likes = safe_int(stats.get("likeCount"))
    comments = safe_int(stats.get("commentCount"))
    published_at = snippet.get("publishedAt", "")
    return VideoMetric(
        video_id=video.get("id", ""),
        title=snippet.get("title", ""),
        published_at=published_at,
        views=views,
        likes=likes,
        comments=comments,
        duration_seconds=duration,
        views_per_day=views_per_day(published_at, views) if published_at else 0.0,
        url=f"https://www.youtube.com/watch?v={video.get('id', '')}",
    )


def channel_recent_metrics(youtube, channel: dict[str, Any], limit: int) -> list[VideoMetric]:
    uploads_playlist_id = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads_playlist_id:
        return []
    video_ids = fetch_playlist_video_ids(youtube, uploads_playlist_id, limit)
    videos = fetch_videos(youtube, video_ids)
    metrics = [simplify_video(video) for video in videos]
    metrics.sort(key=lambda item: item.published_at, reverse=True)
    return metrics


def format_duration(seconds: int) -> str:
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def median_duration(videos: list[VideoMetric]) -> int:
    values = [video.duration_seconds for video in videos if video.duration_seconds > 0]
    return int(statistics.median(values)) if values else 0


def average_views(videos: list[VideoMetric]) -> float:
    values = [video.views for video in videos]
    return round(sum(values) / len(values), 2) if values else 0.0


def average_views_per_day(videos: list[VideoMetric]) -> float:
    values = [video.views_per_day for video in videos]
    return round(sum(values) / len(values), 2) if values else 0.0


def tokenize_title(title: str) -> list[str]:
    return [
        token for token in re.findall(r"[A-Za-z][A-Za-z0-9']+", title.lower())
        if token not in STOPWORDS and len(token) > 2 and not any(ch.isdigit() for ch in token)
    ]


def tokenize_text(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z][A-Za-z0-9']+", (text or "").lower()))


def channel_niche_score(channel: dict[str, Any], queries: list[str]) -> int:
    snippet = channel.get("snippet", {})
    text = " ".join(
        [
            snippet.get("title", ""),
            snippet.get("description", ""),
            " ".join(queries),
        ]
    )
    tokens = tokenize_text(text)
    return len(tokens & NICHE_KEYWORDS)


def channel_focus_score(channel: dict[str, Any], queries: list[str]) -> int:
    snippet = channel.get("snippet", {})
    text = " ".join(
        [
            snippet.get("title", ""),
            snippet.get("description", ""),
            " ".join(queries),
        ]
    )
    tokens = tokenize_text(text)
    return len(tokens & FOCUS_KEYWORDS)


def filter_analysis_videos(videos: list[VideoMetric], min_seconds: int) -> list[VideoMetric]:
    return [
        video for video in videos
        if video.duration_seconds >= min_seconds and len(set(tokenize_title(video.title)) & FOCUS_KEYWORDS) >= 1
    ]


def collect_phrase_candidates(videos: list[VideoMetric], top_n: int = 8) -> list[str]:
    unigram_counter: Counter[str] = Counter()
    bigram_counter: Counter[str] = Counter()
    for video in videos:
        tokens = tokenize_title(video.title)
        unigram_counter.update(tokens)
        bigram_counter.update(" ".join(pair) for pair in zip(tokens, tokens[1:]))

    phrases = [phrase for phrase, _ in bigram_counter.most_common(top_n * 2) if phrase.strip()]
    words = [word for word, _ in unigram_counter.most_common(top_n * 2)]
    merged: list[str] = []
    for candidate in phrases + words:
        if candidate not in merged:
            merged.append(candidate)
    return merged[:top_n]


def title_overlap(reference: list[VideoMetric], comparison: list[VideoMetric]) -> list[str]:
    ref_tokens = set()
    own_tokens = set()
    for video in reference:
        ref_tokens.update(tokenize_title(video.title))
    for video in comparison:
        own_tokens.update(tokenize_title(video.title))
    missing = sorted(ref_tokens - own_tokens)
    return missing[:10]


def discover_competitors(
    youtube,
    config: dict[str, Any],
    own_channel_id: str,
) -> list[dict[str, Any]]:
    discovered: dict[str, dict[str, Any]] = {}

    for entry in config.get("fixed_competitors", []):
        channel_id = entry["channel_id"]
        if channel_id == own_channel_id:
            continue
        discovered[channel_id] = {
            "channel_id": channel_id,
            "queries": ["fixed"],
            "label": entry.get("label"),
        }

    per_query = safe_int(config.get("channel_search_per_query", 5))
    for query in config.get("search_queries", []):
        for item in search_channels(youtube, query, per_query):
            channel_id = item.get("snippet", {}).get("channelId")
            if not channel_id or channel_id == own_channel_id:
                continue
            record = discovered.setdefault(channel_id, {"channel_id": channel_id, "queries": [], "label": None})
            record["queries"].append(query)

    ordered_ids = sorted(
        discovered,
        key=lambda channel_id: (len(discovered[channel_id]["queries"]), discovered[channel_id]["channel_id"]),
        reverse=True,
    )
    max_competitors = safe_int(config.get("max_competitors", 10))
    selected_ids = ordered_ids[:max_competitors]
    channels = fetch_channels(youtube, selected_ids)
    by_id = {channel["id"]: channel for channel in channels}

    results: list[dict[str, Any]] = []
    min_niche_score = safe_int(config.get("min_niche_score", 3))
    for channel_id in selected_ids:
        channel = by_id.get(channel_id)
        if not channel:
            continue
        niche_score = channel_niche_score(channel, discovered[channel_id]["queries"])
        focus_score = channel_focus_score(channel, discovered[channel_id]["queries"])
        if "fixed" not in discovered[channel_id]["queries"] and (niche_score < min_niche_score or focus_score < 1):
            continue
        results.append(
            {
                "channel": channel,
                "queries": discovered[channel_id]["queries"],
                "label": discovered[channel_id]["label"],
                "niche_score": niche_score,
                "focus_score": focus_score,
            }
        )
    return results


def build_report_data(
    youtube,
    config: dict[str, Any],
    channel_title: str,
    analytics_summary: dict[str, Any] | None = None,
    own_video_analytics: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    own_channel = get_own_channel(youtube, own_channel_id=config.get("own_channel_id"))
    own_recent_limit = safe_int(config.get("own_recent_videos", 10))
    own_recent_videos = channel_recent_metrics(youtube, own_channel, own_recent_limit)
    own_recent_videos = attach_analytics_to_videos(own_recent_videos, own_video_analytics or {})

    competitors = []
    min_competitor_video_seconds = safe_int(config.get("min_competitor_video_seconds", 180))
    for item in discover_competitors(youtube, config, own_channel["id"]):
        channel = item["channel"]
        recent_videos = channel_recent_metrics(youtube, channel, safe_int(config.get("recent_videos_per_channel", 5)))
        analysis_videos = filter_analysis_videos(recent_videos, min_competitor_video_seconds)
        if not analysis_videos:
            continue
        competitors.append(
            {
                "channel_id": channel["id"],
                "title": channel.get("snippet", {}).get("title", ""),
                "description": channel.get("snippet", {}).get("description", ""),
                "published_at": channel.get("snippet", {}).get("publishedAt", ""),
                "subscriber_count": safe_int(channel.get("statistics", {}).get("subscriberCount")),
                "video_count": safe_int(channel.get("statistics", {}).get("videoCount")),
                "view_count": safe_int(channel.get("statistics", {}).get("viewCount")),
                "queries": item["queries"],
                "niche_score": item["niche_score"],
                "focus_score": item["focus_score"],
                "recent_videos": [video.__dict__ for video in recent_videos],
                "analysis_videos": [video.__dict__ for video in analysis_videos],
                "avg_views_per_day_recent": average_views_per_day(analysis_videos),
                "median_duration_recent_seconds": median_duration(analysis_videos),
                "channel_url": f"https://www.youtube.com/channel/{channel['id']}",
            }
        )

    competitor_videos = [
        VideoMetric(**video)
        for competitor in competitors
        for video in competitor["analysis_videos"]
    ]
    competitor_videos.sort(key=lambda video: video.views_per_day, reverse=True)
    own_top_recent = sorted(own_recent_videos, key=lambda video: video.views_per_day, reverse=True)
    own_avg_views = average_views(own_recent_videos)
    underperformers = [video for video in own_recent_videos if own_avg_views and video.views < own_avg_views * 0.65]

    top_competitor_phrases = collect_phrase_candidates(competitor_videos)
    missing_title_tokens = title_overlap(competitor_videos[:15], own_recent_videos)
    competitor_median_duration = median_duration(competitor_videos[:20])
    own_median_duration = median_duration(own_recent_videos)

    suggestions: list[str] = []
    if top_competitor_phrases:
        suggestions.append(
            "Test title angles using these high-frequency competitor hooks: "
            + ", ".join(top_competitor_phrases[:5])
            + "."
        )
    if missing_title_tokens:
        suggestions.append(
            "You are not using several niche tokens competitors lean on: "
            + ", ".join(missing_title_tokens[:6])
            + "."
        )
    if competitor_median_duration and own_median_duration:
        if own_median_duration < competitor_median_duration * 0.75:
            suggestions.append(
                f"Competitor lessons are usually longer ({format_duration(competitor_median_duration)}) than your recent median "
                f"({format_duration(own_median_duration)}). Test longer breakdown sections."
            )
        elif own_median_duration > competitor_median_duration * 1.35:
            suggestions.append(
                f"Your recent videos run longer ({format_duration(own_median_duration)}) than the competitor median "
                f"({format_duration(competitor_median_duration)}). Tighten intros and recap sections."
            )
    if own_top_recent and competitor_videos:
        best_own = own_top_recent[0]
        best_competitor = competitor_videos[0]
        if best_own.views_per_day < best_competitor.views_per_day * 0.45:
            suggestions.append(
                f"Your best recent video is at {best_own.views_per_day:.0f} views/day while the top competitor hit "
                f"{best_competitor.views_per_day:.0f} views/day. Improve the first 15 seconds and thumbnail contrast."
            )
    if underperformers:
        suggestions.append(
            "Review these low-performing recent uploads and rewrite title/thumbnail patterns before reusing them: "
            + ", ".join(video.title for video in underperformers[:3])
            + "."
        )

    own_stats = own_channel.get("statistics", {})
    return {
        "generated_at": now_utc().isoformat(timespec="seconds"),
        "channel_title": channel_title,
        "own_channel": {
            "channel_id": own_channel["id"],
            "title": own_channel.get("snippet", {}).get("title", ""),
            "subscriber_count": safe_int(own_stats.get("subscriberCount")),
            "view_count": safe_int(own_stats.get("viewCount")),
            "video_count": safe_int(own_stats.get("videoCount")),
            "channel_url": f"https://www.youtube.com/channel/{own_channel['id']}",
            "analytics_summary": analytics_summary,
            "recent_videos": [video.__dict__ for video in own_recent_videos],
            "avg_views_recent": own_avg_views,
            "avg_views_per_day_recent": average_views_per_day(own_recent_videos),
            "median_duration_recent_seconds": own_median_duration,
        },
        "competitors": competitors,
        "top_competitor_videos": [video.__dict__ for video in competitor_videos[:10]],
        "underperforming_own_videos": [video.__dict__ for video in underperformers[:5]],
        "title_phrase_candidates": top_competitor_phrases,
        "missing_title_tokens": missing_title_tokens,
        "suggestions": suggestions,
    }


def analytics_rows_to_dicts(response: dict[str, Any]) -> list[dict[str, Any]]:
    headers = [header["name"] for header in response.get("columnHeaders", [])]
    rows = response.get("rows", [])
    return [dict(zip(headers, row)) for row in rows]


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def build_analytics_window() -> tuple[str, str]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=27)
    return start.isoformat(), end.isoformat()


def query_channel_analytics(analytics_service) -> dict[str, Any] | None:
    start_date, end_date = build_analytics_window()
    try:
        base = analytics_service.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,subscribersGained,subscribersLost",
        ).execute()
        base_row = analytics_rows_to_dicts(base)
        summary = base_row[0] if base_row else {}
        try:
            impressions = analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="impressions,impressionsCtr",
            ).execute()
            impression_row = analytics_rows_to_dicts(impressions)
            if impression_row:
                summary.update(impression_row[0])
        except HttpError:
            pass
        summary["startDate"] = start_date
        summary["endDate"] = end_date
        return summary
    except HttpError:
        return None


def query_video_analytics(analytics_service, video_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not video_ids:
        return {}
    start_date, end_date = build_analytics_window()
    try:
        response = analytics_service.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions="video",
            filters="video==" + ",".join(video_ids),
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,subscribersGained,subscribersLost",
        ).execute()
    except HttpError:
        return {}

    rows_by_video: dict[str, dict[str, Any]] = {}
    for row in analytics_rows_to_dicts(response):
        video_id = str(row.pop("video", ""))
        if not video_id:
            continue
        rows_by_video[video_id] = row

    try:
        impression_response = analytics_service.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions="video",
            filters="video==" + ",".join(video_ids),
            metrics="impressions,impressionsCtr",
        ).execute()
        for row in analytics_rows_to_dicts(impression_response):
            video_id = str(row.pop("video", ""))
            if video_id:
                rows_by_video.setdefault(video_id, {}).update(row)
    except HttpError:
        pass

    for row in rows_by_video.values():
        row["startDate"] = start_date
        row["endDate"] = end_date
    return rows_by_video


def attach_analytics_to_videos(videos: list[VideoMetric], analytics_rows: dict[str, dict[str, Any]]) -> list[VideoMetric]:
    attached: list[VideoMetric] = []
    for video in videos:
        payload = analytics_rows.get(video.video_id)
        video.analytics = payload or None
        attached.append(video)
    return attached


def analytics_summary_lines(analytics_summary: dict[str, Any] | None) -> list[str]:
    if not analytics_summary:
        return ["- Analytics metrics unavailable. Add an analytics-scoped OAuth token to enable CTR/watch-time reporting."]
    views = safe_int(analytics_summary.get("views"))
    watched = safe_float(analytics_summary.get("estimatedMinutesWatched"))
    avg_duration = safe_float(analytics_summary.get("averageViewDuration"))
    avg_percent = safe_float(analytics_summary.get("averageViewPercentage"))
    impressions = safe_int(analytics_summary.get("impressions"))
    ctr = safe_float(analytics_summary.get("impressionsCtr"))
    return [
        f"- Window: `{analytics_summary.get('startDate')}` to `{analytics_summary.get('endDate')}`",
        f"- Views: `{views}`",
        f"- Watch time (minutes): `{watched:.2f}`",
        f"- Average view duration: `{int(avg_duration)} sec`",
        f"- Average percentage viewed: `{avg_percent:.2f}%`",
        f"- Impressions: `{impressions}`",
        f"- CTR: `{ctr:.2f}%`",
    ]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def make_markdown(report: dict[str, Any]) -> str:
    own = report["own_channel"]
    competitors = report["competitors"]
    lines: list[str] = []
    lines.append(f"# Daily Channel Improvement Report")
    lines.append("")
    lines.append(f"Generated: `{report['generated_at']}`")
    lines.append("")
    lines.append("## Your Channel Snapshot")
    lines.append(
        f"- Channel: [{own['title']}]({own['channel_url']})"
    )
    lines.append(f"- Subscribers: `{own['subscriber_count']}`")
    lines.append(f"- Total views: `{own['view_count']}`")
    lines.append(f"- Videos: `{own['video_count']}`")
    lines.append(f"- Avg recent views: `{own['avg_views_recent']}`")
    lines.append(f"- Avg recent views/day: `{own['avg_views_per_day_recent']}`")
    lines.append(f"- Median recent duration: `{format_duration(own['median_duration_recent_seconds'])}`")
    lines.append("")
    lines.append("## Your Analytics (Last 28 Days)")
    lines.extend(analytics_summary_lines(own.get("analytics_summary")))
    lines.append("")
    lines.append("## Recent Uploads")
    for video in own["recent_videos"][:5]:
        analytics = video.get("analytics") or {}
        suffix = ""
        if analytics:
            suffix = (
                f" | CTR `{safe_float(analytics.get('impressionsCtr')):.2f}%`"
                f" | avg view `{int(safe_float(analytics.get('averageViewDuration')))} sec`"
                f" | avg viewed `{safe_float(analytics.get('averageViewPercentage')):.2f}%`"
            )
        lines.append(
            f"- [{video['title']}]({video['url']}) | `{video['views']}` views | `{video['views_per_day']}` views/day | `{format_duration(video['duration_seconds'])}`{suffix}"
        )
    lines.append("")
    lines.append("## Competitor Radar")
    for competitor in competitors[:6]:
        lines.append(
            f"- [{competitor['title']}]({competitor['channel_url']}) | `{competitor['subscriber_count']}` subs | `{competitor['avg_views_per_day_recent']}` avg views/day | median duration `{format_duration(competitor['median_duration_recent_seconds'])}`"
        )
    lines.append("")
    lines.append("## Top Competitor Videos")
    for video in report["top_competitor_videos"][:8]:
        lines.append(
            f"- [{video['title']}]({video['url']}) | `{video['views']}` views | `{video['views_per_day']}` views/day"
        )
    lines.append("")
    lines.append("## Title Angles To Test")
    for phrase in report["title_phrase_candidates"][:8]:
        lines.append(f"- `{phrase}`")
    lines.append("")
    lines.append("## Missing Tokens In Your Recent Titles")
    if report["missing_title_tokens"]:
        for token in report["missing_title_tokens"][:10]:
            lines.append(f"- `{token}`")
    else:
        lines.append("- No obvious title-token gap today.")
    lines.append("")
    lines.append("## Improvement Actions")
    for suggestion in report["suggestions"]:
        lines.append(f"- {suggestion}")
    lines.append("")
    if report["underperforming_own_videos"]:
        lines.append("## Watch List")
        for video in report["underperforming_own_videos"]:
            lines.append(
                f"- [{video['title']}]({video['url']}) | `{video['views']}` views | `{video['views_per_day']}` views/day"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))
    youtube = auth(args.token_file, args.client_secrets)
    analytics_summary = None
    own_video_analytics: dict[str, dict[str, Any]] = {}
    if args.analytics_token_file and args.analytics_client_secrets:
        analytics_service = auth_analytics(args.analytics_token_file, args.analytics_client_secrets)
        analytics_summary = query_channel_analytics(analytics_service)
        own_channel = get_own_channel(youtube, own_channel_id=config.get("own_channel_id"))
        own_video_ids = fetch_playlist_video_ids(
            youtube,
            own_channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", ""),
            safe_int(config.get("own_recent_videos", 10)),
        )
        own_video_analytics = query_video_analytics(analytics_service, own_video_ids)

    report = build_report_data(
        youtube,
        config,
        args.channel_title,
        analytics_summary=analytics_summary,
        own_video_analytics=own_video_analytics,
    )

    output_root = Path(args.output_root)
    day_dir = output_root / datetime.now().strftime("%Y-%m-%d")
    latest_md = output_root / "latest_report.md"
    latest_json = output_root / "latest_report.json"
    day_md = day_dir / "report.md"
    day_json = day_dir / "report.json"
    summary_txt = output_root / "latest_summary.txt"

    markdown = make_markdown(report)
    day_dir.mkdir(parents=True, exist_ok=True)
    day_md.write_text(markdown, encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")
    write_json(day_json, report)
    write_json(latest_json, report)
    summary_txt.write_text(markdown, encoding="utf-8")

    print(json.dumps(
        {
            "status": "ok",
            "report_markdown": str(day_md),
            "report_json": str(day_json),
            "latest_markdown": str(latest_md),
            "latest_json": str(latest_json),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
