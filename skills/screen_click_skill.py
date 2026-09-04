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
kahan hai (percentage position mein, taaki kisi bhi resolution/DPI pe
sahi kaam kare), aur wahan click/type kar deta hai. Isse WhatsApp,
File Explorer, koi bhi app, koi bhi website - sab pe "X pe click karo"
jaisa command generically kaam karega, sirf WhatsApp tak limited nahi.

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


def _locate_on_screen(description: str):
    """Screenshot lekar vision model se description ki position (percentage
    mein) poochta hai, aur usse actual screen pixel (x, y) mein convert
    karta hai. Returns ((x, y) | None, raw_reply_or_error)."""
    import pyautogui

    screen_w, screen_h = pyautogui.size()
    screenshot_path = os.path.join(config.MEDIA_DIR, "_click_temp_screenshot.png")
    pyautogui.screenshot(screenshot_path)
    with open(screenshot_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    try:
        os.remove(screenshot_path)
    except OSError:
        pass

    prompt = (
        f'Ye current computer screen ka screenshot hai. Isme ye dhundo: "{description}". '
        "Agar mil jaaye, uske EXACT CENTER ki position PERCENTAGE mein do "
        "(0 = bilkul left/top edge, 100 = bilkul right/bottom edge, screenshot "
        "ke pura width/height ke hisaab se). SIRF compact JSON format mein "
        'jawab do, kuch aur text bilkul mat likho: '
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

    x = int((float(x_pct) / 100) * screen_w)
    y = int((float(y_pct) / 100) * screen_h)
    return (x, y), reply


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


ACTIONS = {
    "click_on_screen": click_on_screen,
    "double_click_on_screen": double_click_on_screen,
    "right_click_on_screen": right_click_on_screen,
    "type_in_field": type_in_field,
}

DOCS = """
- click_on_screen: {"description": "Aditya ki chat"}
    (Screen pe koi bhi cheez - contact, button, icon, link, tab - naam/
    description se dhoond ke click karta hai. WhatsApp/koi bhi app/website
    pe generic kaam karta hai - "X pe click karo" jab bhi bole, ye use karo,
    exact coordinates kabhi khud mat banao.)
- double_click_on_screen: {"description": "file/folder ya icon ka naam"}
- right_click_on_screen: {"description": "cheez ka naam"}
- type_in_field: {"description": "message box / search box", "text": "kya likhna hai", "press_enter": false}
    (Kisi field ko dhoond ke click karke usme text type karta hai. "message
    likh ke bhej do" jaisa ho to press_enter: true karo, ya agar text field
    ke baad ek alag 'send button' click karna ho to do actions do: pehle
    type_in_field phir click_on_screen description='send button'.)

Examples:
User: "WhatsApp khol ke Aditya ki chat pe click karo"
-> {"actions": [{"action": "open_app", "params": {"app_name": "whatsapp"}}, {"action": "click_on_screen", "params": {"description": "Aditya ki chat"}}]}

User: "message box mein 'kaha ho' likh ke bhej do"
-> {"actions": [{"action": "type_in_field", "params": {"description": "message input box", "text": "kaha ho", "press_enter": true}}]}

User: "close button pe click karo"
-> {"actions": [{"action": "click_on_screen", "params": {"description": "close (X) button"}}]}

User: "Telegram khol ke Rahul ki chat khol ke 'kal milte hain' bhej do"
-> {"actions": [{"action": "open_app", "params": {"app_name": "telegram"}}, {"action": "click_on_screen", "params": {"description": "Rahul ki chat"}}, {"action": "type_in_field", "params": {"description": "message input box", "text": "kal milte hain", "press_enter": true}}]}

(alag-alag command mein, ek ke baad ek bhi): pehle "Telegram khol do" ->
open_app; baad mein (naya command) "Rahul ki chat khol do" ->
click_on_screen(description="Rahul ki chat"); phir "hi likh ke bhej do" ->
type_in_field. Har baar current screenshot se dhoondta hai, isliye ye
pichli baar Telegram khula chhoda ho to bhi kaam karega - "koi window
nahi mili" jaisa jawab is se kabhi nahi aana chahiye, kyunki ye window
title se nahi, screen content se dhoondta hai.
"""
