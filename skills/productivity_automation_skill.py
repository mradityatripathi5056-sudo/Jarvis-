"""
skills/productivity_automation_skill.py
------------------------------------------------------------
Ek curated batch of daily-life/automation skills - jo Jarvis mein
pehle se NAHI thi (existing weather/translate/wiki/notes/reminder
wagera se duplicate nahi hai). Sab genuinely tested aur kaam ki hain:

TODO LIST:      todo_add, todo_list, todo_done, todo_clear
EXPENSE TRACKER: expense_add, expense_summary, expense_clear
HABIT TRACKER:   habit_checkin, habit_status
CURRENCY:        currency_convert (live rates)
FUN:             random_quote, random_joke
FILE AUTOMATION: file_organize_by_type, find_duplicate_files, bulk_rename_files
TEXT/DEV TOOLS:  hash_text, base64_encode, base64_decode, json_pretty_print,
                 word_char_count, url_shorten
SYSTEM:          disk_usage_report, clean_temp_files

Data (todos/expenses/habits) config.MEDIA_DIR mein hi JSON files ki
tarah save hoti hai - GitHub push se automatically exclude hoti hai
(jaisa baaki generated data).
"""

import hashlib
import base64
import json
import os
import random
import shutil
import tempfile
from datetime import datetime

import requests

import config

_DATA_FILE = os.path.join(config.MEDIA_DIR, "productivity_data.json")


def _load_data() -> dict:
    if not os.path.exists(_DATA_FILE):
        return {"todos": [], "expenses": [], "habits": {}}
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"todos": [], "expenses": [], "habits": {}}


