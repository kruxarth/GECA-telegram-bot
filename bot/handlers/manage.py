import logging
import os

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from bot.services import database

logger = logging.getLogger(__name__)


def _is_primary_admin(user_id: int) -> bool:
    return str(user_id) == os.environ.get("ADMIN_USER_ID", "")


async def add_uploader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_primary_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /adduploader <telegram_user_id>")
        return

    raw = context.args[0]
    if not raw.isdigit():
        await update.message.reply_text("User ID must be a number. They can find it via @userinfobot.")
        return

    user_id = int(raw)
    if _is_primary_admin(user_id):
        await update.message.reply_text("That's you — you already have access as primary admin.")
        return

    try:
        await database.add_uploader(user_id)
        await update.message.reply_text(f"Done. {user_id} can now upload documents.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            await update.message.reply_text(f"{user_id} is already in the uploader list.")
        else:
            logger.error("add_uploader failed: %s", e)
            await update.message.reply_text("Something went wrong. Check logs.")


async def remove_uploader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_primary_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /removeuploader <telegram_user_id>")
        return

    raw = context.args[0]
    if not raw.isdigit():
        await update.message.reply_text("User ID must be a number.")
        return

    user_id = int(raw)
    try:
        removed = await database.remove_uploader(user_id)
        if removed:
            await update.message.reply_text(f"Removed. {user_id} can no longer upload.")
        else:
            await update.message.reply_text(f"{user_id} wasn't in the uploader list.")
    except Exception as e:
        logger.error("remove_uploader failed: %s", e)
        await update.message.reply_text("Something went wrong. Check logs.")


async def list_uploaders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_primary_admin(update.effective_user.id):
        return

    try:
        uploaders = await database.list_uploaders()
    except Exception as e:
        logger.error("list_uploaders failed: %s", e)
        await update.message.reply_text("Something went wrong. Check logs.")
        return

    if not uploaders:
        await update.message.reply_text("No additional uploaders yet. Only you (primary admin) can upload.")
        return

    lines = [f"• {u['user_id']}  (added {u['added_at'][:10]})" for u in uploaders]
    await update.message.reply_text("Current uploaders:\n\n" + "\n".join(lines))
