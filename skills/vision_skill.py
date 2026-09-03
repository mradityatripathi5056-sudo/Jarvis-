"""
JARVIS Screen Vision
====================
Real-time desktop screenshot understanding using an OpenRouter vision model.

Features:
- Full-screen screenshot -> vision model analysis
- UI element detection with approximate screen coordinates
- Find an element (button/icon/text) and return its coordinates
- Click a visual element by asking the vision model where it is
- OCR fallback
- Active-window + running-process context
- Best-effort Windows media-session / currently-playing metadata
- Cached last analysis so a follow-up click can use the same screenshot

IMPORTANT: VISION_MODEL must support image input. A normal text-only model will
return an OpenRouter "no endpoints found that support image input" error.
"""

import base64
import json
import logging
import os
import platform
import subprocess
import tempfile
import time

import requests
import config


_LAST_ANALYSIS = {
    "timestamp": 0.0,
    "screenshot": None,
    "screen_size": None,
    "analysis": None,
}


def _vision_model() -> str:
    # Never silently inherit a text-only model unless the user explicitly asks
    # for it. The normal Jarvis model and vision model should be independent.
    return os.getenv("VISION_MODEL", "openrouter/free").strip()


def _api_error(resp, data):
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)
    if not resp.ok:
        return f"HTTP {resp.status_code}: {resp.text[:500]}"
    return "Unknown OpenRouter error"


