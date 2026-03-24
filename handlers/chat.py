from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID
from llm import get_chat_response

CHAT_SYSTEM = (
    "You are BuildBot, a personal build assistant for a solo developer. "
    "You help with planning, task prioritization, debugging ideas, and build hour reflections. "
    "Be concise and direct. When you don't know something, say so."
)

MAX_HISTORY = 20  # max messages to keep in context (excluding system)


async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    user_text = update.message.text
    history = context.user_data.setdefault("chat_history", [])

    history.append({"role": "user", "content": user_text})

    # Trim history to avoid unbounded growth
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    messages = [{"role": "system", "content": CHAT_SYSTEM}] + history

    response, _ = get_chat_response(messages)

    if response:
        history.append({"role": "assistant", "content": response})
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("All LLM providers are unavailable right now.")
