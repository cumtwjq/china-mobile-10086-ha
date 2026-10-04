"""Check that multiple browser sessions remain open and commands stay separate."""

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "china_mobile_browser"))
import worker  # noqa: E402


class FakePage:
    def __init__(self):
        self.front_count = 0

    async def bring_to_front(self):
        self.front_count += 1


class FakeContext:
    def __init__(self):
        self.pages = [FakePage()]
        self.closed = False

    async def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self):
        self.profiles = []
        self.contexts = []

    async def launch_persistent_context(self, profile, **kwargs):
        self.profiles.append(profile)
        context = FakeContext()
        self.contexts.append(context)
        return context


class BrowserWorkerTests(unittest.TestCase):
    def test_registered_accounts_are_queried_independently(self):
        class StopLoop(Exception):
            pass

        class FakePlaywrightManager:
            def __init__(self, chromium):
                self.playwright = type("Playwright", (), {"chromium": chromium})()

            async def __aenter__(self):
                return self.playwright

            async def __aexit__(self, *args):
                return False

        async def fake_query(page):
            return {"balance": 12.34}

        cycles = 0

        async def stop_after_two_queries(seconds):
            nonlocal cycles
            cycles += 1
            if cycles == 2:
                raise StopLoop()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chromium = FakeChromium()
            accounts = ["0123456789abcdef", "fedcba9876543210"]
            with (
                patch.object(worker, "load_accounts", return_value=accounts),
                patch.object(worker, "profile_path", side_effect=lambda aid: root / aid),
                patch.object(worker, "write_status") as statuses,
                patch.object(worker, "next_command", return_value=None),
                patch.object(worker, "query", side_effect=fake_query),
                patch.object(worker, "async_playwright", return_value=FakePlaywrightManager(chromium)),
                patch.object(worker, "HEARTBEAT", type("Heartbeat", (), {"touch": lambda self: None})()),
                patch.object(worker.asyncio, "sleep", side_effect=stop_after_two_queries),
            ):
                with self.assertRaises(StopLoop):
                    asyncio.run(worker.run())
            self.assertEqual(len(chromium.contexts), 2)
            self.assertIn((accounts[0], "ok", {"balance": 12.34}), [call.args for call in statuses.call_args_list])
            self.assertIn((accounts[1], "ok", {"balance": 12.34}), [call.args for call in statuses.call_args_list])

    def test_two_accounts_keep_separate_open_profiles(self):
        async def exercise(root):
            chromium = FakeChromium()
            browser = worker.BrowserManager(type("Playwright", (), {"chromium": chromium})())
            with patch.object(worker, "profile_path", side_effect=lambda aid: root / aid):
                first = await browser.activate("0123456789abcdef")
                second = await browser.activate("fedcba9876543210")
                self.assertIsNot(first, second)
                self.assertFalse(chromium.contexts[0].closed)
                self.assertEqual(len(set(chromium.profiles)), 2)
                self.assertIs(await browser.activate("0123456789abcdef"), first)
                self.assertEqual(len(chromium.contexts), 2)
                await browser.close()
                self.assertTrue(all(context.closed for context in chromium.contexts))

        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(exercise(Path(directory)))

    def test_independent_auth_command_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = root / "commands"
            commands.mkdir()
            first = {"id": "a" * 32, "account_id": "0123456789abcdef"}
            second = {"id": "b" * 32, "account_id": "fedcba9876543210"}
            (commands / f"{first['id']}.json").write_text(json.dumps(first))
            (commands / f"{second['id']}.json").write_text(json.dumps(second))
            with (
                patch.object(worker, "COMMANDS", commands),
                patch.object(worker, "LEGACY_COMMAND", root / "legacy.json"),
            ):
                self.assertEqual(worker.next_command(), (first, False))
                self.assertEqual(worker.next_command(), (second, False))
                self.assertIsNone(worker.next_command())


if __name__ == "__main__":
    unittest.main()
