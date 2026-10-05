"""Persistent Chromium session and read-only periodic China Mobile queries."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from account_store import (
    COMMANDS, HEARTBEAT, LEGACY_COMMAND, LEGACY_RESPONSE, LEGACY_RESULT,
    RESPONSES, forget_account, load_accounts, profile_path, register_account, result_path,
    valid_account_id, write_json,
)
from mobile_parser import balance_for_display, decode_response, extract_sensors


LOGIN_URL = "https://wx.10086.cn/website/bind/bindAccount/new"
HOME_URL = "https://wx.10086.cn/website/spa/main/newHome"
INTERVAL_SECONDS = 30 * 60
RETRY_SECONDS = 5 * 60
QUERY_ATTEMPTS = 3
API_NAMES = (
    "getNewMarginInfo",
    "fareBalance",
    "accountFeeBalanceQuery",
)
LOG = logging.getLogger("china_mobile_browser")


def write_status(
    account_id: str, status: str, sensors: dict[str, float] | None = None
) -> None:
    payload: dict[str, Any] = {
        "version": 2,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sensors": sensors or {},
    }
    write_json(result_path(account_id), payload)
    if account_id == "legacy":
        # Keep the 0.2.x integration working while its files are being upgraded.
        write_json(LEGACY_RESULT, payload)


def previous_sensor_keys(account_id: str) -> set[str]:
    """Use the last complete result to spot a partially loaded page after restart."""
    try:
        payload = json.loads(result_path(account_id).read_text(encoding="utf-8"))
        sensors = payload.get("sensors")
        if payload.get("status") == "ok" and isinstance(sensors, dict):
            return {key for key in sensors if isinstance(key, str)}
    except (AttributeError, OSError, ValueError, TypeError):
        pass
    return set()


def write_auth_response(request_id: str, status: str, legacy: bool) -> None:
    if not isinstance(request_id, str) or re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
        return
    target = LEGACY_RESPONSE if legacy else RESPONSES / f"{request_id}.json"
    write_json(target, {"id": request_id, "status": status})


async def handle_auth_command(
    page: Any, account_id: str, command: dict[str, Any], legacy: bool
) -> str:
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
                            write_status(account_id, "authenticating")
                            break
    except PlaywrightError:
        status = "login_failed"
    finally:
        # Never log or retain the phone number or SMS code.
        command.clear()
        if request_id and status != "success":
            write_auth_response(request_id, status, legacy)
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


async def query(page: Any, expected_keys: set[str] | None = None) -> dict[str, float] | None:
    """Navigate the logged-in browser, letting its own page issue account APIs."""
    responses: dict[str, dict[str, Any]] = {}
    pending: set[asyncio.Task] = set()
    expected_keys = expected_keys or set()
    generation = 0

    async def capture(response: Any, response_generation: int) -> None:
        name = next((name for name in API_NAMES if name in response.url), None)
        if name is None or response.status != 200:
            return
        try:
            body = await response.text()
            parsed = decode_response(body)
            if parsed is not None and response_generation == generation:
                responses[name] = parsed
        except PlaywrightError:
            pass

    def on_response(response: Any) -> None:
        task = asyncio.create_task(capture(response, generation))
        pending.add(task)
        task.add_done_callback(pending.discard)

    page.on("response", on_response)
    try:
        for attempt in range(QUERY_ATTEMPTS):
            generation += 1
            responses.clear()
            if attempt == 0:
                await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=30000)
            else:
                await page.reload(wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(8000)
            if pending:
                await asyncio.wait(set(pending), timeout=10)
            if await login_page(page):
                return None
            if await upgrade_notice(page):
                return {}

            async def read_snapshot() -> tuple[dict[str, float], str]:
                sensors = extract_sensors(responses)
                try:
                    page_text = await page.locator("body").inner_text(timeout=3000)
                except PlaywrightError:
                    page_text = ""
                api_balance = sensors.get("balance")
                displayed_balance = balance_for_display(api_balance, page_text)
                if displayed_balance is not None:
                    if api_balance is not None and api_balance != displayed_balance:
                        LOG.info("Visible balance differs from API amount; using visible balance")
                    sensors["balance"] = displayed_balance
                return sensors, page_text

            sensors, page_text = await read_snapshot()
            if "点击刷新" in page_text:
                refresh = page.get_by_text("点击刷新")
                try:
                    if await refresh.count():
                        await refresh.first.click(timeout=3000)
                        await page.wait_for_timeout(5000)
                        if pending:
                            await asyncio.wait(set(pending), timeout=10)
                        sensors, page_text = await read_snapshot()
                except PlaywrightError:
                    LOG.info("Page refresh control could not be clicked")

            missing = expected_keys - sensors.keys()
            if sensors and "点击刷新" not in page_text and not missing:
                return sensors
            LOG.warning(
                "Account page incomplete on attempt %d/%d: refresh=%s missing=%s",
                attempt + 1, QUERY_ATTEMPTS, "点击刷新" in page_text,
                sorted(missing),
            )
        return {}
    finally:
        page.remove_listener("response", on_response)
        remaining = tuple(pending)
        for task in remaining:
            task.cancel()
        if remaining:
            await asyncio.gather(*remaining, return_exceptions=True)


def next_command() -> tuple[dict[str, Any], bool] | None:
    """Consume one command without retaining an SMS code in the shared folder."""
    candidates = [LEGACY_COMMAND] if LEGACY_COMMAND.exists() else []
    candidates.extend(sorted(COMMANDS.glob("*.json")))
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
            continue
        path.unlink(missing_ok=True)
        if isinstance(payload, dict):
            return payload, path == LEGACY_COMMAND
    return None


class BrowserManager:
    """Keep one persistent Chromium context open for each account."""

    def __init__(self, playwright: Any) -> None:
        self.playwright = playwright
        self.contexts: dict[str, Any] = {}
        self.pages: dict[str, Any] = {}

    async def activate(self, account_id: str) -> Any:
        if account_id in self.pages:
            page = self.pages[account_id]
            try:
                await page.bring_to_front()
            except PlaywrightError:
                LOG.warning("Could not switch visible browser window for account %s", account_id)
            return page
        profile = profile_path(account_id)
        profile.mkdir(parents=True, exist_ok=True)
        profile.chmod(0o700)
        context = await self.playwright.chromium.launch_persistent_context(
            str(profile),
            headless=False,
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        self.contexts[account_id] = context
        self.pages[account_id] = page
        try:
            await page.bring_to_front()
        except PlaywrightError:
            LOG.warning("Could not show browser window for account %s", account_id)
        return page

    async def close(self) -> None:
        for context in self.contexts.values():
            await context.close()
        self.contexts.clear()
        self.pages.clear()

    async def close_account(self, account_id: str) -> None:
        context = self.contexts.pop(account_id, None)
        self.pages.pop(account_id, None)
        if context is not None:
            await context.close()


async def run() -> None:
    accounts = load_accounts()
    next_query: dict[str, float] = {account_id: 0.0 for account_id in accounts}
    known_keys: dict[str, set[str]] = {
        account_id: previous_sensor_keys(account_id) for account_id in accounts
    }
    for account_id in accounts:
        write_status(account_id, "starting")

    async with async_playwright() as playwright:
        browser = BrowserManager(playwright)
        auth_account: str | None = None
        auth_deadline = 0.0
        try:
            while True:
                HEARTBEAT.touch()
                incoming = next_command()
                if incoming is not None:
                    command, legacy = incoming
                    account_id = "legacy" if legacy else command.get("account_id")
                    request_id = command.get("id", "")
                    if not valid_account_id(account_id):
                        write_auth_response(request_id, "invalid_account", legacy)
                    elif command.get("action") == "forget":
                        try:
                            await browser.close_account(account_id)
                            forget_account(account_id)
                            accounts = [item for item in accounts if item != account_id]
                            next_query.pop(account_id, None)
                            known_keys.pop(account_id, None)
                            if auth_account == account_id:
                                auth_account = None
                        except OSError:
                            LOG.warning("Could not remove browser data for account %s", account_id)
                    elif (
                        auth_account is not None
                        and auth_account != account_id
                        and time.monotonic() < auth_deadline
                    ):
                        write_auth_response(request_id, "browser_busy", legacy)
                    else:
                        try:
                            page = await browser.activate(account_id)
                            status = await handle_auth_command(
                                page, account_id, command, legacy
                            )
                            if status in {"sent", "manual_required"}:
                                auth_account = account_id
                                auth_deadline = time.monotonic() + 5 * 60
                                write_status(account_id, "authenticating")
                            elif status == "success":
                                register_account(account_id)
                                if account_id not in accounts:
                                    accounts.append(account_id)
                                next_query[account_id] = 0.0
                                auth_account = None
                                write_auth_response(request_id, "success", legacy)
                        except (PlaywrightError, OSError) as err:
                            write_auth_response(request_id, "login_failed", legacy)
                            LOG.warning("Browser login failed: %s", type(err).__name__)
                        finally:
                            command.clear()

                if auth_account is not None:
                    if time.monotonic() < auth_deadline:
                        await asyncio.sleep(1)
                        continue
                    auth_account = None

                for account_id in accounts:
                    if time.monotonic() < next_query.get(account_id, 0.0):
                        continue
                    interval = INTERVAL_SECONDS
                    try:
                        page = await browser.activate(account_id)
                        sensors = await query(page, known_keys.get(account_id))
                        if sensors is None:
                            write_status(account_id, "login_required")
                            await page.goto(
                                LOGIN_URL, wait_until="domcontentloaded", timeout=30000
                            )
                            LOG.info("Account %s needs browser login", account_id)
                        elif sensors:
                            known_keys[account_id] = set(sensors)
                            write_status(account_id, "ok", sensors)
                            LOG.info("Account %s updated: %d sensors", account_id, len(sensors))
                        else:
                            interval = RETRY_SECONDS
                            write_status(account_id, "query_failed")
                            LOG.warning("Account %s returned no recognized values", account_id)
                    except PlaywrightError as err:
                        interval = RETRY_SECONDS
                        write_status(account_id, "query_failed")
                        LOG.warning(
                            "Account %s browser query failed: %s",
                            account_id, type(err).__name__,
                        )
                    next_query[account_id] = time.monotonic() + interval
                    break
                await asyncio.sleep(1)
        finally:
            await browser.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run())
