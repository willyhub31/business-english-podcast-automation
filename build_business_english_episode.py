import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from urllib import error, request


API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TEXT_MODEL = "gemini-3-flash-preview"
TTS_MODEL = "gemini-3.1-flash-tts-preview"
DEFAULT_FEMALE_VOICE = "Sadachbia"
DEFAULT_MALE_VOICE = "Puck"
EXTRA_FEMALE_VOICE = "Sulafat"
EXTRA_MALE_VOICE = "Charon"
DEFAULT_EPISODE_TOPIC = "Sales Calls In English: Discovery To Close"
DEFAULT_CHANNEL_TITLE = "The English Pod Club"


@dataclass
class Section:
    title: str
    target_seconds: int
    brief: str
    mode: str = "hosts"
    cast: Tuple[str, ...] = ("Sophie", "Leo")


SECTIONS = [
    Section(
        title="Warm Open And Hook",
        target_seconds=32,
        brief=(
            "Open like real humans. Sophie starts with a playful check-in about Leo's day. "
            "Leo replies naturally. Then pivot into the episode topic and promise a practical win."
        ),
    ),
    Section(
        title="Today's Power Phrases",
        target_seconds=44,
        brief=(
            "Preview only three or four target Business English expressions for this episode. "
            "Keep the explanation short, clear, and easy to remember."
        ),
    ),
    Section(
        title="Live Situation One",
        target_seconds=62,
        brief=(
            "Sophie or Leo introduces a quick live situation. Then two extra actors perform a short, "
            "natural discovery-call scene. After the scene, Sophie and Leo return to explain useful phrases "
            "and one tactic."
        ),
        mode="scene",
        cast=("Sophie", "Leo", "Maya", "Daniel"),
    ),
    Section(
        title="Breakdown One",
        target_seconds=56,
        brief=(
            "Break down the first live situation. Explain only the most useful phrases, why they work, "
            "and give one simple plain-English paraphrase."
        ),
    ),
    Section(
        title="Live Situation Two",
        target_seconds=66,
        brief=(
            "A second quick live situation. Sophie or Leo tees it up, two extra actors perform a short "
            "price or timing objection scene, then Sophie and Leo return later to unpack the language and tactic."
        ),
        mode="scene",
        cast=("Sophie", "Leo", "Nina", "Marcus"),
    ),
    Section(
        title="Breakdown Two",
        target_seconds=56,
        brief=(
            "Break down the second live situation. Focus on the objection-handling language and one tactic "
            "the listener can reuse immediately."
        ),
    ),
    Section(
        title="Slow Replay And Practice",
        target_seconds=58,
        brief=(
            "Replay the key expressions in a slower practice-friendly way. Include a short repeat-after-me section "
            "with pauses and one mini recap."
        ),
    ),
    Section(
        title="Next Step Review And CTA",
        target_seconds=42,
        brief=(
            "End with a quick three-point review, a warm CTA, "
            "and a brief educational disclaimer."
        ),
    ),
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


def call_gemini(model: str, payload: dict, api_key: str) -> dict:
    url = f"{API_BASE}/{model}:generateContent"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error ({exc.code}): {details}") from exc


def extract_text(response_json: dict) -> str:
    try:
        parts = response_json["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Gemini text response: {response_json}") from exc

    text = "".join(part.get("text", "") for part in parts if "text" in part).strip()
    if not text:
        raise RuntimeError(f"Gemini returned no text: {response_json}")
    return normalize_text(text)


def extract_audio_bytes(response_json: dict) -> bytes:
    try:
        data = response_json["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Gemini audio response: {response_json}") from exc
    return base64.b64decode(data)


def try_extract_audio_bytes(response_json: dict) -> bytes | None:
    try:
        data = response_json["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError, TypeError):
        return None
    return base64.b64decode(data)


def ensure_speaker_lines(text: str, allowed_speakers: Tuple[str, ...]) -> List[str]:
    lines = []
    for raw_line in text.splitlines():
        line = normalize_text(raw_line.strip())
        if not line:
            continue
        if any(line.startswith(f"{speaker}:") for speaker in allowed_speakers):
            lines.append(line)
    if not lines:
        raise RuntimeError(f"No speaker lines found in transcript: {text}")
    return lines


def build_section_prompt(section: Section, previous_tail: str, episode_topic: str) -> str:
    cast_list = ", ".join(section.cast)
    if section.mode == "scene":
        return f"""Write one section of a YouTube Business English podcast that includes a short live situation.

Global show concept:
- Topic for this episode: {episode_topic}.
- Channel goal: teach Business English in a way that feels fun, human, practical, and easy to follow.
- The vibe should be lively like a modern English-learning podcast on YouTube: bright, friendly, motivating, and conversational.
- The full episode should feel structured and easy to study, not crowded.
- Allowed speakers for this section are only: {cast_list}.
- Sophie is the energetic female host and coach.
- Leo is the energetic male host and co-teacher.
- The extra actors are temporary characters inside the live situation.
- Every line must start with one of these names exactly: {cast_list}.
- No stage directions.
- No bullet points.
- No headings in the output.
- Keep the language natural for English learners.
- Keep each turn under about 12 seconds.
- Keep the scene compact and useful.

Section title:
{section.title}

Target duration:
About {section.target_seconds} seconds.

Section mission:
{section.brief}

Continuity from the previous section:
{previous_tail}

Required structure:
1. Sophie or Leo says something like "Let's listen to a quick real-world situation."
2. The two temporary actors do a short, realistic business conversation.
3. Sophie and Leo come back immediately and explain vocabulary, tactics, or why a line worked.
4. Make the scene fun, natural, and useful.
5. Keep the total number of guest-actor lines low so the section stays tight.

Extra requirements:
- Use at least one memorable phrase the audience can repeat later.
- Sophie should simplify one business phrase in plain English.
- The extra actors should sound like a believable workplace conversation, not a script exercise.
- Keep the explanation after the scene concise and study-friendly.

Output:
Only the speaker lines for this section.
"""

    return f"""Write one section of a two-host YouTube Business English podcast.

Global show concept:
- Topic for this episode: {episode_topic}.
- Channel goal: teach Business English in a way that feels fun, human, practical, and easy to follow.
- The vibe should be lively like a modern English-learning podcast on YouTube: bright, friendly, motivating, and conversational.
- The full episode should feel structured and easy to study, not crowded.
- The two hosts are:
  Sophie: energetic female coach, warm, funny in a light natural way, great at simplifying business English.
  Leo: energetic male co-host, sharp, calm, practical, and concise.
- Alternate turns naturally. Keep their speaking time balanced.
- Every line must start with either "Sophie:" or "Leo:".
- No stage directions.
- No bullet points.
- No headings in the output.
- Keep the language natural for English learners.
- Avoid corporate stiffness.
- Keep each turn under about 12 seconds.

Section title:
{section.title}

Target duration:
About {section.target_seconds} seconds.

Section mission:
{section.brief}

Continuity from the previous section:
{previous_tail}

Extra requirements:
- Use at least one memorable phrase the audience can repeat later.
- If you use business vocabulary, Sophie should sometimes explain it in simpler English.
- Make the conversation sound like real people talking, not a textbook.
- Keep momentum high.
- Keep the section tight. Do not over-explain.
- Stay focused on only a few target expressions, not too many.

Output:
Only the speaker lines for this section.
"""


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def write_text(path: Path, content: str) -> None:
    path.write_text(normalize_text(content).strip() + "\n", encoding="utf-8")


def save_wav(output_path: Path, pcm_data: bytes, sample_rate: int = 24000) -> None:
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)


def run_command(command: List[str]) -> None:
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


def render_mp3(wav_path: Path, mp3_path: Path) -> None:
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


def apply_speaker_tags(speaker: str, turn_index: int, content: str) -> str:
    if speaker == "Sophie":
        return f"{sophie_tags(turn_index, content)} {content}"
    if speaker == "Leo":
        return f"{leo_tags(turn_index, content)} {content}"
    return f"{guest_tags(turn_index, content)} {content}"


def build_dual_speaker_tts_prompt(
    section_title: str,
    section_lines: List[str],
    speaker_a: str,
    speaker_b: str,
) -> str:
    transcript = []
    for index, line in enumerate(section_lines):
        speaker, content = line.split(":", 1)
        speaker = speaker.strip()
        content = content.strip()
        content = apply_speaker_tags(speaker, index, content)
        if index == 0:
            content = f"[short pause] {content}"
        transcript.append(f"{speaker}: {content}")

    transcript_text = "\n".join(transcript)
    return f"""# AUDIO PROFILE

## {speaker_a}
{speaker_role_description(speaker_a)}

## {speaker_b}
{speaker_role_description(speaker_b)}

## SCENE
A polished YouTube Business English lesson-podcast recorded in a clean studio.
The tone is lively, warm, practical, and very listenable.

## DIRECTOR'S NOTES
- Section title: {section_title}
- Two speakers only: {speaker_a} and {speaker_b}.
- Keep the pace around 150 to 156 words per minute.
- Balanced speaking time.
- Alternate turns naturally.
- Use expressive audio tags, but keep them clean and believable.
- Use short pauses between teaching beats.
- Keep the delivery natural and distinct for both speakers.
- Make the delivery feel fun and human.
- No hype. No shouting.

## TRANSCRIPT
{transcript_text}
"""


def build_single_speaker_tts_prompt(
    section_title: str,
    speaker: str,
    content: str,
    role_description: str,
    tagged_line: str,
) -> str:
    return f"""# AUDIO PROFILE

## {speaker}
{role_description}

## SCENE
A polished YouTube Business English lesson-podcast recorded in a clean studio.
The tone is lively, warm, practical, and easy to follow.

## DIRECTOR'S NOTES
- Section title: {section_title}
- This is a single line from a larger podcast episode.
- Speak naturally, with believable energy and clean diction.
- Keep the delivery human and conversational.
- Do not say any speaker labels.

## TRANSCRIPT
{tagged_line}
"""


def build_single_speaker_fallback_prompt(
    section_title: str,
    role_description: str,
    content: str,
) -> str:
    return f"""Speak this line naturally for a YouTube Business English podcast.

Section: {section_title}
Speaker role: {role_description}
Tone: clear, natural, human, and easy to follow.

Text:
{content}
"""


def sophie_tags(turn_index: int, content: str) -> str:
    lowered = content.lower()
    if "repeat after me" in lowered:
        return "[encouragingly] [very clear] [short pause]"
    if "how was your day" in lowered or "doing today" in lowered:
        return "[warmly] [smiles] [brightly]"
    if "simple english" in lowered or "which means" in lowered or "in plain english" in lowered:
        return "[warmly] [very clear]"
    if "great" in lowered or "love that" in lowered:
        return "[brightly] [smiles]"
    defaults = [
        "[brightly] [encouragingly] [smiles]",
        "[warmly] [upbeat] [clear]",
        "[encouragingly] [very clear]",
    ]
    return defaults[turn_index % len(defaults)]


def leo_tags(turn_index: int, content: str) -> str:
    lowered = content.lower()
    if "today" in lowered or "roadmap" in lowered or "five-step" in lowered:
        return "[upbeat] [focused] [clear]"
    if "role-play" in lowered or "role play" in lowered:
        return "[thoughtfully] [short pause] [focused]"
    if "remember" in lowered or "recap" in lowered:
        return "[confidently] [clear] [measured]"
    defaults = [
        "[focused] [upbeat] [clear]",
        "[thoughtfully] [clear] [confidently]",
        "[confidently] [measured] [upbeat]",
    ]
    return defaults[turn_index % len(defaults)]


def guest_tags(turn_index: int, content: str) -> str:
    lowered = content.lower()
    if "too expensive" in lowered or "tight" in lowered:
        return "[thoughtfully] [serious]"
    if "happy to" in lowered or "sounds good" in lowered:
        return "[natural] [clear]"
    defaults = [
        "[natural] [clear]",
        "[thoughtfully] [measured]",
        "[upbeat] [clear]",
    ]
    return defaults[turn_index % len(defaults)]


def speaker_voice_map(female_voice: str, male_voice: str) -> Dict[str, str]:
    return {
        "Sophie": female_voice,
        "Leo": male_voice,
        "Maya": EXTRA_FEMALE_VOICE,
        "Nina": "Vindemiatrix",
        "Daniel": EXTRA_MALE_VOICE,
        "Marcus": "Iapetus",
    }


def speaker_role_description(speaker: str) -> str:
    roles = {
        "Sophie": "Energetic female English coach. Warm, bright, motivating, playful, and clear.",
        "Leo": "Energetic male co-host. Crisp, thoughtful, practical, upbeat, and grounded.",
        "Maya": "Female business professional in a realistic call situation. Natural, smart, calm, and friendly.",
        "Nina": "Female workplace professional in a realistic business call. Clear, practical, and natural.",
        "Daniel": "Male business professional in a realistic client call. Calm, informative, and believable.",
        "Marcus": "Male prospect in a realistic business call. Natural, thoughtful, and slightly cautious.",
    }
    return roles[speaker]


def speaker_tagged_line(speaker: str, turn_index: int, content: str) -> str:
    return apply_speaker_tags(speaker, turn_index, content)


def generate_section_transcript(
    api_key: str,
    section: Section,
    previous_tail: str,
    episode_topic: str,
) -> List[str]:
    response_json = call_gemini(
        TEXT_MODEL,
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": build_section_prompt(section, previous_tail, episode_topic),
                        }
                    ]
                }
            ]
        },
        api_key,
    )
    return ensure_speaker_lines(extract_text(response_json), section.cast)


