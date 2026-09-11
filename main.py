import asyncio
import json
import os
import re
import sys
import urllib.request
from pyrogram import Client, filters, errors, enums
from pyrogram.types import Message
from typing import Set

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
processed_message_ids: Set[str] = set()

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

def format_otp_message(text: str) -> str:
    """
    Parse raw SMS from Atmosphere Sms and return clean HTML format.
    OTP code in <code> block for one-click copy of digits only.
    Format: 'Use code XXXXXX to approve ... of CURRENCY AMOUNT to MERCHANT with card ending CARD'
    """
    if not text:
        return text

    # Extract OTP code: "Use code XXXXXX to approve"
    otp_match = re.search(r'[Uu]se code (\d+)', text)
    # Extract card ending: "card ending XXXX"
    card_match = re.search(r'card ending (\d+)', text)
    # Extract currency + amount: "transaction of CURRENCY AMOUNT to"
    amount_match = re.search(r'transaction of ([A-Z]+) ([\d\.]+) to', text)
    # Extract merchant: anchored after "CURRENCY AMOUNT to MERCHANT with card"
    merchant_match = re.search(r'transaction of [A-Z]+ [\d\.]+ to (.+?) with card', text)

    if otp_match:
        otp_code = otp_match.group(1)
        card = card_match.group(1) if card_match else "?"
        merchant = merchant_match.group(1).strip() if merchant_match else "?"
        currency = amount_match.group(1) if amount_match else ""
        amount_val = amount_match.group(2) if amount_match else "?"

        formatted = (
            f"<b>OTP:</b> <code>{otp_code}</code>\n\n"
            f"\U0001f4b3 VCC: \u2022\u2022\u2022\u2022{card}\n"
            f"\U0001f3ea Merchant: <b>{merchant}</b>\n"
            f"\U0001f4b0 Amount: {currency} {amount_val}"
        )
        return formatted

    # Fallback: strip SMS BARU header and return plain text
    lines = text.strip().splitlines()
    cleaned = []
    skip_next_blank = False
    for line in lines:
        if "SMS BARU" in line:
            skip_next_blank = True
            continue
        if skip_next_blank and line.strip() == "":
            skip_next_blank = False
            continue
        skip_next_blank = False
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def format_wa_otp_message(text: str) -> str:
    """Format raw SMS into WhatsApp markdown style."""
    if not text:
        return text

    otp_match = re.search(r'[Uu]se code (\d+)', text)
    card_match = re.search(r'card ending (\d+)', text)
    amount_match = re.search(r'transaction of ([A-Z]+) ([\d\.]+) to', text)
    merchant_match = re.search(r'transaction of [A-Z]+ [\d\.]+ to (.+?) with card', text)

    if otp_match:
        otp_code = otp_match.group(1)
        card = card_match.group(1) if card_match else "?"
        merchant = merchant_match.group(1).strip() if merchant_match else "?"
        currency = amount_match.group(1) if amount_match else ""
        amount_val = amount_match.group(2) if amount_match else "?"

        return (
            f"*OTP:* `{otp_code}`\n\n"
            f"💳 VCC: ••••{card}\n"
            f"🏪 Merchant: *{merchant}*\n"
            f"💰 Amount: {currency} {amount_val}"
        )
    return text


def send_to_whatsapp(raw_text: str):
    """Sends OTP notification to WhatsApp target number via local Node.js REST API."""
    if not Config.WA_TARGET_NUMBER or not Config.WA_SERVER_URL:
        return

    wa_text = format_wa_otp_message(raw_text)
    payload = json.dumps({
        "to": Config.WA_TARGET_NUMBER,
        "message": wa_text
    }).encode("utf-8")

    req = urllib.request.Request(
        Config.WA_SERVER_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info(f"✅ OTP WhatsApp berhasil terkirim ke {Config.WA_TARGET_NUMBER}")
    except Exception as e:
        logger.error(f"❌ Gagal mengirim OTP ke WhatsApp ({Config.WA_TARGET_NUMBER}): {e}")



def matches_keywords(text: str) -> bool:
    """Check if message matches configured keywords filter."""
    if not Config.KEYWORDS:
        return True
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in Config.KEYWORDS)


