import asyncio
import html
import json
import urllib.request
import urllib.parse
from typing import Set
from utils.logger import logger

class TelegramBotAPI:
    """Lightweight HTTP Telegram Bot API helper using standard library."""

    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
        self.is_running = False

    def send_message(self, chat_id: int, text: str, parse_mode: str = None) -> bool:
        """Send message via Telegram HTTP Bot API."""
        url = f"{self.base_url}/sendMessage"
        params = {
            "chat_id": chat_id,
            "text": text,
        }
        if parse_mode:
            params["parse_mode"] = parse_mode

        data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                success = res_data.get("ok", False)
                if not success:
                    logger.error(f"Telegram Bot API error saat kirim ke {chat_id}: {res_data}")
                return success
        except Exception as e:
            logger.error(f"Gagal mengirim pesan via Bot API ke {chat_id}: {e}")
            return False

    async def poll_updates(self, subscribers_set: Set[int], save_callback):
        """Poll incoming Telegram Bot updates for /start command."""
        self.is_running = True
        logger.info("🤖 Bot HTTP API Listener Aktif untuk merespon /start...")
        unauthorized_logged = False

        while self.is_running:
            try:
                url = f"{self.base_url}/getUpdates?offset={self.offset}&timeout=5"
                req = urllib.request.Request(url)
                loop = asyncio.get_running_loop()
                
                response_bytes = await loop.run_in_executor(
                    None,
                    lambda: urllib.request.urlopen(req, timeout=10).read()
                )
                
                res = json.loads(response_bytes.decode('utf-8'))
                if res.get("ok"):
                    for update in res.get("result", []):
                        self.offset = update["update_id"] + 1
                        message = update.get("message")
                        if message and "text" in message:
                            text = message["text"].strip()
                            chat_id = message["chat"]["id"]
                            first_name = message["chat"].get("first_name", "User")
                            
                            logger.info(f"Pesan diterima oleh Bot dari {first_name} [{chat_id}]: {text}")
                            
                            if text.startswith("/start"):
                                subscribers_set.add(chat_id)
                                save_callback()
                                welcome = (
                                    "👋 <b>Selamat Datang di Elzoi OTP1 Bot!</b>\n\n"
                                    "🤖 Bot ini adalah layanan resmi <b>OTP VCC dari ELZOI</b>.\n\n"
                                    "📌 <b>Informasi:</b>\n"
                                    "• Semua kode OTP dan notifikasi transaksi VCC Anda akan <b>otomatis muncul di sini</b> secara real-time.\n"
                                    "• Anda tidak perlu melakukan pengaturan tambahan.\n\n"
                                    "⚡ <i>Status System:</i> 🟢 <b>Aktif & Berjalan Normal</b>"
                                )
                                sent = self.send_message(chat_id, welcome, parse_mode="HTML")
                                if sent:
                                    logger.info(f"✅ Balasan /start berhasil dikirim ke {first_name} [{chat_id}]")
                                else:
                                    logger.error(f"❌ Gagal mengirim balasan /start ke {first_name} [{chat_id}]")
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    if not unauthorized_logged:
                        logger.warning(
                            "⚠️ BOT_TOKEN di .env tidak valid (HTTP 401 Unauthorized).\n"
                            "   Silakan buka @BotFather di Telegram, salin ulang Token Bot Anda, dan perbarui di file .env."
                        )
                        unauthorized_logged = True
                    break
                else:
                    logger.error(f"HTTP Error pada Bot API: {e}")
                    await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error pada Bot API polling loop: {e}")
                await asyncio.sleep(5)
            
            await asyncio.sleep(1)

    def stop(self):
        self.is_running = False
