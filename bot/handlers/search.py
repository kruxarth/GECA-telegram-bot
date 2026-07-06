import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.services import database, nlp
from bot.services.database import DOC_TYPE_LABELS

logger = logging.getLogger(__name__)

TYPE_EMOJI = {
    "class_test_1": "\U0001F4DD",
    "class_test_2": "\U0001F4DD",
    "end_sem": "\U0001F4C4",
    "bundle": "\U0001F4E6",
    "notes": "\U0001F4D6",
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
    "Still couldn\N{right single quotation mark}t parse that.\n\n"
    "Please use this exact format:  <branch> sem <number>\n"
    "Example:  CSE sem 4"
)

# ---- courtesy replies (greetings / help / thanks) ----

GREETING_RE = re.compile(
    r"^(hi|hello|hey|yo|sup|good\s+(morning|afternoon|evening)|heya|helo|hii)[\s!.]*$",
    re.IGNORECASE,
)

HELP_INTENT_RE = re.compile(
    r"(what\s+(can\s+)?(you|u|this\s+bot)\s+(do|do\?)|how\s+(to|does?\s+(this|it|u))\s+(use|work|search)|help\s+me|what\s+is\s+this)",
    re.IGNORECASE,
)

THANKS_RE = re.compile(
    r"^(thanks|thank\s*(you|u|s)|thx|ty|tyvm|ok|okay|nice|good|great|awesome|cool|perfect|done)[\s!.]*$",
    re.IGNORECASE,
)

GREETING_REPLY = (
    "Hey there! \N{waving hand sign}\n\n"
    "I\N{right single quotation mark}m the GECA Study Bot. I can find past question papers "
    "and study material from your college. Just type what you need:\n\n"
    "  CSE sem 4 2025\n"
    "  end sem papers for MECH sem 5\n"
    "  3rd sem IT notes\n\n"
    "Branches: MECH \N{middle dot} ENTC \N{middle dot} EEP \N{middle dot} CSE \N{middle dot} MCA \N{middle dot} MTECH \N{middle dot} IT \N{middle dot} CIVIL\n\n"
    "Type /help for the full guide."
)

HELP_REPLY = (
    "I can find past question papers and study material for GECA students.\n\n"
    "Just type what you need in plain English:\n\n"
    "  CSE sem 4\n"
    "  end sem papers for MECH sem 5\n"
    "  class test 1 IT sem 3\n"
    "  Mechanical sem 6 notes\n\n"
    "I understand branch abbreviations (mech, cs, entc), doc types (end sem, pyq, ct1, notes, bundle), "
    "and I learn new phrases over time.\n\n"
    "Type /help for all commands and details."
)

THANKS_REPLY = (
    "Happy to help! Let me know if you need anything else. \N{thumbs up sign}"
)


def _check_courtesy_reply(text: str) -> str | None:
    if GREETING_RE.match(text):
        return GREETING_REPLY
    if HELP_INTENT_RE.search(text):
        return HELP_REPLY
    if THANKS_RE.match(text):
        return THANKS_REPLY
    return None


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
        emoji = TYPE_EMOJI.get(doc["doc_type"], "\U0001F4C4")
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
        courtesy = _check_courtesy_reply(text)
        if courtesy:
            await update.message.reply_text(courtesy)
            context.user_data["nl_pending"] = pending
            context.user_data["nl_pending_retry"] = retry_count
            await update.message.reply_text(
                "Also, about your earlier query \N{en dash} what subject and semester? (e.g., CSE sem 4)"
            )
            return

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

    courtesy = _check_courtesy_reply(text)
    if courtesy:
        await update.message.reply_text(courtesy)
        return

    params = await nlp.extract_search_params(text)
    if not params or "subject" not in params:
        context.user_data["nl_pending"] = text
        await update.message.reply_text(CLARIFY_PROMPT)
        return

    await _execute_search(update, context, params, text)
