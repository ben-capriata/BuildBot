import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import ALLOWED_USER_ID, TELEGRAM_BOT_TOKEN
from db import init_db
from handlers.chat import chat_message
from handlers.plan import plan_command
from handlers.reflect import get_reflect_handler
from handlers.tasks import add_command, done_command, tasks_command
from llm import last_provider
from scheduler import start_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    await update.message.reply_text(
        "Welcome to OpenClaw — your build hour planner.\n\n"
        "Commands:\n"
        "/plan — Get tonight's build hour plan\n"
        "/tasks — View your task backlog\n"
        "/add <task> — Add a new task\n"
        "/done <id> — Mark a task complete\n"
        "/reflect — Start a post-build reflection\n"
        "/status — Bot status"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    from db import get_active_tasks, get_recent_sessions

    tasks = get_active_tasks()
    sessions = get_recent_sessions(limit=1)
    provider = last_provider or "none yet"

    await update.message.reply_text(
        f"🤖 **OpenClaw Status**\n\n"
        f"Active tasks: {len(tasks)}\n"
        f"Last LLM provider: {provider}\n"
        f"Last session: {sessions[0]['date'] if sessions else 'none'}",
        parse_mode="Markdown",
    )


async def post_init(application: Application):
    """Called after the application is initialized."""
    start_scheduler(application.bot, ALLOWED_USER_ID)


def main():
    init_db()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Register handlers — ConversationHandler first so it takes priority
    app.add_handler(get_reflect_handler())
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("status", status_command))
    # Conversational fallback — must be last so commands/ConversationHandler take priority
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))

    logger.info("OpenClaw bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
