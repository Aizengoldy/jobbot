import requests
import os
import json
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

URL = "https://remotive.com/api/remote-jobs"
SEEN_FILE = "seen.json"

def send(msg):
    r = requests.post(API, data={
        "chat_id": CHAT_ID,
        "text": msg
    })
    print("Telegram:", r.status_code, r.text)

def load_seen():
    if os.path.exists(SEEN_FILE):
        return set(json.load(open(SEEN_FILE)))
    return set()

def save_seen(data):
    json.dump(list(data), open(SEEN_FILE, "w"))

def fetch_jobs():
    res = requests.get(URL).json()
    return res["jobs"]

# ---- TEST MESSAGE ON START ----
send("Bot is running correctly ✅")

seen = load_seen()

while True:
    jobs = fetch_jobs()

    for job in jobs[:10]:
        jid = job["id"]
        title = job["title"]
        link = job["url"]

        if jid not in seen:
            send(f"NEW JOB:\n{title}\n{link}")
            seen.add(jid)

    save_seen(seen)
    time.sleep(600)   # every 10 minutes
