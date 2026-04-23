from __future__ import annotations

import json
import os
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


AUTOMATION_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("WORKER_CONFIG_PATH", AUTOMATION_DIR / "worker_config.json"))
RUNNER_PATH = AUTOMATION_DIR / "run_daily_business_english_job.py"


def load_config() -> dict:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    env_host = os.environ.get("WORKER_HOST")
    env_port = os.environ.get("WORKER_PORT")
    env_token = os.environ.get("WORKER_AUTH_TOKEN")
    if env_host:
        config["host"] = env_host
    if env_port:
        config["port"] = int(env_port)
    if env_token:
        config["auth_token"] = env_token
    return config


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def authorized(handler: BaseHTTPRequestHandler, config: dict) -> bool:
    expected = f"Bearer {config['auth_token']}"
    actual = handler.headers.get("Authorization", "")
    return actual == expected


def normalize_cli_args(payload: dict) -> list[str]:
    args: list[str] = []
    mapping = {
        "episode_topic": "--episode-topic",
        "queue_file": "--queue-file",
        "state_file": "--state-file",
        "log_file": "--log-file",
        "output_root": "--output-root",
        "build_script": "--build-script",
        "background": "--background",
        "channel_title": "--channel-title",
        "female_voice": "--female-voice",
        "male_voice": "--male-voice",
        "upload_script": "--upload-script",
        "channel_profile": "--channel-profile",
        "channel_config": "--channel-config",
        "token_file": "--token-file",
        "client_secrets": "--client-secrets",
        "upload_mode": "--upload-mode",
        "synthetic_media": "--synthetic-media",
        "reuse_build_from": "--reuse-build-from",
    }
    for key, flag in mapping.items():
        value = payload.get(key)
        if value not in (None, ""):
            args.extend([flag, str(value)])
    return args


class WorkerHandler(BaseHTTPRequestHandler):
    server_version = "BusinessEnglishWorker/1.0"

    def do_GET(self) -> None:
        config = load_config()
        if self.path == "/health":
            payload = {
                "status": "ok",
                "runner": str(RUNNER_PATH),
                "gemini_api_key_present": bool(os.environ.get("GEMINI_API_KEY")),
            }
            json_response(self, HTTPStatus.OK, payload)
            return

        json_response(self, HTTPStatus.NOT_FOUND, {"status": "error", "error": "Not found"})

    def do_POST(self) -> None:
        config = load_config()
        if not authorized(self, config):
            json_response(self, HTTPStatus.UNAUTHORIZED, {"status": "error", "error": "Unauthorized"})
            return

        if self.path != "/run-job":
            json_response(self, HTTPStatus.NOT_FOUND, {"status": "error", "error": "Not found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                json_response(self, HTTPStatus.BAD_REQUEST, {"status": "error", "error": f"Invalid JSON: {exc}"})
                return
        elif "application/x-www-form-urlencoded" in content_type:
            parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
            payload = {key: values[-1] for key, values in parsed.items()}
        else:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
                payload = {key: values[-1] for key, values in parsed.items()}

        command = [sys.executable, str(RUNNER_PATH), *normalize_cli_args(payload)]
        env = os.environ.copy()
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        response = {
            "status": "ok" if completed.returncode == 0 else "error",
            "returncode": completed.returncode,
            "command": command,
            "stdout": stdout[-12000:],
            "stderr": stderr[-4000:],
        }
        json_response(
            self,
            HTTPStatus.OK if completed.returncode == 0 else HTTPStatus.INTERNAL_SERVER_ERROR,
            response,
        )

    def log_message(self, format: str, *args) -> None:
        return


def main() -> int:
    config = load_config()
    server = ThreadingHTTPServer((config["host"], int(config["port"])), WorkerHandler)
    print(f"Worker listening on http://{config['host']}:{config['port']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
