import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.services import database
from bot.services.database import DOC_TYPE_LABELS

logger = logging.getLogger(__name__)

# Matches: "physics sem 2" or "physics sem 2 2024" or "data structures sem 3"
QUERY_RE = re.compile(
    r"^(?P<subject>.+?)\s+sem\s*(?P<sem>\d)\s*(?P<year>\d{4})?$",
    re.IGNORECASE,
)

TYPE_EMOJI = {
    "class_test_1": "📝",
    "class_test_2": "📝",
    "end_sem": "📄",
    "bundle": "📦",
    "notes": "📖",
}


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "Usage: /search <branch> sem <number> [year]\n\n"
            "Branches: MECH · ENTC · EEP · CSE · MCA · MTECH · IT · CIVIL\n\n"
            "Examples:\n"
            "  /search CSE sem 4\n"
            "  /search CSE sem 3 2025\n"
            "  /search MECH sem 3\n"
            "  /search ENTC sem 5 2025"
        )
        return

    match = QUERY_RE.match(query)
    if not match:
        await update.message.reply_text(
            "Could not understand that query. Format: /search <branch/subject> sem <number>\n\n"
            "Example: /search CSE sem 5"
        )
        return

    subject = match.group("subject").strip()
    semester = int(match.group("sem"))
    year = int(match.group("year")) if match.group("year") else None

    user = update.effective_user
    year_str = f" {year}" if year else ""
    logger.info(
        "SEARCH | user=%s (@%s) | query=%s sem %d%s",
        user.id, user.username or "no_username", subject, semester, year_str,
    )

    msg = await update.message.reply_text(
        f"Searching for {subject} Sem {semester}{year_str}..."
    )

    try:
        results = await database.search_documents(subject, semester, year)
    except Exception as e:
        logger.error("SEARCH FAILED | user=%s | query=%s sem %d%s | error=%s", user.id, subject, semester, year_str, e)
        await msg.edit_text("Search failed. Please try again.")
        return

    if not results:
        logger.info("SEARCH NO RESULTS | user=%s | query=%s sem %d%s", user.id, subject, semester, year_str)
        await msg.edit_text(
            f"No documents found for {subject} Sem {semester}{year_str}.\n"
            "Try a different subject name or semester."
        )
        return

    logger.info("SEARCH HIT | user=%s | query=%s sem %d%s | results=%d", user.id, subject, semester, year_str, len(results))

    text = f"Found {len(results)} result(s) for {subject} Sem {semester}{year_str}:\n\n"
    buttons = []
    for doc in results:
        emoji = TYPE_EMOJI.get(doc["doc_type"], "📄")
        label = DOC_TYPE_LABELS.get(doc["doc_type"], doc["doc_type"])
        year_tag = f" {doc['year']}" if doc.get("year") else ""
        text += f"{emoji} {label}{year_tag} — {doc['file_name']}\n"
        buttons.append([
            InlineKeyboardButton(
                f"{emoji} {label}{year_tag}",
                callback_data=f"dl:{doc['id']}",
            )
        ])

    await msg.edit_text(text.strip(), reply_markup=InlineKeyboardMarkup(buttons))
