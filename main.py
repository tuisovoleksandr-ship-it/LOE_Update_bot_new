import asyncio
import hashlib
import os
from aiohttp import ClientSession, web
from telegram import Bot
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = 60
PAGE_URL = "https://poweron.loe.lviv.ua"

last_hash = None


async def send_to_telegram(image_url: str, content: bytes):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_photo(
        chat_id=CHAT_ID,
        photo=content,
        caption=f"🔄 Оновлене зображення\n{image_url}"
    )


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def get_real_image_url() -> str | None:
    """
    Відкриває poweron.loe.lviv.ua та перехоплює запити до _GPV.png
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        found_url = None

        async def on_request(req):
            nonlocal found_url
            url = req.url
            if url.endswith("_GPV.png") and "api.loe.lviv.ua/media" in url:
                found_url = url

        page.on("request", on_request)

        await page.goto(PAGE_URL, timeout=60000)

        # чекаємо мережеві запити
        for _ in range(60):
            await asyncio.sleep(0.5)
            if found_url:
                break

        await browser.close()
        return found_url


async def check_loop():
    global last_hash

    async with ClientSession() as session:
        while True:
            print("🔍 Перевіряю оновлення...")

            img_url = await get_real_image_url()

            if not img_url:
                print("❌ Не знайдено _GPV.png на сайті")
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            print(f"🔗 Знайдено картинку: {img_url}")

            async with session.get(img_url) as r:
                data = await r.read()

            new_hash = compute_hash(data)

            if last_hash != new_hash:
                print("🆕 НОВЕ ЗОБРАЖЕННЯ — надсилаю…")
                await send_to_telegram(img_url, data)
                last_hash = new_hash
            else:
                print("ℹ️ Без змін")

            await asyncio.sleep(CHECK_INTERVAL)


async def self_ping():
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        return
    async with ClientSession() as session:
        while True:
            try:
                async with session.get(url + "/ping") as r:
                    print(f"[Self-ping] {url} -> {r.status}")
            except:
                print("[Self-ping] ERROR")
            await asyncio.sleep(60)


async def handle_ping(request):
    return web.Response(text="pong")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/ping", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    print("🌐 Web server started")


async def main():
    await start_web_server()
    await asyncio.gather(check_loop(), self_ping())


if __name__ == "__main__":
    asyncio.run(main())