def generate_single_speaker_audio(
    api_key: str,
    section_title: str,
    speaker: str,
    content: str,
    voice_name: str,
    turn_index: int,
) -> bytes:
    role_description = speaker_role_description(speaker)
    payloads = [
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": build_single_speaker_tts_prompt(
                                section_title,
                                speaker,
                                content,
                                role_description,
                                speaker_tagged_line(speaker, turn_index, content),
                            ),
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice_name}
                    }
                },
            },
        },
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": build_single_speaker_fallback_prompt(
                                section_title,
                                role_description,
                                content,
                            ),
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice_name}
                    }
                },
            },
        },
    ]

    last_response = None
    for payload in payloads:
        for attempt in range(3):
            response_json = call_gemini(TTS_MODEL, payload, api_key)
            last_response = response_json
            audio_bytes = try_extract_audio_bytes(response_json)
            if audio_bytes:
                return audio_bytes
            if attempt < 2:
                time.sleep(1.2)

    raise RuntimeError(f"Unexpected Gemini audio response after retries: {last_response}")


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def render_section_assets(
    api_key: str,
    section: Section,
    lines: List[str],
    section_prefix: str,
    section_dir: Path,
    female_voice: str,
    male_voice: str,
) -> Path:
    mp3_path = section_dir / f"{section_prefix}.mp3"

    if section.mode == "hosts":
        wav_path = section_dir / f"{section_prefix}.wav"
        pcm_audio = generate_dual_speaker_audio(
            api_key,
            section.title,
            lines,
            "Sophie",
            female_voice,
            "Leo",
            male_voice,
        )
        save_wav(wav_path, pcm_audio)
        render_mp3(wav_path, mp3_path)
        return mp3_path

    voice_map = speaker_voice_map(female_voice, male_voice)
    block_dir = section_dir / f"{section_prefix}_blocks"
    block_dir.mkdir(parents=True, exist_ok=True)
    block_mp3_paths = []

    for block_index, block_lines in enumerate(split_scene_audio_blocks(lines), start=1):
        block_speakers = ordered_unique_speakers(block_lines)
        wav_path = block_dir / f"{block_index:02d}.wav"
        block_mp3_path = block_dir / f"{block_index:02d}.mp3"

        if len(block_speakers) == 2:
            pcm_audio = generate_dual_speaker_audio(
                api_key,
                section.title,
                block_lines,
                block_speakers[0],
                voice_map[block_speakers[0]],
                block_speakers[1],
                voice_map[block_speakers[1]],
            )
        elif len(block_speakers) == 1:
            speaker = block_speakers[0]
            content = " ".join(line.split(":", 1)[1].strip() for line in block_lines)
            pcm_audio = generate_single_speaker_audio(
                api_key,
                section.title,
                speaker,
                content,
                voice_map[speaker],
                block_index - 1,
            )
        else:
            raise RuntimeError(f"Unsupported speaker mix for block: {block_lines}")

        save_wav(wav_path, pcm_audio)
        render_mp3(wav_path, block_mp3_path)
        block_mp3_paths.append(block_mp3_path)

    concat_audio(block_mp3_paths, mp3_path)
    return mp3_path