def _screenshot_to_data_url(img) -> str:
    """Convert PIL screenshot to a reasonably small JPEG data URL."""
    from io import BytesIO

    # Vision does not need a huge lossless PNG for normal desktop UI.
    max_width = int(os.getenv("VISION_MAX_WIDTH", "1920"))
    if img.width > max_width:
        ratio = max_width / float(img.width)
        img = img.resize((max_width, max(1, int(img.height * ratio))))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = BytesIO()
    quality = int(os.getenv("VISION_JPEG_QUALITY", "82"))
    img.save(buf, format="JPEG", quality=max(50, min(95, quality)), optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _get_active_window() -> str:
    """Get the foreground window title on Windows without requiring pywin32."""
    if platform.system() != "Windows":
        return ""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip()
    except Exception:
        return ""


def _get_running_apps() -> str:
    """Best-effort compact list of visible/running Windows processes."""
    if platform.system() != "Windows":
        return ""
    try:
        out = subprocess.check_output(
            ["tasklist", "/fo", "csv", "/nh"],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        names = []
        seen = set()
        for line in out.splitlines():
            if not line.strip():
                continue
            # CSV first column is executable name.
            name = line.split('","', 1)[0].strip('" ').strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                names.append(name)
        return ", ".join(names[:80])
    except Exception:
        return ""


def _get_media_session() -> str:
    """Best-effort Windows media metadata via WinRT from PowerShell.

    It is intentionally optional: if Windows/PowerShell/SMTC is unavailable,
    screen vision still works normally.
    """
    if platform.system() != "Windows":
        return ""
    ps = r'''
try {
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime] | Out-Null
  $mgr = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync().GetAwaiter().GetResult()
  $session = $mgr.GetCurrentSession()
  if ($null -eq $session) { exit 0 }
  $props = $session.TryGetMediaPropertiesAsync().GetAwaiter().GetResult()
  $status = $session.GetPlaybackInfo().PlaybackStatus.ToString()
  $artist = [string]$props.Artist
  $title = [string]$props.Title
  $album = [string]$props.AlbumTitle
  if ($title -or $artist) { Write-Output ("Title=" + $title + "; Artist=" + $artist + "; Album=" + $album + "; Status=" + $status) }
} catch { }
'''
    try:
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def _build_context() -> dict:
    return {
        "active_window": _get_active_window(),
        "running_apps": _get_running_apps(),
        "media_session": _get_media_session(),
    }


def _call_vision(image_data_url: str, question: str, *, structured: bool = False) -> str:
    """Call OpenRouter with the exact multimodal image_url format."""
    system = (
        "You are JARVIS Desktop Vision. Analyze the supplied desktop screenshot "
        "like a careful computer-vision assistant. Distinguish visible facts from "
        "guesses. Read UI text, app/window names, buttons, menus, icons, alerts, "
        "and media information when visible. Coordinates must be relative to the "
        "FULL screenshot in pixels, origin at top-left. Do not invent coordinates."
    )
    if structured:
        system += (
            " Return ONLY valid JSON with this schema: "
            '{"screen_summary":"...","elements":[{"label":"...","type":"button|icon|text|link|menu|other",'
            '"x":0,"y":0,"confidence":0.0,"notes":"..."}],"warnings":[]}. '
            "Use approximate center coordinates for elements. confidence is 0..1."
        )

    payload = {
        "model": _vision_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]},
        ],
        "max_tokens": int(os.getenv("VISION_MAX_TOKENS", "1400")),
    }
    try:
        resp = requests.post(
            config.OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=int(os.getenv("VISION_TIMEOUT", "45")),
        )
        try:
            data = resp.json()
        except Exception:
            data = {}
        if not resp.ok or "choices" not in data:
            return f"VISION_API_ERROR: {_api_error(resp, data)}"
        content = data["choices"][0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
        return str(content).strip()
    except requests.Timeout:
        return "VISION_API_ERROR: vision request timeout hua."
    except requests.RequestException as e:
        return f"VISION_API_ERROR: network error: {e}"
    except Exception as e:
        logging.exception("screen vision error")
        return f"VISION_API_ERROR: {e}"


def _take_screen():
    import pyautogui
    img = pyautogui.screenshot()
    return img


def screen_read_and_understand(params: dict) -> str:
    """Read the current desktop screen with vision + local system context."""
    global _LAST_ANALYSIS
    question = params.get(
        "question",
        "Screen ko detail mein inspect karo: active app/window, visible text, buttons, icons, menus, dialogs, media/player info, important warnings/errors, and anything the user may need to know."
    )
    try:
        img = _take_screen()
        context = _build_context()
        image_url = _screenshot_to_data_url(img)
        enriched = (
            f"User question: {question}\n\n"
            f"Local context (use only as supporting evidence):\n"
            f"Active window: {context['active_window'] or '(unknown)'}\n"
            f"Media session: {context['media_session'] or '(none/unknown)'}\n"
            f"Running processes: {context['running_apps'] or '(unknown)'}\n\n"
            "Now inspect the screenshot. Clearly label uncertain inferences."
        )
        answer = _call_vision(image_url, enriched, structured=False)
        if answer.startswith("VISION_API_ERROR:"):
            return answer.replace("VISION_API_ERROR:", "Screen vision fail:", 1)
        _LAST_ANALYSIS = {
            "timestamp": time.time(),
            "screenshot": img,
            "screen_size": (img.width, img.height),
            "analysis": answer,
        }
        return (
            f"Active window: {context['active_window'] or 'unknown'}\n"
            f"Media: {context['media_session'] or 'unknown'}\n\n"
            f"Screen vision:\n{answer}"
        )
    except ImportError:
        return "Screen capture ke liye pyautogui missing hai. Chalao: pip install pyautogui pillow"
    except Exception as e:
        logging.exception("screen_read_and_understand failed")
        return f"Screen samajh nahi paya: {e}"


def _vision_elements(question: str):
    """Return structured element coordinates from a fresh screenshot."""
    img = _take_screen()
    image_url = _screenshot_to_data_url(img)
    prompt = (
        f"Find UI elements relevant to this request: {question}\n"
        "List every plausible matching element, including visible text, buttons, "
        "icons or controls. Coordinates should be the CENTER of the element in "
        f"the original {img.width}x{img.height} screenshot."
    )
    raw = _call_vision(image_url, prompt, structured=True)
    if raw.startswith("VISION_API_ERROR:"):
        raise RuntimeError(raw)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    data = json.loads(cleaned)
    data["screen_size"] = [img.width, img.height]
    data["timestamp"] = time.time()
    return data


def screen_find_element(params: dict) -> str:
    """Find a visual UI element and return coordinates + confidence."""
    query = params.get("element", params.get("query", "")).strip()
    if not query:
        return "Kaunsa button/icon/text dhoondhna hai?"
    try:
        data = _vision_elements(query)
        elements = data.get("elements", [])
        if not elements:
            return f"'{query}' screen par nahi mila."
        lines = [f"Screen size: {data.get('screen_size')} pixels"]
        for e in elements[:10]:
            lines.append(
                f"- {e.get('label','unknown')} ({e.get('type','other')}): "
                f"x={e.get('x')}, y={e.get('y')}, confidence={e.get('confidence',0)}"
            )
        return "\n".join(lines)
    except json.JSONDecodeError:
        return "Vision model ne valid element JSON nahi diya. Dobara try karo."
    except Exception as e:
        return f"Element find fail: {e}"


def screen_click_element(params: dict) -> str:
    """Find a requested visual element, then click its center."""
    query = params.get("element", params.get("query", "")).strip()
    if not query:
        return "Kaunsa button/icon click karna hai?"
    try:
        import pyautogui
        data = _vision_elements(query)
        elements = data.get("elements", [])
        if not elements:
            return f"'{query}' screen par nahi mila, isliye click nahi kiya."
        # Highest-confidence valid coordinate wins.
        valid = []
        for e in elements:
            try:
                x, y = float(e["x"]), float(e["y"])
                c = float(e.get("confidence", 0))
                if 0 <= x <= data["screen_size"][0] and 0 <= y <= data["screen_size"][1]:
                    valid.append((c, x, y, e.get("label", query)))
            except Exception:
                continue
        if not valid:
            return f"'{query}' mila, lekin valid coordinates nahi mile."
        confidence, x, y, label = max(valid, key=lambda v: v[0])
        min_conf = float(os.getenv("VISION_CLICK_MIN_CONFIDENCE", "0.70"))
        if confidence < min_conf and str(params.get("force", "false")).lower() != "true":
            return (
                f"'{label}' mila but confidence {confidence:.2f} hai. "
                f"Safe click ke liye kam se kam {min_conf:.2f} chahiye. "
                "Force karna ho to force=true use karo."
            )
        pyautogui.moveTo(int(x), int(y), duration=0.15)
        pyautogui.click()
        return f"'{label}' ko click kar diya (x={int(x)}, y={int(y)}, confidence={confidence:.2f})."
    except ImportError:
        return "pyautogui missing hai. Chalao: pip install pyautogui"
    except Exception as e:
        logging.exception("screen_click_element failed")
        return f"Visual click fail: {e}"


def ocr_screen(params: dict) -> str:
    """Screenshot lekar OCR se text extract karta hai."""
    try:
        import pytesseract
    except ImportError:
        return "pytesseract missing. Chalao: pip install pytesseract (aur Tesseract-OCR binary install karo)."
    tess_path = os.getenv("TESSERACT_PATH", "")
    if tess_path:
        pytesseract.pytesseract.tesseract_cmd = tess_path
    try:
        img = _take_screen()
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


def generate_image(params: dict) -> str:
    prompt = params.get("prompt", "")
    save_path = params.get("save_path", "generated_image.png")
    if not prompt:
        return "Kaisi image banani hai, prompt batao."
    image_model = os.getenv("IMAGE_MODEL", "").strip()
    if not image_model:
        return "IMAGE_MODEL set nahi hai. Image generation ke liye .env mein compatible image model set karo."
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/images",
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": image_model, "prompt": prompt},
            timeout=60,
        )
        data = resp.json()
        if not resp.ok:
            return f"Image generate nahi hui: {_api_error(resp, data)}"
        item = (data.get("data") or [{}])[0]
        b64 = item.get("b64_json")
        if b64:
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64))
            return f"Image ban gayi: {save_path}"
        return "Image generate hui, lekin response mein local image data nahi mila."
    except Exception as e:
        return f"Image generate nahi ho saki: {e}"


