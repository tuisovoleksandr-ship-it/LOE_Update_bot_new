# main.py
import os
import asyncio
import hashlib
from datetime import datetime
import aiohttp
from aiohttp import web
from telegram import Bot
from telegram.error import TelegramError
from playwright.async_api import async_playwright

# -------------------------
# Конфігурація
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SELF_URL = os.environ.get("EXTERNAL_URL")  # наприклад: https://your-app.onrender.com
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))  # секунди
SITE_URL = "https://poweron.loe.lviv.ua"
IMG_SELECTOR = "img[src*='_GPV-mobile.png']"
HASH_FILE = "last_hash.txt"
WEB_PORT = int(os.environ.get("PORT", 10000))

# Валідація
if not BOT_TOKEN:
    raise RuntimeError("ENV BOT_TOKEN не заданий")
if not CHAT_ID:
    raise RuntimeError("ENV CHAT_ID не заданий")

# -------------------------
# Хеш-файли
# -------------------------
def load_last_hash():
    try:
        if os.path.exists(HASH_FILE):
            return open(HASH_FILE, "r").read().strip()
    except Exception as e:
        print("Помилка читання hash:", e)
    return None

def save_last_hash(h):
    try:
        with open(HASH_FILE, "w") as f:
            f.write(h)
    except Exception as e:
        print("Помилка збереження hash:", e)

def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

# -------------------------
# Веб-сервер для Render (/, /ping)
# -------------------------
async def handle_root(request):
    return web.Response(text="✔ LOE update bot is running")

async def handle_ping(request):
    return web.Response(text="pong")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/ping", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f"🌐 Web server started on port {WEB_PORT}")

# -------------------------
# Self-ping (щоб Render не засинав)
# -------------------------
async def self_ping_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                if SELF_URL:
                    ping_url = SELF_URL.rstrip("/") + "/ping"
                    async with session.get(ping_url, timeout=10) as resp:
                        print(f"[{datetime.now()}] Self-ping {ping_url} -> {resp.status}")
                else:
                    # якщо SELF_URL не заданий — нічого не робимо, але лишаємось живими
                    print(f"[{datetime.now()}] Self-ping skipped (EXTERNAL_URL not set)")
            except Exception as e:
                print(f"[{datetime.now()}] Self-ping error: {e}")
            await asyncio.sleep(60)

# -------------------------
# Основна логіка моніторингу (Playwright + aiohttp)
# -------------------------
async def monitor_loop():
    last_hash = load_last_hash()
    if last_hash:
        print(f"Завантажено останній хеш: {last_hash[:8]}...")
    else:
        print("Хеш відсутній — перший запуск")

    bot = Bot(token=BOT_TOKEN)
    async with bot:
        # Сесія для завантаження картинок
        async with aiohttp.ClientSession() as http_session:
            # Використовуємо один екземпляр playwright/browser і пере-відкриваємо сторінку в циклі
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                try:
                    while True:
                        try:
                            print(f"[{datetime.now()}] Перехід на {SITE_URL} ...")
                            # Заходимо на сторінку і чекаємо, поки спокійна мережа
                            await page.goto(SITE_URL, wait_until="networkidle", timeout=15000)
                        except Exception as e:
                            print(f"[{datetime.now()}] Помилка при goto: {e}")
                            await asyncio.sleep(CHECK_INTERVAL)
                            continue

                        try:
                            # Чекаємо на селектор (але не падаємо, якщо його немає)
                            await page.wait_for_selector(IMG_SELECTOR, timeout=8000)
                        except Exception:
                            # селектор не знайдено в межах часу
                            print(f"[{datetime.now()}] Селектор {IMG_SELECTOR} не знайдено на сторінці")
                            await asyncio.sleep(CHECK_INTERVAL)
                            continue

                        try:
                            img_element = await page.query_selector(IMG_SELECTOR)
                            if not img_element:
                                print(f"[{datetime.now()}] img елемент не знайдено")
                                await asyncio.sleep(CHECK_INTERVAL)
                                continue

                            img_src = await img_element.get_attribute("src")
                            if not img_src:
                                print(f"[{datetime.now()}] Атрибут src відсутній")
                                await asyncio.sleep(CHECK_INTERVAL)
                                continue

                            # Нормалізуємо URL (якщо відносний)
                            if img_src.startswith("//"):
                                img_url = "https:" + img_src
                            elif img_src.startswith("/"):
                                img_url = "https://poweron.loe.lviv.ua" + img_src
                            else:
                                img_url = img_src

                            print(f"[{datetime.now()}] Знайдено URL картинки: {img_url}")

                            # Завантажуємо картинку через aiohttp (швидко та надійно)
                            try:
                                async with http_session.get(img_url, timeout=20) as resp:
                                    if resp.status != 200:
                                        print(f"[{datetime.now()}] Помилка завантаження зображення: HTTP {resp.status}")
                                        await asyncio.sleep(CHECK_INTERVAL)
                                        continue
                                    img_bytes = await resp.read()
                            except Exception as e:
                                print(f"[{datetime.now()}] Помилка при GET зображення: {e}")
                                await asyncio.sleep(CHECK_INTERVAL)
                                continue

                            # Обчислюємо хеш
                            new_hash = sha256_bytes(img_bytes)
                            if new_hash != last_hash:
                                print(f"[{datetime.now()}] 🆕 Знайдено нове зображення (хеш {new_hash[:8]})")
                                # Надсилаємо фото в Telegram
                                try:
                                    await bot.send_photo(chat_id=CHAT_ID, photo=img_bytes,
                                                         caption=f"⚡ Оновлення графіка {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                    print(f"[{datetime.now()}] Відправлено в Telegram")
                                except TelegramError as te:
                                    print(f"[{datetime.now()}] Помилка Telegram: {te}")
                                except Exception as e:
                                    print(f"[{datetime.now()}] Невідома помилка при відправці Telegram: {e}")

                                # Зберігаємо хеш
                                last_hash = new_hash
                                save_last_hash(new_hash)
                            else:
                                print(f"[{datetime.now()}] ℹ️ Без змін (хеш {new_hash[:8]})")

                        except Exception as e:
                            print(f"[{datetime.now()}] Помилка обробки елементів на сторінці: {e}")

                        await asyncio.sleep(CHECK_INTERVAL)

                finally:
                    try:
                        await page.close()
                        await context.close()
                        await browser.close()
                    except Exception:
                        pass

# -------------------------
# Runner
# -------------------------
async def runner():
    # Запускаємо одночасно: веб-сервер (async task), self-ping і монітор
    await start_web_server()
    await asyncio.gather(
        self_ping_loop(),
        monitor_loop()
    )

if __name__ == "__main__":
    # запускаємо головну корутину
    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        print("Зупинка по KeyboardInterrupt")
    except Exception as e:
        print("Критична помилка:", e)