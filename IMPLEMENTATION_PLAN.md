# BuildClaw — Rebrand & Configuration Implementation Plan

Estimated time: ~45–60 minutes

---

## Open Questions (decide before Phase 3 & 4)

- **Agent skills:** What new commands or capabilities should BuildClaw support?
  - Examples: new `/` commands, integrations (Notion, GitHub, calendar), different LLM providers, etc.
- **System prompt:** What should `~/.buildclaw/prompts/build_hour.txt` contain?
  - The current bot has no prompt file yet — first run will use an empty string.
  - Draft a focused persona + task description for the plan generator.

---

## Phase 1 — Rename Conda Environment (~5 min)

Check your conda version first:

```bash
conda --version
```

**If conda >= 23.9:**
```bash
conda rename -n openclaw buildclaw
```

**If older conda (clone + delete):**
```bash
conda create --name buildclaw --clone openclaw
conda env remove --name openclaw
```

Verify:
```bash
conda env list
conda activate buildclaw
```

---

## Phase 2 — Move the Hidden Config Directory (~5 min)

```bash
cp -r ~/.openclaw ~/.buildclaw
```

Verify the copy looks correct:
```bash
ls -la ~/.buildclaw/
```

Then, once Phase 3 is done and the bot runs cleanly from `~/.buildclaw/`, remove the old directory:
```bash
rm -rf ~/.openclaw
```

> Do NOT delete `~/.openclaw` until you've confirmed the bot starts successfully.

---

## Phase 3 — Update Source Code (~15 min)

### 3a. `config.py`

Change every `openclaw` path reference to `buildclaw`:

| Find | Replace |
|---|---|
| `".openclaw"` | `".buildclaw"` |
| `OPENCLAW_DIR` | `BUILDCLAW_DIR` (optional — functional either way) |
| `"openclaw.db"` | `"buildclaw.db"` |
| `build_hour.txt` | stays the same (prompt filename, keep as-is) |

### 3b. `handlers/chat.py`

Update the assistant persona string:

```python
# Line 7-10 — change:
"You are OpenClaw, a personal build assistant..."
# to:
"You are BuildClaw, a personal build assistant..."
```

### 3c. `README.md`

- Replace all instances of `OpenClaw` / `openclaw` with `BuildClaw` / `buildclaw`
- Update conda env name in setup instructions
- Update `.env` path references (`~/.buildclaw/.env`)

### 3d. `ARCHITECTURE.md`

- Replace all instances of `OpenClaw` / `openclaw` / `.openclaw` with `BuildClaw` / `buildclaw` / `.buildclaw`

---

## Phase 4 — Agent Skills & System Prompt (~10–15 min)

> Blocked on the Open Questions above. Complete after decisions are made.

### 4a. Write the system prompt

Create `~/.buildclaw/prompts/build_hour.txt` with the agreed content.

### 4b. Add new commands (if any)

For each new skill/command:
1. Add a handler function in `handlers/` (or a new file)
2. Register it in `bot.py`
3. Document it in `README.md`

---

## Phase 5 — (Optional) Rename the Source Directory (~5 min)

If you want the project folder renamed from `ClaudeCode` to `BuildClaw`:

```bash
mv ~/ClaudeCode ~/BuildClaw
```

Then update any aliases, shell scripts, or IDE bookmarks pointing to the old path.

---

## Phase 6 — Verify (~5 min)

```bash
conda activate buildclaw
cd ~/ClaudeCode   # or ~/BuildClaw if renamed
python bot.py
```

Check that:
- Bot starts without errors
- `/status` responds correctly
- `/plan` generates (or fails gracefully if no LLM keys set)
- `~/.buildclaw/data/buildclaw.db` is created on first run

---

## Summary Checklist

- [ ] Conda env renamed to `buildclaw`
- [ ] `~/.buildclaw/` directory created from copy of `~/.openclaw/`
- [ ] `config.py` paths updated
- [ ] `handlers/chat.py` persona string updated
- [ ] `README.md` updated
- [ ] `ARCHITECTURE.md` updated
- [ ] System prompt written to `~/.buildclaw/prompts/build_hour.txt`
- [ ] New skills/commands added (pending decisions)
- [ ] Bot verified running from `~/.buildclaw/`
- [ ] `~/.openclaw/` deleted after confirmed working
