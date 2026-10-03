"""Copy only three verified read-only request templates for HA import."""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from clipboard import copy_to_clipboard
from vault import load_capture


PATHS = {
    "balance": "/website/fareBalance",
    "flow": "/website/personalHome/getNewFlow",
    "voice": "/website/personalHome/getNewVoice",
}
HEADERS = {"accept", "accept-language", "cookie", "csrf-token", "referer", "user-agent"}


def make_import(captured: dict) -> dict:
    result = {"version": 1, "requests": {}}
    for name, path in PATHS.items():
        source = captured[path]["request"]
        url = urlsplit(source["url"])
        if source["method"] != "GET" or url.scheme != "https" or url.hostname != "wx.10086.cn" or url.path != path:
            raise ValueError(f"缺少有效的 {name} 请求")
        headers = {key.lower(): value for key, value in source["headers"].items() if key.lower() in HEADERS}
        if not headers.get("cookie") or not headers.get("csrf-token"):
            raise ValueError(f"{name} 请求缺少登录信息")
        result["requests"][name] = {
            "method": "GET",
            "url": f"https://wx.10086.cn{path}",
            "headers": headers,
        }
    return result


def main() -> None:
    exported = make_import(load_capture())
    copy_to_clipboard(json.dumps(exported, ensure_ascii=False, separators=(",", ":")))
    print("已将中国移动只读请求复制到剪贴板。请直接粘贴到 HA 配置页，不要发到聊天中。")


if __name__ == "__main__":
    main()
