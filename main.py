import asyncio
import json
import os
import sys
from typing import Set
from pyrogram import Client, filters, errors
from pyrogram.types import Message

from config import Config
from utils.logger import logger
from utils.bot_api import TelegramBotAPI

# Validate configuration on startup
try:
    Config.validate()
except Exception as err:
    logger.error(f"Gagal memulai aplikasi: {err}")
    sys.exit(1)

# File persistence for bot subscribers
SUBSCRIBERS_FILE = "subscribers.json"

def load_subscribers() -> Set[int]:
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r") as f:
                data = json.load(f)
                return set(data)
        except Exception as e:
            logger.error(f"Gagal membaca subscribers.json: {e}")
    return set()

def save_subscribers(subscribers: Set[int]):
    try:
        with open(SUBSCRIBERS_FILE, "w") as f:
            json.dump(list(subscribers), f)
    except Exception as e:
        logger.error(f"Gagal menyimpan subscribers.json: {e}")

subscribers: Set[int] = load_subscribers()

# 1. Initialize Userbot Client (reads from source channel)
user_app = Client(
    "userbot_session",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    phone_number=Config.PHONE_NUMBER
)

# 2. Initialize HTTP Bot API Client for /start welcome messages & broadcast
bot_api = None
if Config.BOT_TOKEN:
    bot_api = TelegramBotAPI(Config.BOT_TOKEN)


def matches_keywords(text: str) -> bool:
    """Check if message matches configured keywords filter."""
    if not Config.KEYWORDS:
        return True
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in Config.KEYWORDS)


async def send_to_target(message: Message, target_chat):
    """Sends or forwards message to target chat via Userbot with FloodWait handling."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if Config.FORWARD_MODE == "forward":
                await message.forward(target_chat)
                logger.info(f"-> Forwarded pesan [ID: {message.id}] ke target: {target_chat}")
            else:
                await message.copy(target_chat)
                logger.info(f"-> Copied pesan [ID: {message.id}] ke target: {target_chat}")
            break
        except errors.FloodWait as e:
            logger.warning(f"Telegram FloodWait hit! Tidur selama {e.value} detik...")
            await asyncio.sleep(e.value + 1)
        except errors.RPCError as e:
            logger.error(f"Gagal mengirim ke {target_chat}: {e}")
            break
        except Exception as e:
            logger.error(f"Error tak terduga saat mengirim ke {target_chat}: {e}")
            break


# Handler for incoming messages from source channels/chats (Userbot)
@user_app.on_message(filters.chat(Config.SOURCE_CHATS))
async def handle_incoming_message(client: Client, message: Message):
    """Handler for incoming messages from source channels/chats."""
    chat_title = message.chat.title or message.chat.first_name or str(message.chat.id)
    text_content = message.text or message.caption or ""

    logger.info(f"📩 Pesan Baru Diterima dari [{chat_title}] (ID Pesan: {message.id})")

    # Keyword filtering check
    if not matches_keywords(text_content):
        logger.info("Pesan diabaikan (tidak memenuhi kata kunci filter).")
        return

    # 1. Forward via Userbot to target chats configured in .env
    for target in Config.TARGET_CHATS:
        await send_to_target(message, target)

    # 2. Broadcast via Telegram Bot HTTP API to subscribers who pressed /start
    if bot_api and subscribers and text_content:
        for sub_id in list(subscribers):
            bot_api.send_message(sub_id, text_content, parse_mode=None)
            logger.info(f"-> Broadcast SMS via Bot API ke Chat ID: {sub_id}")


async def start_bot():
    """Start Telegram Userbot and optional HTTP Bot API listener."""
    logger.info("Starting Telegram Auto Forwarder Userbot & Bot HTTP API...")
    
    await user_app.start()
    me_user = await user_app.get_me()
    logger.info(f"Userbot Logged in as: {me_user.first_name} (@{me_user.username or 'No Username'}) [ID: {me_user.id}]")

    # Start HTTP Bot API Polling in background task if BOT_TOKEN present
    bot_task = None
    if bot_api:
        bot_task = asyncio.create_task(bot_api.poll_updates(subscribers, lambda: save_subscribers(subscribers)))

    logger.info(f"Listening on Source Chats: {Config.SOURCE_CHATS}")
    logger.info(f"Forwarding to Target Chats: {Config.TARGET_CHATS}")
    logger.info(f"Mode Forwarding: {Config.FORWARD_MODE.upper()}")

    logger.info("🟢 Bot Auto-Forwarder & Welcome Response 100% Aktif! Tekan Ctrl+C untuk berhenti.")

    # Keep bot running smoothly
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        pass
    finally:
        logger.info("Shutting down Telegram clients...")
        if bot_api:
            bot_api.stop()
        if bot_task:
            bot_task.cancel()
        await user_app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Program dihentikan oleh pengguna.")
    except Exception as e:
        logger.critical(f"Aplikasi terhenti karena error: {e}")
