"""
skills/incognito_skill.py
------------------------------------------------------------
PROBLEM jo fix ho raha hai: pehle "chrome pe incognito tab khol do"
bolne par Jarvis ke paas koi dedicated action hi nahi tha, isliye LLM
sabse paas wala action (web_search) pick kar leta tha - jisse Google
pe "incognito tab" TEXT search ho jaata tha, asli incognito window
kabhi khulti hi nahi thi.

Ab ye skill ek naya action deta hai jo seedha OS-level browser
executable ko incognito/private-window flag ke saath launch karta hai:
  - Chrome / Brave  -> --incognito
  - Edge            -> -inprivate
  - Firefox         -> -private-window

Windows / macOS / Linux teeno pe kaam karta hai (jahan wo browser
installed ho).
"""

import glob
import os
import platform
import shutil
import subprocess

BROWSER_INCOGNITO_FLAG = {
    "chrome": "--incognito",
    "brave": "--incognito",
    "edge": "-inprivate",
    "firefox": "-private-window",
}

# ---- Windows: common install locations (env vars expand karke dhundte hain) ----
_WINDOWS_PATHS = {
    "chrome": [
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    ],
    "edge": [
        r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    ],
    "brave": [
        r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
    "firefox": [
        r"%ProgramFiles%\Mozilla Firefox\firefox.exe",
        r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe",
    ],
}

# ---- macOS: "open -a <App Name>" se launch hota hai ----
_MAC_APP_NAMES = {
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "brave": "Brave Browser",
    "firefox": "Firefox",
}

# ---- Linux: PATH pe in binary naamon mein se koi bhi mil sakta hai ----
_LINUX_BIN_NAMES = {
    "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    "edge": ["microsoft-edge", "microsoft-edge-stable"],
    "brave": ["brave-browser", "brave"],
    "firefox": ["firefox"],
}


def _find_windows_exe(browser: str):
    for raw_path in _WINDOWS_PATHS.get(browser, []):
        matches = glob.glob(os.path.expandvars(raw_path))
        if matches:
            return matches[0]
    return None


def open_incognito(params: dict) -> str:
    browser = (params.get("browser") or "chrome").strip().lower()
    if browser not in BROWSER_INCOGNITO_FLAG:
        browser = "chrome"

    url = (params.get("url") or "").strip()
    if url and not url.startswith("http"):
        url = "https://" + url

    flag = BROWSER_INCOGNITO_FLAG[browser]
    system = platform.system()

    try:
        if system == "Windows":
            exe = _find_windows_exe(browser)
            if not exe:
                return f"'{browser}' is laptop pe installed nahi mila (incognito window ke liye chahiye)."
            subprocess.Popen([exe, flag] + ([url] if url else []))
            return f"{browser} ka incognito/private window khol diya."

        if system == "Darwin":
            app_name = _MAC_APP_NAMES.get(browser, "Google Chrome")
            subprocess.Popen(["open", "-na", app_name, "--args", flag] + ([url] if url else []))
            return f"{browser} ka incognito/private window khol diya."

        # Linux fallback
        for bin_name in _LINUX_BIN_NAMES.get(browser, []):
            if shutil.which(bin_name):
                subprocess.Popen([bin_name, flag] + ([url] if url else []))
                return f"{browser} ka incognito/private window khol diya."
        return f"'{browser}' is system pe nahi mila."
    except Exception as e:
        return f"Incognito window nahi khul saka: {e}"


ACTIONS = {
    "open_incognito": open_incognito,
}

DOCS = """
- open_incognito: {"browser": "chrome", "url": "example.com"}
    (ASLI incognito/private browser window kholta hai - "browser" optional
    hai: "chrome" (default), "edge", "brave", ya "firefox". "url" bhi
    optional hai, na do to khaali incognito window khulegi.
    IMPORTANT: jab bhi user "incognito"/"private" tab ya window kholne ko
    bole, YE action use karo - "web_search" action use MAT karo (wo sirf
    Google pe text search karta hai, koi incognito window nahi kholta).

Example:
User: "chrome pe incognito tab khol do"
-> {"actions": [{"action": "open_incognito", "params": {"browser": "chrome"}}]}

User: "ek private window kholo edge mein"
-> {"actions": [{"action": "open_incognito", "params": {"browser": "edge"}}]}

User: "incognito mein youtube.com khol do"
-> {"actions": [{"action": "open_incognito", "params": {"browser": "chrome", "url": "youtube.com"}}]}
"""
