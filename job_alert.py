import requests
import os
import json
import time
import re
from html import unescape

# ------------ CONFIG ------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API_SEND = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
SEEN_FILE = "seen.json"

# Titles you want (case-insensitive substr checks)
JOB_TITLES = [
    "us recruiter",
    "recruiter",
    "hr executive",
    "hr operations",
    "hr operations associate",
    "hr coordinator",
    "hr coordinator",
    "hrops",
]

# Locations you want (case-insensitive)
LOCATIONS = [
    "delhi",
    "ncr",
    "noida",
    "gurgaon",
    "gurugram"
]

# Experience requirements heuristics (we want ZERO experience)
ZERO_EXPERIENCE_TERMS = [
    "fresher",
    "freshers",
    "no experience",
    "0 years",
    "0-1",
    "entry level",
    "entry-level",
    "graduate",
    "trainee",
    "junior",
]

# Exclude if any of these appear (senior roles / internships / unpaid / contractor)
EXCLUDE_TERMS = [
    "senior",
    "sr.",
    "sr ",
    "manager",
    "lead",
    "intern",
    "internship",
    "volunteer",
    "unpaid",
    "contractor",
    "freelance"
]

# Salary filter (INR). If salary is present and clearly in INR, require it to be within this range.
MIN_SALARY_INR = 200_000   # 2,00,000
MAX_SALARY_INR = 600_000   # 6,00,000

# How many new matches to send per run
MAX_SEND_PER_RUN = 3

# Poll interval (seconds)
SLEEP_SECONDS = 300
# ------------ END CONFIG ------------