def ordered_unique_speakers(lines: List[str]) -> List[str]:
    speakers: List[str] = []
    for line in lines:
        speaker = line.split(":", 1)[0].strip()
        if speaker not in speakers:
            speakers.append(speaker)
    return speakers


def split_scene_audio_blocks(lines: List[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    current_block: List[str] = []
    current_kind: str | None = None

    for line in lines:
        speaker = line.split(":", 1)[0].strip()
        kind = "hosts" if speaker in {"Sophie", "Leo"} else "guests"
        if current_block and kind != current_kind:
            blocks.append(current_block)
            current_block = []
        current_block.append(line)
        current_kind = kind

    if current_block:
        blocks.append(current_block)

    return blocks


def generate_dual_speaker_audio(
    api_key: str,
    section_title: str,
    section_lines: List[str],
    speaker_a: str,
    voice_a: str,
    speaker_b: str,
    voice_b: str,
) -> bytes:
    response_json = call_gemini(
        TTS_MODEL,
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": build_dual_speaker_tts_prompt(
                                section_title,
                                section_lines,
                                speaker_a,
                                speaker_b,
                            ),
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "multiSpeakerVoiceConfig": {
                        "speakerVoiceConfigs": [
                            {
                                "speaker": speaker_a,
                                "voiceConfig": {
                                    "prebuiltVoiceConfig": {"voiceName": voice_a}
                                },
                            },
                            {
                                "speaker": speaker_b,
                                "voiceConfig": {
                                    "prebuiltVoiceConfig": {"voiceName": voice_b}
                                },
                            },
                        ]
                    }
                },
            },
        },
        api_key,
    )
    return extract_audio_bytes(response_json)


