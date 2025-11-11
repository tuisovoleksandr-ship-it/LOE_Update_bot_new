import os
import hashlib
import asyncio
import threading
import logging
from io import BytesIO

import requests
from flask import Flask
from telegram import Bot

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# --- Конфигурация ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
IMAGE_URL = "https://api.loe.lviv.ua/media/690e8dca879d5_GPV-mobile.png"
CHECK_INTERVAL = 300  # секунд (5 минут)
PORT = int(os.environ.get("PORT", 8080))

if not BOT_TOKEN or not CHAT_ID:
    logging.error("Не заданы BOT_TOKEN или CHAT_ID в переменных окружения")
    raise RuntimeError("BOT_TOKEN и CHAT_ID обязательны")

# --- Flask сервер ---
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Скрипт живий і стежить за графіком!"

# --- Функция проверки и отправки картинки ---
async def check_and_send():
    bot = Bot(token=BOT_TOKEN)
    last_hash = None

    async with bot:
        while True:
            try:
                r = await asyncio.to_thread(requests.get, IMAGE_URL, timeout=10)
                if r.status_code == 200:
                    current_hash = hashlib.md5(r.content).hexdigest()
                    if current_hash != last_hash:
                        photo = BytesIO(r.content)
                        photo.name = "graph.png"
                        await bot.send_photo(
                            chat_id=CHAT_ID,
                            photo=photo,
                            caption="⚡ Нове оновлення графіка відключень електроенергії"
                        )
                        logging.info("🆕 Картинка відправлена")
                        last_hash = current_hash
                    else:
                        logging.info("ℹ️ Без змін")
                else:
                    logging.warning(f"⚠️ Помилка завантаження: {r.status_code}")
            except Exception as e:
                logging.error(f"❌ Помилка: {e}")

            await asyncio.sleep(CHECK_INTERVAL)

# --- Запуск асинхронного цикла в фоне ---
def start_async_loop():
    asyncio.run(check_and_send())

# --- Запуск Flask сервера и асинхронного цикла ---
if __name__ == "__main__":
    threading.Thread(target=start_async_loop, daemon=True).start()
    logging.info(f"Запуск Flask на порту {PORT}")
    app.run(host="0.0.0.0", port=PORT)
