"""
click_memory.py
------------------------------------------------------------
Click-memory cache: ek baar jab click_on_screen kisi cheez ko successfully
dhoond leta hai, uski position (percentage + jis window mein thi) yahan
yaad rakh li jaati hai. Agli baar wahi cheez (usi app mein) dobara maangne
par - agar screen resolution/monitor layout badla nahi hai aur cache bahut
purana nahi hai - seedha yaad rakhi hui jagah click ho jaata hai, koi
naya vision API call nahi lagta (fast + free).

Cache automatically STALE ho jaata hai (aur naye sirey se vision se
dhoonda jaata hai) agar:
- 24 ghante se zyada purana ho gaya ho (UI kabhi kabhi update/redesign
  hoti rehti hai)
- Screen resolution ya monitor offset badal gaya ho (jaise laptop dock se
  hataya/lagaya)

File: jarvis_click_memory.json (jarvis_media/gitignore jaisi hi list mein
add kiya gaya hai - personal/generated data hai, code nahi).
"""

import threading
import time

from json_utils import safe_json_load, safe_json_save

MEMORY_FILE = "jarvis_click_memory.json"
_lock = threading.Lock()
MAX_AGE_SECONDS = 24 * 60 * 60  # 24 ghante
MAX_ENTRIES = 300  # bahut zyada ho jayein to sabse purani hata di jaati hain


def _key(description: str, window_title: str) -> str:
    return f"{description.strip().lower()}::{window_title.strip().lower()}"


def _load() -> dict:
    data = safe_json_load(MEMORY_FILE, {"entries": {}})
    return data.get("entries", {})


def _save(entries: dict):
    with _lock:
        safe_json_save(MEMORY_FILE, {"entries": entries})


def get(description: str, window_title: str, width: int, height: int, offset_x: int, offset_y: int):
    """Cache mein mila to (x_pct, y_pct) return karta hai, warna None -
    dono cases mein staleness (age/resolution) khud check kar leta hai."""
    entries = _load()
    entry = entries.get(_key(description, window_title))
    if not entry:
        return None

    if time.time() - entry.get("saved_at", 0) > MAX_AGE_SECONDS:
        return None
    if entry.get("width") != width or entry.get("height") != height:
        return None
    if entry.get("offset_x") != offset_x or entry.get("offset_y") != offset_y:
        return None

    return entry.get("x_pct"), entry.get("y_pct")


def save(description: str, window_title: str, x_pct: float, y_pct: float, width: int, height: int, offset_x: int, offset_y: int):
    entries = _load()
    entries[_key(description, window_title)] = {
        "x_pct": x_pct,
        "y_pct": y_pct,
        "width": width,
        "height": height,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "saved_at": time.time(),
    }
    if len(entries) > MAX_ENTRIES:
        # sabse purani entries hata do (simple LRU-jaisa cleanup)
        oldest_first = sorted(entries.items(), key=lambda kv: kv[1].get("saved_at", 0))
        for k, _ in oldest_first[: len(entries) - MAX_ENTRIES]:
            entries.pop(k, None)
    _save(entries)


def forget(description: str = "", window_title: str = "") -> str:
    """Ek specific cached entry (ya sab, agar description khaali ho)
    delete karta hai - 'ye galat jagah click kar raha hai, bhool ja'
    jaisa troubleshooting ke liye."""
    if not description:
        _save({})
        return "Saara click-memory cache clear kar diya."
    entries = _load()
    key = _key(description, window_title)
    if key in entries:
        entries.pop(key)
        _save(entries)
        return f"'{description}' ka yaad rakha hua location bhula diya."
    return f"'{description}' ke liye koi cached location mila hi nahi."
