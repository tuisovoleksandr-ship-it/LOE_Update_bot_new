import os
import asyncio
import hashlib
import datetime
import threading
import requests
from aiohttp import web
from telegram import Bot

# -------------------------------
# Конфігурація
# -------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
EXTERNAL_URL = os.environ.get("EXTERNAL_URL")  # твій Render URL з https://.../
CHECK_INTERVAL = 60  # перевірка раз на хвилину

TARGET_PAGE = "https://poweron.loe.lviv.ua"
IMAGE_PREFIX = "https://api.loe.lviv.ua/media/"
IMAGE_SUFFIX = "_GPV-mobile.png"

HASH_FILE = "last_hash.txt"
bot = Bot(token=BOT_TOKEN)


# -------------------------------
# Завантаження попереднього хешу
# -------------------------------
def load_last_hash():
    if not os.path.exists(HASH_FILE):
        print("Хеш відсутній — перший запуск")
        return None
    with open(HASH_FILE, "r") as f:
        return f.read().strip()


def save_last_hash(h):
    with open(HASH_FILE, "w") as f:
        f.write(h)


# -------------------------------
# Пошук URL картинки у HTML
# -------------------------------
def extract_image_url(html: str):
    """
    Шукаємо будь-яку появу:
    https://api.loe.lviv.ua/media/<HASH>_GPV-mobile.png
    """

    start = html.find(IMAGE_PREFIX)
    if start == -1:
        return None

    end = html.find(IMAGE_SUFFIX, start)
    if end == -1:
        return None

    end += len(IMAGE_SUFFIX)
    return html[start:end]


# -------------------------------
# Основна логіка перевірки
# -------------------------------
async def check_image():
    while True:
        try:
            # Завантажуємо HTML
            html = requests.get(TARGET_PAGE, timeout=10).text

            # Витягуємо URL картинки
            image_url = extract_image_url(html)

            if not image_url:
                print("⚠️ На сторінці не знайдено URL картинки GPV-mobile")
                print(f"🚫 [{datetime.datetime.now()}] Не вдалося знайти URL картинки")
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            print(f"🔗 Знайдено URL картинки: {image_url}")

            # Завантажуємо саму картинку
            img = requests.get(image_url, timeout=10).content

            # Обчислюємо хеш
            new_hash = hashlib.md5(img).hexdigest()
            old_hash = load_last_hash()

            # Порівняння
            if old_hash != new_hash:
                print("📸 Картинка оновлена! Надсилаємо у Telegram...")

                bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=img,
                    caption=f"📊 Оновлення графіка {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                save_last_hash(new_hash)
            else:
                print("✔ Картинка не змінилася")

        except Exception as e:
            print(f"❌ Помилка перевірки: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# -------------------------------
# Self-ping сервер (для Render)
# -------------------------------
async def handle_root(request):
    return web.Response(text="Bot is running!")


async def self_ping():
    while True:
        try:
            if EXTERNAL_URL:
                requests.get(EXTERNAL_URL)
                print(f"✅ Self-ping OK ({datetime.datetime.now()})")
        except Exception:
            print("⚠️ Self-ping ERROR")

        await asyncio.sleep(60)


# -------------------------------
# Запуск
# -------------------------------
async def main():
    app = web.Application()
    app.add_routes([web.get("/", handle_root)])

    loop = asyncio.get_event_loop()
    loop.create_task(check_image())
    loop.create_task(self_ping())

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    print("🌐 Web-server started on port 10000")

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())