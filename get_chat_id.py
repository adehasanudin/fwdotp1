import asyncio
import os
import sys
from pyrogram import Client
from config import Config
from utils.logger import logger

async def main():
    if not os.path.exists(".env"):
        logger.error("File .env tidak ditemukan!")
        return

    search_query = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    logger.info("Memuat sesi Telegram untuk mencari Chat ID...")
    
    app = Client(
        "userbot_session",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        phone_number=Config.PHONE_NUMBER
    )

    async with app:
        me = await app.get_me()
        logger.info(f"Connected sebagai: {me.first_name} (@{me.username or 'No Username'}) [ID: {me.id}]")
        
        if search_query:
            print(f"\n🔍 Menampilkan hasil pencarian untuk kata kunci: '{search_query}'")
        else:
            print("\n📋 Menampilkan SEMUA Channels & Groups...")

        print("="*85)
        print(f"{'TITLE / NAME':<38} | {'TYPE':<10} | {'USERNAME':<20} | {'CHAT ID'}")
        print("="*85)

        count = 0
        async for dialog in app.get_dialogs():
            chat = dialog.chat
            title = chat.title or chat.first_name or "Unknown"
            username = f"@{chat.username}" if chat.username else "-"
            chat_type = str(chat.type.name)
            chat_id = chat.id

            # Filter search
            match = True
            if search_query:
                match = (search_query in title.lower()) or (search_query in username.lower()) or (search_query in str(chat_id))

            if match:
                if len(title) > 36:
                    display_title = title[:33] + "..."
                else:
                    display_title = title
                print(f"{display_title:<38} | {chat_type:<10} | {username:<20} | {chat_id}")
                count += 1

        print("="*85)
        print(f"Total ditemukan: {count} chat.\n")

if __name__ == "__main__":
    asyncio.run(main())
