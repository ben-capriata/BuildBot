from datetime import date

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ALLOWED_USER_ID, SYSTEM_PROMPT
from db import add_build_session
from llm import get_llm_response

ATTEMPTED, WORKED, DIDNT_WORK, SURPRISED, NEXT_TIME = range(5)


def _auth(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID


async def reflect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _auth(update):
        return ConversationHandler.END

    context.user_data["reflect"] = {}
    await update.message.reply_text("Let's reflect on your build hour.\n\n1/5: What did you attempt to build today?")
    return ATTEMPTED


async def reflect_attempted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _auth(update):
        return ConversationHandler.END

    context.user_data["reflect"]["attempted"] = update.message.text
    await update.message.reply_text("2/5: What worked?")
    return WORKED


async def reflect_worked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _auth(update):
        return ConversationHandler.END

    context.user_data["reflect"]["worked"] = update.message.text
    await update.message.reply_text("3/5: What did not work?")
    return DIDNT_WORK


async def reflect_didnt_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _auth(update):
        return ConversationHandler.END

    context.user_data["reflect"]["didnt_work"] = update.message.text
    await update.message.reply_text("4/5: What surprised you?")
    return SURPRISED


async def reflect_surprised(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _auth(update):
        return ConversationHandler.END

    context.user_data["reflect"]["surprised"] = update.message.text
    await update.message.reply_text("5/5: What would you try next time?")
    return NEXT_TIME


async def reflect_next_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _auth(update):
        return ConversationHandler.END

    data = context.user_data["reflect"]
    data["next_time"] = update.message.text

    await update.message.reply_text("Generating your build log...")

    # Build LLM prompt for the build log
    reflection_text = (
        f"Date: {date.today().isoformat()}\n"
        f"Attempted: {data['attempted']}\n"
        f"Worked: {data['worked']}\n"
        f"Didn't work: {data['didnt_work']}\n"
        f"Surprised: {data['surprised']}\n"
        f"Next time: {data['next_time']}"
    )

    system = (
        "You are OpenClaw, a build session logger. Given a developer's reflection answers, "
        "generate a concise structured build log entry. Use this format:\n\n"
        "📝 **Build Log — [date]**\n"
        "**Attempted:** [summary]\n"
        "**Outcome:** [what worked vs didn't]\n"
        "**Insight:** [key learning]\n"
        "**Next:** [action item]\n\n"
        "Keep it under 150 words."
    )

    build_log, provider = get_llm_response(system, reflection_text)

    if not build_log:
        build_log = "(LLM unavailable — raw reflection saved)"

    add_build_session(
        date=date.today().isoformat(),
        attempted=data["attempted"],
        worked=data["worked"],
        didnt_work=data["didnt_work"],
        surprised=data["surprised"],
        next_time=data["next_time"],
        build_log=build_log,
    )

    await update.message.reply_text(build_log)
    context.user_data.pop("reflect", None)
    return ConversationHandler.END


async def reflect_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("reflect", None)
    await update.message.reply_text("Reflection cancelled.")
    return ConversationHandler.END


def get_reflect_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("reflect", reflect_start)],
        states={
            ATTEMPTED: [MessageHandler(filters.TEXT & ~filters.COMMAND, reflect_attempted)],
            WORKED: [MessageHandler(filters.TEXT & ~filters.COMMAND, reflect_worked)],
            DIDNT_WORK: [MessageHandler(filters.TEXT & ~filters.COMMAND, reflect_didnt_work)],
            SURPRISED: [MessageHandler(filters.TEXT & ~filters.COMMAND, reflect_surprised)],
            NEXT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reflect_next_time)],
        },
        fallbacks=[CommandHandler("cancel", reflect_cancel)],
    )
