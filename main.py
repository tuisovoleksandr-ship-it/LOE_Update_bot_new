import os
import asyncio
import hashlib
import datetime
import aiohttp
from telegram import Bot

API_MEDIA_URL = "https://api.loe.lviv.ua/media/"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = 300  # каждые 5 минут
LAST_HASH_FILE = "last_hash.txt"


async def fetch_listing():
    """Получаем JSON со списком файлов в /media/"""
    async with aiohttp.ClientSession() as session:
        async with session.get(API_MEDIA_URL) as resp:
            if resp.status != 200:
                print("Ошибка получения списка:", resp.status)
                return None
            return await resp.json()


def load_last_hash():
    if not os.path.exists(LAST_HASH_FILE):
        return None
    return open(LAST_HASH_FILE).read().strip()


def save_last_hash(h):
    with open(LAST_HASH_FILE, "w") as f:
        f.write(h)


async def download_file(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
            with open(filename, "wb") as f:
                f.write(data)
            return data


async def find_latest_image():
    """Находим файл, который оканчивается на _GPV-mobile.png"""
    listing = await fetch_listing()
    if not listing:
        return None

    for item in listing:
        name = item.get("name", "")
        if name.endswith("GPV-mobile.png"):
            return API_MEDIA_URL + name

    return None


async def monitor():
    bot = Bot(BOT_TOKEN)
    last_hash = load_last_hash()

    while True:
        print("\n🔄 Проверка...", datetime.datetime.utcnow())

        img_url = await find_latest_image()
        if not img_url:
            print("❌ Не найден GPV-mobile.png")
            await asyncio.sleep(CHECK_INTERVAL)
            continue

        print("🔍 Найден файл:", img_url)

        # скачиваем
        data = await download_file(img_url, "latest.png")
        if not data:
            print("Ошибка скачивания!")
            await asyncio.sleep(CHECK_INTERVAL)
            continue

        # считаем хеш
        new_hash = hashlib.md5(data).hexdigest()

        if new_hash == last_hash:
            print("ℹ️ Файл не изменился")
        else:
            print("📤 Новый файл! Отправляю в Telegram...")
            await bot.send_photo(chat_id=CHAT_ID, photo=open("latest.png", "rb"))
            save_last_hash(new_hash)
            last_hash = new_hash

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(monitor())