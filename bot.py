import logging
import os
from functools import wraps

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_username(update: Update) -> str:
    user = update.effective_user
    if user and user.username:
        return user.username.lower()
    return ""


def require_admin(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        username = get_username(update)
        if not db.is_admin(username):
            await update.message.reply_text("You don't have permission.")
            return
        # Keep chat_id up to date
        if update.effective_user:
            db.update_admin_chat_id(username, update.effective_user.id)
        return await func(update, context, *args, **kwargs)
    return wrapper


GROUP_ID = None  # fallback


def get_group_id():
    val = db.get_setting("group_id")
    if val:
        return int(val)
    return int(config.GROUP_ID) if config.GROUP_ID else None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Backlog Bot 📋\n\nUse /backlog or /bug to log items.")


async def commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username(update)
    text = (
        "Commands:\n"
        "/start — Welcome message\n"
        "/commands — Show this list"
    )
    if db.is_admin(username):
        text += (
            "\n\nAdmin Commands:\n"
            "/backlog <description> — Add a backlog item\n"
            "/bug <description> — Log a bug report\n"
            "/setup — Link this group\n"
            "/newadmin <username> — Add an admin\n"
            "/removeadmin <username> — Remove an admin\n"
            "/admins — List admins"
        )
    await update.message.reply_text(text)


@require_admin
async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Run /setup inside the group you want to link.")
        return
    db.set_setting("group_id", str(chat.id))
    await update.message.reply_text(
        f"✅ Group linked! This group (ID: {chat.id}) is now set as the backlog group."
    )


@require_admin
async def backlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username(update)
    description = None
    image_file_id = None

    if update.message.photo:
        # Photo message — use caption as description
        caption = update.message.caption or ""
        # Strip the /backlog command from caption if present
        if caption.startswith("/backlog"):
            caption = caption[len("/backlog"):].strip()
        description = caption if caption else None
        image_file_id = update.message.photo[-1].file_id
    else:
        if context.args:
            description = " ".join(context.args)

    if not description:
        await update.message.reply_text("Usage: /backlog <description>")
        return

    item_id = db.add_item("backlog", description, image_file_id, username)
    await update.message.reply_text(f"✅ Backlog item #{item_id} added: {description}")


@require_admin
async def bug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username(update)
    description = None
    image_file_id = None

    if update.message.photo:
        caption = update.message.caption or ""
        if caption.startswith("/bug"):
            caption = caption[len("/bug"):].strip()
        description = caption if caption else None
        image_file_id = update.message.photo[-1].file_id
    else:
        if context.args:
            description = " ".join(context.args)

    if not description:
        await update.message.reply_text("Usage: /bug <description>")
        return

    item_id = db.add_item("bug", description, image_file_id, username)
    await update.message.reply_text(f"🐛 Bug #{item_id} logged: {description}")


# ---------------------------------------------------------------------------
# /newadmin and /removeadmin
# ---------------------------------------------------------------------------

@require_admin
async def newadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /newadmin <username>")
        return
    raw = context.args[0].lstrip("@").lower()
    added_by = get_username(update)
    if db.add_admin(raw, added_by):
        await update.message.reply_text(f"✅ @{raw} has been added as an admin.")
    else:
        await update.message.reply_text(f"@{raw} is already an admin.")


@require_admin
async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removeadmin <username>")
        return
    raw = context.args[0].lstrip("@").lower()
    if raw == get_username(update):
        await update.message.reply_text("You can't remove yourself.")
        return
    if db.remove_admin(raw):
        await update.message.reply_text(f"✅ @{raw} has been removed as an admin.")
    else:
        await update.message.reply_text(f"@{raw} was not found in the admin list.")


# ---------------------------------------------------------------------------
# /admins
# ---------------------------------------------------------------------------

@require_admin
async def admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_list = db.list_admins()
    if not admin_list:
        await update.message.reply_text("No admins found.")
        return
    lines = ["Admins:"]
    for a in admin_list:
        added = f" (added by @{a['added_by']})" if a.get("added_by") else ""
        lines.append(f"• @{a['username']}{added}")
    await update.message.reply_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Startup message
# ---------------------------------------------------------------------------

async def post_init(application: Application):
    group_id = get_group_id()
    if not group_id:
        logger.info("No group_id configured — skipping startup message.")
        return

    commit_msg = os.getenv("RAILWAY_GIT_COMMIT_MESSAGE", "")
    text = "Backlog Bot reporting for duty 📋"
    if commit_msg:
        text += f"\n\n_{commit_msg}_"

    try:
        await application.bot.send_message(chat_id=group_id, text=text)
    except Exception as e:
        logger.warning(f"Could not send startup message: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    db.init_db(config.SEED_ADMIN)

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # 1. Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("commands", commands))
    app.add_handler(CommandHandler("setup", setup))

    # 2. Intake commands (group and DM)
    app.add_handler(
        MessageHandler(filters.PHOTO & filters.Caption(["/backlog"]), backlog)
    )
    app.add_handler(CommandHandler("backlog", backlog))
    app.add_handler(
        MessageHandler(filters.PHOTO & filters.Caption(["/bug"]), bug)
    )
    app.add_handler(CommandHandler("bug", bug))

    # 3. Admin management
    app.add_handler(CommandHandler("newadmin", newadmin))
    app.add_handler(CommandHandler("removeadmin", removeadmin))
    app.add_handler(CommandHandler("admins", admins))

    logger.info("Backlog Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
