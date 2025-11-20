import asyncio
import hashlib
import datetime
import os
from aiohttp import web
from playwright.async_api import async_playwright

# ---------------------- CONFIG ----------------------
CHECK_URL = "https://poweron.loe.lviv.ua"
IMAGE_SELECTOR = "img"       # або можеш замінити на конкретний селектор
CHECK_INTERVAL = 60          # 60 сек
SELF_PING_INTERVAL = 120     # 2 хв
PORT = int(os.environ.get("PORT", 10000))
SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
# -----------------------------------------------------

last_hash = None


async def fetch_image_url(playwright):
    """Отримує HTML через Chromium і шукає перше зображення."""
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()

    try:
        await page.goto(CHECK_URL, timeout=30000)
        await page.wait_for_selector(IMAGE_SELECTOR, timeout=15000)

        img = await page.query_selector(IMAGE_SELECTOR)
        if img:
            src = await img.get_attribute("src")
            # Робимо абсолютний URL
            if src.startswith("/"):
                src = CHECK_URL.rstrip("/") + src
            return src
        return None
    finally:
        await browser.close()


def hash_string(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


async def check_updates():
    """Перевірка змін."""
    global last_hash

    while True:
        try:
            async with async_playwright() as p:
                img_url = await fetch_image_url(p)

            if img_url is None:
                print("❌ Не знайшов зображення на сторінці")
            else:
                new_hash = hash_string(img_url)
                print(f"[{datetime.datetime.now()}] Поточний хеш: {new_hash}")

                if last_hash is None:
                    print("Хеш відсутній — перший запуск")
                    last_hash = new_hash
                elif new_hash != last_hash:
                    print("🟢 Зміни знайдено!")
                    last_hash = new_hash
                else:
                    print("ℹ️  Змін немає")

        except Exception as e:
            print("Помилка перевірки:", e)

        await asyncio.sleep(CHECK_INTERVAL)


async def self_ping():
    """Щоб Render не заснув."""
    if not SELF_URL:
        print("⚠️ SELF_URL не встановлено — self-ping вимкнено")
        return

    while True:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                ping_url = f"{SELF_URL}/ping"
                async with session.get(ping_url) as r:
                    print(f"[{datetime.datetime.now()}] Self-ping {ping_url} -> {r.status}")
        except Exception as e:
            print("Self-ping error:", e)

        await asyncio.sleep(SELF_PING_INTERVAL)


async def handle_ping(request):
    return web.Response(text="OK")


async def start_web_server():
    """Локальний сервер на Render."""
    app = web.Application()
    app.router.add_get("/ping", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Web server started on port {PORT}")


async def main():
    await start_web_server()
    await asyncio.gather(
        check_updates(),
        self_ping()
    )


if __name__ == "__main__":
    asyncio.run(main())