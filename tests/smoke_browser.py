"""Run inside the built add-on image to verify headed Chromium."""

import asyncio
import tempfile

from playwright.async_api import async_playwright


async def main() -> None:
    async with async_playwright() as playwright:
        with tempfile.TemporaryDirectory() as profile:
            browser = await playwright.chromium.launch_persistent_context(
                profile,
                headless=False,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.pages[0] if browser.pages else await browser.new_page()
            await page.goto("data:text/html,<title>ready</title><h1>Chromium works</h1>")
            assert await page.title() == "ready"
            assert await page.locator("h1").inner_text() == "Chromium works"
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
