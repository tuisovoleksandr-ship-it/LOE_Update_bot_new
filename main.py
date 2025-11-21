import aiohttp
import asyncio
import os
import re
from datetime import datetime, UTC
from aiohttp import web
from telegram import Bot

# --------------------------- CONFIG ---------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SELF_URL = os.environ.get("SELF_URL")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 120))

bot = Bot(token=BOT_TOKEN)


# ---------------------- SELF-PING WEB SERVER ------------------
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


# ------------------------- SEND PHOTO -------------------------
async def send_photo(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                print("❌ Не можу завантажити фото:", resp.status)
                return
            img = await resp.read()

    await bot.send_photo(chat_id=CHAT_ID, photo=img)
    print("📤 Відправлено в Telegram:", url)


# ----------------------- PARSE <img> --------------------------
async def get_image_url():
    MAIN_URL = "https://poweron.loe.lviv.ua"

    async with aiohttp.ClientSession() as session:
        async with session.get(MAIN_URL) as resp:
            if resp.status != 200:
                print("❌ HTML не отримано:", resp.status)
                return None

            html = await resp.text()

    # Шукаємо <img src="https://api.loe.lviv.ua/media/....png">
    match = re.search(
        r'src="(https://api\.loe\.lviv\.ua/media/[A-Za-z0-9_]+\.(?:png|jpg|jpeg))"',
        html
    )

    if not match:
        print("❌ <img> з картинкою не знайдено")
        return None

    return match.group(1)


# -------------------- CHECK LOOP (main logic) --------------------
async def check_loop():
    last_url = None

    while True:
        print(f"\n🔄 Перевірка... {datetime.now(UTC)}")

        img = await get_image_url()

        if not img:
            print("❌ Картинка не знайдена")
        else:
            print("🔗 Знайдена картинка:", img)

            if img != last_url:
                print("🆕 Нова картинка → відправляю в Telegram")
                await send_photo(img)
                last_url = img
            else:
                print("✓ Картинка без змін")

        await asyncio.sleep(CHECK_INTERVAL)


# ---------------------- SELF-PING LOOP -------------------------
async def self_ping_loop():
    if not SELF_URL:
        print("⚠️ SELF_URL не задано — self-ping не працює")
        return

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SELF_URL + "/ping") as resp:
                    print(f"[{datetime.now(UTC)}] Self-ping →", resp.status)
        except Exception as e:
            print("⚠️ Self-ping error:", e)

        await asyncio.sleep(60)


# ----------------------------- MAIN ----------------------------
async def main():
    await start_web_server()
    await asyncio.gather(check_loop(), self_ping_loop())


if __name__ == "__main__":
    asyncio.run(main())