# GECA Study Bot: Full Project Explanation

This document explains the project in a way you can present to a teacher even if you are not very comfortable with Python yet. It covers:

- what the bot does
- which libraries are used
- how the files are organized
- how Telegram and Python divide the work
- how searching works
- how uploading works
- where the file is actually stored
- how uploader permission is extended to other people
- what each important file is responsible for
- the Python syntax and patterns used in the code
- limitations, quirks, and interview-style explanation points

## 1. Project in One Sentence

This is a Telegram bot for college students to search previous year question papers and study material, and for authorized users to upload new material. The bot stores document metadata in Supabase, while the actual file itself is hosted by Telegram and reused later through Telegram's `file_id`.

## 2. High-Level Architecture

There are really 3 systems involved:

1. Telegram
   - Students and uploaders talk to the bot in Telegram.
   - Telegram delivers messages to the bot.
   - Telegram stores uploaded files on Telegram's side.

2. Python bot application
   - This is your code.
   - It receives commands like `/search` and `/upload`.
   - It decides what to do and talks to Supabase and Telegram.

3. Supabase database
   - It stores metadata only:
     - file id from Telegram
     - file name
     - subject / branch
     - semester
     - year
     - document type
     - who uploaded it

So the design is:

`Telegram chat -> Python bot -> Supabase metadata`

and when downloading:

`Telegram chat -> Python bot -> Supabase lookup -> Telegram resend by file_id`

## 3. File Structure

The repository is small, which makes it easier to explain:

```text
python-bot/
├── README.md
├── requirements.txt
├── .env.example
├── project-explanation.md
└── bot/
    ├── __init__.py
    ├── main.py
    ├── handlers/
    │   ├── __init__.py
    │   ├── start.py
    │   ├── search.py
    │   ├── callbacks.py
    │   ├── upload.py
    │   └── manage.py
    └── services/
        ├── __init__.py
        └── database.py
```

### What each file does

`README.md`
- Human documentation for setup, commands, and SQL schema.

`requirements.txt`
- Lists the Python packages the project depends on.

`.env.example`
- Shows which environment variables must be configured.

`bot/main.py`
- Entry point of the application.
- Creates the Telegram application.
- Registers all command handlers.
- Starts polling or webhook mode.

`bot/handlers/start.py`
- Handles `/start` and `/help`.

`bot/handlers/search.py`
- Handles `/search`.
- Parses the user's text.
- Queries the database.
- Builds inline buttons for results.

`bot/handlers/callbacks.py`
- Handles inline button clicks.
- Fetches the selected document from Supabase.
- Resends the file from Telegram using `file_id`.

`bot/handlers/upload.py`
- Handles the `/upload` multi-step conversation.
- Collects branch, semester, year, type, and file.
- Saves the final document record into Supabase.

`bot/handlers/manage.py`
- Handles `/adduploader`, `/removeuploader`, `/uploaders`.
- Only the main admin can use these.

`bot/services/database.py`
- Contains the Supabase REST calls.
- This file is the "database access layer".

`__init__.py` files
- These are package marker files.
- In this project they are empty.
- Their job is mostly structural: they tell Python these folders are importable packages/modules.

## 4. Libraries Used

These are defined in `requirements.txt`.

### 4.1 `python-telegram-bot[webhooks]==21.9`

Purpose:
- This is the main Telegram bot library.
- It gives high-level Python objects such as:
  - `Application`
  - `CommandHandler`
  - `CallbackQueryHandler`
  - `ConversationHandler`
  - `MessageHandler`
  - `Update`
  - `ContextTypes`
  - inline keyboard classes

Why it matters:
- Without this library, you would have to manually call Telegram Bot API URLs, parse JSON, route commands yourself, and manage long polling/webhook logic manually.

What it gives you over plain Python:
- automatic update parsing
- command routing
- conversation state handling
- typed Telegram objects
- async integration
- built-in polling and webhook support

### 4.2 `httpx==0.27.2`

Purpose:
- Async HTTP client used to talk to Supabase REST endpoints.

Why it matters:
- Supabase is contacted over HTTP.
- The bot uses `httpx.AsyncClient(...)` to make non-blocking requests.

What it gives you over built-in Python:
- Python has built-in networking tools, but `httpx` is much easier and cleaner for modern async HTTP work.
- It integrates naturally with `async` / `await`.

