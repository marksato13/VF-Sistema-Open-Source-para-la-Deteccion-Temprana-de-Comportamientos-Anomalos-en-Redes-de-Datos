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
        
        # --> Assertions to verify final state
        
        # --> Demo banner stating the site is in demo mode and not showing live sensors is visible.
        # Assert-outcome: passed
        # Assert: Demo banner text is visible and indicates demo data.
        await expect(page.locator("#healthbar").nth(0)).to_contain_text("MODO DEMO \u2014 datos de ejemplo del repositorio", timeout=15000), "Demo banner text is visible and indicates demo data."
        
        # --> Health section and the KPI summary (four-key overview) are present.
        await page.get_by_role("link", name="Salud").nth(0).scroll_into_view_if_needed()
        # Assert-outcome: passed
        # Assert: The 'Salud' navigation link is visible.
        await expect(page.get_by_role("link", name="Salud").nth(0)).to_be_visible(timeout=15000), "The 'Salud' navigation link is visible."
        # Assert-outcome: passed
        # Assert: The KPI tour indicator shows '1 / 4'.
        await expect(page.locator("xpath=/html/body/div/div[4]/div/span").nth(0)).to_have_text("1 / 4", timeout=15000), "The KPI tour indicator shows '1 / 4'."
        
        # --> Activity navigation link is present in the sidebar.
        # Assert-outcome: passed
        # Assert: The 'Actividad' sidebar link is visible and labeled 'Actividad'.
        await expect(page.locator("xpath=/html/body/div/aside/nav/a[2]").nth(0)).to_have_text("Actividad", timeout=15000), "The 'Actividad' sidebar link is visible and labeled 'Actividad'."
        
        # --> Decisions navigation link is present in the sidebar.
        # Assert-outcome: passed
        # Assert: The 'Decisiones' sidebar link is visible and labeled 'Decisiones'.
        await expect(page.locator("xpath=/html/body/div/aside/nav/a[4]").nth(0)).to_have_text("Decisiones", timeout=15000), "The 'Decisiones' sidebar link is visible and labeled 'Decisiones'."
        
        # --> Scores navigation link is present in the sidebar.
        # Assert-outcome: passed
        # Assert: The 'Scores' sidebar link is visible and labeled 'Scores'.
        await expect(page.locator("xpath=/html/body/div/aside/nav/a[6]").nth(0)).to_have_text("Scores", timeout=15000), "The 'Scores' sidebar link is visible and labeled 'Scores'."
        await asyncio.sleep(5)

    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

asyncio.run(run_test())
    