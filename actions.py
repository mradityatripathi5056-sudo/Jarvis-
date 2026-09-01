"""
actions.py
Yahan wo saare functions hain jo LLM ke decide kiye action ko actually execute karte hain.
Naya command add karna ho to bas yahan naya function likho aur ACTION_MAP mein register karo.
"""

import os
import re
import ast
import json
import operator
import subprocess
import platform
import glob
import socket
import threading
import psutil
import pyautogui
import pyperclip
import webbrowser
import requests
from datetime import datetime, timedelta
from speech import speak


def open_app(app_name: str) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(app_name)
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
        else:
            subprocess.Popen([app_name])
        return f"{app_name} khol diya."
    except Exception as e:
        return f"{app_name} nahi khul saka: {e}"


def open_camera() -> str:
    """OS ka default camera app kholta hai (Windows Camera / Photo Booth / cheese)."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile("microsoft.windows.camera:")
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "Photo Booth"])
        else:
            subprocess.Popen(["cheese"])
        return "Camera khol diya."
    except Exception as e:
        return f"Camera nahi khul saka: {e}"


def take_photo(params: dict) -> str:
    """Webcam se directly ek photo khinch kar save karta hai - koi camera
    app khulne ki zaroorat nahi, isliye phone se bhi kaam karta hai."""
    try:
        import cv2
    except ImportError:
        return "Photo lene ke liye pehle ye install karo: pip install opencv-python"

    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        cam.release()
        return "Camera access nahi mil paya - check karo koi doosra app use to nahi kar raha camera."

    for _ in range(5):  # warm-up frames, camera ko settle hone do
        cam.read()
    ok, frame = cam.read()
    cam.release()

    if not ok:
        return "Photo capture fail ho gayi."

    filename = params.get("filename") or f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    cv2.imwrite(filename, frame)
    return f"Photo le liya aur save kar diya: {filename}"


def rename_file(params: dict) -> str:
    old_path = params.get("old_path", "")
    new_path = params.get("new_path", "")
    if not old_path or not new_path:
        return "Kis file ka naam kya karna hai, dono path batao."
    try:
        os.rename(old_path, new_path)
        return f"'{old_path}' ka naam badal ke '{new_path}' kar diya."
    except Exception as e:
        return f"Rename nahi ho saka: {e}"


def edit_file(params: dict) -> str:
    """File mein content add (append) ya poora replace karta hai."""
    path = params.get("path", "")
    mode = params.get("mode", "append")  # "append" ya "replace"
    content = params.get("content", "")
    if not path:
        return "Kis file mein edit karna hai, path batao."
    try:
        file_mode = "a" if mode == "append" else "w"
        with open(path, file_mode, encoding="utf-8") as f:
            f.write(content)
        word = "add" if mode == "append" else "replace"
        return f"'{path}' mein content {word} kar diya."
    except Exception as e:
        return f"File edit nahi ho saki: {e}"


def send_message(params: dict) -> str:
    """WhatsApp ke through kisi ko message bhejta hai (pywhatkit se).
    Number country code ke saath hona chahiye, jaise +919876543210.
    Default browser mein WhatsApp Web login hona zaroori hai."""
    phone = params.get("phone", "")
    message = params.get("message", "")
    if not phone or not message:
        return "Kisko aur kya message bhejna hai - dono batao (number country code ke saath, jaise +91...)."
    try:
        import pywhatkit
    except ImportError:
        return "Message bhejne ke liye pehle ye install karo: pip install pywhatkit"
    try:
        pywhatkit.sendwhatmsg_instantly(phone, message, wait_time=15, tab_close=True)
        return f"{phone} ko WhatsApp message bhej diya."
    except Exception as e:
        return f"Message bhejne mein error aaya: {e}"


def close_app(app_name: str) -> str:
    closed = False
    for proc in psutil.process_iter(["pid", "name"]):
        if app_name.lower() in (proc.info["name"] or "").lower():
            proc.kill()
            closed = True
    return f"{app_name} band kar diya." if closed else f"{app_name} chal hi nahi raha tha."


def search_file(query: str, search_path: str = os.path.expanduser("~")) -> str:
    matches = glob.glob(f"{search_path}/**/*{query}*", recursive=True)
    if not matches:
        return f"'{query}' naam ki koi file nahi mili."
    return "Ye files mili:\n" + "\n".join(matches[:5])


def create_file(path: str, content: str = "") -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File ban gayi: {path}"
    except Exception as e:
        return f"File nahi ban saki: {e}"


def delete_file(path: str) -> str:
    try:
        os.remove(path)
        return f"File delete ho gayi: {path}"
    except Exception as e:
        return f"File delete nahi ho saki: {e}"


def system_info() -> str:
    battery = psutil.sensors_battery()
    battery_str = f"{battery.percent}%" if battery else "N/A"
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    now = datetime.now().strftime("%I:%M %p, %d %B %Y")
    return f"Time: {now}. Battery: {battery_str}. CPU usage: {cpu}%. RAM usage: {ram}%."


def volume_control(level: int) -> str:
    level = max(0, min(100, int(level)))
    system = platform.system()
    try:
        if system == "Windows":
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level / 100, None)
            return f"Volume {level}% set kar diya."
        elif system == "Darwin":
            os.system(f"osascript -e 'set volume output volume {level}'")
            return f"Volume {level}% set kar diya."
        else:
            os.system(f"amixer -D pulse sset Master {level}%")
            return f"Volume {level}% set kar diya."
    except Exception as e:
        return f"Volume set nahi ho saka: {e}"


def mute_volume() -> str:
    return volume_control(0)


def brightness_control(level: int) -> str:
    level = max(0, min(100, int(level)))
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        return f"Brightness {level}% set kar diya."
    except Exception as e:
        return f"Brightness set nahi ho saka: {e}"


def screenshot() -> str:
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    img = pyautogui.screenshot()
    img.save(filename)
    return f"Screenshot save ho gaya: {filename}"


def web_search(query: str) -> str:
    webbrowser.open(f"https://www.google.com/search?q={query}")
    return f"'{query}' search kar raha hoon."


def shutdown() -> str:
    system = platform.system()
    if system == "Windows":
        os.system("shutdown /s /t 5")
    else:
        os.system("shutdown -h now")
    return "Computer shutdown ho raha hai."


def restart() -> str:
    system = platform.system()
    if system == "Windows":
        os.system("shutdown /r /t 5")
    else:
        os.system("reboot")
    return "Computer restart ho raha hai."


def clipboard_write(text: str) -> str:
    pyperclip.copy(text)
    return "Clipboard mein copy ho gaya."


def clipboard_read() -> str:
    text = pyperclip.paste()
    return f"Clipboard mein hai: {text}" if text else "Clipboard khali hai."


def lock_screen() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            os.system("rundll32.exe user32.dll,LockWorkStation")
        elif system == "Darwin":
            os.system("pmset displaysleepnow")
        else:
            os.system("loginctl lock-session")
        return "Screen lock kar diya."
    except Exception as e:
        return f"Lock nahi ho saka: {e}"


def youtube_search(query: str) -> str:
    webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
    return f"YouTube pe '{query}' search kar raha hoon."


def youtube_search_and_play(query: str) -> str:
    try:
        search_url = f"https://www.youtube.com/results?search_query={query}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(search_url, headers=headers, timeout=10)
        video_ids = re.findall(r"watch\?v=(\S{11})", response.text)
        if not video_ids:
            video_ids = re.findall(r'"videoId":"(.{11})"', response.text)

        if video_ids:
            webbrowser.open(f"https://www.youtube.com/watch?v={video_ids[0]}")
            return f"'{query}' ka pehla video play kar raha hoon."
        else:
            webbrowser.open(search_url)
            return f"Pehla video nahi mila, search results khol diye '{query}' ke liye."
    except Exception as e:
        webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
        return f"Direct play nahi ho saka, search results khol diye. ({e})"


def open_website(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"{url} khol raha hoon."


def open_folder(path: str) -> str:
    path = os.path.expanduser(path)
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return f"Folder khol diya: {path}"
    except Exception as e:
        return f"Folder nahi khul saka: {e}"


def take_note(content: str) -> str:
    timestamp = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    try:
        with open("jarvis_notes.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {content}\n")
        return "Note save kar diya."
    except Exception as e:
        return f"Note save nahi ho saka: {e}"


def read_notes() -> str:
    if not os.path.exists("jarvis_notes.txt"):
        return "Koi notes nahi hain abhi tak."
    with open("jarvis_notes.txt", "r", encoding="utf-8") as f:
        content = f.read().strip()
    return content if content else "Koi notes nahi hain abhi tak."


def list_running_apps() -> str:
    seen = set()
    apps = []
    for proc in psutil.process_iter(["name"]):
        name = proc.info["name"]
        if name and name not in seen and not name.lower().startswith(("system", "svchost", "runtime")):
            seen.add(name)
            apps.append(name)
    top = apps[:15]
    return "Chal rahe apps: " + ", ".join(top) if top else "Kuch nahi mila."


def kill_process(app_name: str) -> str:
    return close_app(app_name)


def battery_status() -> str:
    battery = psutil.sensors_battery()
    if not battery:
        return "Battery information available nahi hai."
    plugged = "charging hai" if battery.power_plugged else "charging nahi hai"
    return f"Battery {battery.percent}% hai aur {plugged}."


def empty_recycle_bin() -> str:
    system = platform.system()
    if system != "Windows":
        return "Ye feature sirf Windows par kaam karta hai."
    try:
        import winshell
        winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=True)
        return "Recycle bin khali kar diya."
    except Exception as e:
        return f"Recycle bin khali nahi ho saka: {e}"


def minimize_all_windows() -> str:
    try:
        if platform.system() == "Windows":
            pyautogui.hotkey("win", "d")
        else:
            pyautogui.hotkey("ctrl", "super", "d")
        return "Sab windows minimize kar diye."
    except Exception as e:
        return f"Minimize nahi ho saka: {e}"


def media_play_pause() -> str:
    try:
        pyautogui.press("playpause")
        return "Media play/pause kar diya."
    except Exception as e:
        return f"Media control nahi ho saka: {e}"


_ALLOWED_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    else:
        raise ValueError("Invalid expression")


def calculate(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return f"{expression} = {result}"
    except Exception:
        return "Ye expression samajh nahi aaya, sahi se bolo jaise '23 plus 17'."


def disk_space() -> str:
    usage = psutil.disk_usage("/")
    total_gb = usage.total / (1024 ** 3)
    used_gb = usage.used / (1024 ** 3)
    free_gb = usage.free / (1024 ** 3)
    return f"Total: {total_gb:.1f} GB, Used: {used_gb:.1f} GB, Free: {free_gb:.1f} GB."


def ip_address() -> str:
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return f"Aapka local IP address hai: {ip}"
    except Exception as e:
        return f"IP address nahi mil saka: {e}"


# ---- Alarm/Reminder feature ----
# NOTE: Ye alarms sirf tab tak kaam karte hain jab tak gui.py/server.py
# chal raha hai (process band hote hi alarms bhi khatam ho jate hain).
_active_timers = {}  # label -> threading.Timer object, cancel karne ke liye


def set_alarm(params: dict) -> str:
    """
    Alarm set karta hai. Do tarike se time diya ja sakta hai:
    - {"hour": 7, "minute": 30, "label": "wake up"}  -> specific time pe
    - {"in_minutes": 20, "label": "wake up"}          -> X minute baad
    """
    label = params.get("label", "Alarm")

    try:
        if "in_minutes" in params:
            delay_seconds = float(params["in_minutes"]) * 60
        elif "hour" in params and "minute" in params:
            now = datetime.now()
            target = now.replace(
                hour=int(params["hour"]), minute=int(params["minute"]),
                second=0, microsecond=0,
            )
            if target <= now:
                target += timedelta(days=1)  # aaj ka time nikal gaya, kal set karo
            delay_seconds = (target - now).total_seconds()
        else:
            return "Alarm ka time samajh nahi aaya. 'X minute baad' ya 'HH:MM baje' bolo."
    except (ValueError, TypeError):
        return "Alarm ka time sahi format mein nahi tha."

    def ring():
        for _ in range(3):
            speak(f"{label}! Alarm baj raha hai!")
        _active_timers.pop(label, None)

    # Agar isi naam ka alarm pehle se hai, purana cancel karke naya lagao
    if label in _active_timers:
        _active_timers[label].cancel()

    timer = threading.Timer(delay_seconds, ring)
    timer.daemon = True
    timer.start()
    _active_timers[label] = timer

    minutes = int(delay_seconds // 60)
    if minutes >= 60:
        hours = minutes // 60
        mins_left = minutes % 60
        return f"'{label}' alarm set kar diya, {hours} ghante {mins_left} minute baad bajega."
    elif minutes > 0:
        return f"'{label}' alarm set kar diya, {minutes} minute baad bajega."
    else:
        return f"'{label}' alarm set kar diya."


def cancel_alarm(params: dict) -> str:
    """Ek specific alarm, ya sab alarms cancel karta hai (agar label na diya ho)."""
    label = params.get("label")

    if label:
        if label in _active_timers:
            _active_timers[label].cancel()
            del _active_timers[label]
            return f"'{label}' alarm cancel kar diya."
        return f"'{label}' naam ka koi active alarm nahi mila."

    if not _active_timers:
        return "Koi active alarm nahi hai."

    count = len(_active_timers)
    for timer in _active_timers.values():
        timer.cancel()
    _active_timers.clear()
    return f"{count} alarm(s) cancel kar diye."


def list_alarms() -> str:
    if not _active_timers:
        return "Koi active alarm nahi hai."
    return "Active alarms: " + ", ".join(_active_timers.keys())


# ---- Persistent Memory / Facts feature ----
# Ye alarms ki tarah temporary nahi hai - jarvis_memory.json file mein disk pe
# save hota hai, isliye app band karke dobara kholne pe bhi Jarvis ko yaad rahega.
MEMORY_FILE = "jarvis_memory.json"
_memory_lock = threading.Lock()


def _load_memory() -> dict:
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_memory(data: dict):
    with _memory_lock:
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass


def remember_fact(params: dict) -> str:
    """Ek fact/preference ko naam (key) ke saath permanently yaad rakhta hai."""
    key = params.get("key", "").strip().lower()
    value = params.get("value", "").strip()
    if not key or not value:
        return "Kya yaad rakhna hai, aur kis naam se - dono batao."
    data = _load_memory()
    data[key] = value
    _save_memory(data)
    return f"Yaad rakh liya: {key} = {value}"


def recall_fact(params: dict) -> str:
    """Ek specific fact wapas batata hai."""
    key = params.get("key", "").strip().lower()
    data = _load_memory()
    if not key:
        return list_facts()
    if key in data:
        return f"{key}: {data[key]}"
    # exact key na mile to fuzzy match try karo (jaise "ghar ka address" vs "address")
    for k, v in data.items():
        if key in k or k in key:
            return f"{k}: {v}"
    return f"Mujhe '{key}' ke baare mein kuch yaad nahi hai."


def list_facts() -> str:
    data = _load_memory()
    if not data:
        return "Abhi tak mujhe kuch bhi yaad nahi karaya gaya hai."
    lines = [f"{k}: {v}" for k, v in data.items()]
    return "Mujhe ye sab yaad hai - " + "; ".join(lines)


def forget_fact(params: dict) -> str:
    """Ek fact ya sab facts memory se hata deta hai."""
    key = params.get("key", "").strip().lower()
    data = _load_memory()
    if not key:
        _save_memory({})
        return "Sab kuch bhula diya."
    if key in data:
        del data[key]
        _save_memory(data)
        return f"'{key}' bhula diya."
    return f"'{key}' naam ka kuch yaad hi nahi tha."


def get_memory_context() -> str:
    """brain.py isko system prompt mein inject karne ke liye call karta hai,
    taaki Jarvis ko bina bataye bhi user ke facts pata rahein."""
    data = _load_memory()
    if not data:
        return ""
    lines = [f"- {k}: {v}" for k, v in data.items()]
    return "User ke baare mein pehle se yaad rakhi gayi baatein:\n" + "\n".join(lines)


ACTION_MAP = {
    "open_app": lambda params: open_app(params.get("app_name", "")),
    "close_app": lambda params: close_app(params.get("app_name", "")),
    "search_file": lambda params: search_file(params.get("query", "")),
    "create_file": lambda params: create_file(params.get("path", ""), params.get("content", "")),
    "delete_file": lambda params: delete_file(params.get("path", "")),
    "system_info": lambda params: system_info(),
    "volume_control": lambda params: volume_control(params.get("level", 50)),
    "mute_volume": lambda params: mute_volume(),
    "brightness_control": lambda params: brightness_control(params.get("level", 70)),
    "screenshot": lambda params: screenshot(),
    "web_search": lambda params: web_search(params.get("query", "")),
    "shutdown": lambda params: shutdown(),
    "restart": lambda params: restart(),
    "clipboard_write": lambda params: clipboard_write(params.get("text", "")),
    "clipboard_read": lambda params: clipboard_read(),
    "lock_screen": lambda params: lock_screen(),
    "youtube_search": lambda params: youtube_search(params.get("query", "")),
    "youtube_search_and_play": lambda params: youtube_search_and_play(params.get("query", "")),
    "open_website": lambda params: open_website(params.get("url", "")),
    "open_folder": lambda params: open_folder(params.get("path", "")),
    "take_note": lambda params: take_note(params.get("content", "")),
    "read_notes": lambda params: read_notes(),
    "list_running_apps": lambda params: list_running_apps(),
    "kill_process": lambda params: kill_process(params.get("app_name", "")),
    "battery_status": lambda params: battery_status(),
    "empty_recycle_bin": lambda params: empty_recycle_bin(),
    "minimize_all_windows": lambda params: minimize_all_windows(),
    "media_play_pause": lambda params: media_play_pause(),
    "calculate": lambda params: calculate(params.get("expression", "")),
    "disk_space": lambda params: disk_space(),
    "ip_address": lambda params: ip_address(),
    "set_alarm": lambda params: set_alarm(params),
    "cancel_alarm": lambda params: cancel_alarm(params),
    "list_alarms": lambda params: list_alarms(),
    "remember_fact": lambda params: remember_fact(params),
    "recall_fact": lambda params: recall_fact(params),
    "list_facts": lambda params: list_facts(),
    "forget_fact": lambda params: forget_fact(params),
    "open_camera": lambda params: open_camera(),
    "take_photo": lambda params: take_photo(params),
    "rename_file": lambda params: rename_file(params),
    "edit_file": lambda params: edit_file(params),
    "send_message": lambda params: send_message(params),
}