### 4.3 `python-dotenv==1.0.1`

Purpose:
- Loads variables from a `.env` file into `os.environ`.

Why it matters:
- Keeps secrets out of code.
- Bot token and Supabase credentials are not hardcoded.

What it gives you over built-in Python:
- Python has `os.environ`, but not automatic loading from `.env`.
- `load_dotenv()` fills that gap.

## 5. Environment Variables

From `.env.example`, the project expects:

`BOT_TOKEN`
- Secret token given by `@BotFather`.
- This is how your bot authenticates to Telegram.

`SUPABASE_URL`
- Base URL of your Supabase project.

`SUPABASE_KEY`
- API key used to authorize requests to Supabase.

`ADMIN_USER_ID`
- Telegram numeric user id of the primary admin.
- This is the one person with full permission to manage uploaders.

`WEBHOOK_URL`
- If set, the bot runs in webhook mode.
- If empty, it runs in polling mode.

`PORT`
- Port for webhook hosting platform like Render.

## 6. Startup Logic: How the Bot Boots

The application starts from `bot/main.py`.

### Important lines

`bot/main.py:14`
- `load_dotenv()`
- Loads environment variables from `.env`.

`bot/main.py:25-27`
- Reads `BOT_TOKEN`, `WEBHOOK_URL`, and `PORT`.

`bot/main.py:31`
- `app = Application.builder().token(BOT_TOKEN).build()`
- This creates the Telegram bot application object.

This line is the practical beginning of the Telegram bot runtime.

### Handler registration

`bot/main.py:33-40`

These lines connect commands/events to functions:

- `/upload` -> `upload_handler`
- `/start` -> `start`
- `/help` -> `help_cmd`
- `/search` -> `search`
- `/adduploader` -> `add_uploader`
- `/removeuploader` -> `remove_uploader`
- `/uploaders` -> `list_uploaders`
- callback button clicks starting with `dl:` -> `handle_download`

This is the routing table of the bot.

### Polling vs webhook

`bot/main.py:42-50`

If `WEBHOOK_URL` exists:
- `app.run_webhook(...)` is used.
- Telegram sends updates to your server's URL.

If `WEBHOOK_URL` is empty:
- `app.run_polling()` is used.
- Your bot keeps asking Telegram "do you have new updates for me?"

### Why both modes exist

Polling:
- easier for local development
- no public server URL needed

Webhook:
- better for deployment on platforms like Render
- Telegram pushes updates to your app

## 7. Telegram Concepts Used in This Project

To explain the code properly, you need a few Telegram Bot API concepts.

### 7.1 Bot Token

The bot token is like the bot's password/API key.

Used at:
- `bot/main.py:25`

Without this token:
- your code cannot act as that bot
- Telegram would reject requests

### 7.2 Update

An `Update` is one event sent by Telegram to your bot.

Examples:
- a user sends `/start`
- a user sends `/search CSE sem 4`
- a user taps an inline keyboard button
- a user uploads a PDF

In the code, handler functions receive:

```python
async def some_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
```

Meaning:
- `update` = what happened
- `context` = extra info and helper utilities

### 7.3 Handlers

A handler is a rule that says:

"When this kind of Telegram update arrives, run this function."

Examples:
- `CommandHandler("search", search)`
- `CallbackQueryHandler(handle_download, pattern=r"^dl:")`
- `ConversationHandler(...)`

### 7.4 Callback Query

When the bot sends an inline keyboard button and the user taps it, Telegram sends a `callback_query` update instead of a normal message.

That is why result button clicks are handled in `bot/handlers/callbacks.py`, not in `search.py`.

### 7.5 `file_id`

This is one of the most important concepts in the whole project.

When someone sends a file to the bot:
- Telegram stores that file on Telegram's infrastructure
- Telegram includes metadata in the incoming message
- one of those fields is `file_id`

That `file_id` is a reusable identifier for that file for that bot.

Your project stores `file_id` in Supabase at:
- `bot/handlers/upload.py:123`

And later resends the file with:
- `bot/handlers/callbacks.py:33-36`

That is the key design idea of the whole project.

## 8. Where Is the File Actually Stored?

This question is central, and your teacher may ask it.

### Short answer

The actual document bytes are stored on Telegram's servers, not in your Python project and not in Supabase.

### What Supabase stores

Supabase stores only metadata:
- Telegram `file_id`
- original file name
- branch/subject
- semester
- year
- document type
- uploader id

