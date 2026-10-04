"""Private browser profiles and per-account result paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil


DATA = Path("/data")
SHARE = Path("/share/china_mobile_10086")
LEGACY_PROFILE = DATA / "browser_profile"
PROFILES = DATA / "browser_profiles"
REGISTRY = DATA / "accounts.json"
RESULTS = SHARE / "accounts"
COMMANDS = SHARE / "commands"
RESPONSES = SHARE / "responses"
LEGACY_RESULT = SHARE / "account.json"
LEGACY_COMMAND = SHARE / "auth_command.json"
LEGACY_RESPONSE = SHARE / "auth_response.json"
HEARTBEAT = SHARE / "heartbeat"


def valid_account_id(account_id: object) -> bool:
    return isinstance(account_id, str) and (
        account_id == "legacy" or re.fullmatch(r"[0-9a-f]{16}", account_id) is not None
    )


def profile_path(account_id: str) -> Path:
    if not valid_account_id(account_id):
        raise ValueError("invalid account id")
    return LEGACY_PROFILE if account_id == "legacy" else PROFILES / account_id


def result_path(account_id: str) -> Path:
    if not valid_account_id(account_id):
        raise ValueError("invalid account id")
    return RESULTS / f"{account_id}.json"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def load_accounts() -> list[str]:
    try:
        saved = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = []
    accounts = [item for item in saved if valid_account_id(item)] if isinstance(saved, list) else []
    if LEGACY_PROFILE.exists() and "legacy" not in accounts:
        accounts.insert(0, "legacy")
    return list(dict.fromkeys(accounts))


def register_account(account_id: str) -> None:
    if not valid_account_id(account_id):
        raise ValueError("invalid account id")
    accounts = load_accounts()
    if account_id not in accounts:
        accounts.append(account_id)
    write_json(REGISTRY, accounts)


def forget_account(account_id: str) -> None:
    """Stop polling a removed entry and discard its saved login state."""
    if not valid_account_id(account_id):
        raise ValueError("invalid account id")
    write_json(REGISTRY, [item for item in load_accounts() if item != account_id])
    profile = profile_path(account_id)
    if profile.exists():
        shutil.rmtree(profile)
    result_path(account_id).unlink(missing_ok=True)
    if account_id == "legacy":
        LEGACY_RESULT.unlink(missing_ok=True)
