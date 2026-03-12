import logging
import os
import uuid
from functools import wraps

import boto3
from botocore.config import Config
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


class _CaptionStartsWith(filters.MessageFilter):
    def __init__(self, prefix: str):
        self.prefix = prefix
        super().__init__()

    def filter(self, message) -> bool:
        return bool(message.caption and message.caption.startswith(self.prefix))

import config
import database as db


# ---------------------------------------------------------------------------
# R2 upload
# ---------------------------------------------------------------------------

def _get_r2_client():
    if not all([config.R2_ACCOUNT_ID, config.R2_ACCESS_KEY_ID, config.R2_SECRET_ACCESS_KEY]):
        return None
    return boto3.client(
        "s3",
        endpoint_url=f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


async def upload_photo_to_r2(bot, file_id: str) -> str | None:
    """Download a Telegram photo and upload it to R2. Returns the public URL or None."""
    if not config.R2_PUBLIC_URL:
        return None
    try:
        r2 = _get_r2_client()
        if not r2:
            return None
        tg_file = await bot.get_file(file_id)
        photo_bytes = await tg_file.download_as_bytearray()
        key = f"images/{uuid.uuid4().hex}.jpg"
        r2.put_object(
            Bucket=config.R2_BUCKET,
            Key=key,
            Body=bytes(photo_bytes),
            ContentType="image/jpeg",
        )
        return f"{config.R2_PUBLIC_URL.rstrip('/')}/{key}"
    except Exception as e:
        logger.warning(f"R2 upload failed: {e}")
        return None

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


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Backlog Bot reporting for duty 📋")


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
            "/biccs <description> — Add to Biccs channel\n"
            "/c4 <description> — Add to C4 channel\n"
            "/new <description> — Add a new feature idea\n"
            "/newfeature <description> — Add a new feature idea\n"
            "/newfeatures <description> — Add a new feature idea\n"
            "/bangerz <description> — Add to Bangerz channel\n"
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


async def _add_item(update, context, category: str, label: str, emoji: str, cmd: str = None):
    """Shared handler for all intake commands."""
    if cmd is None:
        cmd = category
    username = get_username(update)
    if not db.is_admin(username):
        await update.message.reply_text("You don't have permission.")
        return
    db.update_admin_chat_id(username, update.effective_user.id)

    description = None
    image_file_id = None

    if update.message.photo:
        caption = update.message.caption or ""
        if caption.startswith(f"/{cmd}"):
            caption = caption[len(f"/{cmd}"):].strip()
        description = caption if caption else None
        image_file_id = update.message.photo[-1].file_id
    else:
        if context.args:
            description = " ".join(context.args)

    if not description:
        await update.message.reply_text(f"Usage: /{cmd} <description>")
        return

    image_url = None
    if image_file_id:
        image_url = await upload_photo_to_r2(context.bot, image_file_id)

    item_id = db.add_item(category, description, image_file_id, username, image_url=image_url)
    await update.message.reply_text(f"{emoji} {label} #{item_id} added: {description}")


async def backlog(update, context):
    await _add_item(update, context, "backlog", "Backlog item", "✅")

async def bug(update, context):
    await _add_item(update, context, "bug", "Bug", "🐛")

async def biccs(update, context):
    await _add_item(update, context, "biccs", "Biccs item", "🟣")

async def c4(update, context):
    await _add_item(update, context, "c4", "C4 item", "🔵")

async def newfeatures(update, context):
    await _add_item(update, context, "newfeatures", "New feature", "✨")

async def new_cmd(update, context):
    await _add_item(update, context, "newfeatures", "New feature", "✨", cmd="new")

async def newfeature(update, context):
    await _add_item(update, context, "newfeatures", "New feature", "✨", cmd="newfeature")

async def bangerz(update, context):
    await _add_item(update, context, "bangerz", "Bangerz item", "🟠")


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
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("commands", commands))
    app.add_handler(CommandHandler("setup", setup))

    # 2. Intake commands (group and DM)
    for cmd, handler in [
        ("backlog", backlog), ("bug", bug),
        ("biccs", biccs), ("c4", c4), ("newfeatures", newfeatures), ("newfeature", newfeature), ("new", new_cmd),
        ("bangerz", bangerz),
    ]:
        app.add_handler(MessageHandler(filters.PHOTO & _CaptionStartsWith(f"/{cmd}"), handler))
        app.add_handler(CommandHandler(cmd, handler))

    # 3. Admin management
    app.add_handler(CommandHandler("newadmin", newadmin))
    app.add_handler(CommandHandler("removeadmin", removeadmin))
    app.add_handler(CommandHandler("admins", admins))

    logger.info("Backlog Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