### What Telegram stores

Telegram stores the actual uploaded file because the uploader sends the document to the bot chat inside Telegram.

### Which exact Telegram server?

Your code does not know.

Telegram does not expose to your code:
- which exact physical machine
- which exact data center
- which exact storage node

So the correct explanation is:

"The file is stored somewhere on Telegram's own infrastructure. The bot only receives a reusable `file_id`, not the real storage location."

### Important nuance

Your code does not contain a line that manually uploads the raw bytes to Telegram using `send_document`.

Instead, the upload happens when the human uploader sends a document message to the bot in Telegram chat. By the time your handler runs, Telegram has already accepted and stored the file and is now informing the bot about it.

In this project, the relevant line is:

- `bot/handlers/upload.py:117`
  - `doc = update.message.document`

This line reads the `Document` object from the incoming Telegram message. It does not upload the file. It accesses the file that Telegram already received.

Then:

- `bot/handlers/upload.py:123`
  - `doc.file_id`

This stores Telegram's reusable identifier into the database.

Later:

- `bot/handlers/callbacks.py:33-36`
  - `context.bot.send_document(... document=doc["file_id"] ...)`

This tells Telegram:

"Please resend the file you already know from this `file_id`."

So if someone asks "what line makes Telegram storage possible?"

The honest answer is:

- The actual Telegram-side upload is performed by Telegram automatically when the user sends a document to the bot chat.
- Your code captures the resulting `file_id` at `bot/handlers/upload.py:123`.
- Your code reuses that stored file later at `bot/handlers/callbacks.py:33-36`.

## 9. Database Design

The SQL shown in `README.md` defines 2 tables.

### 9.1 `documents` table

Columns:

- `id`
  - unique document record id, auto-generated UUID
- `file_id`
  - Telegram file identifier
- `file_name`
  - original file name
- `subject`
  - branch/subject label entered by uploader
- `semester`
  - semester number
- `year`
  - optional year
- `doc_type`
  - internal type key like `bundle`, `notes`, etc.
- `uploaded_by`
  - Telegram user id of uploader
- `uploaded_at`
  - timestamp

### 9.2 `uploaders` table

Columns:

- `user_id`
  - Telegram numeric user id
- `added_at`
  - timestamp of access grant

This table is the uploader allowlist.

## 10. The Database Layer in Code

The file `bot/services/database.py` isolates all Supabase communication.

This is a good architecture decision because:
- handlers stay simple
- network/database code is in one place
- logic is easier to maintain

### `_headers()`

`bot/services/database.py:17-24`

Builds the HTTP headers for Supabase:
- `apikey`
- `Authorization`
- `Content-Type`
- `Prefer`

`Prefer: return=representation`
- asks Supabase to return the inserted row after insertion

### `_base()`

`bot/services/database.py:27-28`

Builds the URL for the `documents` REST endpoint:

```python
SUPABASE_URL + "/rest/v1/documents"
```

### `insert_document(data)`

`bot/services/database.py:31-35`

What it does:
- makes HTTP `POST`
- sends JSON data to Supabase
- raises error if request failed
- returns inserted row

### `search_documents(subject, semester, year)`

`bot/services/database.py:38-51`

What it does:
- creates query parameters
- filters subject with `ilike.*subject*`
- filters semester exactly
- optionally filters year
- orders newest uploads first

Important point:
- `ilike` means case-insensitive pattern match in PostgreSQL/Supabase REST style

### `get_document(doc_id)`

`bot/services/database.py:54-60`

What it does:
- fetches one record by UUID
- returns first row or `None`

### Uploader allowlist functions

`bot/services/database.py:65-97`

These operate on the `uploaders` table:
- `is_uploader(user_id)`
- `add_uploader(user_id)`
- `remove_uploader(user_id)`
- `list_uploaders()`

This is how upload privileges are extended and managed dynamically without changing code.

## 11. `/start` and `/help`

Handled in `bot/handlers/start.py`.

This file is simple but good to mention in viva:

- `WELCOME` is a multiline string shown for `/start`
- `HELP` is a multiline string shown for `/help`
- `start(...)` replies with `WELCOME`
- `help_cmd(...)` replies with `HELP`

Python concept used here:
- string concatenation inside parentheses

Example:

```python
WELCOME = (
    "line 1"
    "line 2"
)
```

