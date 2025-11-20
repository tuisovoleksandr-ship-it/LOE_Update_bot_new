import asyncio
import hashlib
import datetime
import os
import aiohttp
from aiohttp import web
from telegram import Bot
from telegram.error import TelegramError

# ---------------------- CONFIG ----------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))
PORT = int(os.environ.get("PORT", 10000))
SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")

# Пряма картинка (змінюється назва файлу, якщо потрібно, можна довантажувати список)
IMAGE_URL = "https://api.loe.lviv.ua/media/691d6ab3b2c3a_GPV-mobile.png"
# -----------------------------------------------------

if not BOT_TOKEN or not CHAT_ID_RAW:
    raise RuntimeError("BOT_TOKEN або CHAT_ID не задано в ENV")

try:
    CHAT_ID = int(CHAT_ID_RAW)
except ValueError:
    CHAT_ID = CHAT_ID_RAW

last_hash = None

# ---------------------- WEB SERVER ----------------------
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

# ---------------------- SELF-PING ----------------------
async def self_ping():
    if not SELF_URL:
        print("⚠️ SELF_URL не задано, self-ping вимкнено")
        return
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                ping_url = f"{SELF_URL}/ping"
                async with session.get(ping_url) as r:
                    print(f"[{datetime.datetime.now()}] Self-ping {ping_url} -> {r.status}")
        except Exception as e:
            print("❌ Self-ping error:", e)
        await asyncio.sleep(120)

# ---------------------- CHECK IMAGE ----------------------
async def check_image():
    global last_hash
    async with Bot(token=BOT_TOKEN) as bot:
        async with aiohttp.ClientSession() as session:
            while True:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    async with session.get(IMAGE_URL) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            current_hash = hashlib.md5(data).hexdigest()

                            if last_hash is None:
                                print(f"[{now}] Перший запуск, хеш збережено: {current_hash[:8]}...")
                                last_hash = current_hash
                            elif current_hash != last_hash:
                                print(f"[{now}] 🟢 Зміни знайдено! Новий хеш: {current_hash[:8]}...")
                                try:
                                    await bot.send_photo(
                                        chat_id=CHAT_ID,
                                        photo=data,
                                        caption="⚡ Нове оновлення графіка відключень електроенергії"
                                    )
                                    print(f"[{now}] ✅ Зображення відправлено")
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

# ---------------------- MAIN ----------------------
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