"""
Automatic YouTube Upload Script
================================

Uploads videos to YouTube with title, description, tags, and thumbnail automatically.

Requirements:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

Setup (First Time Only):
    1. Go to https://console.cloud.google.com/
    2. Create a new project (or use existing)
    3. Enable YouTube Data API v3
    4. Create OAuth 2.0 credentials
    5. Download credentials as client_secrets.json
    6. Place client_secrets.json in the same folder as this script

Usage:
    python upload_to_youtube.py --video "path/to/video.mp4" --title "Video Title" [options]

Options:
    --video PATH          Video file to upload (required unless --auth-only)
    --title TEXT          Video title (required)
    --description TEXT    Video description (optional, or use --metadata-file)
    --tags TEXT           Comma-separated tags (optional)
    --category NUM        Category ID (default: 22 = People & Blogs)
    --privacy STATUS      Privacy: public, private, unlisted (default: private)
    --synthetic-media     Set altered content disclosure: yes or no
    --thumbnail PATH      Thumbnail image (optional)
    --metadata-file PATH  Use metadata from YAML/JSON file (optional)
    --schedule TIME       Schedule publish time (YYYY-MM-DD HH:MM:SS)

Examples:
    # Upload with manual details
    python upload_to_youtube.py --video "exports/ep02_final.mp4" --title "My Video" --description "Description here" --tags "finance,psychology"

    # Upload using metadata file
    python upload_to_youtube.py --video "exports/ep02_final.mp4" --metadata-file "youtube_upload_config.yaml" --thumbnail "images/thumbnails/thumb_01.png"

    # Upload as private (review before publishing)
    python upload_to_youtube.py --video "exports/ep02_final.mp4" --metadata-file "youtube_upload_config.yaml" --privacy private
"""

import os
import sys
import argparse
import json
import pickle
from pathlib import Path
from datetime import datetime

from youtube_channel_profiles import resolve_channel_settings

try:
    import google.oauth2.credentials
    import google_auth_oauthlib.flow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request
except ImportError:
    print("ERROR: Required packages not installed!")
    print("Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)


# YouTube API settings
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
]
DEFAULT_EXPECTED_CHANNEL_ID = 'UCZ7pdGiuePNSygTzp-_KV7g'

# Category IDs: https://developers.google.com/youtube/v3/docs/videoCategories/list
CATEGORY_IDS = {
    'education': 27,
    'people_blogs': 22,
    'howto_style': 26,
    'news_politics': 25,
    'entertainment': 24,
}


def get_authenticated_service(token_file=None, client_secrets_file=None):
    """Authenticate with YouTube API using OAuth 2.0"""
    credentials = None
    script_dir = Path(__file__).resolve().parent
    token_file = Path(token_file) if token_file else script_dir / 'youtube_token_pov_shadow_systems.pickle'
    client_secrets_file = Path(client_secrets_file) if client_secrets_file else script_dir / 'client_secrets.json'

    # Check if we have saved credentials
    if token_file.exists():
        print("Loading saved credentials...")
        with token_file.open('rb') as token:
            credentials = pickle.load(token)

    needs_auth = (
        not credentials
        or not credentials.valid
        or not getattr(credentials, "has_scopes", lambda _: False)(SCOPES)
    )

    # If credentials are invalid, under-scoped, or don't exist, authenticate
    if needs_auth:
        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
            and getattr(credentials, "has_scopes", lambda _: False)(SCOPES)
        ):
            print("Refreshing access token...")
            credentials.refresh(Request())
        else:
            if not client_secrets_file.exists():
                print(f"ERROR: {client_secrets_file} not found!")
                print("\nSetup Instructions:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a project and enable YouTube Data API v3")
                print("3. Create OAuth 2.0 credentials")
                print("4. Download credentials as client_secrets.json")
                print("5. Place client_secrets.json in this directory")
                sys.exit(1)

            print("Starting OAuth 2.0 authentication flow...")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_file), SCOPES
            )
            credentials = flow.run_local_server(port=8080)

        # Save credentials for future use
        with token_file.open('wb') as token:
            pickle.dump(credentials, token)
        print("Credentials saved!")

    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def load_metadata_file(metadata_path):
    """Load metadata from YAML or JSON file"""
    metadata_path = Path(metadata_path)

    if not metadata_path.exists():
        print(f"ERROR: Metadata file not found: {metadata_path}")
        return None

    content = metadata_path.read_text(encoding='utf-8')

    # Try to parse as JSON
    if metadata_path.suffix == '.json':
        return json.loads(content)

    # Try to parse as YAML
    try:
        import yaml
        return yaml.safe_load(content)
    except ImportError:
        print("WARNING: PyYAML not installed. Install with: pip install pyyaml")
        return None


