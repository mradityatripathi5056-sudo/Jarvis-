"""
skills/screen_click_skill.py
------------------------------------------------------------
PROBLEM jo fix ho raha hai: pehle sirf "WhatsApp khol do" jaisa command
kaam karta tha, lekin "Aditya ki chat pe click karo" nahi - kyunki
mouse_click action ko EXACT (x, y) pixel coordinates chahiye hote hain,
aur brain.py ka LLM text-only hai (screenshot nahi dekh sakta), isliye
usse coordinates kabhi nahi aa sakte the.

Ye skill wo gap bharta hai: koi bhi natural-language description do
("Aditya ki chat", "send button", "search icon", "close (X) button")
- ye screenshot lekar vision model se puchta hai ki wo cheez screen pe
kahan hai, aur wahan click/type kar deta hai. Isse WhatsApp, File
Explorer, koi bhi app, koi bhi website - sab pe "X pe click karo" jaisa
command generically kaam karega.

ADVANCED (naya):
1. MULTI-MONITOR: screen_capture.py ke through - agar 2+ monitors hain
   (Windows), sab mein se sahi wale pe click karega, sirf primary tak
   limited nahi. (macOS/Linux pe abhi bhi sirf primary - PIL ka
   limitation, screen_capture.py mein documented hai.)
2. CLICK-MEMORY: click_memory.py ke through - jo cheez pehle successfully
   mil chuki hai (usi app/window mein), uski jagah yaad rehti hai. Agli
   baar wahi maango to seedha wahan click ho jaata hai, koi naya vision
   API call nahi lagta (fast + free). 24 ghante purana ho jaaye, ya
   screen/monitor setup badal jaaye, to khud-ba-khud stale maan ke phir
   se vision se dhoondta hai.

Requirement: vision_skill.py jaisa hi setup - OPENROUTER_API_KEY +
optionally .env mein VISION_MODEL (vision-capable model, jaise
google/gemini-2.5-flash). Alag se kuch install nahi karna.

ACCURACY NOTE: Ye AI-vision guess hai, 100% perfect nahi hoga - chhote
ya bahut paas-paas wale icons pe kabhi galat jagah click ho sakta hai.
Sensitive buttons (payment confirm, delete, send-money) pe use karte
waqt result screenshot/status khud bhi ek baar check kar lena.
"""

import base64
import json
import os
import re
import time

import requests
import config
import screen_capture
import click_memory


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


def _ask_vision_for_position(description: str, capture: dict):
    """Vision model se ek baar puchta hai description ki position
    (percentage mein). Returns (x_pct, y_pct) | None, raw_reply_or_error."""
    with open(capture["path"], "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    try:
        os.remove(capture["path"])
    except OSError:
        pass

    prompt = (
        f'Ye current computer screen ka screenshot hai (agar multiple monitors '
        f'hain to sab ek saath is mein hain). Isme ye dhundo: "{description}". '
        "Agar mil jaaye, uske EXACT CENTER ki position PERCENTAGE mein do "
        "(0 = bilkul left/top edge, 100 = bilkul right/bottom edge, POORE "
        "screenshot ke width/height ke hisaab se). SIRF compact JSON format "
        'mein jawab do, kuch aur text bilkul mat likho: '
        '{"found": true, "x_percent": <number 0-100>, "y_percent": <number 0-100>} '
        'ya agar clearly screen pe dikh hi nahi raha: {"found": false}'
    )
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
                    "max_tokens": 100,
                }
            ),
            timeout=30,
        )
        data = resp.json()
    except Exception as e:
        return None, f"error: {e}"

    if "choices" not in data:
        err = data.get("error", {})
        err_msg = err.get("message", str(data)) if isinstance(err, dict) else str(err)
        return None, f"error: {err_msg}"

    reply = data["choices"][0]["message"]["content"].strip()
    parsed = _extract_json(reply)
    if not parsed or not parsed.get("found"):
        return None, reply
    x_pct, y_pct = parsed.get("x_percent"), parsed.get("y_percent")
    if x_pct is None or y_pct is None:
        return None, reply
    return (float(x_pct), float(y_pct)), reply


def _locate_on_screen(description: str):
    """Screenshot lekar (multi-monitor aware) description ki position
    dhoondta hai - pehle click-memory cache check karta hai (fast, free),
    tabhi vision API call karta hai jab cache mein na mile ya stale ho.
    Returns ((x, y) absolute screen pixel | None, raw_reply_or_source)."""
    capture = screen_capture.capture_for_vision()
    window_title = screen_capture.active_window_title()

    cached = click_memory.get(
        description, window_title, capture["width"], capture["height"],
        capture["offset_x"], capture["offset_y"],
    )
    if cached:
        try:
            os.remove(capture["path"])
        except OSError:
            pass
        x_pct, y_pct = cached
        return screen_capture.percent_to_absolute(x_pct, y_pct, capture), "(yaad rakhi hui jagah se, vision call nahi lagi)"

    result, reply = _ask_vision_for_position(description, capture)
    if not result:
        return None, reply

    x_pct, y_pct = result
    click_memory.save(
        description, window_title, x_pct, y_pct,
        capture["width"], capture["height"], capture["offset_x"], capture["offset_y"],
    )
    return screen_capture.percent_to_absolute(x_pct, y_pct, capture), reply


