"""
skills/autopilot_skill.py
------------------------------------------------------------
AUTOPILOT MODE - ek hi GOAL bolo (jaise "YouTube khol ke cat video
dhundo, comment section kholo, like karo aur subscribe kar do"), aur
Jarvis khud-ba-khud ek-ek karke saare steps chalata hai, bina har step
ke liye dobara pucche. Ye screen_click_skill.py (click_on_screen,
type_in_field) aur baaki normal actions (open_app, yt_*, etc.) ka hi
use karta hai - bas beech mein khud decide karta hai "ab agla step kya
hai" (screenshot dekh ke, vision model se) jab tak goal poora na ho
jaaye ya atak na jaaye.

Ye screen_watch_skill.py se ALAG hai: screen_watch ek SPECIFIC condition
ka wait karta hai (jaise "jab download 100% ho jaye"). Autopilot iske
ulta hai - khud active steps leta hai goal ki taraf badhne ke liye, har
step ke baad phir se screenshot lekar agla decide karta hai.

SAFETY / DESIGN LIMITS (jaan-bujh kar, screen_watch jaisa hi philosophy):
- Ek time pe sirf EK autopilot run active ho sakta hai.
- `max_steps` (default 20, hard cap 40) ke baad khud ruk jaata hai -
  "hamesha ke liye bina rok-tok" wala open-ended loop NAHI hai, taaki
  kisi galat/atki hui state mein API calls infinite na chalte rahein.
- Sirf ek SAFE action whitelist mein se hi action choose kar sakta hai -
  destructive (delete/shutdown/kill_process/etc.), email/call/message-
  send-jaisi high-stakes cheezein, aur system-level actions (install/
  uninstall/registry/etc.) is whitelist mein NAHI hain - autopilot khud
  se inhe kabhi nahi chalayega, chahe vision model kuch bhi decide kare.
- Start karne se pehle EK confirmation maangta hai (jaise self_upgrade) -
  kyunki ye ek autonomous loop hai jo khud clicks/typing karega.
- Har 2 consecutive "samajh nahi aaya / invalid action" pe ginti hoti
  hai - 3 baar lagatar aisa ho to khud ruk jaata hai (taaki atki hui
  state mein bekar API calls na hote rahein).

Requirement: vision_skill.py jaisa hi - OPENROUTER_API_KEY + optionally
.env mein VISION_MODEL.
"""

import base64
import json
import os
import re
import threading
import time

import requests
import config
import actions

_autopilot_thread = None
_stop_event = threading.Event()
_lock = threading.Lock()
_status = {"running": False, "goal": None, "started_at": None, "steps": 0, "last_result": ""}

# Sirf ye actions autopilot khud-ba-khud choose kar sakta hai. Destructive/
# high-stakes/system-level cheezein jaan-bujh kar yahan NAHI hain.
SAFE_ACTIONS = {
    "click_on_screen", "double_click_on_screen", "right_click_on_screen",
    "type_in_field", "open_app", "open_folder", "open_website",
    "press_key", "mouse_scroll", "mouse_click",
    "yt_search", "yt_play", "yt_like", "yt_subscribe", "yt_next",
    "yt_pause_resume", "yt_mute_toggle", "yt_fullscreen_toggle",
}

try:
    if "start_autopilot" not in config.DESTRUCTIVE_ACTIONS:
        config.DESTRUCTIVE_ACTIONS.append("start_autopilot")
except Exception:
    pass


