**Remote Worker**

This is the path to make the channel run with your laptop off:

1. Keep `n8n Cloud` as the scheduler.
2. Run the podcast worker on a VPS with Docker.
3. Let n8n call the worker over HTTPS.
4. The worker renders the episode and uploads it to YouTube directly from the VPS.

Official references:
- n8n confirms `Execute Command` is not available on n8n Cloud: [docs](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/)
- n8n self-hosting / Docker Compose: [docs](https://docs.n8n.io/hosting/installation/server-setups/docker-compose/)
- YouTube server-side OAuth can use a refresh token after the first auth flow: [docs](https://developers.google.com/youtube/v3/guides/moving_to_oauth)

**What To Put On The VPS**

- Clone or copy this project folder to the server.
- Put the YouTube OAuth files in `/app/secrets`:
  - `client_secrets_channel2.json`
  - `youtube_token_channel2.pickle`
- Copy `.env.worker.example` to `.env.worker` and fill the real values.

**Start The Worker**

From the project root:

```bash
cp automation/.env.worker.example automation/.env.worker
docker compose -f docker-compose.worker.yml up -d --build
```

Health check:

```bash
curl http://127.0.0.1:8777/health
```

If you expose it behind a domain, the n8n endpoint should be:

```text
https://your-worker-domain.example.com/run-job
```

**How n8n Should Call It**

Headers:

```text
Authorization: Bearer <WORKER_AUTH_TOKEN>
```

Minimal body:

```json
{
  "upload_mode": "private",
  "synthetic_media": "yes",
  "channel_profile": "channel2"
}
```

All other paths can stay inside the worker environment via `.env.worker`.

**Important**

- This is fully autonomous only if the VPS stays online.
- If Gemini daily TTS quota is exhausted, the worker will still fail that day. The automation is independent from your laptop, but not independent from API quota.
