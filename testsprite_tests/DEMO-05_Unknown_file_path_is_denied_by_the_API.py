import asyncio
import re
from playwright import async_api
from playwright.async_api import expect

async def run_test():
    pw = None
    browser = None
    context = None

    try:
        # Start a Playwright session in asynchronous mode
        pw = await async_api.async_playwright().start()

        # Launch a Chromium browser in headless mode with custom arguments
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--window-size=1280,720",
                "--disable-dev-shm-usage",
                "--ipc=host",
                "--single-process"
            ],
        )

        # Create a new browser context (like an incognito window)
        context = await browser.new_context()
        # Wider default timeout to match the agent's DOM-stability budget;
        # auto-waiting Playwright APIs (expect, locator.wait_for) inherit this.
        context.set_default_timeout(15000)

        # Open a new page in the browser context
        page = await context.new_page()

        # Interact with the page elements to simulate user flow
        # -> navigate
        await page.goto("http://localhost:8799/")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        
        # -> Request the API endpoint '/api/archivo?ruta=/ruta-que-no-esta-en-la-lista.txt' (open it in a new tab) and verify the response status is 403 and no file content is returned.
        await page.goto("http://localhost:8799/api/archivo?ruta=/ruta-que-no-esta-en-la-lista.txt")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        
        # --> Assertions to verify final state
        
        # --> Requesting the API path returned a 403 Forbidden error page and no file content is displayed.
        # Assert-outcome: passed
        # Assert: The page contains the text 'Error code: 403'.
        await expect(page.locator("body").nth(0)).to_contain_text("Error code: 403", timeout=15000), "The page contains the text 'Error code: 403'."
        # Assert-outcome: passed
        # Assert: The page contains the text 'Message: Forbidden.'
        await expect(page.locator("body").nth(0)).to_contain_text("Message: Forbidden.", timeout=15000), "The page contains the text 'Message: Forbidden.'"
        await asyncio.sleep(5)

    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

asyncio.run(run_test())
    