Python automatically joins adjacent string literals inside parentheses.

## 12. Search Flow in Depth

Handled in `bot/handlers/search.py`.

### Step 1: read user command arguments

`bot/handlers/search.py:28`

```python
query = " ".join(context.args).strip()
```

Meaning:
- `context.args` is the list of words after `/search`
- `" ".join(...)` joins them into one sentence
- `.strip()` removes extra spaces

Example:

If user sends:

```text
/search CSE sem 4 2025
```

Then:
- `context.args` becomes something like `["CSE", "sem", "4", "2025"]`
- after join, query becomes `"CSE sem 4 2025"`

### Step 2: validate format with regex

`bot/handlers/search.py:13-16`

```python
QUERY_RE = re.compile(
    r"^(?P<subject>.+?)\s+sem\s*(?P<sem>\d)\s*(?P<year>\d{4})?$",
    re.IGNORECASE,
)
```

This is regular expression parsing.

It means:
- capture any text as `subject`
- then the word `sem`
- then 1 digit as semester
- then optional 4-digit year

Named groups:
- `subject`
- `sem`
- `year`

Examples that match:
- `CSE sem 4`
- `CSE sem 4 2025`
- `Data Structures sem 3`

### Step 3: extract parsed values

`bot/handlers/search.py:49-51`

```python
subject = match.group("subject").strip()
semester = int(match.group("sem"))
year = int(match.group("year")) if match.group("year") else None
```

Python syntax here:

`int(...)`
- converts string to integer

`A if condition else B`
- conditional expression

`None`
- means "no value" / null-like concept in Python

### Step 4: call database search

`bot/handlers/search.py:64-65`

```python
results = await database.search_documents(subject, semester, year)
```

Why `await`?
- because this is async network I/O
- the bot can pause this task while waiting for Supabase response

### Step 5: build display text and buttons

`bot/handlers/search.py:81-95`

For each document:
- determine emoji
- determine label
- append a line to message text
- create one inline button

Important line:

`bot/handlers/search.py:91`

```python
callback_data=f"dl:{doc['id']}"
```

This stores the document UUID into the button payload.

That means when user clicks:
- the bot receives `dl:<uuid>`
- then `callbacks.py` knows exactly which document record to fetch

### Step 6: send result buttons

`bot/handlers/search.py:95`

```python
await msg.edit_text(text.strip(), reply_markup=InlineKeyboardMarkup(buttons))
```

So the "Searching..." message is edited into the final result list.

## 13. Download Flow in Depth

Handled in `bot/handlers/callbacks.py`.

This file runs when a user taps one of the inline buttons created by search.

### Step 1: get callback query

`bot/handlers/callbacks.py:12`

```python
query = update.callback_query
```

This is the button-click event object.

### Step 2: acknowledge button press

`bot/handlers/callbacks.py:13`

```python
await query.answer()
```

Telegram expects callback queries to be answered.

### Step 3: extract document id from payload

`bot/handlers/callbacks.py:15`

```python
doc_id = query.data.split(":", 1)[1]
```

If `query.data` is `dl:1234-uuid`, this extracts only the UUID part.

Python syntax:

`.split(":", 1)`
- split string only once at the first colon

### Step 4: fetch metadata from Supabase

`bot/handlers/callbacks.py:21`

```python
doc = await database.get_document(doc_id)
```

Now the bot gets:
- `file_id`
- file name
- subject
- semester
- year
- type

### Step 5: resend the Telegram file

`bot/handlers/callbacks.py:33-36`

```python
await context.bot.send_document(
    chat_id=query.message.chat_id,
    document=doc["file_id"],
    filename=doc["file_name"],
)
```

This is one of the most important code blocks in the project.

Meaning:
- send a document into the same chat
- but instead of uploading bytes from local disk, pass `document=doc["file_id"]`
- Telegram recognizes this as a known file already stored on Telegram
- Telegram sends that existing file to the user

This is efficient because:
- no local file storage required
- no need to download the document first
- no need to reupload the document every time

### Step 6: delete old result message

`bot/handlers/callbacks.py:44`

```python
await query.delete_message()
```

This removes the inline keyboard message after sending the document.

## 14. Upload Flow in Depth

Handled in `bot/handlers/upload.py`.

This is the most complex part of the bot because it is a multi-step conversation.

### 14.1 Conversation states

`bot/handlers/upload.py:18`

