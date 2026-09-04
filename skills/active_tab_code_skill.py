"""
skills/active_tab_code_skill.py
------------------------------------------------------------
1) Active Tab Tracker - abhi konsi app/window active hai, aur agar
   browser hai to uska (title se pata chalne wala) tab kya hai.
2) Code Explainer & Debugger - screen pe chal raha code OCR se
   nikaal kar existing OPENROUTER LLM se explain/fix karwata hai.
   (Vision model ke bajaye OCR+text LLM use kiya hai kyunki code ke
   exact characters/indentation padhne mein text OCR zyada reliable
   hai screenshot-vision ke comparison mein.)

Extra package: pygetwindow (already requirements.txt mein hai).
Code OCR ke liye skills/vision_skill.py wale hi pytesseract setup
(TESSERACT_PATH env) ka use hota hai.
"""

import json
import os

import requests
import config

_BROWSER_PROCESSES = ("chrome", "msedge", "firefox", "brave", "opera")


def get_active_window(params: dict) -> str:
    """Abhi kaunsi window/app active hai (aur agar browser hai to
    uske title se tab ka andaza)."""
    try:
        import pygetwindow as gw
    except ImportError:
        return "pygetwindow missing. Chalao: pip install PyGetWindow"
    try:
        win = gw.getActiveWindow()
        if not win or not win.title:
            return "Koi active window detect nahi hui."
        title = win.title
        is_browser = any(b in title.lower() for b in ("- google chrome", "- microsoft edge", "- mozilla firefox", "- brave", "- opera"))
        if is_browser:
            tab_title = title.split(" - ")[0].strip()
            return f"Abhi browser mein '{tab_title}' tab khula hai (window: {title})."
        return f"Abhi active window: {title}"
    except Exception as e:
        return f"Active window pata nahi chal saka: {e}"


def _ocr_screen_text() -> str:
    try:
        import pyautogui
        import pytesseract
    except ImportError:
        return "__MISSING__:pytesseract"
    tess_path = os.getenv("TESSERACT_PATH", "")
    if tess_path:
        pytesseract.pytesseract.tesseract_cmd = tess_path
    img = pyautogui.screenshot()
    return pytesseract.image_to_string(img)


def explain_code_on_screen(params: dict) -> str:
    """Screen pe dikh raha code OCR se padh kar LLM se explain/debug
    karwata hai. params.instruction se poochho kya chahiye (explain,
    fix error, optimize, etc.) - default: errors dhoondo aur fix batao."""
    instruction = params.get(
        "instruction",
        "Ye code mein koi error/bug hai kya, dhoondo aur fix suggest karo. "
        "Agar error na ho to bas short mein batao ye code kya karta hai.",
    )
    text = _ocr_screen_text()
    if text == "__MISSING__:pytesseract":
        return "pytesseract missing. Chalao: pip install pytesseract (aur Tesseract-OCR binary bhi install karo)."
    if not text.strip():
        return "Screen pe koi readable code/text nahi mila OCR se."

    try:
        resp = requests.post(
            config.OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": config.OPENROUTER_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": f"{instruction}\n\nScreen se OCR kiya gaya code/text (thoda garbled ho sakta hai, samajh ke padhna):\n{text[:6000]}",
                    }
                ],
                "max_tokens": 700,
            }),
            timeout=30,
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Code samajhne mein LLM error aaya: {e}"


ACTIONS = {
    "get_active_window": get_active_window,
    "explain_code_on_screen": explain_code_on_screen,
}

DOCS = """
- get_active_window: {}  (abhi kaunsi app/browser tab active hai, batata hai)
- explain_code_on_screen: {"instruction": "is error ko fix karo"}
    (screen pe dikh rahe code ko OCR se padh kar LLM se explain/fix/debug
    karwata hai; instruction optional hai - default: error dhoondo aur fix batao)

Example:
User: "abhi kya chal raha hai screen pe"
-> {"actions": [{"action": "get_active_window", "params": {}}]}

User: "screen pe jo code hai usme error fix karo"
-> {"actions": [{"action": "explain_code_on_screen", "params": {"instruction": "Is code mein error dhoondo aur fix batao"}}]}
"""
