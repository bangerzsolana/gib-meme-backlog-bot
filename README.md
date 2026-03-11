# Backlog Bot

A Telegram bot for product backlog intake. Admins in a Telegram group can log feature ideas and bugs using simple commands.

## Features

- `/backlog <description>` — Add a backlog item (with optional photo)
- `/bug <description>` — Log a bug report (with optional photo)
- Admin management via `/newadmin` and `/removeadmin`
- SQLite storage — no external database needed

## Setup

### Local

1. Clone the repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy the example env file and fill in your values:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your-token-here
   SEED_ADMIN=your-telegram-username
   GROUP_ID=          # optional, can also be set via /setup in the group
   ```

4. Run the bot:
   ```bash
   python3 bot.py
   ```

### First-time configuration

1. Start a chat with your bot and send `/start` to verify it's running.
2. Add the bot to your Telegram group.
3. Send `/setup` in the group to link it (the bot will remember the group ID).

## Railway Deploy

1. Create a new Railway project and connect this repo.
2. Set environment variables in Railway:
   - `TELEGRAM_BOT_TOKEN`
   - `SEED_ADMIN` (your Telegram username, without @)
   - `GROUP_ID` (optional — you can also use `/setup`)
3. Add a persistent volume mounted at `/data` so the SQLite database survives redeploys.
4. The `Procfile` configures Railway to run the bot as a worker process.

## File Structure

```
backlog-bot/
  bot.py          # Main bot logic and command handlers
  database.py     # SQLite database setup and queries
  config.py       # Environment variable loading
  .env.example    # Template for environment variables
  requirements.txt
  Procfile        # Railway/Heroku process definition
  README.md
```