```python
SUBJECT, SEMESTER, YEAR, DOC_TYPE, FILE = range(5)
```

Python meaning:
- `range(5)` gives `0, 1, 2, 3, 4`
- these are assigned to the 5 variable names

So effectively:
- `SUBJECT = 0`
- `SEMESTER = 1`
- `YEAR = 2`
- `DOC_TYPE = 3`
- `FILE = 4`

These constants represent stages of the upload conversation.

### 14.2 Document type options

`bot/handlers/upload.py:20-26`

This is a list of tuples:

```python
("Class Test 1", "class_test_1")
```

Meaning:
- first value = human-friendly label shown to user
- second value = internal key stored in database

### 14.3 Primary admin check

`bot/handlers/upload.py:29-30`

```python
def _is_primary_admin(user_id: int) -> bool:
    return str(user_id) == os.environ.get("ADMIN_USER_ID", "")
```

Meaning:
- compare the Telegram user id with environment variable `ADMIN_USER_ID`
- if equal, this person is the main admin

Important design point:
- the primary admin is not stored in Supabase
- the primary admin comes from environment configuration

### 14.4 Upload permission check

`bot/handlers/upload.py:33-36`

```python
async def _can_upload(user_id: int) -> bool:
    if _is_primary_admin(user_id):
        return True
    return await database.is_uploader(user_id)
```

Logic:
- main admin can always upload
- otherwise check if user exists in Supabase `uploaders` table

This is how upload access is decided.

### 14.5 Start upload

`bot/handlers/upload.py:39-55`

When `/upload` is called:
- it checks authorization
- clears previous conversation data
- asks for branch name
- returns `SUBJECT` state

Important line:

`bot/handlers/upload.py:47`

```python
context.user_data.clear()
```

This removes previous temporary conversation values for that user.

### 14.6 Collect subject

`bot/handlers/upload.py:58-61`

```python
context.user_data["subject"] = update.message.text.strip()
```

`context.user_data` is Telegram library's per-user temporary memory.

It is being used here like a dictionary to store conversation progress.

### 14.7 Collect semester

`bot/handlers/upload.py:64-76`

Checks:
- input must be numeric

Stores:
- integer semester

Then sends inline button:
- "Skip" for year

### 14.8 Collect year or skip

Text year path:
- `bot/handlers/upload.py:79-86`

Skip path:
- `bot/handlers/upload.py:89-94`

If skipped:
- year stored as `None`

### 14.9 Ask document type

`bot/handlers/upload.py:97-104`

Creates inline keyboard from `DOC_TYPE_OPTIONS`.

Important line:

```python
InlineKeyboardButton(label, callback_data=f"type_{key}")
```

So button payload looks like:
- `type_class_test_1`
- `type_bundle`
- `type_notes`

### 14.10 Store chosen type

`bot/handlers/upload.py:107-113`

```python
doc_type = query.data.replace("type_", "")
context.user_data["doc_type"] = doc_type
```

This strips the prefix and saves the internal type key.

### 14.11 Receive file

`bot/handlers/upload.py:116-130`

This is the core upload save logic.

Important lines:

`bot/handlers/upload.py:117`

```python
doc = update.message.document
```

Meaning:
- read the uploaded Telegram document from the incoming message

`bot/handlers/upload.py:123-129`

```python
data = {
    "file_id": doc.file_id,
    "file_name": doc.file_name or "document",
    "subject": context.user_data["subject"],
    "semester": context.user_data["semester"],
    "year": context.user_data.get("year"),
    "doc_type": context.user_data["doc_type"],
    "uploaded_by": update.effective_user.id,
}
```

This creates the database row to insert.

Most important field:
- `doc.file_id`

That is the reusable Telegram file reference.

### 14.12 Save to Supabase

`bot/handlers/upload.py:132-147`

```python
result = await database.insert_document(data)
```

This writes metadata to Supabase.

The inserted row is returned, and the bot confirms success with the generated UUID.

### 14.13 End the conversation

`bot/handlers/upload.py:155`

```python
return ConversationHandler.END
```

This ends the upload process.

### 14.14 Conversation registration

`bot/handlers/upload.py:163-176`

This block configures the finite-state machine of the upload feature.

