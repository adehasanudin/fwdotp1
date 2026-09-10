import os
from typing import List, Union
from dotenv import load_dotenv
from utils.logger import logger

# Load environment variables from .env file
load_dotenv()

def _parse_chat_ids(raw_val: str) -> List[Union[int, str]]:
    """Parse comma-separated string into a list of integer IDs or string usernames."""
    if not raw_val or not raw_val.strip():
        return []
    
    chats = []
    for item in raw_val.split(","):
        cleaned = item.strip()
        if not cleaned:
            continue
        if cleaned.lstrip("-").isdigit():
            chats.append(int(cleaned))
        else:
            chats.append(cleaned)
    return chats

class Config:
    """Application configuration loader."""

    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "").strip()
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
    PHONE_NUMBER: str = os.getenv("PHONE_NUMBER", "").strip() or None

    SOURCE_CHATS: List[Union[int, str]] = _parse_chat_ids(os.getenv("SOURCE_CHAT_ID", ""))
    TARGET_CHATS: List[Union[int, str]] = _parse_chat_ids(os.getenv("TARGET_CHAT_ID", ""))

    FORWARD_MODE: str = os.getenv("FORWARD_MODE", "copy").strip().lower()
    
    raw_keywords = os.getenv("KEYWORDS", "").strip()
    KEYWORDS: List[str] = [k.strip().lower() for k in raw_keywords.split(",") if k.strip()]

    @classmethod
    def validate(cls):
        """Validate required configuration values."""
        errors = []
        if not cls.API_ID:
            errors.append("API_ID is required in .env")
        if not cls.API_HASH:
            errors.append("API_HASH is required in .env")
        if not cls.SOURCE_CHATS:
            errors.append("SOURCE_CHAT_ID is required in .env")
        if not cls.TARGET_CHATS:
            errors.append("TARGET_CHAT_ID is required in .env")
        
        if cls.FORWARD_MODE not in ["copy", "forward"]:
            logger.warning("FORWARD_MODE invalid, default to 'copy'")
            cls.FORWARD_MODE = "copy"

        if errors:
            for err in errors:
                logger.error(err)
            raise ValueError("Invalid configuration in .env. Please check the logs.")
