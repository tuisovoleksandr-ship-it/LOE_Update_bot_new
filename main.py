import asyncio
import hashlib
import datetime
import os
from aiohttp import web
from telegram import Bot, TelegramError
from playwright.async_api import async_playwright

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))
PORT = int(os.environ.get("PORT", 10000))
SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")

TARGET_URL = "https://poweron.loe.lviv.ua"
IMAGE_SUBSTRING = "_GPV-mobile.png"  # шукаємо картинку, яка закінчується на це

if not BOT_TOKEN or not CHAT_ID_RAW:
    raise RuntimeError("BOT_TOKEN або CHAT_ID не задано в ENV")

try:
    CHAT_ID = int(CHAT_ID_RAW)
except ValueError:
    CHAT_ID = CHAT_ID_RAW

last_hash = None

# ---------------- WEB SERVER ----------------
async def handle_ping(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/ping", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Web server started on port {PORT}")

# ---------------- SELF-PING ----------------
async def self_ping():
    if not SELF_URL:
        print("⚠️ SELF_URL не задано, self-ping вимкнено")
        return
    while True:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                ping_url = f"{SELF_URL}/ping"
                async with session.get(ping_url) as r:
                    print(f"[{datetime.datetime.now()}] Self-ping {ping_url} -> {r.status}")
        except Exception as e:
            print("❌ Self-ping error:", e)
        await asyncio.sleep(120)

# ---------------- CHECK IMAGE ----------------
async def check_image():
    global last_hash
    async with Bot(token=BOT_TOKEN) as bot:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            while True:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    await page.goto(TARGET_URL, timeout=15000)
                    # знаходимо картинку GPV-mobile
                    img_elements = await page.query_selector_all("img")
                    img_url = None
                    for img in img_elements:
                        src = await img.get_attribute("src")
                        if src and IMAGE_SUBSTRING in src:
                            img_url = src
                            break

                    if not img_url:
                        print(f"[{now}] ❌ Картинку не знайдено на сторінці")
                        await asyncio.sleep(CHECK_INTERVAL)
                        continue

                    if not img_url.startswith("http"):
                        # робимо абсолютний URL
                        from urllib.parse import urljoin
                        img_url = urljoin(TARGET_URL, img_url)

                    # завантажуємо картинку
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img_url) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                current_hash = hashlib.md5(data).hexdigest()

                                if last_hash is None or current_hash != last_hash:
                                    print(f"[{now}] 🟢 Зміни знайдено або перший запуск: {current_hash[:8]}")
                                    try:
                                        await bot.send_photo(
                                            chat_id=CHAT_ID,
                                            photo=data,
                                            caption="⚡ Оновлення графіка відключень електроенергії"
                                        )
                                        print(f"[{now}] ✅ Зображення відправлено в Telegram")
                                        last_hash = current_hash
                                    except TelegramError as e:
                                        print(f"[{now}] ❌ Помилка Telegram: {e}")
                                    except Exception as e:
                                        print(f"[{now}] ❌ Невідома помилка: {e}")
                                else:
                                    print(f"[{now}] ℹ️ Змін немає (хеш: {current_hash[:8]})")
                            else:
                                print(f"[{now}] ❌ Помилка завантаження картинки: HTTP {resp.status}")

                except Exception as e:
                    print(f"[{now}] ❌ Помилка при перевірці картинки: {e}")

                await asyncio.sleep(CHECK_INTERVAL)

# ---------------- MAIN ----------------
async def main():
    await start_web_server()
    await asyncio.gather(
        check_image(),
        self_ping()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Скрипт зупинено")
    except Exception as e:
        import traceback
        print("💥 Критична помилка:")
        traceback.print_exc()