Meaning:
- entry point: `/upload`
- if current state is `SUBJECT`, text goes to `got_subject`
- if state is `SEMESTER`, text goes to `got_semester`
- if state is `YEAR`, either text year or skip callback is accepted
- if state is `DOC_TYPE`, button clicks go to `got_doc_type`
- if state is `FILE`, only document uploads are accepted
- `/cancel` aborts

This is the cleanest architecture in the project because it models a real step-by-step form.

## 15. How Upload Privilege Is Extended to Others

This is handled by `bot/handlers/manage.py`.

### Core model

There are 2 roles:

1. Primary admin
   - defined by `.env` variable `ADMIN_USER_ID`
   - full control
   - can upload
   - can add/remove/list uploaders

2. Uploaders
   - stored in Supabase `uploaders` table
   - can upload
   - cannot manage the uploader list

### How `/adduploader` works

`bot/handlers/manage.py:17-44`

Flow:

1. Check caller is primary admin
   - `bot/handlers/manage.py:18-19`

2. Check argument exists
   - `bot/handlers/manage.py:21-23`

3. Check argument is numeric
   - `bot/handlers/manage.py:25-28`

4. Convert to integer
   - `bot/handlers/manage.py:30`

5. Prevent adding the primary admin as regular uploader
   - `bot/handlers/manage.py:31-33`

6. Insert into Supabase
   - `bot/handlers/manage.py:35-38`
   - calls `database.add_uploader(user_id)`

That function is implemented at:
- `bot/services/database.py:77-80`

which POSTs:

```python
json={"user_id": user_id}
```

to the `uploaders` table endpoint.

### How `/removeuploader` works

`bot/handlers/manage.py:47-70`

Flow:
- only primary admin allowed
- parse numeric user id
- call `database.remove_uploader(user_id)`

That database function is:
- `bot/services/database.py:83-89`

It sends HTTP DELETE to Supabase with filter:

```python
params = {"user_id": f"eq.{user_id}"}
```

### How `/uploaders` works

`bot/handlers/manage.py:73-89`

Flow:
- only primary admin allowed
- fetch all uploaders
- format them into lines
- send as message

### How this connects back to `/upload`

When someone runs `/upload`, this check happens:

- `bot/handlers/upload.py:41`
  - `if not await _can_upload(user.id):`

and `_can_upload()` eventually calls:

- `bot/services/database.py:69-74`
  - `is_uploader(user_id)`

So the privilege extension mechanism is:

`primary admin command -> Supabase uploaders table -> upload permission check during /upload`

## 16. Python Syntax Explained Through This Project

Since you said you do not understand Python much, here are the major syntax ideas actually used in the code.

### 16.1 Imports

Example:

```python
import os
from telegram.ext import Application, CommandHandler
```

Meaning:
- `import os` imports a module
- `from X import Y` imports specific names from a module

### 16.2 Functions

Example:

```python
def main() -> None:
```

Meaning:
- defines a function named `main`
- `-> None` is a type hint saying it returns nothing meaningful

### 16.3 Async functions

Example:

```python
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
```

Meaning:
- asynchronous function
- used when waiting for network/database/Telegram I/O

Inside async functions you often see:

```python
await something()
```

Meaning:
- pause here until the async operation completes

### 16.4 Dictionaries

Example:

```python
data = {
    "file_id": doc.file_id,
    "semester": context.user_data["semester"],
}
```

Meaning:
- key-value storage
- similar to JSON object

### 16.5 Lists

Example:

```python
buttons = []
```

Meaning:
- ordered collection

Appending:

```python
buttons.append(...)
```

### 16.6 Tuples

Example:

```python
("Class Test 1", "class_test_1")
```

Meaning:
- fixed pair of values

### 16.7 f-strings

Example:

```python
f"Done. {user_id} can now upload documents."
```

Meaning:
- insert variable values directly into string

### 16.8 Boolean values

Python booleans:
- `True`
- `False`

Used in permission checks and conditionals.

### 16.9 Conditional statements

Example:

```python
if not context.args:
    ...
```

Meaning:
- if there are no command arguments, run this block

### 16.10 `None`

Python's null-like value.

Used here when year is skipped:
- there may be no year

### 16.11 Type hints

Example:

```python
async def get_document(doc_id: str) -> dict | None:
```

Meaning:
- `doc_id` should be a string
- return value can be either a dictionary or `None`

This helps readability and tooling, but Python does not strictly enforce it at runtime by default.

### 16.12 `range(5)`

Used at:
- `bot/handlers/upload.py:18`

