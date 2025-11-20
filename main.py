import asyncio
from telethon import TelegramClient
from aiohttp import ClientSession
import os

# === КОНФІГУРАЦІЯ ===
BOT_TOKEN = "8502860111:AAEce5oOYXpbIKynDvmnWv-ehUB39Rfw8hM"
API_ID = 36553216
API_HASH = "300474919ffd7aabb34bbd6caf3a0d98"   # <-- ти ще повинен дати мені API_HASH !!
CHANNEL = "https://t.me/lvivoblenergo"
CHAT_ID = -1002248750730   # куди надсилати фото

LAST_FILE = "last_id.txt"


async def save_last(message_id):
    with open(LAST_FILE, "w") as f:
        f.write(str(message_id))


def load_last():
    if not os.path.exists(LAST_FILE):
        return 0
    with open(LAST_FILE) as f:
        return int(f.read())


async def send_to_telegram_photo(url):
    async with ClientSession() as session:
        async with session.get(url) as r:
            photo_bytes = await r.read()

    async with ClientSession() as session:
        await session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID},
            files={"photo": photo_bytes}
        )


async def main():
    client = TelegramClient("session", API_ID, API_HASH)

    print("⏳ Connecting to Telegram…")
    await client.start(bot_token=BOT_TOKEN)
    print("✅ Connected")

    last_id = load_last()

    while True:
        async for msg in client.iter_messages(CHANNEL, limit=1):
            if msg.id != last_id and msg.photo:
                print(f"📸 NEW photo found (ID={msg.id})")

                photo = await msg.download_media()
                if photo:
                    print("➡️ Sending to Telegram chat…")
                    await send_to_telegram_photo(msg.photo.sizes[-1].location.to_url())

                await save_last(msg.id)

        await asyncio.sleep(30)   # перевіряємо кожні 30 сек


asyncio.run(main())