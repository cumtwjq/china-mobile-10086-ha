"""Read-only client for the owner's China Mobile service account session."""

from __future__ import annotations

import json
import re
import ssl
import time
from typing import Any
from urllib.parse import urlsplit

from aiohttp import ClientSession, ClientTimeout
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


HOST = "wx.10086.cn"
PATHS = {
    "balance": "/website/fareBalance",
    "flow": "/website/personalHome/getNewFlow",
    "voice": "/website/personalHome/getNewVoice",
}
ALLOWED_HEADERS = {"accept", "accept-language", "cookie", "csrf-token", "referer", "user-agent"}
AES_KEY = b"1234123412ABCDEF"
AES_IV = b"ABCDEF1234123412"


def _mobile_ssl_context() -> ssl.SSLContext:
    """Permit the site's legacy TLS 1.2 cipher while verifying its certificate."""
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers("ECDHE+AESGCM:ECDHE-RSA-AES128-SHA:@SECLEVEL=1")
    return context


MOBILE_SSL_CONTEXT = _mobile_ssl_context()


class MobileAPIError(ValueError):
    """The server response or imported request is unusable."""


class MobileAuthError(MobileAPIError):
    """The owner's browser session was rejected."""


class MobileServiceUnavailableError(MobileAPIError):
    """China Mobile is temporarily serving its maintenance notice."""


def parse_capture(raw: str | dict[str, Any]) -> dict[str, Any]:
    """Keep only the verified read-only calls and their required headers."""
    try:
        capture = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(capture, dict) or capture.get("version") != 1:
            raise MobileAPIError("invalid capture version")
        requests = capture["requests"]
        normalized: dict[str, Any] = {"version": 1, "requests": {}}
        for kind, expected_path in PATHS.items():
            request = requests[kind]
            if request.get("method") != "GET":
                raise MobileAPIError("unexpected request method")
            parsed = urlsplit(request["url"])
            if (
                parsed.scheme != "https"
                or parsed.hostname != HOST
                or parsed.port not in (None, 443)
                or parsed.path != expected_path
                or parsed.username
                or parsed.password
                or (parsed.query and kind != "voice")
                or parsed.fragment
            ):
                raise MobileAPIError("unexpected request URL")
            source_headers = request["headers"]
            if not isinstance(source_headers, dict):
                raise MobileAPIError("invalid headers")
            headers = {
                str(key).lower(): str(value)
                for key, value in source_headers.items()
                if str(key).lower() in ALLOWED_HEADERS
            }
            if not headers.get("cookie") or not headers.get("csrf-token"):
                raise MobileAPIError("missing session credential")
            if len(json.dumps(headers)) > 65536:
                raise MobileAPIError("credential too large")
            normalized["requests"][kind] = {
                "method": "GET",
                "url": f"https://{HOST}{expected_path}",
                "headers": headers,
                "params": {"videoFlag": "1"} if kind == "voice" else {},
            }
        return normalized
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError, ValueError) as err:
        if isinstance(err, MobileAPIError):
            raise
        raise MobileAPIError("invalid capture") from err


def decrypt_response(ciphertext: str) -> dict[str, Any]:
    """Decode the site's AES-CBC hexadecimal response format."""
    if not isinstance(ciphertext, str) or not re.fullmatch(r"[0-9a-fA-F]+", ciphertext):
        raise MobileAPIError("unexpected response encoding")
    try:
        encrypted = bytes.fromhex(ciphertext)
        if not encrypted or len(encrypted) % 16:
            raise ValueError("invalid AES block count")
        decryptor = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV)).decryptor()
        padded = decryptor.update(encrypted) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()
        payload = json.loads(plaintext.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("not an object")
        return payload
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as err:
        raise MobileAPIError("unable to decode response") from err


async def _fetch(session: ClientSession, request: dict[str, Any]) -> dict[str, Any]:
    params = {**request.get("params", {}), "t": str(int(time.time() * 1000))}
    async with session.get(
        request["url"],
        headers=request["headers"],
        params=params,
        timeout=ClientTimeout(total=20),
        allow_redirects=False,
        ssl=MOBILE_SSL_CONTEXT,
    ) as response:
        if response.status in (301, 302, 303, 307, 308, 401, 403):
            raise MobileAuthError("session rejected")
        body = await response.text()
        if "升级公告" in body and "系统优化升级" in body:
            raise MobileServiceUnavailableError("China Mobile maintenance notice")
        response.raise_for_status()
        if response.content_type == "text/html":
            raise MobileAuthError("session returned a login page")
    return decrypt_response(body)


async def fetch_account(session: ClientSession, capture: dict[str, Any]) -> dict[str, Any]:
    """Fetch account allowance; never send account actions."""
    balance = await _fetch(session, capture["requests"]["balance"])
    flow = await _fetch(session, capture["requests"]["flow"])
    voice = await _fetch(session, capture["requests"]["voice"])
    balance_data = balance.get("data")
    flow_object = flow.get("object")
    voice_object = voice.get("object")
    if balance.get("status") != 0 or not isinstance(balance_data, dict) or not isinstance(balance_data.get("realFeeQryRsp"), dict):
        raise MobileAPIError("balance unavailable")
    if (
        flow.get("returnCode") != "0000"
        or not isinstance(flow_object, dict)
        or flow_object.get("resultCode") != "0000"
        or not isinstance(flow_object.get("resultData"), dict)
    ):
        raise MobileAPIError("flow allowance unavailable")
    if (
        voice.get("returnCode") != "0000"
        or not isinstance(voice_object, dict)
        or voice_object.get("resultCode") != "0000"
        or not isinstance(voice_object.get("resultData"), dict)
    ):
        raise MobileAPIError("voice allowance unavailable")
    return {
        "balance": balance_data["realFeeQryRsp"],
        "flow": flow_object["resultData"],
        "voice": voice_object["resultData"],
        "updated_at": flow_object.get("oprTime"),
    }
