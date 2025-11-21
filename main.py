import asyncio
import aiohttp
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime
from aiohttp import web
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
CHECK_URL = "https://poweron.loe.lviv.ua"
LAST_HASH = None


async def send_to_telegram(image_url):
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            img = await resp.read()

        data = aiohttp.FormData()
        data.add_field("chat_id", CHAT_ID)
        data.add_field("photo", img, filename="image.jpg")

        async with session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data=data
        ) as resp:
            print("Telegram response:", await resp.text())


async def check_once():
    global LAST_HASH

    print("\n🔄 Проверка...", datetime.utcnow())

    async with aiohttp.ClientSession() as session:
        async with session.get(CHECK_URL) as resp:
            html = await resp.text()

    # 🔍 ДІАГНОСТИКА — ДРУК СИРОГО HTML
    print("=== HTML START ===")
    print(html[:2000])
    print("=== HTML END ===")

    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img")

    if not img:
        print("❌ <img> не найден")
        return

    src = img.get("src")
    if not src:
        print("❌ У <img> нет src")
        return

    # Якщо шлях відносний
    if src.startswith("/"):
        src = "https://poweron.loe.lviv.ua" + src

    print("🔗 Найдено изображение:", src)

    # Обчислюємо хеш
    file_hash = hashlib.md5(src.encode()).hexdigest()

    if LAST_HASH != file_hash:
        print("🆕 Новое изображение найдено → отправляю…")
        await send_to_telegram(src)
        LAST_HASH = file_hash
    else:
        print("✔ Изображение не изменилось.")


async def loop_check():
    while True:
        await check_once()
        await asyncio.sleep(60)


# Web сервер для Render
async def handle_ping(request):
    return web.Response(text="pong")

async def start_web():
    app = web.Application()
    app.add_routes([web.get("/ping", handle_ping)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    print("🌐 Web server started on port 10000")


async def main():
    await asyncio.gather(loop_check(), start_web())


if __name__ == "__main__":
    asyncio.run(main())