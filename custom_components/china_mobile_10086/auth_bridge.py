"""Short-lived local command exchange with the HAOS browser app."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import secrets
import time

from homeassistant.core import HomeAssistant


SHARE = Path("/share/china_mobile_10086")
COMMAND = SHARE / "auth_command.json"
RESPONSE = SHARE / "auth_response.json"
HEARTBEAT = SHARE / "heartbeat"


def _submit(action: str, value: str) -> str | None:
    temporary = COMMAND.with_suffix(".tmp")
    try:
        if time.time() - HEARTBEAT.stat().st_mtime > 15:
            return None
        request_id = secrets.token_hex(16)
        payload = {"id": request_id, "action": action}
        payload["phone" if action == "send_code" else "code"] = value
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(COMMAND)
        return request_id
    except OSError:
        temporary.unlink(missing_ok=True)
        return None


def _read_response(request_id: str) -> str | None:
    try:
        response = json.loads(RESPONSE.read_text(encoding="utf-8"))
        if response.get("id") == request_id:
            RESPONSE.unlink(missing_ok=True)
            return response.get("status")
    except (OSError, ValueError):
        pass
    return None


async def async_auth_command(hass: HomeAssistant, action: str, value: str) -> str:
    request_id = await hass.async_add_executor_job(_submit, action, value)
    if request_id is None:
        return "app_not_running"
    for _ in range(90):
        status = await hass.async_add_executor_job(_read_response, request_id)
        if status is not None:
            return status
        await asyncio.sleep(0.5)
    return "app_timeout"
