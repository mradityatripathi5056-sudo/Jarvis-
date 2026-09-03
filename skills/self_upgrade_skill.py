"""
skills/self_upgrade_skill.py
------------------------------------------------------------
Jarvis ko khud apne aap mein NAYE features/skills add karne ki
ability deta hai - bina actions.py/brain.py chhede.

Kaise kaam karta hai:
1. User bolta hai: "bluetooth on/off ka feature add kar do"
2. Jarvis (OpenRouter LLM) us request ko padh kar ek poora naya
   Python skill file generate karta hai (ACTIONS + DOCS format mein,
   jaisa skills/example_skill.py mein hai).
3. Generated code pehle skills/_pending/ folder mein save hota hai
   (LIVE skills/ mein turant nahi jaata) aur syntax-check hota hai.
4. User se confirmation liya jaata hai (kyunki ye DESTRUCTIVE hai -
   phone se allowed nahi, GUI/CLI se "haan/confirm" bolna padega).
5. Confirm karne par file skills/ mein move ho jaati hai. Jarvis ko
   restart karna padta hai taaki naya skill load ho (skill_loader.py
   restart pe automatically pick kar lega).

SAFETY NOTES (zaroor padhna):
- Ye feature LLM se code generate karwata hai - kabhi kabhi galat ya
  adhura code aa sakta hai. Isliye syntax-check + confirmation +
  "_pending" staging folder rakha gaya hai.
- run_shell_command/run_python_code jaisa hi, ye bhi DESTRUCTIVE hai
  - phone/remote se allowed NAHI, sirf trusted user (GUI/CLI) se.
- Generated file kabhi bhi existing actions.py/brain.py/config.py ko
  OVERWRITE nahi karti - sirf naya standalone skill file banti hai.
  Isse "poora bot crash" hone ka risk bahut kam ho jaata hai.
"""

import os
import re
import ast
import requests
import config

PENDING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_pending")
SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))

os.makedirs(PENDING_DIR, exist_ok=True)

try:
    for _action_name in ("self_add_feature", "self_confirm_feature"):
        if _action_name not in config.DESTRUCTIVE_ACTIONS:
            config.DESTRUCTIVE_ACTIONS.append(_action_name)
except Exception:
    pass


SYSTEM_PROMPT = """Tum ek Python developer ho jo Jarvis assistant ke liye NAYE
skill files likhte ho. Sirf ek self-contained Python file ka code do,
kuch aur text nahi (na explanation, na markdown fences).

File mein sirf ye hona chahiye:
1. Zaroori imports (sirf standard library ya already-common packages:
   requests, os, sys, subprocess, psutil, platform, etc.)
2. Ek ya zyada function jo ek dict "params" leta hai aur ek STRING
   return karta hai (jo Jarvis bolega).
3. ACTIONS = {"action_name": function, ...} dict
4. DOCS = \"\"\"...\"\"\"  -> hinglish mein short docs, action ka naam,
   params format, aur ek example, jaisa neeche diya hai:

- action_name: {"param": "value"}
    (kya karta hai, ek line mein)

Example:
User: "..."
-> {"actions": [{"action": "action_name", "params": {...}}]}

RULES:
- Agar feature OS-specific hai (Windows Bluetooth, brightness, etc),
  Windows ke liye likho (ye bot mostly Windows pe chalta hai), aur
  try/except mein wrap karo taaki bina us OS/package ke bhi crash na
  ho, balki clear error string return kare.
- Kabhi bhi os.system/subprocess se destructive commands (format,
  delete system files, registry edits jo system tod sakte hain) mat
  likhna.
- Agar package install nahi hai to except block mein bolna "pip
  install <package>" karna padega, crash mat hone dena.
- Sirf raw Python code do, bina ``` fences ke.
"""


def _extract_code(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _syntax_ok(code: str) -> tuple:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, str(e)


def self_add_feature(params: dict) -> str:
    """LLM se naya skill file generate karwata hai aur _pending mein
    staging ke liye rakhta hai (abhi live nahi hota)."""
    request = params.get("request", "").strip()
    if not request:
        return "Kaunsa feature add karna hai, thoda detail mein batao."

    if not config.OPENROUTER_API_KEY:
        return "OPENROUTER_API_KEY set nahi hai, naya feature generate nahi kar sakta."

    try:
        resp = requests.post(
            config.OPENROUTER_URL,
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
            json={
                "model": config.OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Feature request: {request}"},
                ],
            },
            timeout=60,
        )
        if not resp.ok:
            return f"Feature generate karne mein error: {resp.text[:300]}"
        content = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"LLM se baat karne mein error: {e}"

    code = _extract_code(content)
    ok, err = _syntax_ok(code)
    if not ok:
        return f"Generated code mein syntax error tha, isliye add nahi kiya: {err}"

    slug = re.sub(r"[^a-z0-9_]", "", request.lower().replace(" ", "_"))[:40] or "new_feature"
    filename = f"{slug}_skill.py"
    pending_path = os.path.join(PENDING_DIR, filename)
    with open(pending_path, "w", encoding="utf-8") as f:
        f.write(code)

    return (
        f"Naya skill '{filename}' ban gaya hai aur review ke liye rakh diya "
        f"({pending_path}). Isko apply karne ke liye bolo: "
        f"'{filename} wala feature confirm karo'. Confirm karne ke baad "
        "Jarvis ko restart karna hoga taaki naya feature use ho sake."
    )


def self_confirm_feature(params: dict) -> str:
    """Pending skill file ko live skills/ folder mein move karta hai."""
    filename = params.get("filename", "").strip()
    if not filename:
        return "Kaunsi pending file confirm karni hai, naam batao."
    if not filename.endswith(".py"):
        filename += ".py"

    pending_path = os.path.join(PENDING_DIR, filename)
    if not os.path.exists(pending_path):
        return f"'{filename}' pending list mein nahi mili."

    live_path = os.path.join(SKILLS_DIR, filename)
    with open(pending_path, "r", encoding="utf-8") as f:
        code = f.read()
    with open(live_path, "w", encoding="utf-8") as f:
        f.write(code)
    os.remove(pending_path)

    return f"'{filename}' skills folder mein add ho gayi. Ab Jarvis ko restart karo taaki naya feature load ho."


def self_list_pending(params: dict) -> str:
    """Abhi tak kaunse features generate hue hain but apply nahi hue."""
    files = [f for f in os.listdir(PENDING_DIR) if f.endswith(".py")]
    if not files:
        return "Koi pending feature nahi hai."
    return "Pending features: " + ", ".join(files)


ACTIONS = {
    "self_add_feature": self_add_feature,
    "self_confirm_feature": self_confirm_feature,
    "self_list_pending": self_list_pending,
}

DOCS = """
- self_add_feature: {"request": "bluetooth on/off karne ka feature add karo"}
    (Jarvis khud naya code likh kar review ke liye rakhta hai - turant
    live nahi hota, confirmation chahiye)
- self_confirm_feature: {"filename": "bluetooth_on_off_skill.py"}
    (pending feature ko live kar deta hai - iske baad Jarvis restart chahiye)
- self_list_pending: {}
    (abhi kaunse features review ke liye pending hain, dikhata hai)

Example:
User: "bluetooth on off karne ka feature add kar do"
-> {"actions": [{"action": "self_add_feature", "params": {"request": "bluetooth on off karna"}}]}

User: "haan wo bluetooth wala feature confirm kar do"
-> {"actions": [{"action": "self_confirm_feature", "params": {"filename": "bluetooth_on_off_skill.py"}}]}
"""
