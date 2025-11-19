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
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID")
IMAGE_URL = "https://api.loe.lviv.ua/media/691d6ab3b2c3a_GPV-mobile.png"
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))
HASH_FILE = "last_hash.txt"
PORT = int(os.environ.get("PORT", 8080))
EXTERNAL_URL = os.environ.get("EXTERNAL_URL", "")

# Быстрая валидация обязательных переменных
if not BOT_TOKEN:
    raise RuntimeError("ENV Error: BOT_TOKEN не задан. Додай в .env BOT_TOKEN.")
if not CHAT_ID_RAW:
    raise RuntimeError("ENV Error: CHAT_ID не задан. Додай в .env CHAT_ID.")

# Попробуем привести CHAT_ID к int, если это число; иначе оставим строкой
try:
    CHAT_ID = int(CHAT_ID_RAW)
except ValueError:
    CHAT_ID = CHAT_ID_RAW  # возможно -100... строкой — Telegram это тоже принимает

# --- Веб-сервер ---
async def handle_root(request):
    return web.Response(text="✅ Скрипт живий і стежить за графіком")

async def handle_ping(request):
    print(f"👋 Отримано пінг від {request.remote} у {datetime.datetime.now().strftime('%H:%M:%S')}")
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
        p = Path(HASH_FILE)
        if p.exists():
            return p.read_text().strip()
    except Exception as e:
        print(f"Помилка читання хешу: {e}")
    return None

def save_hash(hash_value):
    try:
        # простая запись — можно улучшить атомарностью при желании
        Path(HASH_FILE).write_text(hash_value)
    except Exception as e:
        print(f"Помилка збереження хешу: {e}")

# --- Self-ping ---
async def keep_alive():
    if not EXTERNAL_URL:
        print("⚠️ EXTERNAL_URL не налаштовано, self-ping вимкнено")
        return

    ping_url = f"{EXTERNAL_URL.rstrip('/')}/ping"
    await asyncio.sleep(60)  # дать время на старт сервиса
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
    last_hash = load_last_hash()

    if last_hash:
        print(f"Завантажено збережений хеш: {last_hash[:8]}...")
    else:
        print("Перший запуск, хеш не знайдено")

    # Создаём бот как асинхронный контекст один раз
    async with Bot(token=BOT_TOKEN) as bot:
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
                                    # отправляем картинку
                                    await bot.send_photo(
                                        chat_id=CHAT_ID,
                                        photo=image_data,
                                        caption="⚡ Нове оновлення графіка відключень електроенергії"
                                    )
                                    print(f"✅ [{now}] Зображення відправлено в Telegram")
                                    last_hash = current_hash
                                    save_hash(current_hash)
                                except TelegramError as e:
                                    print(f"❌ [{now}] Помилка Telegram: {e}")
                                except Exception as e:
                                    print(f"❌ [{now}] Невідома помилка при відправці: {e}")
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
        # выводим полную информацию об ошибке — удобно при отладке
        import traceback
        print("💥 Критична помилка:")
        traceback.print_exc()