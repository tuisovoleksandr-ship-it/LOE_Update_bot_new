import asyncio
import hashlib
import datetime
import os
import re
import aiohttp
from aiohttp import web

# ---------------------- CONFIG ----------------------
CHECK_URL = "https://poweron.loe.lviv.ua"
CHECK_INTERVAL = 60
SELF_PING_INTERVAL = 120
PORT = int(os.environ.get("PORT", 10000))
SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
# -----------------------------------------------------

last_hash = None

async def fetch_image_url():
    """Завантажує HTML і знаходить перший <img src="...">."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(CHECK_URL, timeout=30) as resp:
                html = await resp.text()

        match = re.search(r'<img[^>]+src="([^"]+)"', html)
        if match:
            src = match.group(1)
            if src.startswith("/"):
                src = CHECK_URL.rstrip("/") + src
            return src

        return None

    except Exception as e:
        print("Помилка fetch_image_url:", e)
        return None


def hash_string(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


async def check_updates():
    global last_hash

    while True:
        try:
            img_url = await fetch_image_url()

            if img_url is None:
                print("❌ Картинку не знайдено")
            else:
                new_hash = hash_string(img_url)
                print(f"[{datetime.datetime.now()}] Поточний хеш: {new_hash}")

                if last_hash is None:
                    print("Хеш відсутній — перший запуск")
                    last_hash = new_hash
                elif new_hash != last_hash:
                    print("🟢 ЗМІНИ ЗНАЙДЕНО!")
                    last_hash = new_hash
                else:
                    print("ℹ️  Змін немає")

        except Exception as e:
            print("Помилка check_updates:", e)

        await asyncio.sleep(CHECK_INTERVAL)


async def self_ping():
    """Щоб Render не засинав."""
    if not SELF_URL:
        print("⚠️ SELF_URL не встановлено — self-ping вимкнено")
        return

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                ping_url = f"{SELF_URL}/ping"
                async with session.get(ping_url) as r:
                    print(f"[{datetime.datetime.now()}] Self-ping {ping_url} -> {r.status}")
        except Exception as e:
            print("Self-ping error:", e)

        await asyncio.sleep(SELF_PING_INTERVAL)


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


async def main():
    await start_web_server()
    await asyncio.gather(
        check_updates(),
        self_ping()
    )


if __name__ == "__main__":
    asyncio.run(main())