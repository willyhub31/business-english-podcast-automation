from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


AUTOMATION_DIR = Path(__file__).resolve().parent
BASE_DIR = Path(os.environ.get("BUSINESS_ENGLISH_BASE_DIR", AUTOMATION_DIR.parent))
AUTOMATION_DIR = BASE_DIR / "automation"
LEGACY_UPLOAD_SCRIPT = Path(r"F:\Workspaces\youtube\POV Shadow Systems\claude sonnet\tools\upload_to_youtube.py")
VENDORED_UPLOAD_SCRIPT = AUTOMATION_DIR / "vendor" / "upload_to_youtube.py"


def env_path(name: str, fallback: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else fallback


def default_upload_script() -> Path:
    env_value = os.environ.get("BUSINESS_ENGLISH_UPLOAD_SCRIPT")
    if env_value:
        return Path(env_value)
    if LEGACY_UPLOAD_SCRIPT.exists():
        return LEGACY_UPLOAD_SCRIPT
    return VENDORED_UPLOAD_SCRIPT


DEFAULT_OUTPUT_ROOT = env_path("BUSINESS_ENGLISH_OUTPUT_ROOT", BASE_DIR / "runs")
DEFAULT_BUILD_SCRIPT = env_path("BUSINESS_ENGLISH_BUILD_SCRIPT", BASE_DIR / "build_business_english_episode.py")
DEFAULT_BACKGROUND = env_path("BUSINESS_ENGLISH_BACKGROUND", BASE_DIR / "video background.mp4")
DEFAULT_QUEUE_FILE = AUTOMATION_DIR / "business_english_topics.txt"
DEFAULT_STATE_FILE = AUTOMATION_DIR / "automation_state.json"
DEFAULT_LOG_FILE = AUTOMATION_DIR / "automation_history.jsonl"
DEFAULT_UPLOAD_SCRIPT = default_upload_script()
DEFAULT_CHANNEL_TITLE = os.environ.get("BUSINESS_ENGLISH_CHANNEL_TITLE", "Business English Podcast")
DEFAULT_FEMALE_VOICE = os.environ.get("BUSINESS_ENGLISH_FEMALE_VOICE", "Sadachbia")
DEFAULT_MALE_VOICE = os.environ.get("BUSINESS_ENGLISH_MALE_VOICE", "Puck")
DEFAULT_CHANNEL_PROFILE = os.environ.get("BUSINESS_ENGLISH_CHANNEL_PROFILE", "channel2")
DEFAULT_CHANNEL_CONFIG = os.environ.get("YOUTUBE_CHANNEL_CONFIG")
DEFAULT_TOKEN_FILE = os.environ.get("YOUTUBE_TOKEN_FILE")
DEFAULT_CLIENT_SECRETS = os.environ.get("YOUTUBE_CLIENT_SECRETS")

DEFAULT_TAGS = [
    "business english",
    "english for work",
    "english podcast",
    "business english podcast",
    "sales english",
    "speak english",
    "learn english",
    "english listening practice",
    "professional english",
]


def print_block(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def run_command(command: list[str], env: dict[str, str] | None = None) -> str:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert process.stdout is not None
    lines: list[str] = []
    for line in process.stdout:
        print(line, end="")
        lines.append(line)
    process.wait()
    output = "".join(lines)
    if process.returncode != 0:
        raise RuntimeError(f"Command failed ({process.returncode}): {' '.join(command)}")
    return output


def load_topics(queue_file: Path) -> list[str]:
    if not queue_file.exists():
        raise RuntimeError(f"Topic queue not found: {queue_file}")
    topics = []
    for raw_line in queue_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            topics.append(line)
    if not topics:
        raise RuntimeError(f"No usable topics found in: {queue_file}")
    return topics


def load_state(state_file: Path) -> dict:
    if state_file.exists():
        return json.loads(state_file.read_text(encoding="utf-8"))
    return {
        "next_topic_index": 0,
        "last_run_at": None,
        "last_topic": None,
        "last_run_dir": None,
        "last_video_path": None,
        "last_upload_mode": None,
    }


def save_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def append_history(log_file: Path, record: dict) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def choose_topic(explicit_topic: str | None, queue_file: Path, state: dict) -> tuple[str, int | None]:
    if explicit_topic:
        return explicit_topic.strip(), None
    topics = load_topics(queue_file)
    index = int(state.get("next_topic_index", 0)) % len(topics)
    return topics[index], index


def build_run_dir(output_root: Path, topic: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_root / f"{stamp}_{slugify(topic)[:60]}"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def build_tags(topic: str) -> str:
    topic_tags = [part.strip().lower() for part in re.split(r"[:,-]", topic) if part.strip()]
    merged: list[str] = []
    for tag in topic_tags + DEFAULT_TAGS:
        normalized = re.sub(r"\s+", " ", tag).strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return ",".join(merged[:20])


def verify_outputs(run_dir: Path) -> dict:
    expected = {
        "video": run_dir / "business_english_episode.mp4",
        "audio": run_dir / "business_english_episode_audio.mp3",
        "title": run_dir / "youtube_title.txt",
        "description": run_dir / "youtube_description.txt",
        "transcript": run_dir / "full_transcript.txt",
        "srt": run_dir / "business_english_episode.srt",
    }
    missing = [str(path) for path in expected.values() if not path.exists()]
    if missing:
        raise RuntimeError("Missing expected output files:\n" + "\n".join(missing))
    return {name: str(path) for name, path in expected.items()}


def run_build(
    run_dir: Path,
    build_script: Path,
    background: Path,
    episode_topic: str,
    channel_title: str,
    female_voice: str,
    male_voice: str,
) -> str:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    run_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(build_script),
        "--output-dir",
        str(run_dir),
        "--background",
        str(background),
        "--episode-topic",
        episode_topic,
        "--channel-title",
        channel_title,
        "--female-voice",
        female_voice,
        "--male-voice",
        male_voice,
    ]
    return run_command(command, env=os.environ.copy())


def run_upload(
    upload_script: Path,
    channel_profile: str,
    channel_config: str | None,
    token_file: str | None,
    client_secrets: str | None,
    upload_mode: str,
    run_dir: Path,
    verified: dict,
    synthetic_media: str,
) -> str:
    command = [
        sys.executable,
        str(upload_script),
        "--channel-profile",
        channel_profile,
    ]
    if channel_config:
        command.extend(["--channel-config", channel_config])
    if token_file:
        command.extend(["--token-file", token_file])
    if client_secrets:
        command.extend(["--client-secrets", client_secrets])

    if upload_mode == "auth-check":
        command.append("--auth-only")
        return run_command(command)

    title = read_text(Path(verified["title"]))
    description = read_text(Path(verified["description"]))
    tags = build_tags(title)
    command.extend(
        [
            "--video",
            verified["video"],
            "--title",
            title,
            "--description",
            description,
            "--tags",
            tags,
            "--privacy",
            upload_mode,
            "--synthetic-media",
            synthetic_media,
        ]
    )
    thumbnail = run_dir / "business_english_episode_frame_v2.png"
    if thumbnail.exists():
        command.extend(["--thumbnail", str(thumbnail)])
    return run_command(command)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily Business English podcast pipeline.")
    parser.add_argument("--episode-topic", help="Override the next topic from the queue.")
    parser.add_argument("--queue-file", default=str(DEFAULT_QUEUE_FILE))
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE))
    parser.add_argument("--log-file", default=str(DEFAULT_LOG_FILE))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--build-script", default=str(DEFAULT_BUILD_SCRIPT))
    parser.add_argument("--background", default=str(DEFAULT_BACKGROUND))
    parser.add_argument("--channel-title", default=DEFAULT_CHANNEL_TITLE)
    parser.add_argument("--female-voice", default=DEFAULT_FEMALE_VOICE)
    parser.add_argument("--male-voice", default=DEFAULT_MALE_VOICE)
    parser.add_argument("--upload-script", default=str(DEFAULT_UPLOAD_SCRIPT))
    parser.add_argument("--channel-profile", default=DEFAULT_CHANNEL_PROFILE)
    parser.add_argument("--channel-config", default=DEFAULT_CHANNEL_CONFIG)
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE)
    parser.add_argument("--client-secrets", default=DEFAULT_CLIENT_SECRETS)
    parser.add_argument(
        "--upload-mode",
        default="none",
        choices=["none", "auth-check", "private", "unlisted", "public"],
        help="none = build only, auth-check = verify YouTube auth, others upload with that privacy.",
    )
    parser.add_argument(
        "--synthetic-media",
        default="yes",
        choices=["yes", "no"],
        help="Pass altered-content disclosure flag to the upload script.",
    )
    parser.add_argument(
        "--reuse-build-from",
        help="Skip generation and use an existing run directory for verification or upload tests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root)
    queue_file = Path(args.queue_file)
    state_file = Path(args.state_file)
    log_file = Path(args.log_file)
    build_script = Path(args.build_script)
    background = Path(args.background)
    upload_script = Path(args.upload_script)
    state = load_state(state_file)
    topic, topic_index = choose_topic(args.episode_topic, queue_file, state)

    run_dir: Path | None = None
    try:
        if args.reuse_build_from:
            run_dir = Path(args.reuse_build_from)
        else:
            run_dir = build_run_dir(output_root, topic)
            print_block(f"BUILDING EPISODE: {topic}")
            run_build(
                run_dir=run_dir,
                build_script=build_script,
                background=background,
                episode_topic=topic,
                channel_title=args.channel_title,
                female_voice=args.female_voice,
                male_voice=args.male_voice,
            )

        print_block("VERIFYING OUTPUTS")
        verified = verify_outputs(run_dir)

        if args.upload_mode != "none":
            print_block(f"UPLOAD MODE: {args.upload_mode}")
            run_upload(
                upload_script=upload_script,
                channel_profile=args.channel_profile,
                channel_config=args.channel_config,
                token_file=args.token_file,
                client_secrets=args.client_secrets,
                upload_mode=args.upload_mode,
                run_dir=run_dir,
                verified=verified,
                synthetic_media=args.synthetic_media,
            )

        now = datetime.now().isoformat(timespec="seconds")
        state["last_run_at"] = now
        state["last_topic"] = topic
        state["last_run_dir"] = str(run_dir)
        state["last_video_path"] = verified["video"]
        state["last_upload_mode"] = args.upload_mode
        if topic_index is not None:
            state["next_topic_index"] = topic_index + 1
        save_state(state_file, state)

        result = {
            "status": "ok",
            "ranAt": now,
            "topic": topic,
            "runDir": str(run_dir),
            "verifiedFiles": verified,
            "uploadMode": args.upload_mode,
            "channelProfile": args.channel_profile,
        }
        append_history(log_file, result)
        print_block("RESULT")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        now = datetime.now().isoformat(timespec="seconds")
        result = {
            "status": "error",
            "ranAt": now,
            "topic": topic,
            "runDir": str(run_dir) if run_dir else None,
            "uploadMode": args.upload_mode,
            "channelProfile": args.channel_profile,
            "error": str(exc),
        }
        append_history(log_file, result)
        print_block("ERROR")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
