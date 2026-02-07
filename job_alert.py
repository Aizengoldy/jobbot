import requests
from bs4 import BeautifulSoup
import os
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

URL = "https://www.indeed.com/jobs?q=project+manager&l=remote"
SEEN_FILE = "seen.json"

def send(msg):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(api, data={"chat_id": CHAT_ID, "text": msg})

def load_seen():
    if os.path.exists(SEEN_FILE):
        return set(json.load(open(SEEN_FILE)))
    return set()

def save_seen(data):
    json.dump(list(data), open(SEEN_FILE, "w"))

def run():
    r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = soup.select("a.tapItem")

    seen = load_seen()
    new_seen = set(seen)

    for j in jobs:
        title = j.select_one("h2 span").text.strip()
        link = "https://www.indeed.com" + j["href"]

        if link not in seen:
            send(f"NEW JOB:\n{title}\n{link}")
            new_seen.add(link)

    save_seen(new_seen)

run()
