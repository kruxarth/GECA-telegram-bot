from telegram import Update
from telegram.ext import ContextTypes

WELCOME = (
    "Welcome to the GECA Study Bot!\n\n"
    "I help students of Government College of Engineering, Aurangabad (GECA) "
    "find past question papers and study material.\n\n"
    "Use /search to find documents.\n\n"
    "Example:\n"
    "  /search CSE sem 5 2024\n\n"
    "Type /help for full usage guide."
)

HELP = (
    "GECA Study Bot — Help\n\n"
    "COMMANDS\n"
    "────────────────────\n"
    "/search <branch/subject> sem <n> [year]\n"
    "  Search for documents by branch and semester.\n"
    "  • branch   — branch or subject name (partial match works)\n"
    "  • sem n    — semester number (1–8)\n"
    "  • year     — optional, filter to a specific year\n\n"
    "Examples:\n"
    "  /search CSE sem 5\n"
    "  /search CSE sem 5 2024\n"
    "  /search Mechanical sem 3\n\n"
    "DOCUMENT TYPES\n"
    "────────────────────\n"
    "  📝 Class Test   — in-semester class test papers\n"
    "  📄 End Sem PYQ  — end-semester previous year papers\n"
    "  📦 Paper Set    — full collection of papers for a semester\n"
    "  📖 Notes        — lecture notes / study material\n\n"
    "HOW IT WORKS\n"
    "────────────────────\n"
    "1. Run /search with your branch and semester.\n"
    "2. Tap a result button to download the file directly in chat.\n\n"
    "TIPS\n"
    "────────────────────\n"
    "• Partial names work — \"mech\" will match \"Mechanical\".\n"
    "• Leave out the year to see all available years.\n"
    "• Files are sent directly by the bot — no links, no redirects.\n\n"
    "UPLOADING DOCUMENTS\n"
    "────────────────────\n"
    "Want to upload papers for your class? Message the bot admin @kruxarth with your\n"
    "Telegram user ID (find it via @userinfobot) to get upload access."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP)
