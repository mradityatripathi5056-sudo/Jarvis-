"""
json_utils.py
------------------------------------------------------------
Error Self-Healing (data layer): sab .json memory/log files
(jarvis_history.json, jarvis_memory.json, jarvis_context.json,
jarvis_usage.json) is ek hi safe_json_load() se guzarte hain.

Agar koi file corrupt/galat JSON ho jaaye (jaise crash ke beech
mein write hua ho), to:
1. Crash hone ki jagah - corrupt file ko ".corrupt_backup" naam se
   safe rakh diya jaata hai (data poora zaya nahi hota, dekh sakte ho)
2. Ek fresh/empty default return hota hai taaki Jarvis chalta rahe
3. jarvis.log mein warning likh di jaati hai

Existing brain.py/memory_context_skill.py ke apne try/except already
the (crash nahi hote the), lekin corrupt file backup nahi hota tha aur
kahin log bhi nahi hota tha - ye upgrade wahi gap bharta hai.
"""

import json
import logging
import os
import shutil


def safe_json_load(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, UnicodeDecodeError) as e:
        try:
            backup_path = path + ".corrupt_backup"
            shutil.copy(path, backup_path)
            logging.warning(f"[self-heal] '{path}' corrupt thi ({e}) - backup: '{backup_path}', fresh default use kar rahe hain.")
        except Exception:
            pass
        return default


def safe_json_save(path: str, data) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        logging.error(f"[self-heal] '{path}' save nahi ho payi: {e}")
        return False
