from telegram import Update
from telegram.ext import ContextTypes

WELCOME = (
    "Welcome to the GECA Study Bot!\n\n"
    "I help students of Government College of Engineering, Aurangabad (GECA) "
    "find past question papers and study material.\n\n"
    "Available branches: MECH · ENTC · EEP · CSE · MCA · MTECH · IT · CIVIL\n\n"
    "Just type what you need in plain English — or use /search.\n\n"
    "Examples:\n"
    "  CSE sem 4 2025\n"
    "  end sem papers for MECH sem 5\n"
    "  3rd sem IT notes\n\n"
    "Type /help for full usage guide."
)

HELP = (
    "GECA Study Bot — Help\n\n"
    "BRANCHES\n"
    "────────────────────\n"
    "  MECH · ENTC · EEP · CSE · MCA · MTECH · IT · CIVIL\n\n"
    "SEARCHING\n"
    "────────────────────\n"
    "You can search in two ways:\n\n"
    "1. Natural language — just type what you need:\n"
    "     CSE sem 4 2025\n"
    "     end sem papers for MECH sem 5\n"
    "     3rd sem IT notes\n"
    "     Mechanical sem 6 ct1\n\n"
    "2. Command format:\n"
    "     /search <branch> sem <n> [year]\n"
    "     /search CSE sem 4\n"
    "     /search CSE sem 3 2025\n\n"
    "I understand branch abbreviations (mech, entc, cse...),\n"
    "doc types (end sem, pyq, ct1, ct2, notes, bundle...),\n"
    "and even learn new phrases over time!\n\n"
    "DOCUMENT TYPES\n"
    "────────────────────\n"
    "  📝 Class Test 1 — first class test papers\n"
    "  📝 Class Test 2 — second class test papers\n"
    "  📄 End Sem PYQ  — end-semester previous year papers\n"
    "  📦 Paper Bundle — full question paper bundle for the entire semester\n"
    "  📖 Notes        — lecture notes / study material\n\n"
    "HOW IT WORKS\n"
    "────────────────────\n"
    "1. Type your query (e.g., \"CSE sem 4 2025\").\n"
    "2. Tap a result button to download the file directly in chat.\n"
    "3. If I don't understand something, I'll ask you to clarify —\n"
    "   and I'll remember the correction for next time.\n\n"
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
