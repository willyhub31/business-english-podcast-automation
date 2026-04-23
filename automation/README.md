# Business English Podcast Automation

This folder contains the daily n8n automation package for the Business English podcast workflow.

## Files

- `run_daily_business_english_job.py`
  Single entrypoint for n8n. It picks the next topic, runs the episode builder, verifies outputs, and optionally uploads to YouTube.
- `business_english_topics.txt`
  Ordered topic queue. The wrapper advances through this list via `automation_state.json`.
- `automation_state.json`
  Stores the next topic index and the last successful run details.
- `automation_history.jsonl`
  Append-only run log. Created automatically.
- `n8n_business_english_daily_publish.json`
  Main daily n8n workflow. Manual + scheduled trigger, then one Execute Command node.
- `n8n_business_english_smoketest.json`
  Manual smoke-test workflow. Reuses an existing built episode and checks YouTube auth without spending Gemini TTS quota.

## Required Host Setup

Set `GEMINI_API_KEY` in the environment of the machine that runs n8n.

The daily workflow command expects:

- Python available as `python`
- `ffmpeg` and `ffprobe` on PATH
- access to:
  - `F:\Workspaces\youtube\podcast english\build_business_english_episode.py`
  - `F:\Workspaces\youtube\POV Shadow Systems\claude sonnet\tools\upload_to_youtube.py`

## n8n Import

Import one of these JSON files into n8n:

- Daily production: `n8n_business_english_daily_publish.json`
- Manual smoke test: `n8n_business_english_smoketest.json`

The daily workflow is scheduled for **09:00 Europe/Paris** and uploads as **private** using `channel2`.

## Tested Paths

Confirmed working:

- wrapper script CLI
- output verification against the existing built episode
- YouTube auth check for `channel2`
- n8n workflow JSON validation

Blocked by external quota during fresh render test:

- Gemini `gemini-3.1-flash-tts` daily request quota returned HTTP `429`

## Quota Note

The builder was optimized to reduce TTS calls in live-situation sections by rendering contiguous two-speaker blocks instead of one TTS request per line. This lowers daily quota pressure materially for a single full episode run.
