"""
skills/screen_watch_skill.py
------------------------------------------------------------
CONTINUOUS SCREEN-WATCHING MODE.

Ek background thread jo har `interval` seconds mein screenshot leta
hai aur vision model se pucchta hai "kya di gayi condition ab TRUE ho
gayi hai screen pe?". Jab tak nahi, chup chaap check karta rehta hai -
koi command dobara nahi bolni padti. Jab condition true ho jaye, to:
  1. bol ke/notify karke batata hai, aur
  2. agar `follow_up` diya gaya ho, wahi natural-language command khud
     chala deta hai (bilkul normal Jarvis command jaisa - brain.ask_llm
     + actions.ACTION_MAP use karke).

Example real use: "screen dekhte raho, jab download 100% ho jaye tab
mujhe bata dena" ya "jab loading khatam ho jaye to YouTube khol dena".

SAFETY / DESIGN LIMITS (jaan-bujh kar):
- Ek time pe sirf EK watch active ho sakta hai (naya start karne pe
  purana automatically band ho jaata hai) - taaki multiple background
  loops screenshots/API calls na spam karein.
- Watch ek `max_minutes` ke baad khud-ba-khud band ho jaata hai (default
  30 min) - hamesha ke liye chalte rehne wala open-ended background
  process nahi hai.
- `follow_up` se koi bhi DESTRUCTIVE action (config.DESTRUCTIVE_ACTIONS -
  delete_file, shutdown, restart, kill_process, etc.) trigger NAHI hota.
  Background thread confirmation nahi maang sakta, isliye aisi actions
  safety ke liye silently skip ho jaati hain - user ko wo manually
  bolni padegi.
- Ye "poori screen khud-ba-khud operate karne wala open-ended agent"
  NAHI hai - sirf ek specific, user-diya hua condition watch karta hai
  aur us par ek baar react karke ruk jaata hai.

Requirement: vision_skill.py jaisa hi setup - OPENROUTER_API_KEY +
optionally .env mein VISION_MODEL (vision-capable model, jaise
google/gemini-2.5-flash).
"""

import base64
import json
import os
import threading
import time

import requests
import config
import actions

_watch_thread = None
_stop_event = threading.Event()
_watch_lock = threading.Lock()
_status = {"running": False, "condition": None, "started_at": None, "checks": 0}


def _vision_model() -> str:
    value = os.getenv("VISION_MODEL", "").strip()
    return value or config.OPENROUTER_MODEL


def _check_condition_on_screen(condition: str):
    """Screenshot lekar vision model se pucchta hai condition true hui ya
    nahi. Returns (is_true: bool, raw_reply: str)."""
    import pyautogui

    screenshot_path = os.path.join(config.MEDIA_DIR, "_watch_temp_screenshot.png")
    pyautogui.screenshot(screenshot_path)
    with open(screenshot_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    try:
        os.remove(screenshot_path)
    except OSError:
        pass

    prompt = (
        f'Ye current screen ka screenshot hai. Condition: "{condition}". '
        "Kya ye condition ABHI is screenshot mein TRUE ho chuki hai? "
        "Jawab SIRF ek word se shuru karo: YES ya NO, uske baad ek chhoti si "
        "wajah (max 1 line)."
    )
    resp = requests.post(
        config.OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": _vision_model(),
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 60,
            }
        ),
        timeout=30,
    )
    data = resp.json()
    if "choices" not in data:
        err = data.get("error", {})
        err_msg = err.get("message", str(data)) if isinstance(err, dict) else str(err)
        return False, f"error: {err_msg}"
    reply = data["choices"][0]["message"]["content"].strip()
    return reply.lower().startswith("yes"), reply


def _run_follow_up(follow_up: str) -> str:
    """Follow-up natural-language command ko normal Jarvis command jaisa
    execute karta hai. Destructive actions yahan se kabhi nahi chalte
    (background thread confirmation nahi le sakta)."""
    import brain

    try:
        action_list = brain.ask_llm(follow_up)
    except Exception as e:
        return f"Follow-up samajh nahi paya: {e}"

    results = []
    for decision in action_list:
        action_name = decision.get("action")
        params = decision.get("params", {})
        if action_name == "general_chat":
            results.append(params.get("reply", ""))
            continue
        if action_name in config.DESTRUCTIVE_ACTIONS:
            results.append(
                f"'{action_name}' destructive hai, watch-mode se bina confirmation "
                "ke nahi chalega - ye manually bolni padegi."
            )
            continue
        func = actions.ACTION_MAP.get(action_name)
        if func:
            results.append(actions.run_action_with_retry(func, params, action_name))
        else:
            results.append(f"'{action_name}' samajh nahi aaya.")

    brain.save_action_results(results)
    return " ".join(r for r in results if r)


