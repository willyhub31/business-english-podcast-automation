# Business English Podcast Automation

This repository generates and uploads one Business English podcast-style YouTube video per day.

It includes:

- a Gemini-based episode builder
- a GitHub Actions daily publishing workflow
- YouTube upload automation
- topic rotation state so each run advances to the next lesson

Main workflow:

- [daily-business-english.yml](./.github/workflows/daily-business-english.yml)

Setup guide:

- [GITHUB_ACTIONS_SETUP.md](./GITHUB_ACTIONS_SETUP.md)

Core scripts:

- [build_business_english_episode.py](./build_business_english_episode.py)
- [automation/run_daily_business_english_job.py](./automation/run_daily_business_english_job.py)

Important:

- Add the required GitHub Secrets before enabling the schedule.
- The workflow generates its own simple background video on the runner, so the local MP4 background is not required in the repo.
