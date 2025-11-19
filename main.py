import re
import requests
import hashlib
import asyncio
import aiohttp
from aiohttp import web
import os
from datetime import datetime

# -------------------------------
# Конфігурація
# -------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SELF_URL = os.environ.get("EXTERNAL_URL")  # https://your-service.onrender.com/

POWERON_URL = "https://poweron.loe.lviv.ua"
REGEX_PATTERN = r"https:\/\/api\.loe\.lviv\.ua\/media\/[A-Za-z0-9_]+_GPV-mobile\.png"

CHECK_INTERVAL = 60  # перевірка раз на 60 сек

last_hash = None


# -------------------------------
# Функція пошуку URL картинки
# -------------------------------
def extract_image_url(html: str):
    match = re.search(REGEX_PATTERN, html)
    if match:
        return match.group(0)
    return None


# -------------------------------
# Обчислення SHA256
# -------------------------------
def sha256_bytes(content: bytes):
    return hashlib.sha256(content).hexdigest()


# -------------------------------
# Відправка в Telegram
# -------------------------------
def send_photo_to_telegram(image_content):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    files = {"photo": ("gpv.png", image_content)}
    data = {"chat_id": CHAT_ID}

    try:
        response = requests.post(url, data=data, files=files)
        print("TG response:", response.text)
    except Exception as e:
        print("Помилка TG:", e)


# -------------------------------
# Основний цикл моніторингу
# -------------------------------
async def check_loop():
    global last_hash

    while True:
        try:
            print(f"[{datetime.now()}] 🔍 Перевірка poweron.loe.lviv.ua")

            # 1. Отримуємо HTML
            r = requests.get(POWERON_URL, timeout=10)
            html = r.text

            # 2. Шукаємо картинку через regex
            image_url = extract_image_url(html)
            print("Знайдений URL:", image_url)

            if not image_url:
                print("❌ Картинка не знайдена у HTML")
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            # 3. Завантажуємо саму картинку
            img = requests.get(image_url, timeout=10).content

            # 4. Обчислюємо хеш
            new_hash = sha256_bytes(img)

            # 5. Порівнюємо
            if new_hash != last_hash:
                print(f"🟢 Нове зображення! {datetime.now()}")
                last_hash = new_hash
                send_photo_to_telegram(img)
            else:
                print("Без змін")

        except Exception as e:
            print("Помилка в циклі:", e)

        # пауза
        await asyncio.sleep(CHECK_INTERVAL)


# -------------------------------
# Self-Ping (Render не засинає)
# -------------------------------
async def self_ping():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                if SELF_URL:
                    await session.get(SELF_URL)
                    print(f"[{datetime.now()}] 🔄 Self-ping")
            except:
                pass
            await asyncio.sleep(60)


# -------------------------------
# HTTP-сервер для Render
# -------------------------------
async def index(request):
    return web.Response(text="✔ Bot is running")

app = web.Application()
app.add_routes([web.get("/", index)])

# Старт
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(check_loop())
    loop.create_task(self_ping())
    web.run_app(app, host="0.0.0.0", port=10000)