import requests
import os
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

print("Starting bot...")

API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send(msg):
    r = requests.post(API, data={
        "chat_id": CHAT_ID,
        "text": msg
    })
    print("Telegram:", r.status_code, r.text)

# Test message
send("Bot is running correctly ✅")

# Keep container alive
while True:
    print("Heartbeat...")
    time.sleep(30)
