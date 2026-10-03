"""Persistent Chromium session and read-only periodic China Mobile queries."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from mobile_parser import decode_response, extract_sensors


LOGIN_URL = "https://wx.10086.cn/website/bind/bindAccount/new"
HOME_URL = "https://wx.10086.cn/website/spa/main/newHome"
PROFILE = Path("/data/browser_profile")
OUTPUT = Path("/share/china_mobile_10086/account.json")
COMMAND = Path("/share/china_mobile_10086/auth_command.json")
RESPONSE = Path("/share/china_mobile_10086/auth_response.json")
HEARTBEAT = Path("/share/china_mobile_10086/heartbeat")
INTERVAL_SECONDS = 30 * 60
API_NAMES = (
    "getNewMarginInfo",
    "fareBalance",
    "accountFeeBalanceQuery",
)
LOG = logging.getLogger("china_mobile_browser")


def write_status(status: str, sensors: dict[str, float] | None = None) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": 2,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sensors": sensors or {},
    }
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(OUTPUT)


def write_auth_response(request_id: str, status: str) -> None:
    temporary = RESPONSE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"id": request_id, "status": status}), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(RESPONSE)


async def handle_auth_command(page: Any) -> str | None:
    if not COMMAND.exists():
        return None
    try:
        command = json.loads(COMMAND.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        COMMAND.unlink(missing_ok=True)
        return None
    COMMAND.unlink(missing_ok=True)
    request_id = command.get("id", "")
    status = "login_failed"
    try:
        if command.get("action") == "send_code":
            phone = command.get("phone", "")
            if not (isinstance(phone, str) and len(phone) == 11 and phone.isdigit()):
                status = "invalid_phone"
            else:
                await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                await page.locator("#phone").fill(phone, timeout=10000)
                checkbox = page.locator(".checkCtl.noCheck")
                if await checkbox.count():
                    await checkbox.first.click()
                clicked = await page.evaluate("""() => {
                    const nodes = [...document.querySelectorAll('button, a, span, div')];
                    const target = nodes.find(e => e.offsetWidth > 0 &&
                        ['获取验证码', '发送验证码'].includes((e.innerText || '').trim()) &&
                        e.children.length < 3);
                    if (!target) return false;
                    target.click();
                    return true;
                }""")
                await page.wait_for_timeout(1500)
                code_box = page.locator("#code")
                error_hint = await code_box.get_attribute("placeholder") if await code_box.count() else None
                if error_hint and any(word in error_hint for word in ("频繁", "过多", "稍后", "失败")):
                    status = "send_failed"
                else:
                    status = "sent" if clicked else "manual_required"
        elif command.get("action") == "verify":
            code = command.get("code", "")
            if not (isinstance(code, str) and code.isdigit() and 4 <= len(code) <= 8):
                status = "invalid_code"
            else:
                await page.locator("#code").fill(code, timeout=10000)
                await page.locator("#loginBtn").click(timeout=10000)
                for _ in range(20):
                    await page.wait_for_timeout(1000)
                    if not await login_page(page) and not await upgrade_notice(page):
                        text = await page.locator("body").inner_text(timeout=3000)
                        if any(word in text for word in ("话费余额", "余额", "套餐", "余量")):
                            status = "success"
                            write_status("authenticating")
                            break
    except PlaywrightError:
        status = "login_failed"
    finally:
        # Never log or retain the phone number or SMS code.
        command.clear()
        if request_id:
            write_auth_response(request_id, status)
    return status


async def login_page(page: Any) -> bool:
    url = page.url
    if "/bind/" in url or "login" in url.lower():
        try:
            return await page.locator("#phone").count() > 0
        except PlaywrightError:
            return True
    try:
        text = await page.locator("body").inner_text(timeout=3000)
    except PlaywrightError:
        return False
    return "获取验证码" in text and "手机号" in text and "话费余额" not in text


async def upgrade_notice(page: Any) -> bool:
    try:
        text = await page.locator("body").inner_text(timeout=3000)
    except PlaywrightError:
        return False
    return "系统优化升级" in text or "升级公告" in text


async def query(page: Any) -> dict[str, float] | None:
    """Navigate the logged-in browser, letting its own page issue account APIs."""
    responses: dict[str, dict[str, Any]] = {}
    pending: set[asyncio.Task] = set()

    async def capture(response: Any) -> None:
        name = next((name for name in API_NAMES if name in response.url), None)
        if name is None or response.status != 200:
            return
        try:
            body = await response.text()
            parsed = decode_response(body)
            if parsed is not None:
                responses[name] = parsed
        except PlaywrightError:
            pass

    def on_response(response: Any) -> None:
        task = asyncio.create_task(capture(response))
        pending.add(task)
        task.add_done_callback(pending.discard)

    page.on("response", on_response)
    try:
        await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(8000)
        if pending:
            await asyncio.wait(pending, timeout=10)
        if await login_page(page):
            return None
        if await upgrade_notice(page):
            return {}
        sensors = extract_sensors(responses)
        return sensors if sensors else {}
    finally:
        page.remove_listener("response", on_response)


async def run() -> None:
    write_status("starting")
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(PROFILE),
            headless=False,
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        last_query = 0.0
        auth_deadline = 0.0
        try:
            while True:
                try:
                    HEARTBEAT.touch()
                    auth_result = await handle_auth_command(page)
                    if auth_result in {"sent", "manual_required"}:
                        auth_deadline = time.monotonic() + 5 * 60
                        write_status("authenticating")
                    elif auth_result == "success":
                        auth_deadline = 0.0
                        last_query = 0.0
                    # Never navigate away while the user is entering an SMS code.
                    if await login_page(page):
                        if time.monotonic() >= auth_deadline:
                            write_status("login_required")
                        last_query = 0.0
                        await asyncio.sleep(1)
                        continue
                    if last_query == 0.0 or time.monotonic() - last_query >= INTERVAL_SECONDS:
                        sensors = await query(page)
                        if sensors is None:
                            auth_deadline = 0.0
                            write_status("login_required")
                            if not await login_page(page):
                                await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                            LOG.info("Official login page is ready in the app browser")
                        elif sensors:
                            write_status("ok", sensors)
                            LOG.info("Account values updated: %d sensors", len(sensors))
                            last_query = time.monotonic()
                        else:
                            write_status("query_failed")
                            LOG.warning("Account page returned no recognized values")
                            last_query = time.monotonic()
                    await asyncio.sleep(1)
                except PlaywrightError as err:
                    write_status("query_failed")
                    LOG.warning("Browser query failed: %s", type(err).__name__)
                    await asyncio.sleep(60)
        finally:
            await context.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run())
