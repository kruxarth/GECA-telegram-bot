import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.services import database

logger = logging.getLogger(__name__)


async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    doc_id = query.data.split(":", 1)[1]

    await query.edit_message_text("Fetching document...")

    user = query.from_user
    try:
        doc = await database.get_document(doc_id)
    except Exception as e:
        logger.error("DOWNLOAD FAILED | user=%s (@%s) | doc_id=%s | error=%s", user.id, user.username or "no_username", doc_id, e)
        await query.edit_message_text("Failed to fetch document. Please try again.")
        return

    if not doc:
        logger.warning("DOWNLOAD NOT FOUND | user=%s | doc_id=%s", user.id, doc_id)
        await query.edit_message_text("Document not found.")
        return

    try:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=doc["file_id"],
            filename=doc["file_name"],
        )
        logger.info(
            "DOWNLOAD | user=%s (@%s) | file=%s | branch=%s sem=%s year=%s type=%s",
            user.id, user.username or "no_username",
            doc["file_name"], doc.get("subject"), doc.get("semester"),
            doc.get("year") or "—", doc.get("doc_type"),
        )
        await query.delete_message()
    except Exception as e:
        logger.error("DOWNLOAD SEND FAILED | user=%s | file=%s | error=%s", user.id, doc.get("file_name"), e)
        await query.edit_message_text("Failed to send the file. Please try again.")
