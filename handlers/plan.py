from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID, SYSTEM_PROMPT
from db import get_active_tasks, get_recent_sessions
from llm import get_llm_response


def _build_user_prompt():
    tasks = get_active_tasks()
    sessions = get_recent_sessions(limit=5)

    task_lines = []
    for t in tasks:
        task_lines.append(f"- [{t['status']}] #{t['id']} {t['title']} (priority: {t['priority']})")
    task_block = "\n".join(task_lines) if task_lines else "(no active tasks)"

    session_lines = []
    for s in sessions:
        session_lines.append(
            f"- {s['date']}: attempted={s['attempted']}, "
            f"worked={s['worked']}, stuck={s['didnt_work']}"
        )
    session_block = "\n".join(session_lines) if session_lines else "(no recent sessions)"

    return (
        f"Today is {date.today().isoformat()}.\n\n"
        f"TASK BACKLOG:\n{task_block}\n\n"
        f"RECENT BUILD SESSIONS:\n{session_block}\n\n"
        f"Generate tonight's build hour plan."
    )


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    await update.message.reply_text("Generating your build hour plan...")

    user_prompt = _build_user_prompt()
    response, provider = get_llm_response(SYSTEM_PROMPT, user_prompt)

    if response:
        await update.message.reply_text(response)
    else:
        await update.message.reply_text(
            "All LLM providers are unavailable right now. Try again in a few minutes."
        )


async def generate_plan_for_scheduler(bot, chat_id):
    """Called by the scheduler to proactively send a plan."""
    user_prompt = _build_user_prompt()
    response, provider = get_llm_response(SYSTEM_PROMPT, user_prompt)

    if response:
        await bot.send_message(chat_id=chat_id, text=response)
    else:
        await bot.send_message(
            chat_id=chat_id,
            text="Could not generate today's plan — all LLM providers failed.",
        )
