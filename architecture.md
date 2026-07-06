# Architecture

## Purpose

This repository contains a Telegram study-material bot for GECA students. It lets users search for uploaded documents, download them directly in chat, and allows a small authorized set of users to upload new material.

The bot itself does not store binary files. Telegram stores the uploaded document, and this app stores Telegram `file_id` metadata plus searchable attributes in Supabase.

## Runtime Shape

The executable entrypoint is [bot/main.py](/home/krutarth/coding/pp/python-bot/bot/main.py). It:

- loads environment variables with `python-dotenv`
- builds a `python-telegram-bot` `Application`
- registers command, callback, conversation, and message handlers
- starts either webhook mode or polling mode

Runtime mode is controlled by `WEBHOOK_URL`:

- if `WEBHOOK_URL` is set, the bot runs `app.run_webhook(...)`
- if `WEBHOOK_URL` is empty, the bot falls back to `app.run_polling()`

The deployed production path is webhook mode. Telegram posts updates to `/{BOT_TOKEN}` on the public app URL.

## High-Level Flow

### Search flow (natural language)

1. User types a query — either `/search CSE sem 4` or just plain text like `end sem papers for MECH sem 5`.
2. [bot/handlers/search.py](/home/krutarth/coding/pp/python-bot/bot/handlers/search.py) passes the query to `nlp.extract_search_params()`.
3. [bot/services/nlp.py](/home/krutarth/coding/pp/python-bot/bot/services/nlp.py) runs a 4-tier extraction pipeline:
   - **Tier 1 (regex)**: matches the original `/search <subject> sem <n>` format and common variants.
   - **Tier 2 (keyword scanner)**: scans for known branch aliases, doc type keywords, and numbers regardless of word order.
   - **Tier 3 (fuzzy)**: catches typos via `difflib.get_close_matches` for unrecognized branch names.
   - **Tier 4 (learned patterns)**: queries the `learned_patterns` Supabase table for previously clarified queries that match by token overlap.
4. If all tiers fail, the bot asks the user to clarify ("Which branch and semester?"), parses the structured reply, stores the mapping in `learned_patterns` for next time, and proceeds with the search.
5. The handler calls `database.search_documents(subject, semester, year, doc_type)`.
6. [bot/services/database.py](/home/krutarth/coding/pp/python-bot/bot/services/database.py) issues a REST request to Supabase `documents`.
7. Matching rows are rendered as inline keyboard buttons with callback data shaped like `dl:<uuid>`.

### Download flow

1. User taps an inline result button.
2. [bot/handlers/callbacks.py](/home/krutarth/coding/pp/python-bot/bot/handlers/callbacks.py) extracts the document UUID from callback data.
3. The handler loads the row via `database.get_document(...)`.
4. The bot calls `context.bot.send_document(...)` with the stored Telegram `file_id`.
5. Telegram delivers the original file back into the chat without this app proxying the file contents.

### Upload flow

1. Authorized user sends `/upload`.
2. [bot/handlers/upload.py](/home/krutarth/coding/pp/python-bot/bot/handlers/upload.py) checks access.
3. A `ConversationHandler` collects:
   - subject / branch
   - semester
   - optional year
   - document type
   - Telegram document
4. The handler writes a new row through `database.insert_document(...)`.
5. Supabase stores metadata; Telegram remains the file host.

### Uploader management flow

Primary admin commands are implemented in [bot/handlers/manage.py](/home/krutarth/coding/pp/python-bot/bot/handlers/manage.py):

- `/adduploader <user_id>`
- `/removeuploader <user_id>`
- `/uploaders`

The primary admin is not stored in the database. That identity comes from `ADMIN_USER_ID` in environment variables. Additional uploaders live in the Supabase `uploaders` table.

## Module Responsibilities

### [bot/main.py](/home/krutarth/coding/pp/python-bot/bot/main.py)

- config loading
- logging setup
- handler registration
- polling vs webhook startup

Handler registration order matters: `upload_handler` (ConversationHandler) must be first to intercept upload conversation messages before the generic `MessageHandler` for plaintext NL queries.

