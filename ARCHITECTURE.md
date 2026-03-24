# BuildBot — Architecture Document

## Overview

BuildBot is a single-user personal Telegram bot designed for daily software build hour planning and reflection. It is written in Python 3.11 and runs as a long-lived async process. The bot accepts commands and free-form messages from exactly one authorized Telegram user, routes them through a multi-provider LLM fallback chain, and persists all state in a local SQLite database.

The name and purpose: a solo developer uses a nightly "build hour" to make progress on personal projects. BuildBot acts as a planning assistant, task tracker, and post-session journal, all accessible from Telegram.

---

## High-Level Architecture

```
Telegram App (user's phone)
        |
        | (HTTPS long-poll)
        v
python-telegram-bot (bot.py)
        |
        |-- Command Handlers (/plan, /tasks, /add, /done, /status, /start)
        |-- ConversationHandler (/reflect — 5-step state machine)
        |-- MessageHandler (free-form chat fallback)
        |
        v
   handlers/ (plan.py, tasks.py, reflect.py, chat.py)
        |
        |-- db.py (SQLite read/write)
        |-- llm.py (LLM provider fallback chain)
              |
              |-- Groq API      (llama-3.3-70b-versatile)
              |-- Cerebras API  (llama-3.1-70b)
              |-- Mistral API   (mistral-small-latest)

APScheduler (scheduler.py)
   |
   |-- Cron: 18:30 AST daily
   |-- Calls generate_plan_for_scheduler() -> sends plan message proactively
```

---

## External Configuration Directory

All secrets and runtime data are stored outside the repository at `~/.BuildBot/`:

```
~/.BuildBot/
    .env                    # API keys and Telegram credentials
    data/
        BuildBot.db         # SQLite database (created on first run)
    prompts/
        build_hour.txt      # System prompt for plan generation
```

