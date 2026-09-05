"""
skills/vision_skill.py
------------------------------------------------------------
Screen read & understand (vision), OCR (text extraction from images/
screen), aur AI image generation.

Screen "understand" karne ke liye existing OPENROUTER_API_KEY hi use
hota hai - bas ek vision-capable model chahiye (jaise
"google/gemini-2.5-flash" ya "anthropic/claude-sonnet-4.5" OpenRouter
pe). .env mein VISION_MODEL set kar sakte ho, na kare to
OPENROUTER_MODEL hi try hoga.

OCR ke liye: pip install pytesseract, aur Tesseract-OCR binary bhi
install karo (Windows: https://github.com/UB-Mannheim/tesseract/wiki,
phir .env mein TESSERACT_PATH=C:\\Program Files\\Tesseract-OCR\\tesseract.exe)

Image generation OpenRouter ke image-capable models se hoti hai (jaise
"google/gemini-2.5-flash-image") - model ki availability OpenRouter
pe check karte rehna, ye field change hote rehte hain.

NOTE - Voice cloning is intentionally NOT included: real-person voice
cloning tech ka misuse (fraud calls, impersonation, scams) kaafi
common ho gaya hai, isliye ye skill file usse build nahi karti. TTS
voice change (`.env` ka TTS_VOICE) already available hai agar bas
Jarvis ki apni awaaz badalni ho.
"""

import base64
import json
import os

import requests
import config


def _vision_model() -> str:
    # os.getenv() ka default sirf tab lagta hai jab key .env mein bilkul
    # set na ho - agar VISION_MODEL="" (khaali) set hai to ye "" hi return
    # karta, aur OpenRouter API ko khaali model bhejne pe "No models
    # provided" error aata hai. Isliye khaali string ko bhi "unset" maan
    # ke fallback (OPENROUTER_MODEL) use karte hain.
    value = os.getenv("VISION_MODEL", "").strip()
    return value or config.OPENROUTER_MODEL


def screen_read_and_understand(params: dict) -> str:
    """Screenshot leta hai (multi-monitor aware) aur LLM se pucchta hai ki
    usme kya hai / question ka jawab deta hai."""
    question = params.get("question", "Is screenshot mein kya dikh raha hai, detail mein batao.")
    try:
        import screen_capture

        capture = screen_capture.capture_for_vision()
        screenshot_path = capture["path"]

        with open(screenshot_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()

        resp = requests.post(
            config.OPENROUTER_URL,
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            data=json.dumps({
                "model": _vision_model(),
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    ],
                }],
                "max_tokens": 600,
            }),
            timeout=30,
        )
        os.remove(screenshot_path)
        data = resp.json()
        if "choices" not in data:
            # OpenRouter ne error diya (model vision support nahi karta,
            # ya rate-limit, ya invalid key) - asli reason dikhao, cryptic
            # 'choices' KeyError nahi.
            err = data.get("error", {})
            err_msg = err.get("message", str(data)) if isinstance(err, dict) else str(err)
            return (
                f"Screen samajh nahi paya - API ne error diya: {err_msg}\n"
                f"(Model use ho raha tha: {_vision_model()} - agar ye vision "
                "support nahi karta to .env mein VISION_MODEL=openrouter/free "
                "daal ke dekho.)"
            )
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Screen samajh nahi paya: {e}"


def ocr_screen(params: dict) -> str:
    """Screenshot lekar usme se text extract karta hai (OCR)."""
    try:
        import pyautogui
        import pytesseract
    except ImportError:
        return "pytesseract missing. Chalao: pip install pytesseract (aur Tesseract-OCR binary bhi install karo)."
    tess_path = os.getenv("TESSERACT_PATH", "")
    if tess_path:
        pytesseract.pytesseract.tesseract_cmd = tess_path
    try:
        img = pyautogui.screenshot()
        text = pytesseract.image_to_string(img).strip()
        return text if text else "Screen pe koi readable text nahi mila."
    except Exception as e:
        return f"OCR fail: {e}"


def ocr_image_file(params: dict) -> str:
    path = params.get("path", "")
    if not path or not os.path.exists(path):
        return f"'{path}' image nahi mili."
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "pytesseract/Pillow missing. Chalao: pip install pytesseract pillow"
    tess_path = os.getenv("TESSERACT_PATH", "")
    if tess_path:
        pytesseract.pytesseract.tesseract_cmd = tess_path
    try:
        text = pytesseract.image_to_string(Image.open(path)).strip()
        return text if text else "Image mein koi readable text nahi mila."
    except Exception as e:
        return f"OCR fail: {e}"