Creates numbers `0,1,2,3,4`, assigned into 5 state constants.

### 16.13 `.get()` on dictionary

Example:

```python
context.user_data.get("year")
```

Meaning:
- safely read a key
- returns `None` if key does not exist

### 16.14 `or` fallback

Example:

```python
doc.file_name or "document"
```

Meaning:
- use `doc.file_name` if truthy
- otherwise use `"document"`

## 17. Telegram Features vs Built-In Python

This is a useful teacher-facing comparison.

### Built-in Python provides

- basic language syntax
- functions
- variables
- strings
- lists/dictionaries
- `os.environ`
- `logging`
- regex support through `re`
- async/await language support

### Telegram library provides

- Telegram `Update` objects
- command handling
- button click handling
- inline keyboards
- message/document abstractions
- conversation state machine
- bot methods like `send_document()`
- polling and webhook runtime

### Supabase/HTTP layer provides

- persistent storage
- remote table querying
- uploader list management
- search results storage

So a very simple way to say it is:

"Python is the language. The Telegram library gives bot powers. Supabase gives storage. `httpx` connects the bot to Supabase."

## 18. Important Quirks and Practical Behaviors

These are the kinds of things a teacher may appreciate because they show deeper understanding.

### 18.1 The bot does not store actual files locally

There is no local uploads folder.
There is no filesystem save operation.
No file bytes are written by this code.

### 18.2 Search is actually metadata search

The bot searches Supabase rows, not Telegram's file storage directly.

### 18.3 The subject field is free text

Uploader enters branch/subject manually:
- `bot/handlers/upload.py:59`

So there is no strict validation against a master branch list.

That means:
- flexible input
- but risk of inconsistent naming like `CSE`, `Computer`, `Comp`, etc.

### 18.4 Semester regex allows only one digit in search

`bot/handlers/search.py:14`

```regex
(?P<sem>\d)
```

This means only one digit semester is expected.

In your college semester system that is fine because semester is usually 1-8.

### 18.5 Authorization failure in admin commands is silent

In `manage.py`, if a non-admin uses `/adduploader`, `/removeuploader`, or `/uploaders`, the function simply returns without sending an error message.

Example:
- `bot/handlers/manage.py:18-19`

This is a design choice, but may feel confusing to users.

### 18.6 `file_id` is bot-specific

Telegram's official Bot API notes that `file_id` is specific to a bot.

That means:
- a `file_id` saved by this bot is intended for reuse by this same bot
- you generally cannot move this database to a different bot token and expect all file ids to keep working

### 18.7 `filename` during resend is presentation metadata

In `send_document(...)`, the real power is in:
- `document=doc["file_id"]`

The `filename=doc["file_name"]` part helps preserve or present the file name, but the actual content comes from Telegram's stored file referenced by `file_id`.

### 18.8 Upload conversation data is temporary

`context.user_data` is temporary per-user memory maintained by the Telegram framework runtime.

It is not permanent database storage.

Permanent storage only happens when:
- `database.insert_document(data)` is called

### 18.9 Search result buttons use document UUID, not file_id

This is a smart design.

Why use document UUID in callback instead of file_id directly?
- because the DB row contains not only file id, but also metadata
- easier to fetch one canonical record
- cleaner abstraction

## 19. Official Telegram Behavior Relevant to This Project

From Telegram Bot API documentation:

- files can be sent by `file_id`, by URL, or by multipart upload
- in this project, download/reuse happens by `file_id`
- `sendDocument` accepts a `file_id`
- `getFile` can prepare a file for download if needed

Important for your explanation:

This project does not use `getFile`, because it never needs to download the file to local disk. It simply re-sends by `file_id`.

That is an elegant design choice.

## 20. End-to-End Flow Examples

### 20.1 Search and download flow

1. Student sends `/search CSE sem 4 2025`
2. Telegram sends an update to the bot
3. `search.py` parses the text
4. `database.search_documents(...)` queries Supabase
5. Bot sends inline keyboard buttons
6. Student taps a result button
7. Telegram sends callback query update
8. `callbacks.py` extracts document UUID
9. `database.get_document(...)` fetches row from Supabase
10. `send_document(document=file_id)` tells Telegram to resend the already stored file
11. Telegram delivers the PDF/document to the student

### 20.2 Upload flow

