# BuildBot

Personal Telegram bot for daily build hour planning.

## Setup

1. Create a conda environment:
   ```
   conda create -n buildbot python=3.11 -y
   conda activate buildbot
   pip install -r requirements.txt
   ```

2. Edit `~/.buildbot/.env` with your API keys:
   - `TELEGRAM_BOT_TOKEN` — from @BotFather
   - `TELEGRAM_USER_ID` — your numeric ID (from @userinfobot)
   - `GROQ_API_KEY` — from console.groq.com
   - `CEREBRAS_API_KEY` — from cloud.cerebras.ai
   - `MISTRAL_API_KEY` — from console.mistral.ai

3. Run the bot:
   ```
   python bot.py
   ```

## Commands

- `/plan` — Generate tonight's build hour plan
- `/tasks` — View active task backlog
- `/add <task>` — Add a new task
- `/done <id>` — Mark a task complete
- `/reflect` — Start a post-build reflection (5 questions)
- `/status` — Bot status and active LLM provider

## Daily Scheduler

Sends a build hour plan automatically at 18:30 AST (America/Port_of_Spain).
