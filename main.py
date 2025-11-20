import asyncio
import hashlib
import aiohttp
from aiohttp import web
from playwright.async_api import async_playwright
import os
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SELF_URL = os.getenv("SELF_URL")

CHECK_INTERVAL = 300

HASH_FILE = "last_hash.txt"


async def send_to_telegram(image_url):
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID, "caption": "Оновлене зображення"},
            files={"photo": (image_url, await session.get(image_url).then(lambda r: r.read()))},
        )


def load_last_hash():
    if not os.path.exists(HASH_FILE):
        return None
    with open(HASH_FILE, "r") as f:
        return f.read().strip()


def save_last_hash(h):
    with open(HASH_FILE, "w") as f:
        f.write(h)


async def get_latest_image_url():
    """
    Виловити з Network будь-який файл, що закінчується на _GPV.png
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()

        found_url = None

        def handle_response(response):
            nonlocal found_url
            url = response.url
            if url.endswith("_GPV.png"):  # ❗ ОДНА картинка, завжди кінцівка _GPV.png
                found_url = url

        page.on("response", handle_response)

        await page.goto("https://poweron.loe.lviv.ua", timeout=60000)
        await asyncio.sleep(5)

        await browser.close()

        return found_url


async def check_loop():
    print("Фоновий цикл запущено.")

    while True:
        print("\n--- Перевірка ---")
        image_url = await get_latest_image_url()

        if not image_url:
            print("❌ Картинку не знайдено")
        else:
            print(f"🔗 Знайдено картинку: {image_url}")

            async with aiohttp.ClientSession() as session:
                img = await (await session.get(image_url)).read()
                new_hash = hashlib.md5(img).hexdigest()
                old_hash = load_last_hash()

            if old_hash != new_hash:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"🆕 НОВЕ ЗОБРАЖЕННЯ ({timestamp}) → Відправляю у Telegram…")

                save_last_hash(new_hash)
                await send_to_telegram(image_url)
            else:
                print("🔁 Картинка не змінилась.")

        await asyncio.sleep(CHECK_INTERVAL)


async def handle_ping(request):
    return web.Response(text="OK")


async def create_app():
    app = web.Application()
    app.router.add_get("/ping", handle_ping)
    return app


async def self_ping():
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await session.get(SELF_URL + "/ping")
                print(f"[{datetime.now()}] Self-ping OK")
        except Exception as e:
            print(f"Self-ping error: {e}")

        await asyncio.sleep(60)


async def main():
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    print("🌐 Web server started on port 10000")

    await asyncio.gather(
        check_loop(),
        self_ping(),
    )


if __name__ == "__main__":
    asyncio.run(main())