def click_on_screen(params: dict) -> str:
    description = str(params.get("description", "")).strip()
    if not description:
        return "Kis cheez pe click karna hai, batao (jaise 'Aditya ki chat')."
    import pyautogui

    coords, reply = _locate_on_screen(description)
    if not coords:
        return f"'{description}' screen pe nahi mila (shayad scroll/wait karna pade). Vision ne kaha: {reply[:150]}"
    x, y = coords
    pyautogui.click(x, y)
    return f"'{description}' pe click kar diya."


def double_click_on_screen(params: dict) -> str:
    description = str(params.get("description", "")).strip()
    if not description:
        return "Kis cheez pe double click karna hai, batao."
    import pyautogui

    coords, reply = _locate_on_screen(description)
    if not coords:
        return f"'{description}' screen pe nahi mila. Vision ne kaha: {reply[:150]}"
    x, y = coords
    pyautogui.doubleClick(x, y)
    return f"'{description}' pe double click kar diya."


def right_click_on_screen(params: dict) -> str:
    description = str(params.get("description", "")).strip()
    if not description:
        return "Kis cheez pe right click karna hai, batao."
    import pyautogui

    coords, reply = _locate_on_screen(description)
    if not coords:
        return f"'{description}' screen pe nahi mila. Vision ne kaha: {reply[:150]}"
    x, y = coords
    pyautogui.rightClick(x, y)
    return f"'{description}' pe right click kar diya."


def type_in_field(params: dict) -> str:
    """Kisi field/box ko description se dhoond ke click karta hai, phir
    text type karta hai - jaise 'message box mein "hi" likh do'."""
    description = str(params.get("description", "")).strip()
    text = str(params.get("text", ""))
    press_enter = bool(params.get("press_enter", False))
    if not description:
        return "Kaunsa field/box hai jisme likhna hai, batao."
    import pyautogui

    coords, reply = _locate_on_screen(description)
    if not coords:
        return f"'{description}' field screen pe nahi mila. Vision ne kaha: {reply[:150]}"
    x, y = coords
    pyautogui.click(x, y)
    time.sleep(0.3)
    if text:
        pyautogui.typewrite(text, interval=0.02)
    if press_enter:
        pyautogui.press("enter")
    result = f"'{description}' mein click kar diya"
    if text:
        result += f" aur '{text}' likh diya"
    if press_enter:
        result += ", enter bhi daba diya"
    return result + "."


def forget_screen_memory(params: dict) -> str:
    """Agar click-memory ne kabhi galat jagah yaad rakh li ho, isse reset
    kar sakte ho - 'X ki yaad rakhi hui jagah bhula do' ya 'saara
    screen-memory clear kar do'."""
    description = str(params.get("description", "")).strip()
    return click_memory.forget(description, screen_capture.active_window_title())


ACTIONS = {
    "click_on_screen": click_on_screen,
    "double_click_on_screen": double_click_on_screen,
    "right_click_on_screen": right_click_on_screen,
    "type_in_field": type_in_field,
    "forget_screen_memory": forget_screen_memory,
}

DOCS = """
- click_on_screen: {"description": "Aditya ki chat"}
    (Screen pe koi bhi cheez - contact, button, icon, link, tab - naam/
    description se dhoond ke click karta hai. WhatsApp/koi bhi app/website
    pe generic kaam karta hai - "X pe click karo" jab bhi bole, ye use karo,
    exact coordinates kabhi khud mat banao. Multi-monitor setup pe bhi
    sahi monitor pe kaam karta hai. Jo cheez ek baar mil chuki hai wo yaad
    rehti hai - agli baar fast hoga, koi extra API call nahi lagega.)
- double_click_on_screen: {"description": "file/folder ya icon ka naam"}
- right_click_on_screen: {"description": "cheez ka naam"}
- type_in_field: {"description": "message box / search box", "text": "kya likhna hai", "press_enter": false}
    (Kisi field ko dhoond ke click karke usme text type karta hai. "message
    likh ke bhej do" jaisa ho to press_enter: true karo, ya agar text field
    ke baad ek alag 'send button' click karna ho to do actions do: pehle
    type_in_field phir click_on_screen description='send button'.)
- forget_screen_memory: {"description": "send button"}  YA {"description": ""}
    (Agar click-memory kabhi galat jagah yaad rakh le, "X ki yaad rakhi
    jagah bhula do" ya "screen memory clear kar do" (khaali description =
    sab clear) bolne pe use karo.)

Examples:
User: "WhatsApp khol ke Aditya ki chat pe click karo"
-> {"actions": [{"action": "open_app", "params": {"app_name": "whatsapp"}}, {"action": "click_on_screen", "params": {"description": "Aditya ki chat"}}]}

User: "message box mein 'kaha ho' likh ke bhej do"
-> {"actions": [{"action": "type_in_field", "params": {"description": "message input box", "text": "kaha ho", "press_enter": true}}]}

User: "close button pe click karo"
-> {"actions": [{"action": "click_on_screen", "params": {"description": "close (X) button"}}]}

User: "Telegram khol ke Rahul ki chat khol ke 'kal milte hain' bhej do"
-> {"actions": [{"action": "open_app", "params": {"app_name": "telegram"}}, {"action": "click_on_screen", "params": {"description": "Rahul ki chat"}}, {"action": "type_in_field", "params": {"description": "message input box", "text": "kal milte hain", "press_enter": true}}]}

User: "send button ki yaad rakhi jagah bhool ja, galat click kar raha hai"
-> {"actions": [{"action": "forget_screen_memory", "params": {"description": "send button"}}]}
"""
