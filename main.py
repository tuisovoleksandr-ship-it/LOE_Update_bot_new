import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import os

# === КОНФІГУРАЦІЯ ===
# API_ID та API_HASH повинні належати вашому користувацькому акаунту!
# Їх можна отримати на https://my.telegram.org/auth
API_ID = 36553216
API_HASH = "300474919ffd7aabb34bbd6caf3a0d98"  # <-- ВАШ API_HASH

# Токен бота використовується лише для надсилання файлів у кінцевий чат
BOT_TOKEN = "8502860111:AAEce5oOYXpbIKynDvmnWv-ehUB39Rfw8hM" 

# Канал для моніторингу (зчитуємо як користувач)
CHANNEL = "lvivoblenergo" 
# ID чату або каналу, куди надсилати фото (надсилаємо як бот)
CHAT_ID = -1002248750730 

# Назва файлу сесії. У ньому буде зберігатися авторизація користувача.
SESSION_NAME = "user_session"
LAST_FILE = "last_id.txt"

# --- Функції для збереження/завантаження останнього ID залишаються без змін ---

def save_last(message_id):
    """Зберігає ID останнього обробленого повідомлення у файл."""
    with open(LAST_FILE, "w") as f:
        f.write(str(message_id))


def load_last():
    """Завантажує ID останнього обробленого повідомлення з файлу."""
    if not os.path.exists(LAST_FILE):
        return 0
    with open(LAST_FILE) as f:
        try:
            return int(f.read().strip())
        except ValueError:
            return 0


# --- Основна логіка ---

async def main():
    # Ініціалізуємо клієнта як користувача. 
    # Клієнт буде використовувати наш API_ID та API_HASH
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    print("⏳ Connecting to Telegram as User...")
    
    # Запускаємо клієнта. При першому запуску тут буде запит на номер телефону/код.
    await client.start()
    
    user_info = await client.get_me()
    print(f"✅ Connected as user: @{user_info.username} (ID: {user_info.id})")

    last_id = load_last()
    print(f"Loaded last processed ID: {last_id}")

    # =========================================================================
    # ВАЖЛИВО: Оскільки ми використовуємо ТОКЕН БОТА для відправки, нам потрібен 
    # окремий клієнт-бот для функції відправки. 
    # У Telethon не можна використовувати один клієнт одночасно як користувача і як бота.
    
    bot_client = TelegramClient('bot_sender', API_ID, API_HASH)
    await bot_client.start(bot_token=BOT_TOKEN)
    print(f"✅ Bot sender connected: @{(await bot_client.get_me()).username}")
    
    # =========================================================================

    while True:
        try:
            # Читаємо канал як користувач (можна читати історію)
            messages = await client.get_messages(CHANNEL, limit=1)

            if messages:
                msg = messages[0]
                
                if msg.id > last_id and msg.photo:
                    print(f"\n📸 NEW photo found (ID={msg.id}) from {CHANNEL}")
                    
                    # 1. Завантажуємо фото у пам'ять/на диск (потрібно для відправки ботом)
                    print("➡️ Downloading media...")
                    # Завантажуємо медіафайл. Telethon повертає шлях до збереженого файлу.
                    photo_path = await client.download_media(msg.photo)
                    
                    if photo_path:
                        # 2. Відправляємо фото через клієнта-бота
                        print("➡️ Sending file via Bot client...")
                        await bot_client.send_file(
                            entity=CHAT_ID,
                            file=photo_path,
                            caption=msg.text or "Нове фото"
                        )
                        print("✅ Photo sent successfully.")
                        
                        # 3. Видаляємо тимчасовий файл
                        os.remove(photo_path)
                        
                        # Зберігаємо ID лише після успішного надсилання
                        await save_last(msg.id)
                        last_id = msg.id
                        
                elif msg.id > last_id:
                    print(f"ℹ️ Skipping new message (ID={msg.id}) - not a photo.")
                    await save_last(msg.id)
                    last_id = msg.id
            else:
                print("ℹ️ No messages found (check if channel name is correct).")

        except SessionPasswordNeededError:
             # Обробка 2FA, якщо ви не ввели пароль при першому запуску
            print("❌ ERROR: Two-Factor Authentication required. Please restart and follow prompts.")
            break
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR during message check: {e}")
            
        print(f"Sleeping for 30 seconds... (Last ID: {last_id})")
        await asyncio.sleep(30)
    
    # Обов'язково закриваємо обидва клієнти при завершенні
    await client.disconnect()
    await bot_client.disconnect()


if __name__ == "__main__":
    try:
        # Для коректного завершення
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred in the runner: {e}")