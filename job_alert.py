import requests
import os
import json
import time
import traceback

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

URL = "https://remotive.com/api/remote-jobs"
SEEN_FILE = "seen.json"


def send(msg):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(api, data={
        "chat_id": CHAT_ID,
        "text": msg
    })
    print("Telegram send status:", r.status_code)


def load_seen():
    if os.path.exists(SEEN_FILE):
        return set(json.load(open(SEEN_FILE)))
    return set()


def save_seen(seen):
    json.dump(list(seen), open(SEEN_FILE, "w"))


def run_once():
    try:
        print("Checking jobs from Remotive API")

        r = requests.get(URL, timeout=20)
        if r.status_code != 200:
            print("Non-200 response:", r.status_code)
            return

        data = r.json()
        jobs = data.get("jobs", [])

        seen = load_seen()
        new_seen = set(seen)

        for job in jobs:
            title = job.get("title")
            link = job.get("url")

            if not title or not link:
                continue

            if link not in seen:
                msg = f"NEW JOB:\n{title}\n{link}"
                print("Sending:", title)
                send(msg)
                new_seen.add(link)

        save_seen(new_seen)

    except Exception as e:
        print("ERROR:", e)
        print(traceback.format_exc())


while True:
    run_once()
    time.sleep(300)
