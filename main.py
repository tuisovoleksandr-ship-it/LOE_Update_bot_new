import aiohttp
import asyncio
import os
import re
from datetime import datetime, UTC
from aiohttp import web
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SELF_URL = os.environ.get("SELF_URL", "")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 120))

bot = Bot(token=BOT_TOKEN)

# ------------------------- Веб-сервер для self-ping -------------------------
async def handle_ping(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/ping", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    print("🌐 Web server started on port 10000")


# ------------------------ Відправка картинки ------------------------------
async def send_photo(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                print("❌ Не можу завантажити фото:", resp.status)
                return

            img = await resp.read()

    try:
        await bot.send_photo(chat_id=CHAT_ID, photo=img)
        print("📤 Відправлено у Telegram:", url)
    except Exception as e:
        print("❌ Помилка відправки фото:", e)


# ------------------------ Основна логіка парсингу --------------------------
async def get_image_url():
    MAIN_URL = "https://poweron.loe.lviv.ua"

    async with aiohttp.ClientSession() as session:
        # 1. HTML
        async with session.get(MAIN_URL) as resp:
            html = await resp.text()

        # 2. Шукаємо main.js
        js_match = re.search(r'/static/js/main\.[a-zA-Z0-9]+\.js', html)
        if not js_match:
            print("❌ Не знайдено main.js")
            return None

        js_path = js_match.group(0)
        js_url = MAIN_URL + js_path

        # 3. Завантажуємо JS-файл
        async with session.get(js_url) as resp:
            js_code = await resp.text()

        # 4. Витягуємо URL картинки
        img_match = re.search(
            r'https://api\.loe\.lviv\.ua/media/[A-Za-z0-9_]+\.(?:png|jpg|jpeg)',
            js_code
        )

        if not img_match:
            print("❌ Не знайдено GPV-mobile")
            return None

        return img_match.group(0)


# ------------------------ Цикл перевірки --------------------------
async def check_loop():
    last = ""

    while True:
        print("\n🔄 Перевірка...", datetime.now(UTC))

        img = await get_image_url()

        if not img:
            print("❌ Картинка не знайдена")
        else:
            print("🔗 Знайдена картинка:", img)

            if img != last:
                print("🆕 Нова картинка → відправляю в Telegram")
                await send_photo(img)
                last = img
            else:
                print("✓ Картинка без змін")

        await asyncio.sleep(CHECK_INTERVAL)


# ------------------------ Self-ping --------------------------
async def self_ping_loop():
    if not SELF_URL:
        print("⚠️ SELF_URL не задано — self-ping не працює")
        return

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SELF_URL + "/ping") as resp:
                    print(f"[{datetime.now(UTC)}] Self-ping → {resp.status}")
        except:
            print("⚠️ Self-ping error")

        await asyncio.sleep(60)


# -------------------------- Main ------------------------------
async def main():
    await start_web_server()
    await asyncio.gather(check_loop(), self_ping_loop())


if __name__ == "__main__":
    asyncio.run(main())