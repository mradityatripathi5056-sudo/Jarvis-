"""
screen_capture.py
------------------------------------------------------------
Shared helper: multi-monitor-aware, SPEED-OPTIMIZED screenshot capture,
taaki click_on_screen/autopilot/screen_watch jaise sab vision-based
features fast bhi hon aur 2+ monitors wale setup pe bhi sahi kaam karein.

FIX 1 - MULTI-MONITOR: Windows pe `PIL.ImageGrab.grab(all_screens=True)`
se SAARE monitors ek hi merged image mein capture hote hain, aur
`GetSystemMetrics` se virtual-desktop ka असli offset nikal ke coordinates
sahi se convert kiye jaate hain. (macOS/Linux pe `all_screens` PIL mein
support nahi hai - wahan fallback sirf PRIMARY monitor - known limitation.)

FIX 2 - SPEED: Pehle full-resolution PNG DISK pe likha jaata tha, phir
wapas file se PADHA jaata tha, phir base64 encode hota tha - 4K/high-DPI
screen pe ye file kaafi bada (kayi MB) ho sakta tha, jisse (a) disk I/O,
(b) upload time, aur (c) vision-model ka apna processing time - teeno
slow ho jaate the. Ab:
  - Disk round-trip HATA diya - screenshot seedha memory mein rehta hai.
  - Image ko max ~1280px width tak RESIZE kiya jaata hai (chhota upload =
    fast). Isse click ACCURACY par koi asar nahi padta kyunki hum
    PERCENTAGE-based coordinates use karte hain (0-100%), jo resize se
    (aspect-ratio preserve hone ki wajah se) bilkul invariant hote hain.
  - PNG ki jagah JPEG (quality~65) - kaafi chhota file size, UI text/
    buttons pehchanne ke liye ye quality bilkul kaafi hai.
Isse ek vision-call ka total time kaafi kam ho jaata hai (bada payload
hi sabse bada slow-down factor tha, model ka apna response-time nahi).
"""

import base64
import io
import platform

DEFAULT_MAX_WIDTH = 1280
DEFAULT_JPEG_QUALITY = 65


def capture_for_vision(max_width: int = DEFAULT_MAX_WIDTH, jpeg_quality: int = DEFAULT_JPEG_QUALITY) -> dict:
    """Screenshot leta hai (Windows pe sab monitors, warna sirf primary),
    speed ke liye resize+JPEG-compress karke base64 mein deta hai - koi
    disk round-trip nahi.

    Returns dict: {"image_b64": str, "width": int, "height": int,
                   "offset_x": int, "offset_y": int}
    width/height = ORIGINAL (full-resolution) screenshot ke dimensions -
    isi se percent_to_absolute() sahi ABSOLUTE screen pixel nikalta hai.
    Resize sirf upload-speed ke liye hai, percentage-based location isse
    प्रभावित nahi hoti.
    offset_x/offset_y = virtual-desktop ka top-left - agar koi monitor
    primary ke left/upar hai to ye negative bhi ho sakta hai. Single
    monitor setups pe hamesha (0, 0) hota hai.
    """
    offset_x, offset_y = 0, 0
    img = None

    if platform.system() == "Windows":
        try:
            from PIL import ImageGrab
            import ctypes

            img = ImageGrab.grab(all_screens=True)
            user32 = ctypes.windll.user32
            offset_x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            offset_y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        except Exception:
            img = None

    if img is None:
        # Fallback (macOS/Linux, ya Windows pe upar wala kisi wajah se
        # fail ho gaya) - sirf primary monitor, offset hamesha (0, 0).
        import pyautogui

        img = pyautogui.screenshot()
        offset_x, offset_y = 0, 0

    orig_width, orig_height = img.size

    resized = img
    if orig_width > max_width:
        scale = max_width / orig_width
        resized = img.resize((max_width, max(1, int(orig_height * scale))))

    buf = io.BytesIO()
    resized.convert("RGB").save(buf, format="JPEG", quality=jpeg_quality)
    image_b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "image_b64": image_b64,
        "width": orig_width,
        "height": orig_height,
        "offset_x": offset_x,
        "offset_y": offset_y,
    }


def percent_to_absolute(x_pct: float, y_pct: float, capture: dict) -> tuple:
    """capture_for_vision() se aaye meta-info ke hisaab se, image ke
    percentage position ko ABSOLUTE screen (x, y) pixel mein convert
    karta hai - multi-monitor offset ke saath."""
    x = capture["offset_x"] + int((float(x_pct) / 100) * capture["width"])
    y = capture["offset_y"] + int((float(y_pct) / 100) * capture["height"])
    return x, y


def active_window_title() -> str:
    """Best-effort current active/focused window ka title - click-memory
    ke liye disambiguation context (isse 'send button' Telegram aur
    WhatsApp mein alag-alag yaad rehta hai). Fail ho to khaali string."""
    try:
        import pygetwindow as gw

        win = gw.getActiveWindow()
        return win.title if win else ""
    except Exception:
        return ""
