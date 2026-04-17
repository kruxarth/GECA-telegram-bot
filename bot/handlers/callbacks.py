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

    try:
        doc = await database.get_document(doc_id)
    except Exception as e:
        logger.error("DB fetch failed for %s: %s", doc_id, e)
        await query.edit_message_text("Failed to fetch document. Please try again.")
        return

    if not doc:
        await query.edit_message_text("Document not found.")
        return

    try:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=doc["file_id"],
            filename=doc["file_name"],
        )
        await query.delete_message()
    except Exception as e:
        logger.error("Send document failed: %s", e)
        await query.edit_message_text("Failed to send the file. Please try again.")
