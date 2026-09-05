"""
screen_capture.py
------------------------------------------------------------
Shared helper: multi-monitor-aware screenshot capture, taaki
click_on_screen/autopilot/screen_watch jaise sab vision-based features
2+ monitors wale setup pe bhi sahi kaam karein.

PROBLEM jo fix ho raha hai: pehle har skill apna khud ka
`pyautogui.screenshot()` use karta tha - jo sirf PRIMARY monitor
capture karta hai. Agar koi cheez SECONDARY monitor pe hoti (jaise
YouTube doosri screen pe khula ho), to vision model use dhoond hi nahi
paata (screenshot mein wo tha hi nahi), aur click galat jagah (primary
monitor pe) chala jaata.

Ab Windows pe `PIL.ImageGrab.grab(all_screens=True)` se SAARE monitors
ek hi merged image mein capture hote hain, aur `GetSystemMetrics` se
virtual-desktop ka असli offset (agar koi monitor primary ke LEFT/ABOVE
hai to uska top-left negative hota hai) nikal ke coordinates sahi se
convert kiye jaate hain.

NOTE: macOS/Linux pe `all_screens` PIL mein support nahi hai - wahan
fallback sirf PRIMARY monitor capture karta hai (single-monitor jaisa
hi behavior jo pehle sab jagah tha) - ye ek known limitation hai.
"""

import os
import platform

import config


def capture_for_vision() -> dict:
    """Screenshot leta hai (Windows pe sab monitors, warna sirf primary),
    disk pe save karta hai, aur uski meta-info deta hai taaki baad mein
    percentage coordinates ko sahi ABSOLUTE screen position mein convert
    kiya ja sake.

    Returns dict: {"path": str, "width": int, "height": int,
                   "offset_x": int, "offset_y": int}
    offset_x/offset_y = virtual-desktop ka top-left, jo screenshot ke
    pixel (0,0) ke barabar hai - agar koi monitor primary ke left/upar
    hai to ye negative bhi ho sakta hai. Single monitor setups pe
    hamesha (0, 0) hota hai.
    """
    screenshot_path = os.path.join(config.MEDIA_DIR, "_vision_capture_temp.png")
    offset_x, offset_y = 0, 0

    if platform.system() == "Windows":
        try:
            from PIL import ImageGrab
            import ctypes

            img = ImageGrab.grab(all_screens=True)
            user32 = ctypes.windll.user32
            offset_x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            offset_y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            img.save(screenshot_path)
            width, height = img.size
            return {
                "path": screenshot_path,
                "width": width,
                "height": height,
                "offset_x": offset_x,
                "offset_y": offset_y,
            }
        except Exception:
            pass  # fallback neeche

    # Fallback (macOS/Linux, ya Windows pe upar wala kisi wajah se fail ho
    # gaya) - sirf primary monitor, offset hamesha (0, 0).
    import pyautogui

    pyautogui.screenshot(screenshot_path)
    width, height = pyautogui.size()
    return {"path": screenshot_path, "width": width, "height": height, "offset_x": 0, "offset_y": 0}


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