def parse_metadata_markdown(md_file):
    """Parse YouTube metadata from markdown file (YOUTUBE_METADATA.md format)"""
    md_file = Path(md_file)

    if not md_file.exists():
        return None

    content = md_file.read_text(encoding='utf-8')

    metadata = {
        'title': None,
        'description': None,
        'tags': None
    }

    # Extract title (look for first title option)
    if '### Option 1:' in content or '## Video Title' in content:
        lines = content.split('\n')
        in_title_section = False
        for line in lines:
            if 'POV:' in line and '```' not in line and metadata['title'] is None:
                metadata['title'] = line.strip('# ').strip('`').strip()
                break

    # Extract description
    if '## Video Description' in content:
        desc_start = content.find('## Video Description')
        desc_section = content[desc_start:desc_start+2000]
        # Find content between ``` markers
        if '```' in desc_section:
            parts = desc_section.split('```')
            if len(parts) > 1:
                metadata['description'] = parts[1].strip()

    # Extract tags
    if '## Tags' in content:
        tags_start = content.find('## Tags')
        tags_section = content[tags_start:tags_start+1000]
        if '```' in tags_section:
            parts = tags_section.split('```')
            if len(parts) > 1:
                metadata['tags'] = parts[1].strip()

    return metadata


def parse_yes_no(value):
    """Parse yes/no style input into True/False/None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {'yes', 'true', '1', 'y'}:
        return True
    if normalized in {'no', 'false', '0', 'n'}:
        return False
    raise ValueError(f"Invalid yes/no value: {value}")


def upload_video(youtube, video_file, title, description, tags, category_id, privacy_status,
                 contains_synthetic_media=None):
    """Upload video to YouTube"""
    print(f"\n{'='*70}")
    print("UPLOADING TO YOUTUBE")
    print(f"{'='*70}")
    print(f"Video: {video_file}")
    print(f"Title: {title}")
    print(f"Privacy: {privacy_status}")
    if contains_synthetic_media is not None:
        print(f"Altered content: {'yes' if contains_synthetic_media else 'no'}")
    print(f"{'='*70}\n")

    # Process tags - clean and validate
    if isinstance(tags, str):
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
    elif isinstance(tags, list):
        tag_list = [str(t).strip() for t in tags if t]
    else:
        tag_list = []

    # Limit to 500 characters total and valid tags
    tag_list = [t for t in tag_list if len(t) <= 30][:50]  # Max 50 tags, each max 30 chars

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tag_list,
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': privacy_status,
            'selfDeclaredMadeForKids': False
        }
    }
    if contains_synthetic_media is not None:
        body['status']['containsSyntheticMedia'] = contains_synthetic_media

    # Create media file upload
    media = MediaFileUpload(
        video_file,
        chunksize=1024*1024,  # 1MB chunks
        resumable=True
    )

    # Execute upload
    request = youtube.videos().insert(
        part='snippet,status',
        body=body,
        media_body=media
    )

    print("Starting upload...")
    response = None
    error = None
    retry = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"Upload progress: {progress}%", end='\r')
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                error = f"HTTP error {e.resp.status} occurred:\n{e.content}"
                retry += 1
                if retry > 5:
                    print(f"\nERROR: {error}")
                    return None
                print(f"\nRetrying upload (attempt {retry})...")
            else:
                raise

    print(f"\nUpload complete!")
    return response


def upload_thumbnail(youtube, video_id, thumbnail_file):
    """Upload custom thumbnail to video"""
    print(f"\nUploading thumbnail: {thumbnail_file}")

    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_file)
        ).execute()
        print("Thumbnail uploaded successfully!")
        return True
    except HttpError as e:
        print(f"ERROR uploading thumbnail: {e}")
        return False


def get_authenticated_channel(youtube):
    """Return authenticated channel metadata for verification."""
    response = youtube.channels().list(
        part='snippet',
        mine=True
    ).execute()

    items = response.get('items', [])
    if not items:
        return None

    channel = items[0]
    snippet = channel.get('snippet', {})
    return {
        'id': channel.get('id'),
        'title': snippet.get('title', ''),
        'custom_url': snippet.get('customUrl')
    }


def main():
    parser = argparse.ArgumentParser(
        description="Upload videos to YouTube automatically",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--video', help='Video file to upload')
    parser.add_argument('--title', help='Video title')
    parser.add_argument('--description', help='Video description')
    parser.add_argument('--tags', help='Comma-separated tags')
    parser.add_argument('--category', default='27', help='Category ID (default: 27 = Education)')
    parser.add_argument('--privacy', default='private', choices=['public', 'private', 'unlisted'],
                        help='Privacy status (default: private)')
    parser.add_argument('--synthetic-media', choices=['yes', 'no'],
                        help='Set altered content disclosure to yes or no')
    parser.add_argument('--thumbnail', help='Thumbnail image file')
    parser.add_argument('--metadata-file', help='Load metadata from YAML/JSON file')
    parser.add_argument('--token-file',
                        default=os.getenv('YOUTUBE_TOKEN_FILE'),
                        help='OAuth token file path (default: tools/youtube_token_pov_shadow_systems.pickle)')
    parser.add_argument('--client-secrets',
                        default=os.getenv('YOUTUBE_CLIENT_SECRETS'),
                        help='OAuth client_secrets.json path (default: tools/client_secrets.json)')
    parser.add_argument('--channel-profile',
                        help='Named channel profile from youtube_channel_profiles.json')
    parser.add_argument('--channel-config',
                        help='Path to channel profiles JSON (default: tools/youtube_channel_profiles.json)')
    parser.add_argument('--expected-channel-name',
                        help='Fail upload if authenticated channel title does not contain this value')
    parser.add_argument('--expected-channel-id',
                        default=os.getenv('YOUTUBE_EXPECTED_CHANNEL_ID'),
                        help='Fail upload if authenticated channel ID does not match this value')
    parser.add_argument('--auth-only', action='store_true',
                        help='Authenticate and verify channel, then exit without uploading')

    args = parser.parse_args()
    script_dir = Path(__file__).resolve().parent
    resolved_channel = resolve_channel_settings(
        script_dir,
        profile_name=args.channel_profile,
        config_path=args.channel_config,
        token_file=args.token_file,
        client_secrets=args.client_secrets,
        expected_channel_name=args.expected_channel_name,
        expected_channel_id=args.expected_channel_id,
        default_expected_channel_id=DEFAULT_EXPECTED_CHANNEL_ID,
    )
    resolved_token_file = resolved_channel["token_file"]

    # Validate video file unless we only want authentication
    video_file = Path(args.video) if args.video else None
    if not args.auth_only:
        if not video_file:
            print("ERROR: --video is required unless --auth-only is used")
            sys.exit(1)
        if not video_file.exists():
            print(f"ERROR: Video file not found: {video_file}")
            sys.exit(1)

    # Load metadata
    metadata = {}

    if args.metadata_file:
        print(f"Loading metadata from: {args.metadata_file}")

        # Check if it's a markdown file
        if args.metadata_file.endswith('.md'):
            metadata = parse_metadata_markdown(args.metadata_file)
        else:
            metadata = load_metadata_file(args.metadata_file)

        if not metadata:
            print("ERROR: Failed to load metadata file")
            sys.exit(1)

    # Use command-line args or metadata file
    title = args.title or metadata.get('title')
    description = args.description or metadata.get('description', '')
    tags = args.tags or metadata.get('tags', '')
    contains_synthetic_media = parse_yes_no(
        args.synthetic_media if args.synthetic_media is not None else metadata.get('containsSyntheticMedia')
    )
    if contains_synthetic_media is None and args.privacy == 'private':
        contains_synthetic_media = True

    if not args.auth_only and not title:
        print("ERROR: Title is required (use --title or --metadata-file)")
        sys.exit(1)

    # Authenticate
    print("Authenticating with YouTube...")
    if resolved_channel["profile_name"]:
        print(f"Channel profile: {resolved_channel['profile_name']}")
    youtube = get_authenticated_service(
        token_file=resolved_channel["token_file"],
        client_secrets_file=resolved_channel["client_secrets"]
    )

    try:
        channel = get_authenticated_channel(youtube)
    except HttpError as e:
        message = str(e).lower()
        if getattr(e, 'resp', None) is not None and e.resp.status == 403 and 'insufficient authentication scopes' in message:
            print("\nERROR: Current OAuth token has insufficient scope to read channel metadata for verification.")
            print(f"Delete token and authenticate again: {resolved_token_file}")
            if resolved_channel["expected_channel_name"] or resolved_channel["expected_channel_id"] or args.auth_only:
                sys.exit(1)
            channel = None
        else:
            raise
    if channel:
        print("\nAuthenticated YouTube channel:")
        print(f"  Title: {channel['title']}")
        print(f"  ID: {channel['id']}")
        if channel.get('custom_url'):
            print(f"  Custom URL: {channel['custom_url']}")

        if resolved_channel["expected_channel_name"]:
            expected_name = resolved_channel["expected_channel_name"].strip().lower()
            actual_name = channel.get('title', '').strip().lower()
            if expected_name not in actual_name:
                print(f"\nERROR: Authenticated channel title '{channel['title']}' does not match expected '{resolved_channel['expected_channel_name']}'")
                sys.exit(1)

        if resolved_channel["expected_channel_id"]:
            if channel.get('id') != resolved_channel["expected_channel_id"]:
                print(f"\nERROR: Authenticated channel ID '{channel.get('id')}' does not match expected '{resolved_channel['expected_channel_id']}'")
                sys.exit(1)
    else:
        print("\nWARNING: Could not verify authenticated channel metadata.")

    if args.auth_only:
        print("\nAuthentication check complete. No upload was performed.")
        sys.exit(0)

    # Upload video
    response = upload_video(
        youtube,
        str(video_file),
        title,
        description,
        tags,
        args.category,
        args.privacy,
        contains_synthetic_media
    )

    if not response:
        print("ERROR: Video upload failed")
        sys.exit(1)

    video_id = response['id']
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    print(f"\n{'='*70}")
    print("VIDEO UPLOADED SUCCESSFULLY!")
    print(f"{'='*70}")
    print(f"Video ID: {video_id}")
    print(f"Video URL: {video_url}")
    print(f"Privacy: {args.privacy}")
    print(f"{'='*70}")

    # Upload thumbnail if provided
    if args.thumbnail:
        thumbnail_file = Path(args.thumbnail)
        if thumbnail_file.exists():
            upload_thumbnail(youtube, video_id, str(thumbnail_file))
        else:
            print(f"WARNING: Thumbnail file not found: {thumbnail_file}")

    print(f"\nDONE! Video is now {args.privacy} on YouTube.")
    if args.privacy == 'private':
        print("Remember to make it public/unlisted when ready!")

    print(f"\nVideo URL: {video_url}")


if __name__ == '__main__':
    main()
