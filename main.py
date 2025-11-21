import asyncio
import os
import datetime
from playwright.async_api import async_playwright
from aiohttp import web

SELF_URL = os.environ.get("SELF_URL")
TARGET_URL = "https://poweron.loe.lviv.ua"
CHECK_INTERVAL = 300  # 5 хв
LAST_IMAGE = None


async def fetch_image_url():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(TARGET_URL, timeout=45000)

            # Чекаємо поки React намалює <img>
            await page.wait_for_selector("img[src]", timeout=20000)

            img = await page.query_selector("img[src]")
            if not img:
                return None

            src = await img.get_attribute("src")
            if src and src.startswith("http"):
                return src
            elif src:
                return TARGET_URL + src
            return None

        finally:
            await browser.close()


async def monitor(bot=None, chat_id=None):
    global LAST_IMAGE

    while True:
        print("\nПеревірка...", datetime.datetime.now(datetime.timezone.utc))

        if not SELF_URL:
            print("⚠️ SELF_URL не задано — self-ping не працює")

        url = await fetch_image_url()
        if not url:
            print("❌ Картинка не знайдена")
        else:
            print(f"🟩 Знайдено картинку: {url}")

            if url != LAST_IMAGE:
                print("🔄 Картинка змінилася!")
                LAST_IMAGE = url
            else:
                print("✔ Картинка без змін")

        await asyncio.sleep(CHECK_INTERVAL)


async def handle_ping(request):
    return web.Response(text="ok")


async def create_app():
    app = web.Application()
    app.router.add_get("/", handle_ping)

    asyncio.create_task(monitor())
    return app


def main():
    app = create_app()
    web.run_app(app, port=8080)


if __name__ == "__main__":
    main()