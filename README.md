# GECA Study Bot

A Telegram bot for students of **Government College of Engineering, Aurangabad (GECA)** to find and download past question papers and study material directly in chat.

---

## What It Does

- Students send `/search CSE sem 5 2024` and get a list of matching documents as inline buttons.
- Tapping a button delivers the file (PDF, etc.) straight into the chat — no links, no redirects.
- An admin uses `/upload` to add new documents through a guided conversation flow.
- All document metadata is stored in Supabase; files are stored as Telegram `file_id`s (Telegram hosts the actual files).

---

## Architecture

```
python-bot/
├── bot/
│   ├── main.py              # Entry point: registers handlers, runs polling or webhook
│   ├── handlers/
│   │   ├── start.py         # /start and /help
│   │   ├── search.py        # /search command — queries Supabase, returns inline buttons
│   │   ├── callbacks.py     # Inline button handler — fetches and sends the file
│   │   ├── upload.py        # /upload — multi-step ConversationHandler (uploaders only)
│   │   └── manage.py        # /adduploader, /removeuploader, /uploaders (primary admin only)
│   └── services/
│       └── database.py      # Supabase REST API calls (insert, search, get, uploader list)
├── .env                     # Secrets — NOT committed
├── .env.example             # Template — committed, fill in and rename to .env
├── requirements.txt
└── architecture.md          # Detailed architecture notes
```

### Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Telegram library | `python-telegram-bot` v21 (async) |
| Database | Supabase (PostgreSQL via REST API) |
| HTTP client | `httpx` (async) |
| Hosting | Render (free tier, webhook mode) |

### Data Flow

```
User: /search Physics sem 2
  └─→ search.py parses query (subject, semester, optional year)
      └─→ database.search_documents() — ilike match against Supabase
          └─→ results shown as inline buttons

User taps a button  (callback_data = "dl:<uuid>")
  └─→ callbacks.py fetches document row from Supabase
      └─→ bot.send_document(file_id=...) — Telegram delivers the file
```

### Upload & Access Control

There are two tiers:

- **Primary admin** — set via `ADMIN_USER_ID` in `.env`. Can upload and manage the uploader list.
- **Uploaders** — stored in the `uploaders` Supabase table. Can upload but cannot manage the list.

The primary admin adds/removes uploaders via bot commands — no redeployment needed.

```
/upload → branch/subject → semester → year (optional) → doc type → send file → saved to Supabase
/cancel at any step to abort
```

---

## Running Locally

### Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A [Supabase](https://supabase.com) project with a `documents` table (see below)

### Supabase Tables

Run both in your Supabase SQL editor:

```sql
create table documents (
  id            uuid primary key default gen_random_uuid(),
  file_id       text not null,
  file_name     text not null,
  subject       text not null,
  semester      int  not null,
  year          int,
  doc_type      text not null,
  uploaded_by   bigint,
  uploaded_at   timestamptz default now()
);

create table uploaders (
  user_id       bigint primary key,
  added_at      timestamptz default now()
);
```

### Setup

```bash
# Clone and enter the project
git clone <repo-url>
cd python-bot

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, ADMIN_USER_ID
# Leave WEBHOOK_URL empty to use polling mode locally
```

### Run

```bash
python -m bot.main
```

The bot starts in **polling mode** when `WEBHOOK_URL` is empty — no public URL needed locally.

---

## Deploying to Render

1. Push the repo to GitHub.
2. Create a new **Web Service** on [Render](https://render.com).
3. Set **Start Command** to `python -m bot.main`.
4. Add environment variables in the Render dashboard:
   - `BOT_TOKEN`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `ADMIN_USER_ID`
   - `WEBHOOK_URL` — your Render app's public URL (e.g. `https://your-app.onrender.com`)
   - `PORT` is set automatically by Render.

The bot will register its webhook on startup and switch to webhook mode automatically.

> **Free tier note:** Render spins down the service after 15 min of inactivity. The first message after a cold start takes ~30 s. Use [UptimeRobot](https://uptimerobot.com) (free) to keep it warm if needed.

---

## Commands

| Command | Description |
|---|---|
| `/start` | Introduction and quick-start |
| `/help` | Full usage guide with examples |
| `/search <branch/subject> sem <n> [year]` | Search for documents |
| `/upload` | *(Uploaders only)* Upload a new document |
| `/cancel` | Cancel an in-progress upload |
| `/adduploader <user_id>` | *(Primary admin only)* Grant upload access |
| `/removeuploader <user_id>` | *(Primary admin only)* Revoke upload access |
| `/uploaders` | *(Primary admin only)* List all uploaders |

---

## Environment Variables

See `.env.example` for a full template.

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/service key |
| `ADMIN_USER_ID` | Your Telegram user ID (find via @userinfobot) |
| `WEBHOOK_URL` | Public URL for webhook mode; leave empty for local polling |
| `PORT` | HTTP port (set automatically by Render) |

---

*College project — Government College of Engineering, Aurangabad (GECA)*
