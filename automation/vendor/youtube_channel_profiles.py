import json
from pathlib import Path


DEFAULT_CONFIG_NAME = "youtube_channel_profiles.json"


def _clean_optional(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_path(script_dir: Path, value):
    cleaned = _clean_optional(value)
    if not cleaned:
        return None
    path = Path(cleaned)
    if not path.is_absolute():
        path = (script_dir / path).resolve()
    return path


def load_channel_profiles(script_dir: Path, config_path=None):
    config_file = Path(config_path) if config_path else script_dir / DEFAULT_CONFIG_NAME
    if not config_file.exists():
        return {"default_profile": None, "profiles": {}}, config_file

    data = json.loads(config_file.read_text(encoding="utf-8"))
    if "profiles" not in data:
        data["profiles"] = {}
    return data, config_file


def resolve_channel_settings(
    script_dir: Path,
    profile_name=None,
    config_path=None,
    token_file=None,
    client_secrets=None,
    expected_channel_name=None,
    expected_channel_id=None,
    default_token_name="youtube_token_pov_shadow_systems.pickle",
    default_client_secrets_name="client_secrets.json",
    default_expected_channel_id=None,
):
    config, config_file = load_channel_profiles(script_dir, config_path)
    active_profile = _clean_optional(profile_name) or _clean_optional(config.get("default_profile"))

    profile = {}
    if active_profile:
        profiles = config.get("profiles", {})
        if active_profile not in profiles:
            available = ", ".join(sorted(profiles.keys())) or "(none)"
            raise ValueError(
                f"Unknown channel profile '{active_profile}'. "
                f"Available profiles in {config_file.name}: {available}"
            )
        profile = profiles.get(active_profile, {})

    resolved_token = (
        _resolve_path(script_dir, token_file)
        or _resolve_path(script_dir, profile.get("token_file"))
        or (script_dir / default_token_name)
    )
    resolved_client_secrets = (
        _resolve_path(script_dir, client_secrets)
        or _resolve_path(script_dir, profile.get("client_secrets"))
        or (script_dir / default_client_secrets_name)
    )
    resolved_expected_name = (
        _clean_optional(expected_channel_name)
        or _clean_optional(profile.get("expected_channel_name"))
    )
    resolved_expected_id = (
        _clean_optional(expected_channel_id)
        or _clean_optional(profile.get("expected_channel_id"))
        or (_clean_optional(default_expected_channel_id) if not active_profile else None)
    )

    return {
        "profile_name": active_profile,
        "config_file": config_file,
        "token_file": resolved_token,
        "client_secrets": resolved_client_secrets,
        "expected_channel_name": resolved_expected_name,
        "expected_channel_id": resolved_expected_id,
    }
