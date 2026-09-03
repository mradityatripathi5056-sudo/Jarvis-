"""
skills/memory_context_skill.py
------------------------------------------------------------
Long-term project context + behavior learning. Jarvis ke existing
`remember_fact`/`recall_fact` (jarvis_memory.json) aur
`jarvis_history.json` (last 10 turns) ke upar ye extra layer hai:

- set_project_context / get_project_context: kisi bhi project ke
  baare mein lambi context ek naam se save/retrieve karo (jaise
  "For Future app" -> "vanilla JS + Supabase, PWA, group study timer").
  remember_fact chhoti facts ke liye hai, ye lambi project context ke
  liye better hai.
- list_recent_topics: history file se andaza lagata hai recently kis
  baare mein baat hui.
- log_usage / usage_summary: kaunsa action kitni baar use hua, isse
  Jarvis dheere-dheere "seekhta" hai user ka pattern (jaise agar user
  roz raat 10 baje "night mode on" bolta hai to Jarvis suggest kar
  sakta hai).

Sab data jarvis_memory.json/jarvis_context.json/jarvis_usage.json
files mein local hi save hota hai - kahin cloud pe nahi jaata.
"""

import os
import threading
from collections import Counter
from datetime import datetime

from json_utils import safe_json_load, safe_json_save

CONTEXT_FILE = "jarvis_context.json"
USAGE_FILE = "jarvis_usage.json"
_lock = threading.Lock()


def _load(path: str) -> dict:
    return safe_json_load(path, {})


def _save(path: str, data: dict):
    with _lock:
        safe_json_save(path, data)


def set_project_context(params: dict) -> str:
    project = params.get("project", "").strip()
    context = params.get("context", "").strip()
    if not project or not context:
        return "Project ka naam aur uski context, dono batao."
    data = _load(CONTEXT_FILE)
    data[project.lower()] = {"context": context, "updated": datetime.now().isoformat()}
    _save(CONTEXT_FILE, data)
    return f"'{project}' ki context yaad rakh li."


def get_project_context(params: dict) -> str:
    project = params.get("project", "").strip().lower()
    data = _load(CONTEXT_FILE)
    if not project:
        if not data:
            return "Abhi tak koi project context save nahi hai."
        return "Saved projects:\n" + "\n".join(f"{k}: {v['context']}" for k, v in data.items())
    if project in data:
        return data[project]["context"]
    for k, v in data.items():
        if project in k or k in project:
            return v["context"]
    return f"'{project}' ke baare mein mujhe kuch yaad nahi hai."


def list_recent_topics(params: dict) -> str:
    history_file = "jarvis_history.json"
    if not os.path.exists(history_file):
        return "Abhi koi recent conversation nahi hai."
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        user_msgs = [h["content"] for h in history if h.get("role") == "user"]
        if not user_msgs:
            return "Abhi koi recent conversation nahi hai."
        return "Recent topics:\n" + "\n".join(f"- {m}" for m in user_msgs[-8:])
    except Exception as e:
        return f"History padh nahi paya: {e}"


def log_usage(action_name: str):
    """Skill files ke bahar se bhi call ho sakta hai - but yahan hum
    isko ek action ki tarah expose kar rahe hain taaki brain.py chahe
    to future mein automatically call kare."""
    data = _load(USAGE_FILE)
    data[action_name] = data.get(action_name, 0) + 1
    _save(USAGE_FILE, data)


def usage_summary(params: dict) -> str:
    data = _load(USAGE_FILE)
    if not data:
        return "Abhi tak koi usage data nahi hai."
    top = Counter(data).most_common(10)
    return "Sabse zyada use hone wale actions:\n" + "\n".join(f"{name}: {count} baar" for name, count in top)


ACTIONS = {
    "set_project_context": set_project_context,
    "get_project_context": get_project_context,
    "list_recent_topics": list_recent_topics,
    "usage_summary": usage_summary,
}

DOCS = """
- set_project_context: {"project": "For Future app", "context": "Vanilla JS + Supabase PWA, group study timer"}
    (lambi project details yaad rakhne ke liye - remember_fact chhoti
    facts ke liye hai, ye poore project context ke liye)
- get_project_context: {"project": "For Future app"}  (project khaali chhodo to sab projects list ho jaayenge)
- list_recent_topics: {}  (recent conversation ka summary)
- usage_summary: {}  (kaunse commands sabse zyada use kiye - pattern samajhne ke liye)

Example:
User: "For Future app ke baare mein yaad rakho - vanilla JS aur Supabase se bana hai"
-> {"actions": [{"action": "set_project_context", "params": {"project": "For Future app", "context": "Vanilla JS aur Supabase se bana hai"}}]}
"""
