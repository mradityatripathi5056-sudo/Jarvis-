"""
skill_loader.py
============================================================
JARVIS SKILLS SYSTEM
============================================================
Ab naya action/skill add karne ke liye actions.py ya brain.py
chhedne ki zaroorat NAHI hai. Bas `skills/` folder ke andar ek
naya .py file banao aur do cheezein define karo:

    ACTIONS = {"action_name": function}
        -> function ek dict "params" leta hai, aur ek STRING
           return karta hai (jo Jarvis bolega/dikhayega).

    DOCS = "..."
        -> Ye text LLM ke system prompt mein automatically inject
           hota hai, taaki LLM ko pata chale ye naya action kaise
           use karna hai (TOOLS_DEFINITION jaisa hi format - action
           name, params, aur ek example).

Jarvis restart karte hi naya skill AUTOMATICALLY load ho jayega -
actions.py ya brain.py mein kuch bhi manually jodne ki zaroorat
nahi. Poora example `skills/example_skill.py` mein dekho.

Rules:
- File ka naam "_" se shuru NAHI hona chahiye (aisi files skip ho
  jaati hain - helper files ke liye use kar sakte ho).
- Ek skill file mein ek se zyada action bhi ho sakte hain.
- Agar kisi skill file mein error hai (import fail, syntax error),
  to sirf wahi skill skip hoti hai - baaki Jarvis normal chalta
  rehta hai (jarvis.log mein error dikhega).
"""

import importlib.util
import logging
import os
import sys

# NOTE: PyInstaller EXE (frozen) ke andar __file__ se path nikalna kaam
# nahi karta (wo bundle ke internal path ki taraf point karta hai, disk
# wale asli exe folder ki taraf nahi) - isliye jab .exe ke roop mein
# chal rahe ho to sys.executable ke folder se skills/ dhoondo, jaisa
# config.py .env ke liye karta hai.
if getattr(sys, "frozen", False):
    _base_dir = os.path.dirname(sys.executable)
else:
    _base_dir = os.path.dirname(os.path.abspath(__file__))

SKILLS_DIR = os.path.join(_base_dir, "skills")


def _load_skill_modules():
    """skills/ folder ke andar sab .py files ko Python modules ki
    tarah load karta hai."""
    modules = []
    if not os.path.isdir(SKILLS_DIR):
        logging.warning(f"[skills] SKILLS_DIR nahi mila: {SKILLS_DIR}")
        return modules

    for filename in sorted(os.listdir(SKILLS_DIR)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue
        path = os.path.join(SKILLS_DIR, filename)
        module_name = f"jarvis_skill_{filename[:-3]}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules.append((filename, module))
        except Exception as e:
            logging.error(f"[skills] '{filename}' load nahi ho saki: {e}")
    return modules


def load_all_actions() -> dict:
    """Sab skills ke ACTIONS dict ko ek combined dict mein merge karta hai."""
    combined = {}
    for filename, module in _load_skill_modules():
        actions_dict = getattr(module, "ACTIONS", None)
        if isinstance(actions_dict, dict):
            combined.update(actions_dict)
        elif actions_dict is not None:
            logging.warning(f"[skills] '{filename}' ka ACTIONS dict format galat hai.")
    return combined


def load_all_docs() -> str:
    """Sab skills ke DOCS text ko ek block mein jodta hai (system
    prompt mein append hoga)."""
    docs = []
    for filename, module in _load_skill_modules():
        doc_text = getattr(module, "DOCS", "")
        if doc_text and doc_text.strip():
            docs.append(doc_text.strip())
    if not docs:
        return ""
    return "\n\nCUSTOM SKILLS (upar wali built-in list ke alawa extra actions):\n" + "\n\n".join(docs)
