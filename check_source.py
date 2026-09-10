import asyncio
from pyrogram import Client
from config import Config

async def main():
    app = Client(
        "userbot_session",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        phone_number=Config.PHONE_NUMBER
    )
    async with app:
        print("Checking all channels joined by account...")
        print("="*80)
        async for dialog in app.get_dialogs():
            chat = dialog.chat
            if chat.type.name in ["CHANNEL", "SUPERGROUP", "GROUP"]:
                print(f"Title: {chat.title}")
                print(f"Chat ID: {chat.id}")
                print(f"Username: @{chat.username}" if chat.username else "Username: None")
                print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
