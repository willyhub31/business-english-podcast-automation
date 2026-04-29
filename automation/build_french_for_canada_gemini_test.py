from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import wave
from datetime import datetime
from pathlib import Path
from urllib import error, request


API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TEXT_MODEL = "gemini-2.5-flash"
TTS_MODELS = [
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
]

TRANSCRIPT = [
    ("Sophie", "Salut Leo. Aujourd'hui, on va aider les nouveaux arrivants avec du vrai français pour le Canada."),
    ("Leo", "Oui. On va apprendre trois phrases utiles pour la vie quotidienne, surtout au Quebec et a Montreal."),
    ("Sophie", "Premiere phrase: je viens d'arriver au Canada. C'est simple, poli, et tres naturel."),
    ("Leo", "Deuxieme phrase: est-ce que vous pouvez parler un peu plus lentement, s'il vous plait? C'est tres utile quand quelqu'un parle vite."),
    ("Sophie", "Troisieme phrase: j'aimerais prendre rendez-vous. Tu peux l'utiliser pour la banque, le logement, ou une clinique."),
    ("Leo", "Petit dialogue. Bonjour, je viens d'arriver au Canada et je cherche un appartement."),
    ("Sophie", "Bien sur. Est-ce que vous pouvez parler un peu plus lentement, s'il vous plait? Je comprends, mais pas encore tout."),
    ("Leo", "Aucun probleme. Si vous voulez visiter, j'aimerais prendre rendez-vous pour demain apres-midi."),
    ("Sophie", "Tu vois? Ce n'est pas du francais scolaire. C'est du francais utile pour la vraie vie au Canada."),
    ("Leo", "Repete avec nous. Je viens d'arriver au Canada."),
    ("Sophie", "Est-ce que vous pouvez parler un peu plus lentement, s'il vous plait?"),
    ("Leo", "J'aimerais prendre rendez-vous."),
    ("Sophie", "Si tu veux, la prochaine fois on fera un dialogue pour le travail, le logement, et les papiers d'installation."),
]


def normalize_text(value: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def call_gemini(model: str, payload: dict, api_key: str) -> dict:
    url = f"{API_BASE}/{model}:generateContent"
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=240) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error for {model} ({exc.code}): {details}") from exc


def extract_audio_bytes(response_json: dict) -> bytes:
    try:
        data = response_json["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Gemini audio response: {response_json}") from exc
    return base64.b64decode(data)


def save_wav(output_path: Path, pcm_data: bytes, sample_rate: int = 24000) -> None:
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)


def run_command(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\nSTDOUT:\n"
            + completed.stdout
            + "\nSTDERR:\n"
            + completed.stderr
        )


def ffprobe_duration(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}:\n{completed.stderr}")
    return float(completed.stdout.strip())


def build_prompt() -> str:
    transcript_text = "\n".join(f"{speaker}: {line}" for speaker, line in TRANSCRIPT)
    return f"""# AUDIO PROFILE

## Sophie
Warm female podcast coach for French learners. Reassuring, energetic, clear, and expressive.

## Leo
Calm male podcast coach. Slightly analytical, grounded, friendly, and concise.

## THE SCENE
This is a practical French-learning podcast for people preparing for life in Canada. The tone is modern, human, warm, and easy to follow. The listeners are adult newcomers who want useful real-life French.

### DIRECTOR'S NOTES
Style:
- Natural podcast energy, not robotic.
- Friendly and confident, like two real co-hosts.
- Keep the performance easy for learners to understand.

Accent:
- Use clear French with a light Canadian French influence.
- Aim for a Montreal or Quebec French feel, but keep pronunciation accessible to international learners.
- Do not use exaggerated slang or heavy regional compression.

Pacing:
- Moderate pace for learners.
- Add small natural pauses between ideas.
- Keep repetition lines slightly slower and more deliberate.

### SAMPLE CONTEXT
Sophie and Leo are recording a short podcast lesson called "French for Canada". They want listeners to feel welcomed, capable, and ready to use a few important phrases in real life.

#### TRANSCRIPT
{transcript_text}
"""


def render_audio(api_key: str) -> tuple[bytes, str]:
    prompt = build_prompt()
    last_error: Exception | None = None
    for model in TTS_MODELS:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "multiSpeakerVoiceConfig": {
                        "speakerVoiceConfigs": [
                            {
                                "speaker": "Sophie",
                                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Sadachbia"}},
                            },
                            {
                                "speaker": "Leo",
                                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Puck"}},
                            },
                        ]
                    }
                },
            },
        }
        try:
            response_json = call_gemini(model, payload, api_key)
            return extract_audio_bytes(response_json), model
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    assert last_error is not None
    raise last_error


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def seconds_to_srt(value: float) -> str:
    total_ms = int(round(value * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def write_transcript(path: Path) -> None:
    path.write_text("\n".join(f"{speaker}: {line}" for speaker, line in TRANSCRIPT) + "\n", encoding="utf-8")


def write_srt(path: Path, duration: float) -> None:
    total_words = max(sum(word_count(text) for _, text in TRANSCRIPT), 1)
    current = 0.0
    blocks: list[str] = []
    for index, (_, text) in enumerate(TRANSCRIPT, start=1):
        words = max(word_count(text), 1)
        segment = max(2.1, duration * (words / total_words))
        end = min(duration, current + segment)
        if index == len(TRANSCRIPT):
            end = duration
        blocks.append(
            f"{index}\n{seconds_to_srt(current)} --> {seconds_to_srt(end)}\n{text}\n"
        )
        current = end
    path.write_text("\n".join(blocks), encoding="utf-8")


def build_video(background: Path, mp3_path: Path, srt_path: Path, mp4_path: Path, frame_path: Path) -> None:
    subtitle_path = srt_path.resolve().as_posix().replace(":", r"\:")
    run_command(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(background),
            "-i",
            str(mp3_path),
            "-vf",
            f"scale=1920:1080,crop=1920:1080,subtitles='{subtitle_path}'",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "21",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(mp4_path),
        ]
    )
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp4_path),
            "-vf",
            r"select=eq(n\,60)",
            "-vframes",
            "1",
            "-update",
            "1",
            str(frame_path),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="runs")
    parser.add_argument("--background", default="video background.mp4")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    base_dir = Path.cwd()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / args.output_root / f"{timestamp}_{slugify('french for canada gemini test')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    transcript_path = run_dir / "french_for_canada_gemini_test_transcript.txt"
    wav_path = run_dir / "french_for_canada_gemini_test.wav"
    mp3_path = run_dir / "french_for_canada_gemini_test.mp3"
    srt_path = run_dir / "french_for_canada_gemini_test.srt"
    mp4_path = run_dir / "french_for_canada_gemini_test.mp4"
    frame_path = run_dir / "french_for_canada_gemini_test_frame.png"
    summary_path = run_dir / "build_summary.json"

    pcm_audio, model_used = render_audio(api_key)
    save_wav(wav_path, pcm_audio)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(wav_path),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(mp3_path),
        ]
    )

    write_transcript(transcript_path)
    duration = ffprobe_duration(mp3_path)
    write_srt(srt_path, duration)

    background = (base_dir / args.background).resolve()
    if background.exists():
        build_video(background, mp3_path, srt_path, mp4_path, frame_path)

    summary = {
        "model_used": model_used,
        "transcript": str(transcript_path),
        "wav": str(wav_path),
        "mp3": str(mp3_path),
        "srt": str(srt_path),
        "mp4": str(mp4_path if mp4_path.exists() else ""),
        "frame": str(frame_path if frame_path.exists() else ""),
        "duration_seconds": duration,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