### `.env` variables

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_USER_ID` | Numeric Telegram user ID of the sole authorized user |
| `GROQ_API_KEY` | API key for Groq (primary LLM provider) |
| `CEREBRAS_API_KEY` | API key for Cerebras (secondary LLM provider) |
| `MISTRAL_API_KEY` | API key for Mistral (tertiary LLM provider) |

---

## File-by-File Reference

### `bot.py` — Entry Point

The main executable. Responsibilities:

1. Calls `init_db()` to create database tables if they do not exist.
2. Builds the `python-telegram-bot` `Application` instance using the Telegram bot token.
3. Registers all handlers in priority order:
   - `ConversationHandler` for `/reflect` is registered **first** so it intercepts free-text messages during an active reflection session before the generic chat handler can.
   - Command handlers for `/start`, `/plan`, `/tasks`, `/add`, `/done`, `/status`.
   - `MessageHandler` (free-form text) registered **last** as a catch-all.
4. Uses a `post_init` hook to start the APScheduler after the application is fully initialized, avoiding event loop conflicts.
5. Runs the bot with `app.run_polling()` — a blocking async loop that long-polls the Telegram API.

**Authorization:** Every handler checks `update.effective_user.id != ALLOWED_USER_ID` and silently drops the message if it is not the authorized user. This is enforced at the handler level, not the framework level.

---

### `config.py` — Configuration and Constants

Loads and exposes all runtime configuration. Executed once at import time.

- Defines canonical directory paths (`BUILDBOT_DIR`, `DATA_DIR`, `PROMPTS_DIR`, `DB_PATH`, `ENV_PATH`) using `pathlib.Path`.
- Calls `load_dotenv(ENV_PATH)` to populate environment variables from `~/.BuildBot/.env`.
- Reads `TELEGRAM_BOT_TOKEN` and `ALLOWED_USER_ID` from the environment.
- Defines the `PROVIDERS` list — an ordered list of dicts, each containing `name`, `model`, `base_url`, and `api_key`. The order defines the fallback priority: Groq → Cerebras → Mistral.
- Loads `SYSTEM_PROMPT` by reading `~/.BuildBot/prompts/build_hour.txt`. If the file does not exist, `SYSTEM_PROMPT` is an empty string and plan generation will proceed without a system-level instruction.

---

### `db.py` — Data Layer

A thin SQLite wrapper with no ORM. All functions open a connection, execute, commit, and close — there is no connection pooling or persistent connection. Uses `sqlite3.Row` as the row factory so results can be accessed as dicts.

#### Tables

**`tasks`**

Stores the user's task backlog.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `title` | TEXT | Task name |
| `priority` | TEXT | `high`, `medium`, or `low`. Default: `medium` |
| `status` | TEXT | `todo`, `in_progress`, or `done`. Default: `todo` |
| `tags` | TEXT | Comma-separated tags. Default: empty string |
| `estimated_minutes` | INTEGER | Default: 60 |
| `created_at` | TIMESTAMP | Set by SQLite default |
| `completed_at` | TIMESTAMP | Set when task is marked done |

**`build_sessions`**

One row per completed reflection session.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `date` | TEXT | ISO date string (YYYY-MM-DD) |
| `plan` | TEXT | Reserved; not currently populated |
| `attempted` | TEXT | Answer to "What did you attempt?" |
| `worked` | TEXT | Answer to "What worked?" |
| `didnt_work` | TEXT | Answer to "What didn't work?" |
| `surprised` | TEXT | Answer to "What surprised you?" |
| `next_time` | TEXT | Answer to "What would you try next time?" |
| `build_log` | TEXT | LLM-generated summary of the session |
| `created_at` | TIMESTAMP | Set by SQLite default |

**`llm_logs`**

Audit log for every LLM API call attempt, including failures.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `timestamp` | TIMESTAMP | Set by SQLite default |
| `provider` | TEXT | `groq`, `cerebras`, or `mistral` |
| `model` | TEXT | Model name string |
| `prompt_tokens` | INTEGER | From API usage response; nullable |
| `completion_tokens` | INTEGER | From API response; nullable |
| `success` | BOOLEAN | `1` for success, `0` for failure |
| `error` | TEXT | First 500 chars of exception message on failure |

#### Functions

| Function | Description |
|---|---|
| `init_db()` | Creates all three tables if they do not exist. Called once at startup. |
| `add_task(title, priority)` | Inserts a new task, returns the new row ID. |
| `get_active_tasks()` | Returns all non-done tasks, ordered by priority (high first) then by ID. |
| `complete_task(task_id)` | Sets status to `done` and records `completed_at`. Returns `True` if a row was updated. |
| `add_build_session(...)` | Inserts a completed reflection session. |
| `get_recent_sessions(limit)` | Returns the N most recent sessions, newest first. |
| `log_llm_call(...)` | Inserts one row into `llm_logs` for every API attempt. |

---

### `llm.py` — LLM Provider Abstraction

Wraps all LLM calls. Iterates through `PROVIDERS` from `config.py` in order, skipping any provider with a missing API key. On success, updates the module-level `last_provider` variable (used by `/status`). On failure, logs the error to `llm_logs` and continues to the next provider. Returns `(None, None)` if all providers fail.

All providers expose an OpenAI-compatible `/chat/completions` endpoint, so a single `openai.OpenAI` client (with a custom `base_url`) handles all three. Each call has a 10-second timeout and a 1024-token completion limit.

#### Two call modes

**`get_llm_response(system_prompt, user_prompt)`**
Used for structured tasks (plan generation, build log synthesis) where the system and user roles are distinct. Constructs a two-message array: one `system` message and one `user` message.

**`get_chat_response(messages)`**
Used for free-form conversational chat. Accepts a pre-built message array (including history) and sends it directly, allowing multi-turn conversation context.

---

### `scheduler.py` — Background Scheduler

Uses APScheduler's `AsyncIOScheduler` to fire a daily cron job. The scheduler is started once via `start_scheduler(bot, chat_id)` and shares the same asyncio event loop as the Telegram polling loop.

- **Trigger:** `CronTrigger(hour=18, minute=30, timezone="America/Port_of_Spain")` — fires every day at 18:30 AST.
- **Action:** Creates an asyncio task that calls `generate_plan_for_scheduler(bot, chat_id)` from `handlers/plan.py`, which builds the same plan prompt as the `/plan` command and proactively sends it to the user without them having to ask.
- The job is registered with `replace_existing=True`, so restarting the bot does not create duplicate jobs.

---

### `handlers/plan.py` — Plan Generation

Handles the `/plan` command and the scheduled proactive plan delivery.

**`_build_user_prompt()`** constructs the LLM user prompt by:
1. Fetching all active tasks from the database and formatting them as a numbered list with status and priority.
2. Fetching the 5 most recent build sessions and formatting them as a summary of what was attempted and what worked or didn't.
3. Injecting today's date.
4. Appending the instruction: `"Generate tonight's build hour plan."`

This prompt is combined with `SYSTEM_PROMPT` (from `build_hour.txt`) and sent to the LLM via `get_llm_response()`.

**`plan_command()`** is the Telegram command handler. It sends an acknowledgment message ("Generating your build hour plan...") before the LLM call to give immediate feedback, since the call may take several seconds.

**`generate_plan_for_scheduler()`** is the same logic without a `Update` object — it uses `bot.send_message(chat_id=...)` directly, which is the correct method for proactive bot-initiated messages.

---

### `handlers/tasks.py` — Task Management

Three command handlers, none of which involve the LLM.

| Command | Handler | Behavior |
|---|---|---|
| `/tasks` | `tasks_command` | Fetches and displays all active tasks with status icons (⬜ todo, hammer in_progress) and priority labels. |
| `/add <title>` | `add_command` | Joins `context.args` to form the task title, inserts via `db.add_task()`, replies with the new task ID. |
| `/done <id>` | `done_command` | Parses the task ID integer, calls `db.complete_task()`, reports success or not-found. |

---

### `handlers/reflect.py` — Post-Build Reflection (ConversationHandler)

Implements a 5-step guided reflection using `python-telegram-bot`'s `ConversationHandler`, which is a state machine that intercepts the user's free-text messages until the conversation ends.

**States and flow:**

```
/reflect
    |
    v
