from __future__ import annotations

import argparse
import json
from pathlib import Path

from google_oauth_service import build_authenticated_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or refresh a YouTube Analytics OAuth token.")
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--client-secrets", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = build_authenticated_service(
        token_file=args.token_file,
        client_secrets_file=args.client_secrets,
        api_service_name="youtubeAnalytics",
        api_version="v2",
        scopes=[
            "https://www.googleapis.com/auth/yt-analytics.readonly",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
        port=8080,
    )
    profile = service.reports().query(
        ids="channel==MINE",
        startDate="2026-04-01",
        endDate="2026-04-01",
        metrics="views",
    ).execute()
    print(json.dumps({"status": "ok", "token_file": str(Path(args.token_file).resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
