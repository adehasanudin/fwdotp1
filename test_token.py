import urllib.request
import json
from config import Config

token = Config.BOT_TOKEN
print(f"Testing BOT_TOKEN: '{token}'")

url = f"https://api.telegram.org/bot{token}/getMe"
try:
    with urllib.request.urlopen(url) as resp:
        print("SUCCESS! Bot info:", resp.read().decode('utf-8'))
except Exception as e:
    print("FAILED with error:", e)
    if hasattr(e, 'read'):
        print("Response body:", e.read().decode('utf-8'))