def _vision_model() -> str:
    value = os.getenv("VISION_MODEL", "").strip()
    return value or config.OPENROUTER_MODEL


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _decide_next_step(goal: str, history: list) -> dict | None:
    import pyautogui

    screenshot_path = os.path.join(config.MEDIA_DIR, "_autopilot_temp_screenshot.png")
    pyautogui.screenshot(screenshot_path)
    with open(screenshot_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    try:
        os.remove(screenshot_path)
    except OSError:
        pass

    history_text = "\n".join(history) if history else "(abhi tak koi step nahi liya)"
    prompt = f"""Tum ek computer-use assistant ho jo current screenshot dekh ke ek
GOAL poora karne ke liye AGLA EK SINGLE action decide karte ho.

GOAL: "{goal}"

Ab tak ke steps aur unke result:
{history_text}

Current screenshot dekho aur decide karo:
- Agar GOAL already poora ho chuka hai (screenshot se confirm hota hai): status "done".
- Agar aage badhna possible nahi lag raha (error, cheez mil hi nahi rahi, atka
  hua hai): status "stuck".
- Warna: status "continue", aur neeche di gayi list mein se EK action choose karo.

Sirf inhi actions mein se choose karo (exact naam aur param format use karo):
- click_on_screen: {{"description": "screen pe jo dikh raha hai uska naam"}}
- double_click_on_screen: {{"description": "..."}}
- right_click_on_screen: {{"description": "..."}}
- type_in_field: {{"description": "...", "text": "...", "press_enter": true/false}}
- open_app: {{"app_name": "..."}}
- open_website: {{"url": "..."}}
- press_key: {{"key": "enter/tab/escape/etc"}}
- mouse_scroll: {{"direction": "up/down", "amount": 10}}
- open_folder: {{"path": ""}}
- yt_search / yt_play: {{"query": "..."}}
- yt_like / yt_subscribe / yt_next / yt_pause_resume / yt_mute_toggle / yt_fullscreen_toggle: {{}}

SIRF compact JSON do, koi aur text/markdown nahi:
{{"status": "continue", "action": "<action_name>", "params": {{...}}, "reason": "<max 1 line>"}}
YA {{"status": "done", "reason": "..."}}
YA {{"status": "stuck", "reason": "..."}}"""

    try:
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
                    "max_tokens": 200,
                }
            ),
            timeout=30,
        )
        data = resp.json()
    except Exception as e:
        return {"status": "stuck", "reason": f"API error: {e}"}

    if "choices" not in data:
        err = data.get("error", {})
        err_msg = err.get("message", str(data)) if isinstance(err, dict) else str(err)
        return {"status": "stuck", "reason": f"API error: {err_msg}"}

    reply = data["choices"][0]["message"]["content"].strip()
    parsed = _extract_json(reply)
    if not parsed or "status" not in parsed:
        return {"status": "stuck", "reason": f"Samajh nahi paya vision reply: {reply[:150]}"}
    return parsed


def _autopilot_loop(goal: str, interval: int, max_steps: int):
    try:
        from speech import speak
    except Exception:
        def speak(_text):
            return None

    history = []
    invalid_streak = 0
    step = 0

    while not _stop_event.is_set() and step < max_steps:
        step += 1
        _status["steps"] = step

        decision = _decide_next_step(goal, history[-5:])
        status = decision.get("status")

        if status == "done":
            speak(f"Goal poora ho gaya: {decision.get('reason', '')}")
            _status["last_result"] = "done"
            break

        if status == "stuck":
            speak(f"Autopilot atak gaya, ruk raha hoon: {decision.get('reason', '')}")
            _status["last_result"] = "stuck"
            break

        action_name = decision.get("action")
        params = decision.get("params", {}) or {}

        if action_name not in SAFE_ACTIONS:
            invalid_streak += 1
            history.append(f"Step {step}: '{action_name}' allowed nahi hai, skip kiya.")
            if invalid_streak >= 3:
                speak("Autopilot baar-baar galat/disallowed action choose kar raha hai, ruk raha hoon.")
                _status["last_result"] = "stuck (invalid actions)"
                break
            _stop_event.wait(interval)
            continue

        func = actions.ACTION_MAP.get(action_name)
        if not func:
            invalid_streak += 1
            history.append(f"Step {step}: '{action_name}' mila hi nahi, skip kiya.")
            if invalid_streak >= 3:
                speak("Autopilot repeatedly ek action dhoond nahi pa raha, ruk raha hoon.")
                _status["last_result"] = "stuck (unknown action)"
                break
            _stop_event.wait(interval)
            continue

        invalid_streak = 0
        result = actions.run_action_with_retry(func, params, action_name)
        history.append(f"Step {step}: {action_name}({params}) -> {result}")
        _status["last_result"] = result

        _stop_event.wait(interval)
    else:
        if step >= max_steps and not _stop_event.is_set():
            speak(f"Autopilot {max_steps} steps ki limit tak pahunch gaya, ruk raha hoon.")
            _status["last_result"] = f"stopped (max_steps={max_steps} reached)"

    _status["running"] = False