ACTIONS = {
    "screen_read_and_understand": screen_read_and_understand,
    "screen_find_element": screen_find_element,
    "screen_click_element": screen_click_element,
    "ocr_screen": ocr_screen,
    "ocr_image_file": ocr_image_file,
    "generate_image": generate_image,
}

DOCS = r"""
SCREEN VISION ACTIONS:
- screen_read_and_understand: {"question": "screen pe abhi kya chal raha hai?"}
    Current full desktop screenshot ko vision model se read karta hai. Visible apps,
    text, buttons, icons, dialogs, errors, menus aur media/player information batata hai.
- screen_find_element: {"element": "Settings button"}
    Screen par visual element dhoondhkar approximate CENTER x/y coordinates aur confidence deta hai.
- screen_click_element: {"element": "Play button"}
    Vision se element locate karke safe confidence threshold cross hone par click karta hai.
    Low-confidence click ko by default rokta hai. Zarurat par {"force": true} diya ja sakta hai.
- ocr_screen: {}
    Tesseract se exact visible text nikalta hai. Code/text ke liye useful fallback.

EXAMPLES:
User: "Jarvis screen dekho"
-> {"actions":[{"action":"screen_read_and_understand","params":{"question":"Screen ko detail mein inspect karo aur batao kya kya open/chal raha hai."}}]}
User: "screen pe settings button kaha hai?"
-> {"actions":[{"action":"screen_find_element","params":{"element":"Settings button"}}]}
User: "screen wala play button click karo"
-> {"actions":[{"action":"screen_click_element","params":{"element":"Play button"}}]}
User: "abhi kaunsa gana chal raha hai?"
-> {"actions":[{"action":"screen_read_and_understand","params":{"question":"Currently playing song identify karo. Screen par jo title/artist dikh raha ho use read karo aur media-session metadata se cross-check karo. Agar confirm nahi hai to clearly bolo."}}]}
"""
