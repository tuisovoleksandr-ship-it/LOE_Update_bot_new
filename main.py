import asyncio
import aiohttp
import os
import re
from datetime import datetime, timezone
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API_MEDIA = "https://api.loe.lviv.ua/media/"
CHECK_INTERVAL = 60  # секунд

bot = Bot(BOT_TOKEN)


def load_last_image():
    """Читаємо останній файл, який уже постили."""
    if not os.path.exists("last_image.txt"):
        return None
    try:
        with open("last_image.txt", "r") as f:
            return f.read().strip()
    except:
        return None


def save_last_image(url):
    """Зберігаємо файл, щоб не постити двічі."""
    with open("last_image.txt", "w") as f:
        f.write(url)


async def get_latest_image():
    """Отримуємо список файлів у каталозі /media/."""
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(API_MEDIA) as r:
                if r.status != 200:
                    print("❌ Ошибка получения списка:", r.status)
                    return None
                html = await r.text()
        except Exception as e:
            print("❌ Ошибка запроса:", e)
            return None

    # Пошук посилання на GPV-mobile
    matches = re.findall(r'href="([^"]+GPV-mobile[^"]+)"', html)

    if not matches:
        print("❌ Не найден ни один файл GPV-mobile")
        return None

    latest = matches[-1]
    return API_MEDIA + latest


async def send_to_telegram(url):
    """Відправляємо фото по URL через Bot API."""
    try:
        await bot.send_photo(chat_id=CHAT_ID, photo=url)
        print("📤 Відправлено:", url)
    except Exception as e:
        print("❌ Помилка відправки:", e)


async def main():
    last_sent = load_last_image()

    while True:
        print("\n🔄 Перевірка...", datetime.now(timezone.utc))

        url = await get_latest_image()

        if url and url != last_sent:
            print("🆕 Нове зображення:", url)
            await send_to_telegram(url)
            save_last_image(url)
            last_sent = url
        else:
            print("ℹ️ Немає оновлень")

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())