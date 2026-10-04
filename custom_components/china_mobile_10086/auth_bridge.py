"""Short-lived local command exchange with the HAOS browser app."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import secrets
import time

from homeassistant.core import HomeAssistant


SHARE = Path("/share/china_mobile_10086")
COMMANDS = SHARE / "commands"
RESPONSES = SHARE / "responses"
HEARTBEAT = SHARE / "heartbeat"


def _submit(account_id: str, action: str, value: str) -> str | None:
    if re.fullmatch(r"legacy|[0-9a-f]{16}", account_id) is None:
        return None
    request_id = secrets.token_hex(16)
    command_path = COMMANDS / f"{request_id}.json"
    temporary = command_path.with_suffix(".tmp")
    try:
        if action != "forget" and time.time() - HEARTBEAT.stat().st_mtime > 15:
            return None
        COMMANDS.mkdir(parents=True, exist_ok=True)
        payload = {"id": request_id, "account_id": account_id, "action": action}
        if action in {"send_code", "verify"}:
            payload["phone" if action == "send_code" else "code"] = value
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(command_path)
        return request_id
    except OSError:
        temporary.unlink(missing_ok=True)
        return None


def _read_response(request_id: str) -> str | None:
    try:
        response_path = RESPONSES / f"{request_id}.json"
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if response.get("id") == request_id:
            response_path.unlink(missing_ok=True)
            return response.get("status")
    except (OSError, ValueError):
        pass
    return None


async def async_auth_command(
    hass: HomeAssistant, account_id: str, action: str, value: str
) -> str:
    request_id = await hass.async_add_executor_job(_submit, account_id, action, value)
    if request_id is None:
        return "app_not_running"
    for _ in range(90):
        status = await hass.async_add_executor_job(_read_response, request_id)
        if status is not None:
            return status
        await asyncio.sleep(0.5)
    return "app_timeout"


async def async_queue_forget(hass: HomeAssistant, account_id: str) -> None:
    """Queue account removal even when the app is temporarily stopped."""
    await hass.async_add_executor_job(_submit, account_id, "forget", "")
