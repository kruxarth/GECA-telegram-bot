from telegram import Update
from telegram.ext import ContextTypes

WELCOME = (
    "Welcome to the GECA Study Bot!\n\n"
    "I help students of Government College of Engineering, Aurangabad (GECA) "
    "find past question papers and study material.\n\n"
    "Available branches: MECH · ENTC · EEP · CSE · MCA · MTECH · IT · CIVIL\n\n"
    "Use /search to find documents.\n\n"
    "Example:\n"
    "  /search CSE sem 5 2024\n\n"
    "Type /help for full usage guide."
)

HELP = (
    "GECA Study Bot — Help\n\n"
    "BRANCHES\n"
    "────────────────────\n"
    "  MECH · ENTC · EEP · CSE · MCA · MTECH · IT · CIVIL\n\n"
    "COMMANDS\n"
    "────────────────────\n"
    "/search <branch> sem <n> [year]\n"
    "  Search for documents by branch and semester.\n"
    "  • branch   — branch name from the list above (partial match works)\n"
    "  • sem n    — semester number (1–8)\n"
    "  • year     — optional, filter to a specific year\n\n"
    "Examples:\n"
    "  /search CSE sem 5\n"
    "  /search CSE sem 5 2024\n"
    "  /search MECH sem 3\n"
    "  /search ENTC sem 4 2023\n\n"
    "DOCUMENT TYPES\n"
    "────────────────────\n"
    "  📝 Class Test   — in-semester class test papers\n"
    "  📄 End Sem PYQ  — end-semester previous year papers\n"
    "  📦 Paper Bundle — full question paper bundle for the entire semester\n"
    "  📖 Notes        — lecture notes / study material\n\n"
    "HOW IT WORKS\n"
    "────────────────────\n"
    "1. Run /search with your branch and semester.\n"
    "2. Tap a result button to download the file directly in chat.\n\n"
    "HOW BUNDLES WORK\n"
    "────────────────────\n"
    "Uploaders collect all question papers for an entire semester into a single\n"
    "PDF/ZIP bundle and upload it as a 📦 Paper Bundle. This means you get every\n"
    "paper for that sem in one download — no hunting for individual files.\n\n"
    "TIPS\n"
    "────────────────────\n"
    "• Partial names work — \"mech\" will match \"MECH\".\n"
    "• Leave out the year to see all available years.\n"
    "• Files are sent directly by the bot — no links, no redirects.\n\n"
    "UPLOADING DOCUMENTS\n"
    "────────────────────\n"
    "Have question papers for your semester? You can contribute!\n"
    "• Collect all papers for the semester into one bundle (PDF or ZIP).\n"
    "• Message the bot admin @kruxarth with your Telegram user ID\n"
    "  (find it via @userinfobot) to get upload access.\n"
    "• Once authorized, use /upload to submit your bundle."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP)
