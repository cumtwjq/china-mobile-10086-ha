"""mitmproxy addon: collect only three owner-initiated, read-only 10086 calls."""

from __future__ import annotations

from datetime import datetime
import json
import os
from urllib.parse import urlsplit

from vault import VAULT, save_capture


PATHS = {
    "/website/fareBalance",
    "/website/personalHome/getNewFlow",
    "/website/personalHome/getNewVoice",
}
HEADERS = {"accept", "accept-language", "cookie", "csrf-token", "referer", "user-agent"}
READY_MARKER = VAULT.with_name("capture-ready.json")
captured: dict = {}
finished = False


def response(flow) -> None:
    global finished
    if finished:
        return
    request = flow.request
    reply = flow.response
    parsed = urlsplit(request.pretty_url)
    if (
        request.method != "GET"
        or parsed.scheme != "https"
        or parsed.hostname != "wx.10086.cn"
        or parsed.path not in PATHS
        or reply is None
        or reply.status_code != 200
    ):
        return
    body = reply.get_text(strict=False)
    if not body or len(body) % 32 or not all(ch in "0123456789abcdefABCDEF" for ch in body):
        return
    headers = {key: value for key, value in request.headers.items() if key.lower() in HEADERS}
    if not any(key.lower() == "cookie" and value for key, value in headers.items()):
        return
    if not any(key.lower() == "csrf-token" and value for key, value in headers.items()):
        return
    captured[parsed.path] = {
        "request": {
            "method": "GET",
            "url": request.pretty_url,
            "headers": headers,
        }
    }
    if len(captured) != len(PATHS):
        return
    save_capture(captured)
    READY_MARKER.write_text(
        json.dumps(
            {
                "session": os.environ.get("CHINA_MOBILE_CAPTURE_SESSION"),
                "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "capture_file_modified_ns": VAULT.stat().st_mtime_ns,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    finished = True