def seconds_to_srt(value: float) -> str:
    total_ms = int(round(value * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def seconds_to_ass(value: float) -> str:
    centis = int(round(value * 100))
    hours = centis // 360000
    minutes = (centis % 360000) // 6000
    seconds = (centis % 6000) // 100
    cs = centis % 100
    return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"


def seconds_to_clock(value: float) -> str:
    total = int(round(value))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def build_caption_entries(section_title: str, lines: List[str], start_time: float, section_duration: float):
    section_word_total = max(sum(word_count(line) for line in lines), 1)
    current = start_time
    entries = []

    for index, raw_line in enumerate(lines):
        speaker, content = raw_line.split(":", 1)
        content = content.strip()
        words = max(word_count(content), 1)
        duration = max(2.2, section_duration * (words / section_word_total))
        end_time = min(start_time + section_duration, current + duration)
        if index == len(lines) - 1:
            end_time = start_time + section_duration
        entries.append(
            {
                "kind": "line",
                "start": current,
                "end": max(current + 1.8, end_time),
                "text": content,
                "speaker": speaker,
            }
        )
        current = end_time
    return entries


def wrap_caption_text(text: str, max_chars: int = 58) -> str:
    text = sanitize_caption_text(text)
    words = text.split()
    lines = []
    current = []
    current_len = 0
    for word in words:
        projected = current_len + len(word) + (1 if current else 0)
        if current and projected > max_chars:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len = projected
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines[:3])


def sanitize_caption_text(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"\[(.*?)\]", "", text)
    text = text.replace("\\", "")
    text = text.replace("/", " ")
    text = text.replace("|", " ")
    text = text.replace(">>", "")
    text = text.replace("<<", "")
    text = text.replace("*", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def write_srt(path: Path, entries: list) -> None:
    blocks = []
    index = 1
    for entry in entries:
        if entry["kind"] != "line":
            continue
        blocks.append(
            f"{index}\n{seconds_to_srt(entry['start'])} --> {seconds_to_srt(entry['end'])}\n{wrap_caption_text(entry['text'])}\n"
        )
        index += 1
    write_text(path, "\n".join(blocks))


def write_ass(path: Path, entries: list) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: SophieCaption,Arial,48,&H00A8F6FF,&H000000FF,&H00000000,&H6B101820,-1,0,0,0,100,100,0,0,4,0,0,2,130,130,94,1
Style: LeoCaption,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H6B101820,-1,0,0,0,100,100,0,0,4,0,0,2,130,130,94,1
Style: Chapter,Arial,34,&H00F5D44A,&H000000FF,&H00000000,&H70101820,-1,0,0,0,100,100,0,0,4,0,0,8,90,90,92,1
Style: Caption,Arial,30,&H00FFFFFF,&H000000FF,&H00000000,&H40101820,-1,0,0,0,100,100,0,0,1,2.6,0,2,360,360,126,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for entry in entries:
        style = "Caption"
        content = wrap_caption_text(entry["text"]).replace("\n", r"\N").replace(",", r"\,")
        lines.append(
            f"Dialogue: 1,{seconds_to_ass(entry['start'])},{seconds_to_ass(entry['end'])},{style},,0,0,0,,{content}"
        )
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def concat_audio(section_mp3_paths: List[Path], output_mp3: Path) -> None:
    concat_file = output_mp3.with_suffix(".concat.txt")
    concat_lines = [f"file '{path.as_posix()}'" for path in section_mp3_paths]
    concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(output_mp3),
        ]
    )


