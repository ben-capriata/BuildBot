from datetime import date, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID
from db import get_active_tasks, get_sessions_since
from llm import get_llm_response

WEEKLY_SYSTEM_PROMPT = """\
You are a build hour retrospective coach for a solo developer.
Analyze their week of build sessions and write a concise weekly review with three sections:

**This Week** — what was accomplished and shipped (2-4 bullets)
**Patterns** — recurring themes, blockers, or habits you notice (1-3 bullets)
**Next Week** — 1-2 specific focus suggestions based on momentum and active tasks

Be honest, direct, and encouraging. Keep it under 200 words.\
"""


def _build_weekly_prompt(sessions, tasks):
    start_date = (date.today() - timedelta(days=7)).isoformat()
    today = date.today().isoformat()

    session_lines = []
    for s in sessions:
        session_lines.append(
            f"- {s['date']}: attempted={s['attempted']}, "
            f"worked={s['worked']}, didnt_work={s['didnt_work']}, "
            f"summary={s['build_log']}"
        )
    session_block = "\n".join(session_lines)

    task_lines = [
        f"- [{t['status']}] #{t['id']} {t['title']} (priority: {t['priority']})"
        for t in tasks
    ]
    task_block = "\n".join(task_lines) if task_lines else "(no active tasks)"

    return (
        f"Week of {start_date} to {today}.\n\n"
        f"BUILD SESSIONS ({len(sessions)} sessions):\n{session_block}\n\n"
        f"CURRENT TASK BACKLOG:\n{task_block}\n\n"
        f"Generate the weekly review."
    )


async def weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    sessions = get_sessions_since(days=7)
    if not sessions:
        await update.message.reply_text(
            "No build sessions this week. Run /reflect after your next session to start tracking."
        )
        return

    await update.message.reply_text("Generating your weekly digest...")

    tasks = get_active_tasks()
    user_prompt = _build_weekly_prompt(sessions, tasks)
    response, provider = get_llm_response(WEEKLY_SYSTEM_PROMPT, user_prompt)

    if response:
        await update.message.reply_text(response, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "All LLM providers are unavailable right now. Try again in a few minutes."
        )
