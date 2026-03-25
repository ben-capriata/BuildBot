from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID
from db import get_active_tasks, get_recent_sessions
from llm import get_chat_response

MAX_HISTORY = 20  # max messages to keep in context (excluding system)


def _build_system_prompt() -> str:
    tasks = get_active_tasks()
    sessions = get_recent_sessions(limit=3)

    task_lines = "\n".join(
        f"  [{t['id']}] ({t['priority']}) {t['title']}" for t in tasks
    ) or "  No active tasks."

    session_lines = "\n".join(
        f"  {s['date']}: attempted={s['attempted']}, worked={s['worked']}"
        for s in sessions
    ) or "  No recent sessions."

    return (
        "You are BuildBot, a personal build assistant for a solo developer. "
        "You help with planning, task prioritization, debugging ideas, and build hour reflections. "
        "Be concise and direct. When you don't know something, say so.\n\n"
        f"Current active tasks:\n{task_lines}\n\n"
        f"Recent build sessions (newest first):\n{session_lines}\n\n"
        "The user can also use /tasks, /add, /done, /plan, /reflect, and /weekly for direct actions."
    )


async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    user_text = update.message.text
    history = context.user_data.setdefault("chat_history", [])

    history.append({"role": "user", "content": user_text})

    # Trim history to avoid unbounded growth
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    messages = [{"role": "system", "content": _build_system_prompt()}] + history

    response, _ = get_chat_response(messages)

    if response:
        history.append({"role": "assistant", "content": response})
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("All LLM providers are unavailable right now.")