def describe_image_file(params: dict) -> str:
    """Kisi bhi photo/image file ko dekh kar AI se samjhta/describe karta
    hai (OCR jaisa sirf text nahi nikalta - poori image samajhta hai,
    jaisa screen_read_and_understand karta hai but ek file ke liye).
    Telegram pe koi photo bheje to bhi yahi use hota hai."""
    path = params.get("path", "")
    question = params.get("question", "Is image mein kya hai, detail mein batao.")
    if not path or not os.path.exists(path):
        return f"'{path}' image nahi mili."
    try:
        with open(path, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(path)[1].lstrip(".").lower() or "jpeg"
        if ext == "jpg":
            ext = "jpeg"
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
            json={
                "model": _vision_model(),
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64,{b64_image}"}},
                    ],
                }],
            },
            timeout=45,
        )
        data = resp.json()
        if "choices" not in data:
            err = data.get("error", {})
            err_msg = err.get("message", str(data)) if isinstance(err, dict) else str(err)
            return f"Image samajh nahi paya - API ne error diya: {err_msg}"
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Image samajh nahi paya: {e}"


def generate_image(params: dict) -> str:
    prompt = params.get("prompt", "")
    save_path = params.get("save_path", "generated_image.png")
    if not os.path.isabs(save_path) and os.path.dirname(save_path) == "":
        save_path = os.path.join(config.MEDIA_DIR, save_path)
    if not prompt:
        return "Kaisi image banani hai, prompt batao."
    image_model = os.getenv("IMAGE_MODEL", "google/gemini-2.5-flash-image")
    try:
        resp = requests.post(
            config.OPENROUTER_URL,
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            data=json.dumps({
                "model": image_model,
                "messages": [{"role": "user", "content": prompt}],
                "modalities": ["image", "text"],
            }),
            timeout=45,
        )
        data = resp.json()
        message = data["choices"][0]["message"]
        images = message.get("images", [])
        if not images:
            return f"Image generate nahi hui. Model ne kaha: {message.get('content', '(no text)')}"
        image_url = images[0].get("image_url", {}).get("url", "")
        if image_url.startswith("data:image"):
            b64_data = image_url.split(",", 1)[1]
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64_data))
            return f"Image ban gayi: {save_path}"
        return f"Image URL mila: {image_url}"
    except Exception as e:
        return f"Image generate nahi ho saki: {e}"


ACTIONS = {
    "screen_read_and_understand": screen_read_and_understand,
    "ocr_screen": ocr_screen,
    "ocr_image_file": ocr_image_file,
    "describe_image_file": describe_image_file,
    "generate_image": generate_image,
}

DOCS = """
- screen_read_and_understand: {"question": "is error ka matlab kya hai?"}
    (screenshot lekar AI vision model se samjhata hai - IMPORTANT: jab
    bhi user "screen pe kya hai/chal raha hai", "screen pe dekho aur
    batao", "ye error/page/UI kya hai samjhao" jaisa kuch bole - matlab
    koi EXPLANATION/ANSWER chahta hai screen ke baare mein - to YE action
    use karo, built-in `screenshot` action NAHI (wo sirf file save karta
    hai, kuch bata nahi sakta). Agar user ne koi specific question nahi
    poocha, generic question use karo jaise "is screenshot mein kya
    dikh raha hai, detail mein batao".)
- ocr_screen: {}  (poori screen ka text nikalta hai, exact text chahiye ho tab)
- ocr_image_file: {"path": "photo.png"}  (kisi image file se text nikalta hai)
- describe_image_file: {"path": "photo.png", "question": "is mein kya hai?"}
    (OCR text nahi, poori image ko dekh kar samjhta/describe karta hai -
    "is photo mein kya hai batao" jaisa kuch bole to ye use karo)
- generate_image: {"prompt": "a cat wearing sunglasses, digital art", "save_path": "cat.png"}

Examples:
User: "screen pe kya chal raha hai batao"
-> {"actions": [{"action": "screen_read_and_understand", "params": {"question": "screen pe abhi kya dikh raha hai, detail mein batao"}}]}

User: "screen pe dekho aur batao ye error kya hai"
-> {"actions": [{"action": "screen_read_and_understand", "params": {"question": "screen pe koi error dikh raha hai kya, uska matlab batao"}}]}
"""
