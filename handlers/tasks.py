from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID
from db import add_task, complete_task, get_active_tasks


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    tasks = get_active_tasks()
    if not tasks:
        await update.message.reply_text("No active tasks. Use /add to create one.")
        return

    lines = []
    for t in tasks:
        status_icon = {"todo": "⬜", "in_progress": "🔨"}.get(t["status"], "⬜")
        lines.append(f"{status_icon} #{t['id']} {t['title']} ({t['priority']})")

    await update.message.reply_text("📋 **Active Tasks:**\n\n" + "\n".join(lines), parse_mode="Markdown")


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /add <task title>")
        return

    title = " ".join(context.args)
    task_id = add_task(title)
    await update.message.reply_text(f"Added task #{task_id}: {title}")


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /done <task number>")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid task number.")
        return

    if complete_task(task_id):
        await update.message.reply_text(f"Completed task #{task_id}!")
    else:
        await update.message.reply_text(f"Task #{task_id} not found.")