def send_telegram(text):
    try:
        resp = requests.post(API_SEND, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
        print("Telegram:", resp.status_code, resp.text[:500])
        return resp.status_code == 200
    except Exception as e:
        print("Telegram exception:", e)
        return False

def load_seen():
    try:
        if os.path.exists(SEEN_FILE):
            return set(json.load(open(SEEN_FILE, "r", encoding="utf-8")))
    except Exception as e:
        print("load_seen error:", e)
    return set()

def save_seen(seen):
    try:
        json.dump(list(seen), open(SEEN_FILE, "w", encoding="utf-8"))
    except Exception as e:
        print("save_seen error:", e)

def text_lower(item):
    if not item:
        return ""
    return unescape(item).lower()

def contains_any(text, tokens):
    t = text_lower(text)
    for token in tokens:
        if token.lower() in t:
            return True
    return False

def parse_salary_inr(salary_str):
    """
    Try to detect INR salary from a string and return (min_inr, max_inr) or None.
    Supports patterns like: "₹3,00,000", "3 LPA", "3 lakh - 5 lakh", "INR 3,00,000"
    """
    if not salary_str:
        return None
    s = salary_str.replace(",", " ").replace("\u00A0", " ").lower()
    # quick currency check: require INR symbol or words 'inr' 'rs' '₹' or 'lakh'/'lac'
    if not (("₹" in salary_str) or ("inr" in s) or (" rs " in s) or ("rs " in s) or ("lakh" in s) or ("lac" in s) or ("lpa" in s)):
        return None

    # Normalize words
    s = s.replace("lacs", "lakh").replace("lakhs", "lakh")
    # Extract all numbers (including decimals)
    nums = re.findall(r"(\d+(?:\.\d+)?)", s)
    if not nums:
        return None

    # Convert textual amounts to INR
    vals = []
    for i, n in enumerate(nums):
        try:
            val = float(n)
        except:
            continue
        # check unit near the number (look around in string)
        # attempt to find 'lakh' or 'lpa' within 10 chars after the number
        idx = s.find(n)
        unit_segment = s[idx: idx + 20]
        if "lakh" in unit_segment or "lac" in unit_segment or "lpa" in unit_segment:
            val_inr = int(val * 100_000)
        elif "₹" in unit_segment or "rs" in unit_segment or "inr" in unit_segment:
            val_inr = int(val)
            # if number is small (like 3) and '₹' missing near, it might be 3 LPA; fallback not applied here
        else:
            # If number less than 100 and 'lakh' not found, it might mean lakhs: e.g., '3-5' with 'lakh' earlier.
            if val < 100:
                # try to detect 'lakh' anywhere nearby
                if "lakh" in s or "lpa" in s or "lac" in s:
                    val_inr = int(val * 100_000)
                else:
                    # ambiguous: treat as simple rupees (not typical); skip
                    val_inr = int(val)
            else:
                val_inr = int(val)
        vals.append(val_inr)

    if not vals:
        return None
    if len(vals) == 1:
        return (vals[0], vals[0])
    return (min(vals), max(vals))

def job_matches(job):
    title = text_lower(job.get("title", ""))
    desc = text_lower(job.get("description", ""))
    location_field = text_lower(job.get("candidate_required_location", "") or job.get("location", ""))

    # 1) Must match one of the job title tokens
    title_match = any(t.lower() in title for t in JOB_TITLES)
    # Also check tags if available
    tags = [t.lower() for t in job.get("tags", [])] if job.get("tags") else []
    if not title_match:
        for tkn in JOB_TITLES:
            if tkn.lower() in " ".join(tags):
                title_match = True
                break
    if not title_match:
        return False

    # 2) Location must match one of LOCATIONS keywords
    loc_ok = any(loc.lower() in location_field for loc in LOCATIONS) or any(loc.lower() in title for loc in LOCATIONS) or any(loc.lower() in desc for loc in LOCATIONS)
    if not loc_ok:
        return False

    # 3) Exclude if contains exclude terms (intern, senior, manager, unpaid, volunteer)
    if contains_any(title + " " + desc, EXCLUDE_TERMS):
        return False

    # 4) Experience: require a zero-experience indicator OR absence of an explicit >0 requirement
    # Accept if description/title includes positive zero-experience terms
    if contains_any(title + " " + desc, ZERO_EXPERIENCE_TERMS):
        exp_ok = True
    else:
        # If description explicitly mentions 'experience' with years >0, reject (heuristic)
        m = re.search(r"(\d+)\s*(?:\+|\-)?\s*(?:years|yrs|year)", desc)
        if m:
            years = int(m.group(1))
            if years > 0:
                exp_ok = False
            else:
                exp_ok = True
        else:
            # Unknown: assume not a match for zero experience
            exp_ok = False
    if not exp_ok:
        return False

    # 5) Exclude unpaid / volunteer
    if "unpaid" in desc or "volunteer" in desc:
        return False

    # 6) Salary filter if present and in INR
    salary_field = job.get("salary") or ""
    parsed = parse_salary_inr(salary_field)
    if parsed:
        min_sal, max_sal = parsed
        # check overlap with desired range
        if max_sal < MIN_SALARY_INR or min_sal > MAX_SALARY_INR:
            return False

    # Passed all checks
    return True

def format_job_message(job):
    title = job.get("title") or "No title"
    company = job.get("company_name") or job.get("company") or ""
    location = job.get("candidate_required_location") or job.get("location") or ""
    salary = job.get("salary") or ""
    url = job.get("url") or job.get("job_apply_link") or ""
    msg = f"*{title}*\n{company}\nLocation: {location}\n"
    if salary:
        msg += f"Salary: {salary}\n"
    msg += f"{url}"
    # Telegram markdown escaped lightly (we'll avoid complex escaping)
    return msg

def fetch_jobs():
    try:
        r = requests.get(REMOTIVE_URL, timeout=20)
        if r.status_code != 200:
            print("Remotive non-200:", r.status_code)
            return []
        data = r.json()
        return data.get("jobs", [])
    except Exception as e:
        print("fetch_jobs exception:", e)
        return []

def run_once():
    print("Checking Remotive...")
    jobs = fetch_jobs()
    print("Total jobs fetched:", len(jobs))
    seen = load_seen()
    new_seen = set(seen)
    sent = 0

    for job in jobs:
        jid = str(job.get("id") or job.get("job_id") or job.get("url"))
        if jid in seen:
            continue
        if job_matches(job):
            msg = format_job_message(job)
            ok = send_telegram(msg)
            if ok:
                new_seen.add(jid)
                sent += 1
            else:
                print("Telegram send failed for:", jid)
            if sent >= MAX_SEND_PER_RUN:
                break

    save_seen(new_seen)
    print(f"Sent {sent} new matches.")

if __name__ == "__main__":
    # quick start heartbeat; job runs every SLEEP_SECONDS
    while True:
        run_once()
        time.sleep(SLEEP_SECONDS)
