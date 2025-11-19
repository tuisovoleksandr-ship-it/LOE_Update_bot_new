import aiohttp
import asyncio
import hashlib
import datetime
import os
from pathlib import Path
from aiohttp import web
from telegram import Bot
from telegram.error import TelegramError
from bs4 import BeautifulSoup

# --- Конфігурація ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))
HASH_FILE = "last_hash.txt"
PORT = int(os.environ.get("PORT", 8080))
EXTERNAL_URL = os.environ.get("EXTERNAL_URL", "")

# Валідація ENV
if not BOT_TOKEN:
    raise RuntimeError("ENV Error: BOT_TOKEN не заданий!")
if not CHAT_ID_RAW:
    raise RuntimeError("ENV Error: CHAT_ID не заданий!")

try:
    CHAT_ID = int(CHAT_ID_RAW)
except ValueError:
    CHAT_ID = CHAT_ID_RAW

# --- Web-сервер ---
async def handle_root(request):
    return web.Response(text="✅ Скрипт працює")

async def handle_ping(request):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"👋 Пінг від {request.remote} у {now}")
    return web.Response(text="pong")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/ping", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Web-сервер запущено на порту {PORT}")

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
        Path(HASH_FILE).write_text(hash_value)
    except Exception as e:
        print(f"Помилка збереження хешу: {e}")

# --- Парсинг HTML для пошуку актуального URL картинки ---
async def get_actual_image_url(session):
    PAGE_URL = "https://poweron.loe.lviv.ua/shedule-off"

    try:
        async with session.get(PAGE_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                print(f"⚠️ Не вдалося завантажити HTML (HTTP {resp.status})")
                return None

            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

            img = soup.find("img", src=lambda x: x and "GPV-mobile" in x)
            if not img:
                print("⚠️ На сторінці не знайдено зображення GPV-mobile")
                return None

            src = img.get("src")

            # Якщо шлях відносний
            if src.startswith("/"):
                src = "https://poweron.loe.lviv.ua" + src

            print(f"🔍 Знайдено актуальний URL: {src}")
            return src

    except Exception as e:
        print(f"❌ Помилка парсингу HTML: {e}")
        return None

# --- Self-ping ---
async def keep_alive():
    if not EXTERNAL_URL:
        print("⚠️ EXTERNAL_URL не заданий — self-ping вимкнено")
        return

    ping_url = EXTERNAL_URL.rstrip("/") + "/ping"
    await asyncio.sleep(60)
    print(f"🔁 Self-ping активовано: {ping_url}")

    async with aiohttp.ClientSession() as session:
        while True:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                async with session.get(ping_url, timeout=10) as response:
                    if response.status == 200:
                        print(f"✅ Self-ping OK ({now})")
                    else:
                        print(f"⚠️ Self-ping статус {response.status} ({now})")
            except Exception as e:
                print(f"❌ Помилка self-ping: {e} ({now})")

            await asyncio.sleep(240)

# --- Основна логіка ---
async def check_and_send():
    last_hash = load_last_hash()

    if last_hash:
        print(f"Завантажено хеш: {last_hash[:8]}")
    else:
        print("Хеш відсутній — перший запуск")

    async with Bot(token=BOT_TOKEN) as bot:
        async with aiohttp.ClientSession() as session:
            while True:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                image_url = await get_actual_image_url(session)
                if not image_url:
                    print(f"🚫 [{now}] Не вдалося знайти URL картинки")
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue

                try:
                    async with session.get(image_url, timeout=15) as resp:
                        if resp.status != 200:
                            print(f"⚠️ [{now}] Помилка завантаження картинки: HTTP {resp.status}")
                            await asyncio.sleep(CHECK_INTERVAL)
                            continue

                        img_data = await resp.read()
                        current_hash = hashlib.md5(img_data).hexdigest()

                        if current_hash != last_hash:
                            print(f"🆕 [{now}] Новий графік! Хеш: {current_hash[:8]}")
                            try:
                                await bot.send_photo(
                                    chat_id=CHAT_ID,
                                    photo=img_data,
                                    caption="⚡ Оновлено графік відключень електроенергії"
                                )
                                last_hash = current_hash
                                save_hash(current_hash)
                                print(f"📨 [{now}] Відправлено в Telegram")
                            except TelegramError as e:
                                print(f"❌ Помилка Telegram: {e}")
                        else:
                            print(f"ℹ️ [{now}] Без змін (хеш {current_hash[:8]})")

                except Exception as e:
                    print(f"❌ [{now}] Помилка завантаження: {e}")

                await asyncio.sleep(CHECK_INTERVAL)

# --- Запуск ---
async def main():
    print("🚀 Скрипт запущено!")
    print(f"Інтервал перевірки: {CHECK_INTERVAL} сек")
    print(f"Telegram Chat ID: {CHAT_ID}")
    print(f"Self-ping URL: {EXTERNAL_URL or '—'}")
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
        print("🛑 Зупинка…")
    except Exception as e:
        import traceback
        print("💥 Критична помилка:")
        traceback.print_exc()