This file is the first place to inspect when deployment behavior changes.

### [bot/handlers/start.py](/home/krutarth/coding/pp/python-bot/bot/handlers/start.py)

- static `/start` and `/help` responses
- no I/O besides replying to Telegram

### [bot/handlers/search.py](/home/krutarth/coding/pp/python-bot/bot/handlers/search.py)

- `/search` command handler — delegates to `nlp.extract_search_params()` and renders results
- plaintext `MessageHandler` — treats any non-command text as a natural language search query
- clarification flow — when extraction fails, prompts the user for structured input and stores the learned mapping
- shared `_execute_search()` function that queries Supabase and renders inline keyboard results
- handles `doc_type` filtering on search results

### [bot/handlers/callbacks.py](/home/krutarth/coding/pp/python-bot/bot/handlers/callbacks.py)

- handles `dl:<uuid>` callback payloads
- fetches metadata for one document
- sends the corresponding Telegram file

### [bot/handlers/upload.py](/home/krutarth/coding/pp/python-bot/bot/handlers/upload.py)

- owns the upload conversation state machine
- checks whether the caller is the primary admin or an allowed uploader
- persists uploaded document metadata

Conversation states are:

- `SUBJECT`
- `SEMESTER`
- `YEAR`
- `DOC_TYPE`
- `FILE`

### [bot/handlers/manage.py](/home/krutarth/coding/pp/python-bot/bot/handlers/manage.py)

- uploader allowlist administration
- primary-admin-only command gate

### [bot/services/database.py](/home/krutarth/coding/pp/python-bot/bot/services/database.py)

- wraps all Supabase REST calls
- builds request headers from `SUPABASE_KEY`
- targets three REST resources:
  - `/rest/v1/documents` — insert, search (with optional `doc_type` and `semester` filters), get-by-id
  - `/rest/v1/uploaders` — CRUD for uploader allowlist
  - `/rest/v1/learned_patterns` — search by token overlap, insert, delete, list-all

The code uses plain `httpx.AsyncClient` calls rather than the Supabase Python SDK. That keeps dependencies small but means auth headers, query params, and error handling are hand-written here.

### [bot/services/nlp.py](/home/krutarth/coding/pp/python-bot/bot/services/nlp.py)

- **Keyword knowledge base**: dictionaries of branch aliases (`"mech" → "MECH"`, `"computer science" → "CSE"`, etc.), document type aliases (`"pyq" → "end_sem"`, `"ct1" → "class_test_1"`, etc.), and stopwords for token filtering.
- **4-tier extraction pipeline**:
  1. Regex patterns (original format + 4 variants: sem-first, implicit sem, with doc type, ordinal)
  2. Keyword scanner — greedy longest-first entity matching, number classification (1-8 = semester, 4-digit 20xx = year), proximity heuristics for semester disambiguation
  3. Fuzzy matching — `difflib.get_close_matches` on words ≥4 chars for typo correction
  4. Learned patterns — queries Supabase `learned_patterns` table, matches by Jaccard similarity on token sets
- **Self-improvement**: `store_learned_pattern()` persists successful clarifications to Supabase
- **Tokenization**: `tokenize_query()` strips stopwords and extracts significant tokens for pattern matching
- **Zero external dependencies** — uses only `re` and `difflib` from stdlib

## Data Model

### `documents`

Expected columns:

- `id uuid primary key default gen_random_uuid()`
- `file_id text not null`
- `file_name text not null`
- `subject text not null`
- `semester int` (optional — search works without a semester filter)
- `year int`
- `doc_type text not null`
- `uploaded_by bigint`
- `uploaded_at timestamptz default now()`

Meaning:

- `file_id` is the Telegram-hosted file reference used for re-sending
- `subject` is effectively the branch label entered by uploaders
- `doc_type` is an internal enum-like string such as `bundle` or `end_sem`

### `uploaders`

Expected columns:

- `user_id bigint primary key`
- `added_at timestamptz default now()`

