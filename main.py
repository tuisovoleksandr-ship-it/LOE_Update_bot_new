import asyncio
import hashlib
import os
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from playwright.async_api import async_playwright

# -------------------------------
# Конфигурация
# -------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SELF_URL = os.environ.get("EXTERNAL_URL")  # https://your-app.onrender.com

CHECK_INTERVAL = 300  # интервал проверки в секундах
SITE_URL = "https://poweron.loe.lviv.ua"
IMG_SELECTOR = "img[src*='_GPV-mobile.png']"

last_hash = None

# -------------------------------
# Функция для хеша картинки
# -------------------------------
def sha256_bytes(content: bytes):
    return hashlib.sha256(content).hexdigest()

# -------------------------------
# Отправка в Telegram
# -------------------------------
async def send_photo(bot: Bot, img_content):
    try:
        await bot.send_photo(
            chat_id=CHAT_ID,
            photo=img_content,
            caption="⚡ Новое обновление графика отключений электроэнергии"
        )
        print(f"✅ [{datetime.now()}] Фото отправлено")
    except TelegramError as e:
        print(f"❌ Ошибка Telegram: {e}")
    except Exception as e:
        print(f"❌ Неизвестная ошибка при отправке: {e}")

# -------------------------------
# Проверка страницы
# -------------------------------
async def check_page(bot: Bot):
    global last_hash
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(SITE_URL)
        await page.wait_for_selector(IMG_SELECTOR, timeout=10000)

        img_element = await page.query_selector(IMG_SELECTOR)
        if img_element is None:
            print(f"❌ [{datetime.now()}] Картинка не найдена")
            await browser.close()
            return

        img_url = await img_element.get_attribute("src")
        print(f"Найден URL картинки: {img_url}")

        # Скачиваем картинку
        img_bytes = await page.evaluate("""async (url) => {
            const res = await fetch(url);
            const buf = await res.arrayBuffer();
            return Array.from(new Uint8Array(buf));
        }""", img_url)
        img_content = bytes(img_bytes)

        # Проверяем хеш
        current_hash = sha256_bytes(img_content)
        if current_hash != last_hash:
            print(f"🟢 [{datetime.now()}] Обнаружено новое изображение")
            last_hash = current_hash
            await send_photo(bot, img_content)
        else:
            print(f"ℹ️ [{datetime.now()}] Без изменений (хеш {current_hash[:8]}...)")

        await browser.close()

# -------------------------------
# Основной цикл
# -------------------------------
async def main_loop():
    bot = Bot(token=BOT_TOKEN)
    async with bot:
        while True:
            try:
                await check_page(bot)
            except Exception as e:
                print(f"❌ Ошибка в основном цикле: {e}")
            await asyncio.sleep(CHECK_INTERVAL)

# -------------------------------
# Self-ping для Render
# -------------------------------
async def self_ping():
    import aiohttp
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
# Запуск
# -------------------------------
if __name__ == "__main__":
    asyncio.run(asyncio.gather(main_loop(), self_ping()))