# French for Canada Podcast

This workspace is now focused on French-learning podcast videos for people preparing for life in Canada.

Current positioning:

- practical French for Canada
- Quebec and Montreal-style daily situations
- newcomer vocabulary for housing, work, health, appointments, and TEF-style speaking/listening
- podcast scenes with Sophie, Leo, and guest role-play actors

## Folder Layout

- `automation/` - builders, YouTube helpers, and workflow scripts
- `branding/` - channel art, logo, watermark, and thumbnail assets
- `runs/` - generated test episodes and output files
- `video/` - source background videos
- `reports/` - channel improvement reports
- `archive/business-english-legacy/` - old Business English renders and assets kept for reference

## Current Long Test

Main builder:

- `automation/build_french_for_canada_long_episode.py`

Default background:

- `video/download.mp4`

Run locally:

```powershell
$env:GEMINI_API_KEY="YOUR_KEY"
python "automation/build_french_for_canada_long_episode.py" --background "video/download.mp4"
```

The builder creates:

- MP3 audio
- MP4 video
- SRT captions
- ASS burned-caption style
- transcript
- YouTube title and description drafts
- preview frame

## Legacy Note

Some old automation files still reference Business English. They are left in place until the daily cloud publishing workflow is rebuilt for the French-for-Canada niche.
