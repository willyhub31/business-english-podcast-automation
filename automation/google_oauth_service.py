from __future__ import annotations

import pickle
from pathlib import Path

import google_auth_oauthlib.flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def build_authenticated_service(
    *,
    token_file: str | Path,
    client_secrets_file: str | Path,
    api_service_name: str,
    api_version: str,
    scopes: list[str],
    port: int = 8080,
):
    token_path = Path(token_file)
    client_secrets_path = Path(client_secrets_file)
    credentials = None

    if token_path.exists():
        with token_path.open("rb") as handle:
            credentials = pickle.load(handle)

    needs_auth = (
        not credentials
        or not credentials.valid
        or not getattr(credentials, "has_scopes", lambda _: False)(scopes)
    )

    if needs_auth:
        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
            and getattr(credentials, "has_scopes", lambda _: False)(scopes)
        ):
            credentials.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path),
                scopes,
            )
            credentials = flow.run_local_server(port=port)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        with token_path.open("wb") as handle:
            pickle.dump(credentials, handle)

    return build(api_service_name, api_version, credentials=credentials)
