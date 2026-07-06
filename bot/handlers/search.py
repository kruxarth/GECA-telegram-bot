import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.services import database, nlp
from bot.services.database import DOC_TYPE_LABELS

logger = logging.getLogger(__name__)

TYPE_EMOJI = {
    "class_test_1": "\ud83d\udcdd",
    "class_test_2": "\ud83d\udcdd",
    "end_sem": "\ud83d\udcc4",
    "bundle": "\ud83d\udce6",
    "notes": "\ud83d\udcd6",
}

USAGE_TEXT = (
    "Usage: /search <query>\n\n"
    "Branches: MECH \u00b7 ENTC \u00b7 EEP \u00b7 CSE \u00b7 MCA \u00b7 MTECH \u00b7 IT \u00b7 CIVIL\n\n"
    "Examples:\n"
    "  /search CSE sem 4\n"
    "  /search CSE sem 3 2025\n"
    "  /search end sem papers for MECH sem 5\n"
    "  /search 3rd sem IT notes\n"
    "  /search Mechanical sem 6 ct1"
)

CLARIFY_PROMPT = (
    "I couldn\u2019t understand that query.\n\n"
    "Which branch and semester are you looking for?\n"
    "Please type it like:  CSE sem 4 2025\n\n"
    "Branches: MECH | ENTC | EEP | CSE | MCA | MTECH | IT | CIVIL"
)

CLARIFY_RETRY = (
    "Still couldn\u2019t parse that.\n\n"
    "Please use this exact format:  <branch> sem <number>\n"
    "Example:  CSE sem 4"
)


# ---- shared search execution ----

def _build_summary(params: dict) -> str:
    parts = [params["subject"]]
    if params.get("semester"):
        parts.append(f"Sem {params['semester']}")
    if params.get("doc_type"):
        parts.append(DOC_TYPE_LABELS.get(params["doc_type"], params["doc_type"]))
    if params.get("year"):
        parts.append(str(params["year"]))
    return " \u00b7 ".join(parts)


async def _execute_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    params: dict,
    source_text: str,
) -> None:
    subject = params["subject"]
    semester = params.get("semester")
    year = params.get("year")
    doc_type = params.get("doc_type")

    user = update.effective_user
    logger.info(
        "SEARCH | user=%s (@%s) | raw=%r | subject=%s sem=%s year=%s type=%s",
        user.id, user.username or "no_username", source_text,
        subject, semester, year, doc_type,
    )

    summary = _build_summary(params)
    msg = await update.message.reply_text(f"Searching for {summary}\u2026")

    try:
        results = await database.search_documents(subject, semester, year, doc_type)
    except Exception as e:
        logger.error(
            "SEARCH FAILED | user=%s | params=%r | error=%s", user.id, params, e,
        )
        await msg.edit_text("Search failed. Please try again.")
        return

    if not results:
        logger.info("SEARCH NO RESULTS | user=%s | params=%r", user.id, params)
        await msg.edit_text(
            f"No documents found for {summary}.\n"
            "Try a different subject name or semester."
        )
        return

    logger.info(
        "SEARCH HIT | user=%s | params=%r | results=%d",
        user.id, params, len(results),
    )

    text = f"Found {len(results)} result(s) for {summary}:\n\n"
    buttons = []
    for doc in results:
        emoji = TYPE_EMOJI.get(doc["doc_type"], "\ud83d\udcc4")
        label = DOC_TYPE_LABELS.get(doc["doc_type"], doc["doc_type"])
        year_tag = f" {doc['year']}" if doc.get("year") else ""
        text += f"{emoji} {label}{year_tag} \u2014 {doc['file_name']}\n"
        buttons.append([
            InlineKeyboardButton(
                f"{emoji} {label}{year_tag}",
                callback_data=f"dl:{doc['id']}",
            )
        ])

    await msg.edit_text(text.strip(), reply_markup=InlineKeyboardMarkup(buttons))


# ---- /search command ----

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("nl_pending", None)
    context.user_data.pop("nl_pending_retry", None)

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(USAGE_TEXT)
        return

    params = await nlp.extract_search_params(query)
    if not params or "subject" not in params:
        context.user_data["nl_pending"] = query
        await update.message.reply_text(CLARIFY_PROMPT)
        return

    await _execute_search(update, context, params, query)


# ---- plaintext handler (commandless NL queries + clarification replies) ----

async def handle_plaintext(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()

    pending = context.user_data.pop("nl_pending", None)
    retry_count = context.user_data.pop("nl_pending_retry", 0)

    if pending is not None:
        structured = nlp.extract_search_params_static(text)
        if not structured or "subject" not in structured:
            if retry_count < 1:
                context.user_data["nl_pending"] = pending
                context.user_data["nl_pending_retry"] = retry_count + 1
                await update.message.reply_text(CLARIFY_RETRY)
                return
            await update.message.reply_text(
                "Giving up on that query. Try /search CSE sem 4 instead."
            )
            return

        await nlp.store_learned_pattern(pending, structured)
        await _execute_search(update, context, structured, pending)
        return

    params = await nlp.extract_search_params(text)
    if not params or "subject" not in params:
        context.user_data["nl_pending"] = text
        await update.message.reply_text(CLARIFY_PROMPT)
        return

    await _execute_search(update, context, params, text)