async def send_to_target(raw_text: str, target_chat):
    """Sends formatted OTP message to target chat via Userbot with FloodWait handling."""
    formatted = format_otp_message(raw_text)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await user_app.send_message(target_chat, formatted, parse_mode=enums.ParseMode.HTML)
            logger.info(f"-> Userbot: Sent formatted OTP ke target: {target_chat}")
            break
        except errors.FloodWait as e:
            logger.warning(f"Telegram FloodWait hit! Tidur selama {e.value} detik...")
            await asyncio.sleep(e.value + 1)
        except errors.RPCError as e:
            logger.error(f"Gagal Userbot send ke {target_chat}: {e}")
            break
        except Exception as e:
            logger.error(f"Error tak terduga Userbot send ke {target_chat}: {e}")
            break



def is_source_chat(message: Message) -> bool:
    """Check if message originates from configured source chats or known OTP channels."""
    if not message or not message.chat:
        return False

    chat_id = message.chat.id
    chat_title = (message.chat.title or message.chat.first_name or "").lower()
    username = (message.chat.username or "").lower()

    for source in Config.SOURCE_CHATS:
        if isinstance(source, int) and source == chat_id:
            return True
        if isinstance(source, str):
            clean_s = source.lstrip("@").lower()
            if clean_s and (clean_s == username or clean_s in chat_title):
                return True

    # Auto-detect known OTP channel titles
    if "atmosphere sms" in chat_title:
        return True
    if "otp quin" in chat_title:
        return True

    return False


