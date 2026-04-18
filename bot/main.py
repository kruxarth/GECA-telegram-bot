import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from bot.handlers.callbacks import handle_download
from bot.handlers.manage import add_uploader, list_uploaders, remove_uploader
from bot.handlers.search import search
from bot.handlers.start import help_cmd, start
from bot.handlers.upload import upload_handler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Silence noisy HTTP-level logs from httpx and telegram internals
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.environ.get("PORT", 8080))


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(upload_handler)  # must be before generic handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("adduploader", add_uploader))
    app.add_handler(CommandHandler("removeuploader", remove_uploader))
    app.add_handler(CommandHandler("uploaders", list_uploaders))
    app.add_handler(CallbackQueryHandler(handle_download, pattern=r"^dl:"))

    if WEBHOOK_URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        app.run_polling()


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
