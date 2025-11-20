import asyncio
from telethon import TelegramClient
import os

# === КОНФІГУРАЦІЯ ===
# ВАЖЛИВО: Заповніть усі поля своїми даними.
BOT_TOKEN = "8502860111:AAEce5oOYXpbIKynDvmnWv-ehUB39Rfw8hM"
API_ID = 36553216
API_HASH = "300474919ffd7aabb34bbd6caf3a0d98"  # <-- ОБОВ'ЯЗКОВО ВСТАВТЕ СВІЙ API_HASH
CHANNEL = "https://t.me/lvivoblenergo"
CHAT_ID = -1002248750730  # ID чату або каналу, куди надсилати фото

LAST_FILE = "last_id.txt"


def save_last(message_id):
    """Зберігає ID останнього обробленого повідомлення у файл."""
    with open(LAST_FILE, "w") as f:
        f.write(str(message_id))


def load_last():
    """Завантажує ID останнього обробленого повідомлення з файлу."""
    if not os.path.exists(LAST_FILE):
        # Повертаємо 0, якщо файл не існує
        return 0
    with open(LAST_FILE) as f:
        try:
            return int(f.read().strip())
        except ValueError:
            # У разі помилки читання (якщо файл порожній), починаємо з 0
            return 0


async def main():
    # Використовуємо сесію 'session', авторизуємось через Bot Token
    client = TelegramClient("session", API_ID, API_HASH)

    print("⏳ Connecting to Telegram...")
    # client.start() з параметром bot_token ініціює вхід через токен
    await client.start(bot_token=BOT_TOKEN)
    print(f"✅ Connected as bot: @{(await client.get_me()).username}")

    last_id = load_last()
    print(f"Loaded last processed ID: {last_id}")

    while True:
        # Отримуємо останнє повідомлення у каналі
        # Використовуємо .get_messages, оскільки нам потрібне лише одне, а не ітератор
        messages = await client.get_messages(CHANNEL, limit=1)

        if messages:
            msg = messages[0]
            
            # Перевіряємо, чи це нове повідомлення (ID більше, ніж останній збережений)
            # і чи містить воно фото.
            if msg.id > last_id and msg.photo:
                print(f"\n📸 NEW photo found (ID={msg.id})")
                
                try:
                    # Надсилаємо фото безпосередньо за допомогою Telethon
                    # client.send_file автоматично обробляє медіаоб'єкт (msg.photo)
                    # та завантажує його до CHAT_ID
                    print("➡️ Sending photo to target chat...")
                    await client.send_file(
                        entity=CHAT_ID,
                        file=msg.photo,
                        caption=msg.text or "Нове фото" # Додаємо підпис, якщо є
                    )
                    print("✅ Photo sent successfully.")
                    
                    # Зберігаємо ID лише після успішного надсилання
                    await save_last(msg.id)
                    last_id = msg.id # Оновлюємо поточний ID
                    
                except Exception as e:
                    print(f"❌ ERROR sending message ID {msg.id}: {e}")
                    # У разі помилки не зберігаємо ID, щоб спробувати надіслати його знову
                    
            elif msg.id > last_id:
                # Якщо повідомлення нове, але не фото, просто оновлюємо останній ID,
                # щоб не обробляти його повторно.
                print(f"ℹ️ Skipping new message (ID={msg.id}) - not a photo.")
                await save_last(msg.id)
                last_id = msg.id

        # Чекаємо 30 секунд перед наступною перевіркою
        await asyncio.sleep(30)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")