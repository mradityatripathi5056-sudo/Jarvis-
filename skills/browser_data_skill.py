"""
skills/browser_data_skill.py
------------------------------------------------------------
PROBLEM jo fix ho raha hai: pehle "history delete karo" bolne par
Jarvis chrome://settings/clearBrowserData khol ke ANDHAADHUND
'tab' 'tab' 'tab' 'enter' keys press karta tha (screenshot mein dikha)
- ye fragile hai kyunki:
  - Chrome ke different versions/languages mein dialog ka tab-order
    alag hota hai
  - Window focus thoda bhi idhar-udhar ho to galat jagah click/type
    ho jaata hai
  - Isiliye "DLT NHI HUI" wala result aaya

SOLUTION: UI guess karne ke bajaye seedha OS-level History file delete
karo. Chrome/Edge/Brave teeno Chromium-based hain aur history ek SQLite
file ("History", bina extension ke) mein store karte hain, browser
profile folder ke andar. Deterministic aur 100% reliable tarika ye hai:
  1. Browser process band karo (taaki file locked na ho)
  2. Uski "History" file(s) delete karo (sab profiles - Default,
     Profile 1, Profile 2, ...)
Isse UI ka bilkul bharosa nahi karna padta.
"""

import glob
import os
import platform
import subprocess
import time

import config

try:
    if "clear_browser_history" not in config.DESTRUCTIVE_ACTIONS:
        config.DESTRUCTIVE_ACTIONS.append("clear_browser_history")
except Exception:
    pass

# Windows: Chromium browsers ka user-data folder yahan hota hai
_PROFILE_ROOTS_WINDOWS = {
    "chrome": r"%LocalAppData%\Google\Chrome\User Data",
    "edge": r"%LocalAppData%\Microsoft\Edge\User Data",
    "brave": r"%LocalAppData%\BraveSoftware\Brave-Browser\User Data",
}

_PROFILE_ROOTS_MAC = {
    "chrome": "~/Library/Application Support/Google/Chrome",
    "edge": "~/Library/Application Support/Microsoft Edge",
    "brave": "~/Library/Application Support/BraveSoftware/Brave-Browser",
}

_PROFILE_ROOTS_LINUX = {
    "chrome": "~/.config/google-chrome",
    "edge": "~/.config/microsoft-edge",
    "brave": "~/.config/BraveSoftware/Brave-Browser",
}

_PROCESS_NAMES_WINDOWS = {
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "brave": "brave.exe",
}

_PROCESS_NAMES_UNIX = {
    "chrome": ["google-chrome", "chrome", "Google Chrome"],
    "edge": ["msedge", "Microsoft Edge"],
    "brave": ["brave", "Brave Browser"],
}


def _kill_browser(browser: str):
    system = platform.system()
    try:
        if system == "Windows":
            name = _PROCESS_NAMES_WINDOWS.get(browser)
            if name:
                subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True, timeout=10)
        else:
            for name in _PROCESS_NAMES_UNIX.get(browser, []):
                subprocess.run(["pkill", "-f", name], capture_output=True, timeout=10)
        time.sleep(1.5)  # OS ko file handle release karne ka time do
    except Exception:
        pass


def _profile_root(browser: str) -> str | None:
    system = platform.system()
    if system == "Windows":
        raw = _PROFILE_ROOTS_WINDOWS.get(browser)
        return os.path.expandvars(raw) if raw else None
    if system == "Darwin":
        raw = _PROFILE_ROOTS_MAC.get(browser)
        return os.path.expanduser(raw) if raw else None
    raw = _PROFILE_ROOTS_LINUX.get(browser)
    return os.path.expanduser(raw) if raw else None


def clear_browser_history(params: dict) -> str:
    browser = (params.get("browser") or "chrome").strip().lower()
    if browser not in _PROFILE_ROOTS_WINDOWS:
        browser = "chrome"

    root = _profile_root(browser)
    if not root or not os.path.isdir(root):
        return f"'{browser}' ka profile folder nahi mila is system pe - installed hai confirm karo."

    _kill_browser(browser)

    # Sab profiles ("Default", "Profile 1", "Profile 2", ...) ke andar
    # "History" file dhoondo aur delete karo.
    deleted = 0
    for history_path in glob.glob(os.path.join(root, "*", "History")) + glob.glob(os.path.join(root, "History")):
        try:
            os.remove(history_path)
            deleted += 1
        except FileNotFoundError:
            pass
        except PermissionError:
            return (
                f"{browser} abhi bhi chal raha hai isliye History file delete nahi ho payi "
                "(background mein koi process reh gaya hoga) - browser poora band karke dobara try karo."
            )
        except Exception as e:
            return f"History delete karne mein error: {e}"

    if deleted == 0:
        return f"{browser} mein history file mili hi nahi (shayad already khaali hai)."
    return f"{browser} ki history delete kar di ({deleted} profile(s) se)."


ACTIONS = {
    "clear_browser_history": clear_browser_history,
}

DOCS = """
- clear_browser_history: {"browser": "chrome"}
    (browser band karke uski History file(s) seedha disk se delete karta
    hai - "browser" optional hai: "chrome" (default), "edge", ya "brave".
    IMPORTANT: history delete karne ke liye YE action use karo, keyboard
    shortcuts (ctrl+shift+delete) ya tab/enter guess karke UI navigate
    karne ki koshish MAT karo - wo unreliable hai.

Example:
User: "chrome ki history delete kar do"
-> {"actions": [{"action": "clear_browser_history", "params": {"browser": "chrome"}}]}
"""