1. Authorized uploader sends `/upload`
2. Bot checks if uploader is allowed
3. Bot asks branch
4. Bot asks semester
5. Bot asks year or skip
6. Bot asks document type
7. Uploader sends file in Telegram chat
8. Telegram stores that file and includes a `Document` object in the update
9. Bot reads `doc.file_id`
10. Bot stores metadata + `file_id` in Supabase
11. Later searches can find and resend this file

### 20.3 Grant upload access flow

1. Primary admin runs `/adduploader 123456789`
2. `manage.py` verifies caller is admin
3. Bot inserts `123456789` into Supabase `uploaders` table
4. That user can now use `/upload`
5. During `/upload`, `_can_upload()` checks `is_uploader(user_id)`

## 21. Why This Architecture Is Good for a College Project

Strengths:

- simple and understandable
- very little infrastructure
- no need to store large files yourself
- Telegram handles file hosting
- Supabase handles searchable metadata
- clear separation between handlers and database layer
- uploader permissions can be changed without redeploying

## 22. Limitations and Possible Improvements

These are useful if your teacher asks "what can be improved?"

### Current limitations

- no strict branch validation
- no duplicate detection for same document
- no edit/update document command
- no delete document command
- no pagination if many search results
- admin unauthorized actions fail silently
- search is only by subject/branch + semester + optional year
- document type label shown in upload success is internal key, not pretty label

### Good improvement ideas

- add branch dropdown / fixed branch validation
- add duplicate check on `file_id` or metadata combination
- add `/deletedoc <id>`
- add `/myuploads`
- normalize subject names
- store prettified document labels in confirmation
- add role levels beyond single admin + uploaders
- add rate limiting or audit logs

## 23. Teacher-Ready Short Explanation

If you need a compact viva answer, say this:

"This project is a Telegram bot written in Python using the `python-telegram-bot` library. It uses handlers to process commands like `/search`, `/upload`, and admin commands. Search results are stored as metadata in Supabase using REST calls through `httpx`. When an uploader sends a file to the bot, Telegram stores the actual file and gives the bot a `file_id`. My code saves that `file_id` in Supabase along with branch, semester, year, and type. Later, when a student clicks a search result button, the bot fetches the database row and calls `send_document()` with that saved `file_id`, so Telegram resends the file directly without our server storing the file locally. Upload permission is controlled by one primary admin from `.env` and an uploader allowlist stored in a Supabase table." 

## 24. Likely Viva Questions and Good Answers

### Q: Is Supabase storing the actual PDF file?

Answer:
- No. Supabase stores only metadata and the Telegram `file_id`.
- The actual file bytes are stored by Telegram.

### Q: What line stores the uploaded file?

Answer:
- The actual byte upload is done by Telegram when the user sends the document in chat.
- My code captures the resulting `file_id` at `bot/handlers/upload.py:123`.

### Q: What line sends the file back to students?

Answer:
- `bot/handlers/callbacks.py:33-36`
- `context.bot.send_document(... document=doc["file_id"] ...)`

### Q: How is uploader access extended?

Answer:
- The primary admin uses `/adduploader <user_id>`.
- That inserts the user's Telegram id into the `uploaders` table in Supabase.
- `/upload` checks this table before allowing upload.

### Q: Why use Telegram storage instead of local server storage?

Answer:
- Simpler architecture
- less storage management
- no need to host files ourselves
- faster resend using `file_id`

### Q: Why use async functions?

Answer:
- Because Telegram calls and Supabase HTTP requests are network operations.
- `async`/`await` helps the bot stay responsive while waiting for I/O.

## 25. External References

Official Telegram Bot API:
- https://core.telegram.org/bots/api

Relevant official points:
- `sendDocument` accepts `file_id`
- Telegram supports sending files by `file_id`
- files can be reused without reupload
- `getUpdates` and webhooks are the two update delivery models

Official python-telegram-bot docs:
- https://docs.python-telegram-bot.org/

## 26. Final Bottom Line

The most important conceptual summary of this project is:

- Telegram handles chat interaction and file hosting
- Python handles logic and orchestration
- Supabase handles metadata and permissions

The most important technical summary is:

- uploaders send file to bot in Telegram
- Telegram stores file and provides `file_id`
- bot saves `file_id` and metadata in Supabase
- student searches metadata
- student clicks result button
- bot fetches row and resends the Telegram file using `file_id`

That is the complete heart of the project.