### `learned_patterns`

Expected columns:

- `id uuid primary key default gen_random_uuid()`
- `tokens text[] not null` — significant tokens from the user's original query (stopwords stripped)
- `subject text not null` — canonical branch name learned from clarification
- `semester int` — nullable
- `year int` — nullable
- `doc_type text` — nullable
- `source_query text not null` — the original query text that failed to parse
- `learned_at timestamptz default now()`

Index: GIN index on `tokens` for fast overlap queries.

## External Dependencies

### Telegram Bot API

Used through `python-telegram-bot`. Telegram is responsible for:

- receiving user messages
- delivering webhook updates
- storing uploaded document binaries
- re-serving files by `file_id`

### Supabase REST API

Used as the persistent metadata store. All reads and writes go through REST calls rather than direct SQL from the app.

## Deployment Notes

### Environment variables

Current runtime expects:

- `BOT_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `ADMIN_USER_ID`
- `WEBHOOK_URL`
- `PORT`

No new environment variables were added for the NL feature.

### Idle-host keepalive

Some free hosting platforms suspend the app after inactivity. This repo includes:

- [scripts/keepalive_ping.py](/home/krutarth/coding/pp/python-bot/scripts/keepalive_ping.py) for manual cron-style pinging
- [.github/workflows/keepalive.yml](/home/krutarth/coding/pp/python-bot/.github/workflows/keepalive.yml) to send a scheduled request every 14 minutes (at minutes 0, 14, 28, 42, 56 of every hour)

The workflow expects a GitHub Actions secret named `KEEPALIVE_URL`, usually set to the deployed app URL such as `https://your-app.example.com`.

Even if that URL returns a `404`, it still proves the host woke up and processed an HTTP request, which is enough for most idle timers. Only `5xx` responses are treated as failure by the bundled keepalive automation.

## Current Constraints And Risks

- Search input and stored `subject` values are free text, so branch naming consistency depends on uploader discipline.
- The bot trusts environment variables at import time. Missing required env vars fail fast during startup.
- There are no automated tests in the repository.
- The `learned_patterns` table must exist in Supabase for the self-improvement feature to persist patterns; without it the feature degrades gracefully (patterns are not saved, but search still works).
- The repository contains a local `venv/`, which is useful for inspection here but should usually stay out of version control in a normal repo.
- Webhook mode depends on the hosting platform exposing the configured `PORT` and public `WEBHOOK_URL`.

## Good Starting Points For Future Agents

When debugging:

- startup or deployment issue: inspect [bot/main.py](/home/krutarth/coding/pp/python-bot/bot/main.py)
- search / NL parsing issue: inspect [bot/handlers/search.py](/home/krutarth/coding/pp/python-bot/bot/handlers/search.py) and [bot/services/nlp.py](/home/krutarth/coding/pp/python-bot/bot/services/nlp.py)
- database query issue: inspect [bot/services/database.py](/home/krutarth/coding/pp/python-bot/bot/services/database.py)
- upload permission issue: inspect [bot/handlers/upload.py](/home/krutarth/coding/pp/python-bot/bot/handlers/upload.py) and [bot/handlers/manage.py](/home/krutarth/coding/pp/python-bot/bot/handlers/manage.py)
- document delivery issue: inspect [bot/handlers/callbacks.py](/home/krutarth/coding/pp/python-bot/bot/handlers/callbacks.py)

When extending:

- add new branch aliases or doc type aliases in [bot/services/nlp.py](/home/krutarth/coding/pp/python-bot/bot/services/nlp.py) `BRANCH_ALIASES` and `DOC_TYPE_ALIASES` dictionaries
- add new commands by registering new handlers in [bot/main.py](/home/krutarth/coding/pp/python-bot/bot/main.py)
- add new persistence behavior in [bot/services/database.py](/home/krutarth/coding/pp/python-bot/bot/services/database.py) rather than spreading raw Supabase calls across handlers
- keep Telegram-specific interaction logic in handlers and HTTP/database logic in services
