import aiohttp
import asyncio
import hashlib
import datetime
import os
from pathlib import Path
from aiohttp import web
from telegram import Bot
from telegram.error import TelegramError

# --- Конфігурація ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
IMAGE_URL = "https://api.loe.lviv.ua/media/690e8dca879d5_GPV-mobile.png"
CHECK_INTERVAL = 300
HASH_FILE = "last_hash.txt"
PORT = 8080

EXTERNAL_URL = os.environ.get("EXTERNAL_URL", "")

# --- Веб-сервер ---
async def handle_root(request):
    return web.Response(text="✅ Скрипт живий і стежить за графіком")

async def handle_ping(request):
    return web.Response(text="pong")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/ping", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"✅ Веб-сервер запущено на порту {PORT}")

# --- Робота з хешем ---
def load_last_hash():
    try:
        if Path(HASH_FILE).exists():
            with open(HASH_FILE, 'r') as f:
                return f.read().strip()
    except Exception as e:
        print(f"Помилка читання хешу: {e}")
    return None

def save_hash(hash_value):
    try:
        with open(HASH_FILE, 'w') as f:
            f.write(hash_value)
    except Exception as e:
        print(f"Помилка збереження хешу: {e}")

# --- Self-ping ---
async def keep_alive():
    if not EXTERNAL_URL:
        print("⚠️ EXTERNAL_URL не налаштовано, self-ping вимкнено")
        return

    ping_url = f"{EXTERNAL_URL.rstrip('/')}/ping"
    await asyncio.sleep(60)
    print(f"🔁 Self-ping активовано: {ping_url}")

    async with aiohttp.ClientSession() as session:
        while True:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                async with session.get(ping_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        print(f"✅ Self-ping успішний ({now})")
                    else:
                        print(f"⚠️ Self-ping повернув статус {response.status} ({now})")
            except Exception as e:
                print(f"❌ Помилка self-ping: {e} ({now})")

            await asyncio.sleep(240)

# --- Основна логіка ---
async def check_and_send():
    bot = Bot(token=BOT_TOKEN)
    last_hash = load_last_hash()

    if last_hash:
        print(f"Завантажено збережений хеш: {last_hash[:8]}...")
    else:
        print("Перший запуск, хеш не знайдено")

    async with aiohttp.ClientSession() as session:
        while True:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                async with session.get(IMAGE_URL, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        current_hash = hashlib.md5(image_data).hexdigest()

                        if current_hash != last_hash:
                            print(f"🆕 [{now}] Виявлено зміни! Новий хеш: {current_hash[:8]}...")

                            try:
                                async with bot:
                                    await bot.send_photo(
                                        chat_id=CHAT_ID,
                                        photo=image_data,
                            caption=f"⚡ Нове оновлення графіка відключень електроенергії"
                                    )
                                print(f"✅ [{now}] Зображення відправлено в Telegram")
                                last_hash = current_hash
                                save_hash(current_hash)
                            except TelegramError as e:
                                print(f"❌ [{now}] Помилка Telegram: {e}")
                        else:
                            print(f"ℹ️ [{now}] Без змін (хеш: {current_hash[:8]}...)")
                    else:
                        print(f"⚠️ [{now}] Помилка завантаження: HTTP {response.status}")
            except asyncio.TimeoutError:
                print(f"⏱️ [{now}] Таймаут при завантаженні зображення")
            except Exception as e:
                print(f"❌ [{now}] Помилка: {e}")

            await asyncio.sleep(CHECK_INTERVAL)

# --- Запуск ---
async def main():
    print("🚀 Запуск моніторингу графіка відключень…")
    print(f"URL зображення: {IMAGE_URL}")
    print(f"Інтервал перевірки: {CHECK_INTERVAL} секунд")
    print(f"Telegram Chat ID: {CHAT_ID}")
    print(f"EXTERNAL_URL: {EXTERNAL_URL or 'не задано'}")
    print("-" * 50)

    await asyncio.gather(
        start_web_server(),
        keep_alive(),
        check_and_send()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Зупинка скрипта…")
    except Exception as e:
        print(f"💥 Критична помилка: {e}")
