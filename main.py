import aiohttp
import asyncio
import hashlib
import os
from aiohttp import web
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SELF_URL = os.environ.get("EXTERNAL_URL")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))

HASH_FILE = "last_hash.txt"
API_FOLDER = "https://api.loe.lviv.ua/media/"
SUFFIX = "_GPV-mobile.png"

# ----------------- Зберігання хеша -----------------

def load_last_hash():
    if os.path.exists(HASH_FILE):
        return open(HASH_FILE).read().strip()
    return None

def save_last_hash(h):
    with open(HASH_FILE, "w") as f:
        f.write(h)

# ----------------- Пошук картинки -----------------

async def find_latest_image():
    async with aiohttp.ClientSession() as session:
        async with session.get(API_FOLDER) as r:
            if r.status == 403:
                # каталоги закриті → робимо brute-force через HEAD
                for i in range(1, 999):
                    guess = f"{API_FOLDER}{i:03d}_GPV-mobile.png"
                    async with session.head(guess) as h:
                        if h.status == 200:
                            return guess
                return None
            else:
                html = await r.text()
                # каталог відкритий (малоймовірно)
                import re
                found = re.findall(r'href="([^"]+GPV-mobile\.png)"', html)
                if found:
                    return API_FOLDER + found[-1]
                return None

# ----------------- Відправка картинки -----------------

async def send_telegram(image_url):
    async with aiohttp.ClientSession() as s:
        # Завантажуємо файл
        async with s.get(image_url) as r:
            data = await r.read()

        form = aiohttp.FormData()
        form.add_field("chat_id", CHAT_ID)
        form.add_field("photo", data, filename="update.png", content_type="image/png")

        async with s.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data=form) as resp:
            print("Telegram response:", await resp.text())

# ----------------- Основний цикл -----------------

async def checker():
    last_hash = load_last_hash()

    while True:
        url = await find_latest_image()

        if not url:
            print("❌ Картинку не знайдено")
            await asyncio.sleep(CHECK_INTERVAL)
            continue

        new_hash = hashlib.md5(url.encode()).hexdigest()

        if last_hash != new_hash:
            print("🔔 Знайдено нову картинку:", url)
            await send_telegram(url)
            save_last_hash(new_hash)
            last_hash = new_hash
        else:
            print("[", datetime.now(), "] Змін немає")

        await asyncio.sleep(CHECK_INTERVAL)

# ----------------- Self-ping сервер -----------------

async def handle_ping(request):
    return web.Response(text="OK")

async def start_server():
    app = web.Application()
    app.add_routes([web.get("/ping", handle_ping)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    print("🌐 Web server started on port 10000")

# ----------------- MAIN -----------------

async def main():
    await start_server()
    await checker()

if __name__ == "__main__":
    asyncio.run(main())