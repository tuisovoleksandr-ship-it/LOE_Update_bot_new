import asyncio
import aiohttp
import os
from telegram import Bot
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API_MEDIA = "https://api.loe.lviv.ua/media/"
CHECK_INTERVAL = 60  # секунд

bot = Bot(BOT_TOKEN)

async def get_latest_image():
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(API_MEDIA) as r:
                if r.status != 200:
                    print("Ошибка получения списка:", r.status)
                    return None
                html = await r.text()
        except Exception as e:
            print("Ошибка запроса:", e)
            return None

    # Ищем любые файлы содержащие "GPV-mobile"
    import re
    matches = re.findall(r'href="([^"]+GPV-mobile[^"]+)"', html)

    if not matches:
        print("❌ Не найден GPV-mobile.png")
        return None

    latest = matches[-1]  # последний файл
    return API_MEDIA + latest

async def send_to_telegram(url):
    try:
        await bot.send_photo(chat_id=CHAT_ID, photo=url)
        print("📤 Отправлено:", url)
    except Exception as e:
        print("Ошибка отправки:", e)

async def main():
    last_sent = None

    while True:
        print("\n🔄 Проверка...", datetime.now(timezone.utc))

        url = await get_latest_image()

        if url and url != last_sent:
            await send_to_telegram(url)
            last_sent = url

        await asyncio.sleep(CHECK_INTERVAL)

asyncio.run(main())