ATTEMPTED  ("What did you attempt to build today?")
    |
    v
WORKED     ("What worked?")
    |
    v
DIDNT_WORK ("What did not work?")
    |
    v
SURPRISED  ("What surprised you?")
    |
    v
NEXT_TIME  ("What would you try next time?")
    |
    v
[LLM generates structured build log]
    |
    v
db.add_build_session() — saved to database
    |
    v
Build log sent to user
    |
    v
ConversationHandler.END
```

All five answers are accumulated in `context.user_data["reflect"]` as the conversation progresses. At the final step, all five answers are assembled into a single text block and sent to the LLM with a specific system prompt instructing it to produce a structured build log entry under 150 words.

The build log is stored in `build_sessions.build_log` regardless of whether the LLM call succeeded (a fallback message is used on failure so the raw reflection data is never lost).

The `/cancel` command is registered as a fallback that ends the conversation at any step.

**Why ConversationHandler is registered first in `bot.py`:** During an active reflection session, the user's text messages must be captured by the state machine, not routed to the generic chat handler. Handler priority in `python-telegram-bot` is determined by registration order.

---

### `handlers/chat.py` — Free-Form Chat

The catch-all handler for any non-command text message outside of an active reflection session.

- Maintains a rolling conversation history of up to 20 messages in `context.user_data["chat_history"]` (in-memory, not persisted to the database — history is lost on bot restart).
- Prepends a fixed system message identifying the assistant as "BuildBot, a personal build assistant."
- Sends the full history to the LLM via `get_chat_response()`, then appends the assistant's reply back into history.
- Caps history at 20 messages by slicing the oldest entries, preventing unbounded memory growth and token limit issues.

---

## Data Flow: `/plan` Command

```
User sends /plan
    -> plan_command() checks ALLOWED_USER_ID
    -> Sends "Generating..." acknowledgment
    -> _build_user_prompt() queries db for tasks + recent sessions
    -> get_llm_response(SYSTEM_PROMPT, user_prompt) called
        -> Tries Groq (llama-3.3-70b-versatile)
            -> On success: log_llm_call(), return response
            -> On failure: log_llm_call(success=False), try next
        -> Tries Cerebras (llama-3.1-70b) if Groq failed
        -> Tries Mistral (mistral-small-latest) if Cerebras failed
        -> Returns (None, None) if all fail
    -> Bot replies with plan text or error message
```

## Data Flow: Scheduled Daily Plan (18:30 AST)

```
APScheduler fires CronTrigger
    -> _run_plan() creates asyncio task
    -> generate_plan_for_scheduler(bot, chat_id) called
    -> Same _build_user_prompt() + get_llm_response() path as /plan
    -> bot.send_message(chat_id=...) sends result proactively
```

---

## Dependency Summary

| Package | Version Constraint | Purpose |
|---|---|---|
| `python-telegram-bot` | >=21.0 | Telegram Bot API client and async framework |
| `openai` | >=1.0 | OpenAI-compatible HTTP client for all LLM providers |
| `python-dotenv` | any | Loads `.env` file into environment variables |
| `apscheduler` | >=3.10 | In-process async job scheduler for the daily cron |

All LLM providers (Groq, Cerebras, Mistral) are accessed through the `openai` package by overriding `base_url` — no provider-specific SDKs are required.

---

## Security and Access Control

- The bot is single-user. Every handler independently checks the incoming Telegram user ID against `ALLOWED_USER_ID` and returns silently without responding to any unauthorized user.
- All secrets (bot token, API keys, user ID) are stored in `~/.BuildBot/.env`, outside the repository, and never appear in source code.
- The SQLite database is stored in `~/.BuildBot/data/` on the local filesystem. There is no network-exposed database.
- No web server or publicly exposed port is required. The bot communicates outbound only, via Telegram's long-polling mechanism.

---

## Startup Sequence

```
python bot.py
    1. init_db()           — creates ~/.BuildBot/data/BuildBot.db and tables if missing
    2. Application.build() — initializes Telegram client with bot token
    3. Register handlers   — ConversationHandler, commands, chat fallback
    4. post_init()         — start_scheduler() attaches APScheduler to the event loop
    5. run_polling()       — enters the async event loop, begins long-polling Telegram
```

---

## Limitations and Design Decisions

- **No persistence of chat history.** Free-form conversation context (`context.user_data`) is stored in memory and reset on every bot restart. This is intentional for simplicity.
- **Single-connection SQLite.** Each database function opens and closes its own connection. This is safe for a single-user bot with no concurrent writes.
- **LLM provider fallback is sequential, not parallel.** If Groq is slow, the user waits for the Groq timeout before Cerebras is tried. The 10-second per-provider timeout means worst-case latency is 30 seconds if all three providers fail.
- **No task editing.** Tasks can be added and marked complete but not edited or reprioritized after creation.
- **`tasks.tags` and `tasks.estimated_minutes` are defined in the schema but not exposed via any command.** They are reserved for future use.
- **`build_sessions.plan` column exists in the schema but is never populated.** It is reserved for future use to store the plan that was generated before a session.
