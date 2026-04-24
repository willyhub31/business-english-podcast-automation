from __future__ import annotations

import argparse
import sys
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
sys.path.insert(0, str(VENDOR_DIR))

from upload_to_youtube import get_authenticated_service  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage YouTube channel assets and uploaded videos.")
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--client-secrets", required=True)
    parser.add_argument("--list-recent", action="store_true")
    parser.add_argument("--delete-video-id")
    parser.add_argument("--thumbnail-video-id")
    parser.add_argument("--thumbnail-file")
    parser.add_argument("--banner-file")
    parser.add_argument("--watermark-file")
    return parser.parse_args()


def auth(token_file: str, client_secrets: str):
    return get_authenticated_service(token_file=token_file, client_secrets_file=client_secrets)


def list_recent_videos(youtube) -> None:
    response = youtube.search().list(part="snippet", forMine=True, type="video", maxResults=10, order="date").execute()
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        print(f"{snippet['publishedAt']} | {video_id} | {snippet['title']}")


def delete_video(youtube, video_id: str) -> None:
    youtube.videos().delete(id=video_id).execute()
    print(f"Deleted video: {video_id}")


def set_thumbnail(youtube, video_id: str, thumbnail_file: Path) -> None:
    youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_file))).execute()
    print(f"Updated thumbnail for: {video_id}")


def set_banner(youtube, banner_file: Path) -> None:
    banner_upload = youtube.channelBanners().insert(media_body=MediaFileUpload(str(banner_file))).execute()
    banner_url = banner_upload["url"]

    current = youtube.channels().list(part="brandingSettings", mine=True).execute()
    item = current["items"][0]
    branding = item.get("brandingSettings", {})
    image_settings = branding.get("image", {})
    image_settings["bannerExternalUrl"] = banner_url
    branding["image"] = image_settings

    youtube.channels().update(
        part="brandingSettings",
        body={
            "id": item["id"],
            "brandingSettings": branding,
        },
    ).execute()
    print(f"Updated channel banner: {banner_file}")


def set_watermark(youtube, watermark_file: Path) -> None:
    channel = youtube.channels().list(part="id", mine=True).execute()["items"][0]
    youtube.watermarks().set(
        channelId=channel["id"],
        body={
            "position": {
                "type": "corner",
                "cornerPosition": "topRight",
            },
            "targetChannelId": channel["id"],
            "timing": {
                "type": "offsetFromStart",
                "offsetMs": "5000",
                "durationMs": "600000",
            },
        },
        media_body=MediaFileUpload(str(watermark_file)),
    ).execute()
    print(f"Updated watermark: {watermark_file}")


def main() -> int:
    args = parse_args()
    youtube = auth(args.token_file, args.client_secrets)

    try:
        if args.list_recent:
            list_recent_videos(youtube)
        if args.thumbnail_video_id and args.thumbnail_file:
            set_thumbnail(youtube, args.thumbnail_video_id, Path(args.thumbnail_file))
        if args.banner_file:
            set_banner(youtube, Path(args.banner_file))
        if args.watermark_file:
            set_watermark(youtube, Path(args.watermark_file))
        if args.delete_video_id:
            delete_video(youtube, args.delete_video_id)
    except HttpError as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
