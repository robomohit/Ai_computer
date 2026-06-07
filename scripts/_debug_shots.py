import asyncio
import hashlib
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8080
BASE = f"http://127.0.0.1:{PORT}"


async def main() -> None:
    proc = None
    try:
        healthy = httpx.get(f"{BASE}/healthz", timeout=1).status_code == 200
    except Exception:
        healthy = False
    if not healthy:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", f"--port", str(PORT)],
            cwd=ROOT,
        )
        for _ in range(40):
            if httpx.get(f"{BASE}/healthz", timeout=1).status_code == 200:
                break
            time.sleep(0.25)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1360, "height": 860}, color_scheme="dark")
        await context.request.post(f"{BASE}/api/session")
        await context.request.post(
            f"{BASE}/api/preferences",
            data='{"preferences":{"onboarded":true}}',
            headers={"Content-Type": "application/json"},
        )
        page = await context.new_page()
        await page.goto(f"{BASE}/", wait_until="networkidle")
        await page.evaluate("document.getElementById('onboarding').hidden = true")
        await page.evaluate("window.__aiComputerPlayNotepadDemoStream()")
        tmp = ROOT / "_shots"
        tmp.mkdir(exist_ok=True)
        for i in range(12):
            await page.screenshot(path=str(tmp / f"{i}.png"))
            await asyncio.sleep(1.0)
        await browser.close()

    for i in range(12):
        digest = hashlib.md5((tmp / f"{i}.png").read_bytes()).hexdigest()[:8]
        print(i, digest)

    if proc:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