def make_pingpong_background(background_path: Path, output_path: Path) -> None:
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(background_path),
            "-filter_complex",
            "[0:v]split[vf][vr];[vr]reverse[rev];[vf][rev]concat=n=2:v=1:a=0,scale=1920:1080,crop=1920:1080,format=yuv420p[v]",
            "-map",
            "[v]",
            "-an",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            str(output_path),
        ]
    )


def build_video_filter_script(path: Path, ass_path: Path, overlay_title: str) -> None:
    ass_filter_path = ass_path.as_posix().replace(":", r"\:")
    font_path = "C\\:/Windows/Fonts/arialbd.ttf"
    escaped_title = overlay_title.replace("'", r"\'")
    filter_script = f"""[0:v]scale=1920:1080,crop=1920:1080,format=yuv420p,
drawbox=x=310:y=905:w=1300:h=88:color=0A1625@0.18:t=fill,
drawbox=x=80:y=44:w=980:h=68:color=0A1625@0.44:t=fill,
drawtext=fontfile='{font_path}':text='{escaped_title}':fontcolor=white:fontsize=34:x=92:y=63,
subtitles='{ass_filter_path}'[v]
"""
    path.write_text(filter_script, encoding="utf-8")


def render_video(
    background_path: Path,
    audio_path: Path,
    ass_path: Path,
    output_path: Path,
    duration: float,
    overlay_title: str,
) -> None:
    filter_script = output_path.with_suffix(".filter.txt")
    build_video_filter_script(filter_script, ass_path, overlay_title)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(background_path),
            "-i",
            str(audio_path),
            "-filter_complex_script",
            str(filter_script),
            "-map",
            "[v]",
            "-map",
            "1:a:0",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]
    )