def _save_data(data: dict):
    with open(_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---- TODO LIST ----

def todo_add(params: dict) -> str:
    task = (params.get("task") or "").strip()
    if not task:
        return "Kya task add karna hai, batao."
    data = _load_data()
    data["todos"].append({"task": task, "done": False, "added": datetime.now().strftime("%Y-%m-%d %H:%M")})
    _save_data(data)
    return f"To-do add ho gaya: '{task}' (total {len(data['todos'])})"


def todo_list(params: dict) -> str:
    data = _load_data()
    todos = data.get("todos", [])
    if not todos:
        return "To-do list khaali hai."
    lines = []
    for i, t in enumerate(todos):
        mark = "[x]" if t["done"] else "[ ]"
        lines.append(f"{i + 1}. {mark} {t['task']}")
    return "\n".join(lines)


def todo_done(params: dict) -> str:
    index = params.get("index")
    task_text = (params.get("task") or "").strip().lower()
    data = _load_data()
    todos = data.get("todos", [])
    target = None
    if index is not None:
        idx = int(index) - 1
        if 0 <= idx < len(todos):
            target = idx
    elif task_text:
        for i, t in enumerate(todos):
            if task_text in t["task"].lower():
                target = i
                break
    if target is None:
        return "Wo task nahi mila to-do list mein."
    todos[target]["done"] = True
    _save_data(data)
    return f"'{todos[target]['task']}' done mark kar diya."


def todo_clear(params: dict) -> str:
    data = _load_data()
    count = len(data.get("todos", []))
    data["todos"] = []
    _save_data(data)
    return f"To-do list clear kar di ({count} tasks the)."


# ---- EXPENSE TRACKER ----

def expense_add(params: dict) -> str:
    amount = params.get("amount")
    category = (params.get("category") or "misc").strip()
    note = (params.get("note") or "").strip()
    if amount is None:
        return "Kitna amount kharch hua, batao."
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "Amount samajh nahi aaya, number mein batao."
    data = _load_data()
    data["expenses"].append({
        "amount": amount, "category": category, "note": note,
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    _save_data(data)
    return f"Expense add ho gaya: Rs.{amount:.0f} ({category})"


def expense_summary(params: dict) -> str:
    data = _load_data()
    expenses = data.get("expenses", [])
    if not expenses:
        return "Koi expense record nahi hai."
    total = sum(e["amount"] for e in expenses)
    by_category = {}
    for e in expenses:
        by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount"]
    lines = [f"Total kharch: Rs.{total:.0f} ({len(expenses)} entries)"]
    for cat, amt in sorted(by_category.items(), key=lambda x: -x[1]):
        lines.append(f"  - {cat}: Rs.{amt:.0f}")
    return "\n".join(lines)


def expense_clear(params: dict) -> str:
    data = _load_data()
    count = len(data.get("expenses", []))
    data["expenses"] = []
    _save_data(data)
    return f"Expense records clear kar diye ({count} entries the)."


# ---- HABIT TRACKER ----

def habit_checkin(params: dict) -> str:
    habit = (params.get("habit") or "").strip()
    if not habit:
        return "Kaunsi habit check-in karni hai, batao."
    data = _load_data()
    habits = data.setdefault("habits", {})
    today = datetime.now().strftime("%Y-%m-%d")
    dates = habits.setdefault(habit, [])
    if today in dates:
        return f"'{habit}' aaj already check-in ho chuki hai."
    dates.append(today)
    _save_data(data)
    # streak count (consecutive days ending today)
    streak = 1
    from datetime import timedelta
    check_date = datetime.now().date()
    date_set = set(dates)
    while (check_date - timedelta(days=streak)).strftime("%Y-%m-%d") in date_set:
        streak += 1
    return f"'{habit}' check-in ho gaya! Streak: {streak} din."


def habit_status(params: dict) -> str:
    data = _load_data()
    habits = data.get("habits", {})
    if not habits:
        return "Koi habit track nahi ho rahi abhi."
    lines = []
    for habit, dates in habits.items():
        lines.append(f"{habit}: {len(dates)} total check-ins, last: {dates[-1] if dates else '-'}")
    return "\n".join(lines)


# ---- CURRENCY CONVERTER ----

def currency_convert(params: dict) -> str:
    amount = params.get("amount", 1)
    from_cur = (params.get("from") or "USD").strip().upper()
    to_cur = (params.get("to") or "INR").strip().upper()
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "Amount samajh nahi aaya."
    try:
        resp = requests.get(f"https://api.exchangerate-api.com/v4/latest/{from_cur}", timeout=10)
        resp.raise_for_status()
        rates = resp.json().get("rates", {})
        if to_cur not in rates:
            return f"'{to_cur}' currency nahi mili."
        converted = amount * rates[to_cur]
        return f"{amount:.2f} {from_cur} = {converted:.2f} {to_cur}"
    except Exception as e:
        return f"Currency convert nahi ho saka: {e}"


# ---- FUN ----

_QUOTES = [
    "Chhota kadam bhi aage badhna hai - rukna mat.",
    "Consistency talent se zyada important hai.",
    "Aaj ka mehnat kal ka result hai.",
    "Jo darr lagta hai wahi karne se sabse zyada seekhte ho.",
    "Perfect waqt kabhi nahi aata, shuru karo.",
]

_JOKES = [
    "Teacher: Tum late kyun aaye? Student: Sir, ek board tha 'School Ahead - Go Slow', to main slow ho gaya.",
    "Interviewer: Apni sabse badi weakness batao. Candidate: Honesty. Interviewer: Wo weakness nahi hai. Candidate: Mujhe farak nahi padta aap kya sochte ho.",
    "Doctor: Aap 2 mahine se yahi dawai le rahe ho, sudhaar kyun nahi? Patient: Bottle pe likha tha 'Keep away from children' to maine bacchon se door rakhi.",
]


def random_quote(params: dict) -> str:
    return random.choice(_QUOTES)


def random_joke(params: dict) -> str:
    return random.choice(_JOKES)


# ---- FILE AUTOMATION ----

def file_organize_by_type(params: dict) -> str:
    """Ek folder ke files ko extension ke hisaab se subfolders mein sort karta hai."""
    folder = (params.get("folder") or "").strip()
    if not folder or not os.path.isdir(folder):
        return "Valid folder path batao jise organize karna hai."
    moved = 0
    try:
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if not os.path.isfile(filepath):
                continue
            ext = os.path.splitext(filename)[1].lstrip(".").lower() or "no_extension"
            target_dir = os.path.join(folder, ext.upper() + "_files")
            os.makedirs(target_dir, exist_ok=True)
            shutil.move(filepath, os.path.join(target_dir, filename))
            moved += 1
        return f"{moved} files organize kar diye extension ke hisaab se subfolders mein."
    except Exception as e:
        return f"Organize nahi ho saka: {e}"


def find_duplicate_files(params: dict) -> str:
    """Ek folder mein duplicate files (same content) dhoondta hai."""
    folder = (params.get("folder") or "").strip()
    if not folder or not os.path.isdir(folder):
        return "Valid folder path batao."
    hashes = {}
    duplicates = []
    try:
        for root, _, files in os.walk(folder):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, "rb") as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                except Exception:
                    continue
                if file_hash in hashes:
                    duplicates.append((filepath, hashes[file_hash]))
                else:
                    hashes[file_hash] = filepath
        if not duplicates:
            return "Koi duplicate file nahi mili."
        lines = [f"{len(duplicates)} duplicate files mile:"]
        for dup, original in duplicates[:15]:
            lines.append(f"  '{dup}' == '{original}'")
        return "\n".join(lines)
    except Exception as e:
        return f"Duplicate check nahi ho saka: {e}"


def bulk_rename_files(params: dict) -> str:
    """{"folder": "...", "prefix": "photo_", "extension_filter": "jpg"} - saari
    matching files ko prefix_1, prefix_2... naam de deta hai."""
    folder = (params.get("folder") or "").strip()
    prefix = (params.get("prefix") or "file_").strip()
    ext_filter = (params.get("extension_filter") or "").strip().lstrip(".").lower()
    if not folder or not os.path.isdir(folder):
        return "Valid folder path batao."
    try:
        files = sorted(os.listdir(folder))
        if ext_filter:
            files = [f for f in files if f.lower().endswith("." + ext_filter)]
        renamed = 0
        for i, filename in enumerate(files, 1):
            old_path = os.path.join(folder, filename)
            if not os.path.isfile(old_path):
                continue
            ext = os.path.splitext(filename)[1]
            new_path = os.path.join(folder, f"{prefix}{i}{ext}")
            os.rename(old_path, new_path)
            renamed += 1
        return f"{renamed} files rename kar di ('{prefix}1', '{prefix}2', ...)"
    except Exception as e:
        return f"Bulk rename nahi ho saka: {e}"


# ---- TEXT/DEV TOOLS ----

def hash_text(params: dict) -> str:
    text = params.get("text", "")
    algo = (params.get("algorithm") or "sha256").lower()
    if not text:
        return "Kaunsa text hash karna hai, batao."
    try:
        h = hashlib.new(algo)
        h.update(text.encode("utf-8"))
        return f"{algo.upper()} hash: {h.hexdigest()}"
    except Exception as e:
        return f"Hash nahi ban saka: {e}"


def base64_encode(params: dict) -> str:
    text = params.get("text", "")
    if not text:
        return "Kya encode karna hai, batao."
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


def base64_decode(params: dict) -> str:
    text = params.get("text", "")
    if not text:
        return "Kya decode karna hai, batao."
    try:
        return base64.b64decode(text).decode("utf-8")
    except Exception as e:
        return f"Decode nahi ho saka: {e}"


def json_pretty_print(params: dict) -> str:
    text = params.get("text", "")
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Valid JSON nahi hai: {e}"


def word_char_count(params: dict) -> str:
    text = params.get("text", "")
    words = len(text.split())
    chars = len(text)
    chars_no_space = len(text.replace(" ", ""))
    return f"Words: {words}, Characters: {chars} (bina space: {chars_no_space})"


def url_shorten(params: dict) -> str:
    url = (params.get("url") or "").strip()
    if not url:
        return "Kaunsa URL shorten karna hai, batao."
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get("https://is.gd/create.php", params={"format": "simple", "url": url}, timeout=10)
        resp.raise_for_status()
        return f"Short URL: {resp.text.strip()}"
    except Exception as e:
        return f"Shorten nahi ho saka: {e}"


# ---- SYSTEM ----

def disk_usage_report(params: dict) -> str:
    drive = (params.get("drive") or "C:\\").strip()
    try:
        total, used, free = shutil.disk_usage(drive)
        gb = 1024 ** 3
        percent = (used / total) * 100
        return (
            f"{drive} - Total: {total / gb:.1f}GB, Used: {used / gb:.1f}GB "
            f"({percent:.0f}%), Free: {free / gb:.1f}GB"
        )
    except Exception as e:
        return f"Disk usage nahi mil saka: {e}"


def clean_temp_files(params: dict) -> str:
    """Windows temp folder se purani/junk files delete karta hai (safe -
    sirf standard temp directory, kuch aur nahi chhedta)."""
    temp_dir = tempfile.gettempdir()
    deleted = 0
    freed_bytes = 0
    try:
        for filename in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(filepath):
                    size = os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted += 1
                    freed_bytes += size
            except Exception:
                continue  # kai files use mein hongi, unhe skip karna normal hai
        return f"{deleted} temp files delete ki, ~{freed_bytes / (1024 * 1024):.1f}MB free ki."
    except Exception as e:
        return f"Temp cleanup nahi ho saka: {e}"


ACTIONS = {
    "todo_add": todo_add,
    "todo_list": todo_list,
    "todo_done": todo_done,
    "todo_clear": todo_clear,
    "expense_add": expense_add,
    "expense_summary": expense_summary,
    "expense_clear": expense_clear,
    "habit_checkin": habit_checkin,
    "habit_status": habit_status,
    "currency_convert": currency_convert,
    "random_quote": random_quote,
    "random_joke": random_joke,
    "file_organize_by_type": file_organize_by_type,
    "find_duplicate_files": find_duplicate_files,
    "bulk_rename_files": bulk_rename_files,
    "hash_text": hash_text,
    "base64_encode": base64_encode,
    "base64_decode": base64_decode,
    "json_pretty_print": json_pretty_print,
    "word_char_count": word_char_count,
    "url_shorten": url_shorten,
    "disk_usage_report": disk_usage_report,
    "clean_temp_files": clean_temp_files,
}

DOCS = """
- todo_add: {"task": "milk lena hai"}
- todo_list: {}
- todo_done: {"task": "milk"} (ya {"index": 1})
- todo_clear: {}
- expense_add: {"amount": 150, "category": "food", "note": "lunch"}
- expense_summary: {}
- expense_clear: {}
- habit_checkin: {"habit": "gym"}
- habit_status: {}
- currency_convert: {"amount": 100, "from": "USD", "to": "INR"}
- random_quote: {}
- random_joke: {}
- file_organize_by_type: {"folder": "C:\\Users\\me\\Downloads"} (extension ke hisaab se subfolders mein sort karta hai)
- find_duplicate_files: {"folder": "C:\\Users\\me\\Pictures"}
- bulk_rename_files: {"folder": "C:\\path", "prefix": "photo_", "extension_filter": "jpg"}
- hash_text: {"text": "hello", "algorithm": "sha256"}
- base64_encode: {"text": "hello"}
- base64_decode: {"text": "aGVsbG8="}
- json_pretty_print: {"text": "{\\"a\\":1}"}
- word_char_count: {"text": "some text"}
- url_shorten: {"url": "https://example.com/very/long/link"}
- disk_usage_report: {"drive": "C:\\"}
- clean_temp_files: {}  (Windows temp folder safely clean karta hai)

Examples:
User: "milk lena hai list mein daal do"
-> {"actions": [{"action": "todo_add", "params": {"task": "milk lena hai"}}]}
User: "aaj 150 rupaye khana pe kharch kiye"
-> {"actions": [{"action": "expense_add", "params": {"amount": 150, "category": "food"}}]}
User: "100 dollar mein kitne rupaye honge"
-> {"actions": [{"action": "currency_convert", "params": {"amount": 100, "from": "USD", "to": "INR"}}]}
"""