def send_to_web_dashboard(raw_text: str, source_name: str = ""):
    """Sends structured OTP data to local Web OTP Dashboard REST API."""
    if not raw_text:
        return

    # Format 1 (Atmosphere Sms): 'Use code 123456 to approve...'
    # Format 2 (Otp quin):       '🔐 Kode OTP: 123456\n📩 Pesan: Use code 123456 to approve...'
    otp_match = re.search(r'[Uu]se code (\d+)', raw_text)
    if not otp_match:
        # Fallback: parse 'Kode OTP: 123456' line (Otp quin format)
        otp_match = re.search(r'[Kk]ode OTP[:\s]+([\d]+)', raw_text)

    card_match = re.search(r'card ending (\d+)', raw_text)
    amount_match = re.search(r'transaction of ([A-Z]+) ([\d\.]+) to', raw_text)
    merchant_match = re.search(r'transaction of [A-Z]+ [\d\.]+ to (.+?) with card', raw_text)

    otp_code = otp_match.group(1) if otp_match else ""
    card = card_match.group(1) if card_match else "?"
    merchant = merchant_match.group(1).strip() if merchant_match else "?"
    currency = amount_match.group(1) if amount_match else ""
    amount_val = amount_match.group(2) if amount_match else "?"
    amount_str = f"{currency} {amount_val}".strip() if amount_match else "?"

    payload = json.dumps({
        "otp": otp_code,
        "vcc": card,
        "merchant": merchant,
        "amount": amount_str,
        "raw_text": raw_text
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://127.0.0.1:4001/api/otp",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info("🌐 OTP berhasil dikirim ke Web Dashboard (http://IP-VPS:4001)")
    except Exception as e:
        logger.debug(f"Web Dashboard note: {e}")


async def process_and_forward_message(message: Message):
    """Processes incoming message and forwards/broadcasts it."""
    if not message:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in processed_message_ids:
        return
    processed_message_ids.add(msg_key)

    chat_title = message.chat.title or message.chat.first_name or str(message.chat.id)
    text_content = message.text or message.caption or ""

    logger.info(f"📩 Pesan SMS OTP Baru Diterima dari [{chat_title}] (ID Pesan: {message.id})")

    # Keyword filtering check
    if not matches_keywords(text_content):
        logger.info("Pesan diabaikan (tidak memenuhi kata kunci filter).")
        return

    # Push OTP directly to Web Dashboard (http://IP-VPS:4001)
    send_to_web_dashboard(text_content)


# Real-time event handlers
@user_app.on_message()
async def handle_incoming_message(client: Client, message: Message):
    if is_source_chat(message):
        await process_and_forward_message(message)


@user_app.on_edited_message()
async def handle_edited_message(client: Client, message: Message):
    if is_source_chat(message):
        await process_and_forward_message(message)


async def poll_channel_history_fallback():
    """Fallback polling loop every 5 seconds to guarantee zero missed messages."""
    logger.info("🔄 Fallback History Poller Aktif (Memeriksa pesan baru setiap 5 detik)...")
    while True:
        try:
            await asyncio.sleep(5)
            for source_chat in list(Config.SOURCE_CHATS):
                try:
                    async for msg in user_app.get_chat_history(source_chat, limit=5):
                        if is_source_chat(msg):
                            await process_and_forward_message(msg)
                except Exception as e:
                    logger.debug(f"Polling history note for {source_chat}: {e}")
        except Exception as e:
            logger.error(f"Error fallback history loop: {e}")
            await asyncio.sleep(5)


async def start_bot():
    """Start Telegram Userbot and optional HTTP Bot API listener."""
    logger.info("Starting Telegram Auto Forwarder Userbot & Bot HTTP API...")
    
    await user_app.start()
    me_user = await user_app.get_me()
    logger.info(f"Userbot Logged in as: {me_user.first_name} (@{me_user.username or 'No Username'}) [ID: {me_user.id}]")

    # Warm up peer cache and auto-detect known OTP source channels
    logger.info("Warming up channel peer cache & discovering OTP source channels...")
    atmosphere_found = False
    otp_quin_found = False
    async for dialog in user_app.get_dialogs():
        title = (dialog.chat.title or "").lower()
        if "atmosphere sms" in title:
            atmosphere_found = True
            logger.info(f"🎯 Terdeteksi Channel: '{dialog.chat.title}' [Chat ID: {dialog.chat.id}]")
            if dialog.chat.id not in Config.SOURCE_CHATS:
                Config.SOURCE_CHATS.append(dialog.chat.id)
        if "otp quin" in title:
            otp_quin_found = True
            logger.info(f"🎯 Terdeteksi Channel: '{dialog.chat.title}' [Chat ID: {dialog.chat.id}]")
            if dialog.chat.id not in Config.SOURCE_CHATS:
                Config.SOURCE_CHATS.append(dialog.chat.id)

    if not atmosphere_found:
        logger.warning(
            "⚠️ Channel 'Atmosphere Sms' TIDAK DITEMUKAN di daftar chat akun Telegram Userbot!\n"
            "   Pastikan akun Telegram yang di-login-kan SUDAH JOIN ke channel Atmosphere Sms!"
        )
    if not otp_quin_found:
        logger.warning(
            "⚠️ Channel 'Otp quin' TIDAK DITEMUKAN di daftar chat akun Telegram Userbot!\n"
            "   Pastikan akun Telegram yang di-login-kan SUDAH JOIN ke channel Otp quin!"
        )


    # Seed recent channel history so old OTP messages are NOT sent on restart
    logger.info("Mengindeks pesan-pesan lama di channel agar TIDAK terkirim ulang saat restart...")
    for source_chat in list(Config.SOURCE_CHATS):
        try:
            async for msg in user_app.get_chat_history(source_chat, limit=50):
                if msg and msg.chat:
                    msg_key = f"{msg.chat.id}_{msg.id}"
                    processed_message_ids.add(msg_key)
            logger.info(f"✅ Berhasil mengabaikan pesan lama dari chat ID: {source_chat}")
        except Exception as e:
            logger.warning(f"Gagal mengindeks riwayat pesan lama untuk {source_chat}: {e}")

    # Start HTTP Bot API Polling in background task if BOT_TOKEN present
    bot_task = None
    if bot_api:
        bot_task = asyncio.create_task(bot_api.poll_updates(subscribers, lambda: save_subscribers(subscribers)))

    # Start Fallback Polling task
    fallback_task = asyncio.create_task(poll_channel_history_fallback())

    logger.info(f"Listening on Source Chats: {Config.SOURCE_CHATS}")
    logger.info(f"Forwarding to Target Chats: {Config.TARGET_CHATS}")
    logger.info(f"Mode Forwarding: {Config.FORWARD_MODE.upper()}")
    logger.info(f"Jumlah Registered Subscribers Bot: {len(subscribers)} (IDs: {list(subscribers)})")

    logger.info("🟢 Bot Auto-Forwarder (Real-time + Polling Fallback) 100% Aktif!")

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
        if fallback_task:
            fallback_task.cancel()
        await user_app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Program dihentikan oleh pengguna.")
    except Exception as e:
        logger.critical(f"Aplikasi terhenti karena error: {e}")
