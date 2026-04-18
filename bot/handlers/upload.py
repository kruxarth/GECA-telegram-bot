import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.services import database

logger = logging.getLogger(__name__)

SUBJECT, SEMESTER, YEAR, DOC_TYPE, FILE = range(5)

DOC_TYPE_OPTIONS = [
    ("Class Test", "class_test"),
    ("End Sem PYQ", "end_sem"),
    ("Paper Set", "bundle"),
    ("Notes", "notes"),
]


def _is_primary_admin(user_id: int) -> bool:
    return str(user_id) == os.environ.get("ADMIN_USER_ID", "")


async def _can_upload(user_id: int) -> bool:
    if _is_primary_admin(user_id):
        return True
    return await database.is_uploader(user_id)


async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _can_upload(update.effective_user.id):
        await update.message.reply_text("You are not authorized to upload documents.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "Starting upload.\n\n"
        "What is the branch name?\n"
        "Available branches: MECH · ENTC · EEP · CSE · MCA · MTECH · IT · CIVIL\n\n"
        "Tip: for a semester bundle, collect all question papers for that sem into\n"
        "a single PDF or ZIP before uploading, then choose 'Paper Bundle' as the type."
    )
    return SUBJECT


async def got_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["subject"] = update.message.text.strip()
    await update.message.reply_text("Which semester? (enter a number, e.g. 2)")
    return SEMESTER


async def got_semester(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Please enter a number for the semester.")
        return SEMESTER

    context.user_data["semester"] = int(text)
    keyboard = [[InlineKeyboardButton("Skip", callback_data="year_skip")]]
    await update.message.reply_text(
        "Which year? (e.g. 2024) — or tap Skip:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return YEAR


async def got_year_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or len(text) != 4:
        await update.message.reply_text("Enter a 4-digit year (e.g. 2024) or tap Skip.")
        return YEAR

    context.user_data["year"] = int(text)
    return await _ask_doc_type(update)


async def got_year_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["year"] = None
    await query.edit_message_text("Year skipped.")
    return await _ask_doc_type(update)


async def _ask_doc_type(update: Update) -> int:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"type_{key}")]
        for label, key in DOC_TYPE_OPTIONS
    ]
    msg = update.message or update.callback_query.message
    await msg.reply_text("What type of document?", reply_markup=InlineKeyboardMarkup(buttons))
    return DOC_TYPE


async def got_doc_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    doc_type = query.data.replace("type_", "")
    context.user_data["doc_type"] = doc_type
    await query.edit_message_text(f"Type: {doc_type}\n\nNow send the file (PDF or any format).")
    return FILE


async def got_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc = update.message.document
    if not doc:
        await update.message.reply_text("Please send a file.")
        return FILE

    data = {
        "file_id": doc.file_id,
        "file_name": doc.file_name or "document",
        "subject": context.user_data["subject"],
        "semester": context.user_data["semester"],
        "year": context.user_data.get("year"),
        "doc_type": context.user_data["doc_type"],
        "uploaded_by": update.effective_user.id,
    }

    try:
        result = await database.insert_document(data)
        await update.message.reply_text(
            f"Saved!\n\n"
            f"Subject: {data['subject']}\n"
            f"Semester: {data['semester']}\n"
            f"Year: {data['year'] or '—'}\n"
            f"Type: {data['doc_type']}\n"
            f"ID: {result['id']}"
        )
    except Exception as e:
        logger.error("Failed to save document: %s", e)
        await update.message.reply_text("Failed to save. Check logs.")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Upload cancelled.")
    return ConversationHandler.END


upload_handler = ConversationHandler(
    entry_points=[CommandHandler("upload", upload_start)],
    states={
        SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_subject)],
        SEMESTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_semester)],
        YEAR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_year_text),
            CallbackQueryHandler(got_year_skip, pattern="^year_skip$"),
        ],
        DOC_TYPE: [CallbackQueryHandler(got_doc_type, pattern=r"^type_")],
        FILE: [MessageHandler(filters.Document.ALL, got_file)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
