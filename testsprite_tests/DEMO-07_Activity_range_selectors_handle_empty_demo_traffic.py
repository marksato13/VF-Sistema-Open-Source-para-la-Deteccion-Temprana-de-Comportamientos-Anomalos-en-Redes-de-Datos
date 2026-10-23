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
        
        # -> Click the 'Cerrar' button on the tour modal, then click the 'Actividad' link to open the Activity view.
        # Cerrar button
        elem = page.get_by_role("button", name="Cerrar")
        await elem.click(timeout=10000)
        
        # -> Click the 'Cerrar' button on the tour modal, then click the 'Actividad' link to open the Activity view.
        # Actividad link
        elem = page.get_by_role("link", name="Actividad", exact=True)
        await elem.click(timeout=10000)
        
        # -> Click the 'Última hora' button and verify the chart updates without errors and shows no fabricated live events.
        # Última hora button
        elem = page.get_by_role("button", name="Última hora")
        await elem.click(timeout=10000)
        
        # -> Click the 'Última hora' button and verify the chart updates without errors and shows no fabricated live events.
        # Últimas 24h button
        elem = page.get_by_role("button", name="Últimas 24h")
        await elem.click(timeout=10000)
        
        # -> Click the 'Última hora' button and verify the chart updates to minute ticks (−60, −45, −30, −15, ahora) and that no fabricated live events appear in the IPs or charts.
        # Última hora button
        elem = page.get_by_role("button", name="Última hora")
        await elem.click(timeout=10000)
        
        # -> Click the 'Últimas 24h' button and verify the x-axis updates to hourly ticks and that no fabricated live events appear.
        # Últimas 24h button
        elem = page.get_by_role("button", name="Últimas 24h")
        await elem.click(timeout=10000)
        
        # --> Assertions to verify final state
        
        # --> Selecting 'Últimas 24h' updated the Activity chart to a 24-hour/hourly view without errors.
        await page.get_by_role("button", name="Últimas 24h").nth(0).scroll_into_view_if_needed()
        # Assert-outcome: passed
        # Assert: The 'Últimas 24h' time-range button is visible.
        await expect(page.get_by_role("button", name="Últimas 24h").nth(0)).to_be_visible(timeout=15000), "The '\u00daltimas 24h' time-range button is visible."
        # Assert-outcome: passed
        # Assert: The chart shows the hourly aggregation label 'por hora'.
        await expect(page.locator("#sparkRangeLabel").nth(0)).to_have_text("por hora", timeout=15000), "The chart shows the hourly aggregation label 'por hora'."
        
        # --> Top-IPs table shows no IP actions (no fabricated live events).
        # Assert-outcome: passed
        # Assert: The top-IPs table displays 'Ninguna IP con acciones en la última hora.' indicating no IP actions.
        await expect(page.locator("#topIps").nth(0)).to_have_text("Ninguna IP con acciones en la \u00faltima hora.", timeout=15000), "The top-IPs table displays 'Ninguna IP con acciones en la \u00faltima hora.' indicating no IP actions."
        await asyncio.sleep(5)

    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

asyncio.run(run_test())
    