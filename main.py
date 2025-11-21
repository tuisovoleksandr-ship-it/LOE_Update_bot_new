import asyncio
import aiohttp
from bs4 import BeautifulSoup
import hashlib
import os
from datetime import datetime
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
LAST_HASH_FILE = "last_hash.txt"

URL = "https://poweron.loe.lviv.ua"

async def fetch_image_url():
    async with aiohttp.ClientSession() as session:
        async with session.get(URL) as resp:
            if resp.status != 200:
                print("❌ Не удалось загрузить страницу")
                return None

            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

            img = soup.find("img")
            if not img:
                print("❌ <img> не найден")
                return None

            src = img.get("src")
            if not src:
                print("❌ src не найден")
                return None

            # Если путь относительный — добавляем домен
            if src.startswith("/"):
                src = "https://poweron.loe.lviv.ua" + src

            return src


async def download_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                print("❌ Ошибка загрузки картинки:", resp.status)
                return None
            return await resp.read()


def calc_hash(data):
    return hashlib.sha256(data).hexdigest()


def load_last_hash():
    if not os.path.exists(LAST_HASH_FILE):
        return None
    return open(LAST_HASH_FILE).read().strip()


def save_last_hash(h):
    with open(LAST_HASH_FILE, "w") as f:
        f.write(h)


async def send_to_telegram(image_bytes):
    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field("chat_id", CHAT_ID)
        form.add_field("photo", image_bytes, filename="image.png")

        async with session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data=form
        ) as resp:
            if resp.status == 200:
                print("📨 Картинка отправлена в Telegram")
            else:
                print("❌ Ошибка Telegram:", resp.status, await resp.text())


async def check_loop():
    while True:
        print("\n🔄 Проверка...", datetime.utcnow())

        image_url = await fetch_image_url()
        if not image_url:
            await asyncio.sleep(60)
            continue

        print("🔗 Найдено изображение:", image_url)

        img = await download_image(image_url)
        if not img:
            await asyncio.sleep(60)
            continue

        new_hash = calc_hash(img)
        last_hash = load_last_hash()

        if new_hash != last_hash:
            print("🆕 Новое изображение! Отправляем в Telegram…")
            await send_to_telegram(img)
            save_last_hash(new_hash)
        else:
            print("➖ Картинка не изменилась")

        await asyncio.sleep(60)


async def ping_handler(request):
    return web.Response(text="pong")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/ping", ping_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    print("🌐 Web server started on port 10000")


async def main():
    await start_web_server()
    await check_loop()


if __name__ == "__main__":
    asyncio.run(main())