def start_autopilot(params: dict) -> str:
    global _autopilot_thread, _stop_event, _status

    goal = str(params.get("goal", "")).strip()
    try:
        interval = max(2, int(params.get("interval", 4) or 4))
    except (TypeError, ValueError):
        interval = 4
    try:
        max_steps = min(40, max(1, int(params.get("max_steps", 20) or 20)))
    except (TypeError, ValueError):
        max_steps = 20

    if not goal:
        return "Goal kya hai batao - jaise 'YouTube pe cat video dhundo, comment kholo, like karo aur subscribe kar do'."

    with _lock:
        if _status["running"]:
            _stop_event.set()
            if _autopilot_thread:
                _autopilot_thread.join(timeout=2)

        _stop_event = threading.Event()
        _status = {"running": True, "goal": goal, "started_at": time.time(), "steps": 0, "last_result": ""}
        _autopilot_thread = threading.Thread(
            target=_autopilot_loop, args=(goal, interval, max_steps), daemon=True
        )
        _autopilot_thread.start()

    return (
        f"Autopilot shuru kar diya - goal: '{goal}' (max {max_steps} steps, har {interval} sec ek step). "
        "Beech mein kabhi bhi 'autopilot band karo' bol sakte ho."
    )


def stop_autopilot(params: dict) -> str:
    if not _status["running"]:
        return "Koi autopilot chal hi nahi raha."
    _stop_event.set()
    _status["running"] = False
    return "Autopilot band kar diya."


def autopilot_status(params: dict) -> str:
    if not _status["running"]:
        last = f" (aakhri result: {_status['last_result']})" if _status.get("last_result") else ""
        return f"Koi autopilot active nahi hai.{last}"
    elapsed = int(time.time() - _status["started_at"])
    return (
        f"Autopilot chal raha hai - goal: '{_status['goal']}' "
        f"({_status['steps']} step ho chuke, {elapsed}s se). "
        f"Aakhri step ka result: {_status['last_result']}"
    )


ACTIONS = {
    "start_autopilot": start_autopilot,
    "stop_autopilot": stop_autopilot,
    "autopilot_status": autopilot_status,
}

DOCS = """
- start_autopilot: {"goal": "YouTube pe cat video dhundo, comment section kholo, like karo aur subscribe kar do", "max_steps": 20, "interval": 4}
    (User jab ek hi baar mein ek BADA/MULTI-STEP goal bole aur chahe ki
    Jarvis khud-ba-khud saare steps chain kare bina har step ke liye
    dobara pucche - "khud karta rahe", "lagatar kaam karta rahe", "sab
    khud kar le" jaisa bole - to ye action use karo. Ye khud screenshot
    lekar decide karta hai agla step kya hai (click_on_screen, type_in_field,
    open_app, yt_* etc. use karke), jab tak goal poora na ho jaaye, ya
    atak na jaaye, ya max_steps khatam na ho jaayein. Destructive hai
    (confirmation lagegi) kyunki ye khud-ba-khud clicks/typing karega.
    Har step 'continue' hone pe hi agla step leta hai; goal complete hote
    hi ya atakne pe khud ruk jaata hai aur bata deta hai.)
- stop_autopilot: {}  ("autopilot band karo", "rok do khud-ba-khud karna")
- autopilot_status: {}  ("autopilot kya kar raha hai abhi", "kitne steps ho chuke")

Example:
User: "YouTube khol ke lofi gaana dhundo, comment section kholo, like kar do aur subscribe kar do - khud hi kar lena sab"
-> {"actions": [{"action": "start_autopilot", "params": {"goal": "YouTube khol ke lofi gaana search karo, ek video kholo, comment section kholo, video ko like karo aur channel subscribe karo"}}]}

User: "Telegram khol ke Aditya ki chat khol ke 'hi' bhej do - baaki khud kar lena"
-> {"actions": [{"action": "start_autopilot", "params": {"goal": "Telegram khol ke Aditya ki chat kholo aur usme 'hi' likh ke bhej do"}}]}

User: "autopilot rok do"
-> {"actions": [{"action": "stop_autopilot", "params": {}}]}
"""