def write_youtube_files(
    output_dir: Path,
    section_starts: List[float],
    total_duration: float,
    full_lines: List[str],
    channel_title: str,
    episode_topic: str,
) -> None:
    title = f"{channel_title} | {episode_topic}"
    description_lines = [
        title,
        "",
        "Practice real Business English with Sophie and Leo.",
        f"This episode focuses on {episode_topic.lower()}.",
        "",
        "Timestamps",
    ]
    for start, section in zip(section_starts, SECTIONS):
        description_lines.append(f"{seconds_to_clock(start)} {section.title}")
    description_lines.extend(
        [
            "",
            "What you will learn",
            "- How to open a sales call naturally",
            "- Discovery questions that sound professional but human",
            "- Value and fit language without sounding pushy",
            "- Objection handling and next-step phrases",
            "",
            "Disclaimer",
            "This episode is for English-learning and general education only.",
            "",
            f"Total runtime: {seconds_to_clock(total_duration)}",
        ]
    )
    write_text(output_dir / "youtube_title.txt", title)
    write_text(output_dir / "youtube_description.txt", "\n".join(description_lines))
    write_text(output_dir / "full_transcript.txt", "\n".join(full_lines))
    write_text(
        output_dir / "channel_episode_template.txt",
        "\n".join(
            [
                f"{channel_title} Template",
                "",
                "1. Human hook and warm banter",
                "2. Today's 3-4 power phrases",
                "3. Live situation one",
                "4. Breakdown one",
                "5. Live situation two",
                "6. Breakdown two",
                "7. Slow replay and repeat-after-me practice",
                "8. Short review, CTA, and disclaimer",
                "",
                "Core rule: teach a few expressions deeply, not many expressions quickly.",
            ]
        ),
    )


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Build an 8-minute Business English podcast video.")
    parser.add_argument(
        "--output-dir",
        default=str(base_dir),
        help="Directory where the episode assets will be written.",
    )
    parser.add_argument(
        "--background",
        default=str(base_dir / "video background.mp4"),
        help="Background video path.",
    )
    parser.add_argument(
        "--female-voice",
        default=DEFAULT_FEMALE_VOICE,
        help="Gemini voice name for Sophie.",
    )
    parser.add_argument(
        "--male-voice",
        default=DEFAULT_MALE_VOICE,
        help="Gemini voice name for Leo.",
    )
    parser.add_argument(
        "--episode-topic",
        default=DEFAULT_EPISODE_TOPIC,
        help="Lesson focus used in prompts, metadata, and on-video title.",
    )
    parser.add_argument(
        "--channel-title",
        default=DEFAULT_CHANNEL_TITLE,
        help="Top-level channel/program title for metadata and on-video overlay.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set.", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    section_dir = output_dir / "episode_sections"
    section_dir.mkdir(parents=True, exist_ok=True)

    background_path = Path(args.background)
    pingpong_background = output_dir / "video_background_pingpong.mp4"
    full_audio_mp3 = output_dir / "business_english_episode_audio.mp3"
    srt_path = output_dir / "business_english_episode.srt"
    ass_path = output_dir / "business_english_episode.ass"
    final_video = output_dir / "business_english_episode.mp4"

    section_mp3_paths = []
    all_entries = []
    all_lines = []
    section_starts = []
    previous_tail = "This is the opening section."
    current_start = 0.0

    for index, section in enumerate(SECTIONS, start=1):
        lines = generate_section_transcript(api_key, section, previous_tail, args.episode_topic)
        all_lines.extend(lines)

        section_prefix = f"{index:02d}_{safe_slug(section.title)}"
        transcript_path = section_dir / f"{section_prefix}.txt"

        write_text(transcript_path, "\n".join(lines))
        mp3_path = render_section_assets(
            api_key,
            section,
            lines,
            section_prefix,
            section_dir,
            female_voice=args.female_voice,
            male_voice=args.male_voice,
        )

        section_duration = ffprobe_duration(mp3_path)
        section_starts.append(current_start)
        all_entries.extend(build_caption_entries(section.title, lines, current_start, section_duration))
        current_start += section_duration
        section_mp3_paths.append(mp3_path)
        previous_tail = "Continue smoothly from these last lines:\n" + "\n".join(lines[-2:])

    concat_audio(section_mp3_paths, full_audio_mp3)
    full_duration = ffprobe_duration(full_audio_mp3)
    write_srt(srt_path, all_entries)
    write_ass(ass_path, all_entries)
    write_youtube_files(
        output_dir,
        section_starts,
        full_duration,
        all_lines,
        args.channel_title,
        args.episode_topic,
    )
    make_pingpong_background(background_path, pingpong_background)
    render_video(
        pingpong_background,
        full_audio_mp3,
        ass_path,
        final_video,
        full_duration,
        f"{args.channel_title} - {args.episode_topic}",
    )

    print(f"Video: {final_video}")
    print(f"Audio: {full_audio_mp3}")
    print(f"SRT: {srt_path}")
    print(f"ASS: {ass_path}")
    print(f"Description: {output_dir / 'youtube_description.txt'}")
    print(f"Duration: {seconds_to_clock(full_duration)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
