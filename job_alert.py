import requests
from bs4 import BeautifulSoup
import os
import json
import time
import traceback

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

URL = "https://www.indeed.com/jobs?q=project+manager&l=remote"
SEEN_FILE = "seen.json"

def send(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: BOT_TOKEN or CHAT_ID missing")
        return
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(api, data={"chat_id": CHAT_ID, "text": msg})
        print("Telegram send status:", resp.status_code, resp.text[:200])
    except Exception as e:
        print("Telegram send exception:", e)
        print(traceback.format_exc())

def load_seen():
    try:
        if os.path.exists(SEEN_FILE):
            return set(json.load(open(SEEN_FILE, "r")))
    except Exception as e:
        print("load_seen error:", e)
    return set()

def save_seen(data):
    try:
        json.dump(list(data), open(SEEN_FILE, "w"))
    except Exception as e:
        print("save_seen error:", e)

def run_once():
    try:
        print("Checking jobs at URL:", URL)
        r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        if r.status_code != 200:
            print("Non-200 response:", r.status_code)
            return
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = soup.select("a.tapItem")
        print("Found job elements:", len(jobs))

        seen = load_seen()
        new_seen = set(seen)

        for j in jobs:
            # safe extraction with checks
            title_el = j.select_one("h2 span")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = j.get("href")
            if not href:
                continue
            link = href if href.startswith("http") else "https://www.indeed.com" + href

            if link not in seen:
                msg = "NEW JOB:\n" + title + "\n" + link
                print("Sending message for:", title)
                send(msg)
                new_seen.add(link)

        save_seen(new_seen)
    except Exception as e:
        print("run_once exception:", e)
        print(traceback.format_exc())

if __name__ == "__main__":
    # loop forever; Railway will keep the worker running
    while True:
        run_once()
        # check every 300 seconds (5 minutes)
        time.sleep(300)