def _watch_loop(condition: str, follow_up: str, interval: int, max_checks: int):
    try:
        from speech import speak
    except Exception:
        def speak(_text):
            return None

    checked = 0
    while not _stop_event.is_set() and checked < max_checks:
        checked += 1
        _status["checks"] = checked
        try:
            is_true, _reply = _check_condition_on_screen(condition)
        except Exception:
            is_true = False

        if is_true:
            message = f"Watch condition poori ho gayi: {condition}."
            if follow_up:
                message += " " + _run_follow_up(follow_up)
            speak(message)
            break

        _stop_event.wait(interval)
    else:
        if checked >= max_checks and not _stop_event.is_set():
            speak(f"Watch timeout ho gaya, '{condition}' condition milte hue nahi dikhi.")

    _status["running"] = False


def start_screen_watch(params: dict) -> str:
    global _watch_thread, _stop_event, _status

    condition = str(params.get("condition", "")).strip()
    follow_up = str(params.get("follow_up", "")).strip()
    try:
        interval = max(3, int(params.get("interval", 8) or 8))
    except (TypeError, ValueError):
        interval = 8
    try:
        max_minutes = max(1, int(params.get("max_minutes", 30) or 30))
    except (TypeError, ValueError):
        max_minutes = 30
    max_checks = max(1, (max_minutes * 60) // interval)

    if not condition:
        return "Kis cheez ka watch karna hai (condition) batao - jaise 'download complete ho jaye'."

    with _watch_lock:
        if _status["running"]:
            _stop_event.set()
            if _watch_thread:
                _watch_thread.join(timeout=2)

        _stop_event = threading.Event()
        _status = {"running": True, "condition": condition, "started_at": time.time(), "checks": 0}
        _watch_thread = threading.Thread(
            target=_watch_loop, args=(condition, follow_up, interval, max_checks), daemon=True
        )
        _watch_thread.start()

    msg = (
        f"Theek hai, screen watch shuru kar diya - condition: '{condition}' "
        f"(har {interval} sec check hoga, max {max_minutes} min tak)."
    )
    if follow_up:
        msg += f" Jab true hui, ye bhi karunga: '{follow_up}'."
    return msg


def stop_screen_watch(params: dict) -> str:
    if not _status["running"]:
        return "Koi watch chal hi nahi raha."
    _stop_event.set()
    _status["running"] = False
    return "Screen watch band kar diya."


def screen_watch_status(params: dict) -> str:
    if not _status["running"]:
        return "Koi watch active nahi hai."
    elapsed = int(time.time() - _status["started_at"])
    return f"Watch chal raha hai: '{_status['condition']}' ({_status['checks']} checks, {elapsed}s se)."


ACTIONS = {
    "start_screen_watch": start_screen_watch,
    "stop_screen_watch": stop_screen_watch,
    "screen_watch_status": screen_watch_status,
}

DOCS = """
- start_screen_watch: {"condition": "download complete ho gaya", "follow_up": "", "interval": 8, "max_minutes": 30}
    (Background mein screen ko baar-baar (har `interval` sec) dekh ke check
    karta hai ki `condition` true ho gayi ya nahi - user ko dobara bolna
    nahi padta. `follow_up` OPTIONAL hai: condition true hote hi wahi agla
    natural-language command khud chala dega (jaise "YouTube khol ke gaana
    lagao"). Agar user sirf "bata dena/bol dena" bole (koi action nahi),
    follow_up khaali chhodo - sirf notify karega. `max_minutes` ke baad
    watch khud-ba-khud ruk jayega agar condition kabhi true na hui. Sirf
    ek time pe ek hi watch chal sakta hai - naya start karne pe purana
    khud replace ho jaata hai. Destructive actions (delete/shutdown/etc.)
    follow_up se kabhi execute nahi hote, safety ke liye skip ho jaate
    hain. User jab bole "screen dekhte raho/watch karo, jab X ho jaye tab
    Y karo/bata dena" - ye action use karo.
- stop_screen_watch: {}  ("watch band karo", "screen dekhna band karo")
- screen_watch_status: {}  ("watch ka status batao", "abhi kya dekh rahe ho")

Examples:
User: "screen pe dekhte raho, jab loading khatam ho jaye tab mujhe bol dena"
-> {"actions": [{"action": "start_screen_watch", "params": {"condition": "loading/progress bar khatam ho gayi hai", "follow_up": ""}}]}

User: "jab video buffer/loading khatam ho jaye to YouTube ka volume 100 kar dena"
-> {"actions": [{"action": "start_screen_watch", "params": {"condition": "video ka loading/buffering khatam ho gayi hai", "follow_up": "volume 100 kar do"}}]}

User: "watch band kar do"
-> {"actions": [{"action": "stop_screen_watch", "params": {}}]}
"""
