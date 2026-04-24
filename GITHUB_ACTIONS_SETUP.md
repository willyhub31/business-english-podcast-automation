**GitHub Actions Setup**

This project can publish one Business English episode per day from GitHub Actions, without your laptop.

**What The Workflow Does**

- checks out the repo
- installs Python + ffmpeg
- restores YouTube OAuth files from GitHub Secrets
- runs [automation/run_daily_business_english_job.py](</F:/Workspaces/youtube/podcast english/automation/run_daily_business_english_job.py>)
- uploads the generated episode files as an Actions artifact
- commits the updated topic/state files back to the repo so the next day uses the next topic

Workflow file:
- [daily-business-english.yml](</F:/Workspaces/youtube/podcast english/.github/workflows/daily-business-english.yml>)
- [daily-channel-improvement.yml](</F:/Workspaces/youtube/podcast english/.github/workflows/daily-channel-improvement.yml>)

**Daily Improvement Workflow**

- runs a second scheduled GitHub Action focused on growth, not publishing
- scans your own latest uploads and basic channel stats
- discovers and monitors Business English competitors from [channel_improvement_config.json](</F:/Workspaces/youtube/podcast english/automation/channel_improvement_config.json>)
- writes:
  - [latest_report.md](</F:/Workspaces/youtube/podcast english/reports/channel-improvement/latest_report.md>)
  - [latest_report.json](</F:/Workspaces/youtube/podcast english/reports/channel-improvement/latest_report.json>)
- uploads the report as an artifact and commits report history back to the repo

**Required GitHub Secrets**

- `GEMINI_API_KEY`
- `YOUTUBE_TOKEN_PICKLE_B64`
- `YOUTUBE_CLIENT_SECRETS_JSON_B64`

Encode the local files to base64 before adding them as secrets:

Windows PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("F:\Workspaces\youtube\POV Shadow Systems\claude sonnet\tools\youtube_token_channel2.pickle"))
[Convert]::ToBase64String([IO.File]::ReadAllBytes("F:\Workspaces\youtube\POV Shadow Systems\claude sonnet\tools\client_secrets_channel2.json"))
```

**Recommended Repo Settings**

- Make the repo **public** if you want the best chance of staying inside GitHub’s free Actions limits.
- In `Actions > General`, allow workflows to have read/write repository contents permission.
- Keep the generated media out of git; the workflow already uploads it as an artifact.

**Schedule**

The workflow runs daily at:

- `07:17 UTC`
- `05:47 UTC` for the improvement report

That is roughly:

- `09:17` in France during CEST
- `08:17` in France during CET

Change the cron line in the workflow if you want another publish time.

**Important Limits**

- GitHub scheduled workflows can be delayed.
- GitHub-hosted runners are not production-grade video infrastructure.
- This is a strong v1 automation, not a guaranteed broadcaster.
