"""
actions.py
Yahan wo saare functions hain jo LLM ke decide kiye action ko actually execute karte hain.
Naya command add karna ho to bas yahan naya function likho aur ACTION_MAP mein register karo.
"""

import os
import re
import ast
import json
import logging
import operator
import subprocess
import platform
import glob
import socket
import threading
import time
import struct
from urllib.parse import quote
import psutil
import pyautogui
import pyperclip
import webbrowser
import requests
from datetime import datetime, timedelta
import config
from speech import speak


def open_app(app_name: str) -> str:
    system = platform.system()
    name_key = app_name.strip().lower()

    if system == "Windows":
        # 1) Kuch apps (Telegram, WhatsApp, Spotify, Discord) apna khud ka URI
        # protocol register karte hain (install method - Store/installer/
        # portable - kuch bhi ho, protocol hamesha kaam karta hai). Ye path
        # guess karne se zyada reliable hai isliye pehle isko try karo.
        protocol = APP_PROTOCOLS.get(name_key)
        if protocol:
            try:
                os.startfile(protocol)
                return f"{app_name} khol diya."
            except Exception:
                pass

        # 2) Kuch apps (Telegram, WhatsApp, Spotify, Discord, VS Code) Windows mein
        # "registered" nahi hote, isliye os.startfile(app_name) fail hota hai -
        # unke common install locations yahan try karo (version-folder wildcards
        # ke saath, kyunki Discord/WhatsApp jaisi apps folder naam mein version
        # number rakhte hain).
        for raw_path in COMMON_APP_PATHS.get(name_key, []):
            matches = glob.glob(os.path.expandvars(raw_path))
            if matches:
                try:
                    subprocess.Popen([matches[0]])
                    return f"{app_name} khol diya."
                except Exception:
                    pass

        # 3) Start Menu shortcuts mein dhundo - zyadatar installed apps yahan
        # milte hain, chahe registered ho ya na ho.
        shortcut = _find_start_menu_shortcut(app_name)
        if shortcut:
            try:
                os.startfile(shortcut)
                return f"{app_name} khol diya."
            except Exception:
                pass

    # 4) purana fallback - registered app names (chrome, notepad, calc, mspaint, etc.)
    try:
        if system == "Windows":
            os.startfile(app_name)
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
        else:
            subprocess.Popen([app_name])
        return f"{app_name} khol diya."
    except Exception:
        # 5) Bahut baar log "youtube kholo", "gmail kholo", "instagram kholo"
        # jaisa bolte hain jabki ye apps nahi, websites hain - app na milne par
        # in known websites ke liye seedha browser mein khol dete hain.
        website_url = KNOWN_WEBSITES.get(name_key)
        if website_url:
            webbrowser.open(website_url)
            return f"{app_name} ek website hai, browser mein khol diya."
        return f"{app_name} nahi khul saka: koi installed app ya jaana-pehchana naam nahi mila. App installed hai confirm karo."


# Apps jo apna khud ka URI protocol register karte hain - install location
# (Store / official installer / portable) se independent, isliye path-guessing
# se zyada reliable hai.
APP_PROTOCOLS = {
    "telegram": "tg://",
    "whatsapp": "whatsapp://",
    "spotify": "spotify:",
    "discord": "discord://",
    "skype": "skype:",
    "steam": "steam://open/main",
    "slack": "slack://open",
    "zoom": "zoommtg://",
}


KNOWN_WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://www.twitter.com",
    "x": "https://www.x.com",
    "whatsapp web": "https://web.whatsapp.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.in",
    "linkedin": "https://www.linkedin.com",
    "github": "https://www.github.com",
    "chatgpt": "https://chat.openai.com",
    "maps": "https://maps.google.com",
    "drive": "https://drive.google.com",
    "reddit": "https://www.reddit.com",
    "flipkart": "https://www.flipkart.com",
}


COMMON_APP_PATHS = {
    "telegram": [r"%AppData%\Telegram Desktop\Telegram.exe"],
    "whatsapp": [r"%LocalAppData%\WhatsApp\WhatsApp.exe", r"%LocalAppData%\WhatsApp\app-*\WhatsApp.exe"],
    "spotify": [r"%AppData%\Spotify\Spotify.exe"],
    "discord": [r"%LocalAppData%\Discord\app-*\Discord.exe"],
    "vscode": [r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe"],
    "vs code": [r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe"],
    "code": [r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe"],
    "steam": [r"C:\Program Files (x86)\Steam\Steam.exe"],
}


def _find_start_menu_shortcut(app_name: str):
    search_dirs = [
        os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("AppData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
    ]
    for base in search_dirs:
        if not base or not os.path.isdir(base):
            continue
        matches = glob.glob(os.path.join(base, "**", f"*{app_name}*.lnk"), recursive=True)
        if matches:
            return matches[0]
    return None


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


def _telegram_contacts_load() -> dict:
    """telegram_contacts.json se saare saved contacts padhta hai.
    Format: {"chat_id": {"name": "...", "username": "...", "first_name": "..."}}"""
    path = config.TELEGRAM_CONTACTS_FILE
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _telegram_contacts_save(contacts: dict) -> None:
    path = config.TELEGRAM_CONTACTS_FILE
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(contacts, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _telegram_contacts_last_update_id() -> int:
    contacts = _telegram_contacts_load()
    return contacts.get("_meta", {}).get("last_update_id", 0)


def sync_telegram_contacts(params: dict = None) -> str:
    """Telegram se naye messages check karke jinhon ne bhi bot ko kabhi
    message kiya hai (jaise /start) unka naam+username+chat_id
    telegram_contacts.json mein save kar leta hai. Isse baad mein sirf
    naam/username bolke unko message bheja ja sakta hai, chat_id
    dobara nahi doondhni padti.
    Ye function bar bar (background poller se) ya manually call ho sakta hai."""
    if not config.TELEGRAM_BOT_TOKEN:
        return "Telegram set up nahi hai - .env mein TELEGRAM_BOT_TOKEN daalo."

    contacts = _telegram_contacts_load()
    last_update_id = contacts.get("_meta", {}).get("last_update_id", 0)

    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
        resp = requests.get(
            url, params={"offset": last_update_id + 1, "timeout": 0}, timeout=15
        )
        if not resp.ok:
            return f"Telegram contacts sync mein error aaya: {resp.text}"
        data = resp.json()
    except Exception as e:
        return f"Telegram contacts sync mein error aaya: {e}"

    new_people = []
    max_update_id = last_update_id
    for update in data.get("result", []):
        max_update_id = max(max_update_id, update.get("update_id", 0))
        msg = update.get("message") or update.get("channel_post")
        if not msg:
            continue
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id", ""))
        if not chat_id:
            continue
        username = (chat.get("username") or "").lstrip("@")
        first_name = chat.get("first_name", "") or chat.get("title", "")
        last_name = chat.get("last_name", "")
        display_name = (first_name + " " + last_name).strip() or username or chat_id

        existing = contacts.get(chat_id, {})
        contacts[chat_id] = {
            "name": existing.get("name", display_name),
            "username": username,
            "first_name": first_name,
            "chat_id": chat_id,
        }
        if chat_id not in contacts or existing != contacts[chat_id]:
            new_people.append(display_name)

    contacts["_meta"] = {"last_update_id": max_update_id}
    _telegram_contacts_save(contacts)

    if new_people:
        return f"Naye contacts save hue: {', '.join(new_people)}"
    return "Koi naya contact nahi mila."


def _telegram_resolve_contact(name_or_username: str) -> str:
    """Diye gaye naam ya @username se saved contacts mein dhoond kar
    chat_id return karta hai. Nahi mile to empty string."""
    if not name_or_username:
        return ""
    query = name_or_username.strip().lstrip("@").lower()
    contacts = _telegram_contacts_load()
    for chat_id, info in contacts.items():
        if chat_id == "_meta":
            continue
        if query == str(info.get("username", "")).lower():
            return chat_id
        if query == str(info.get("name", "")).lower():
            return chat_id
        if query in str(info.get("name", "")).lower().split():
            return chat_id
    return ""


def list_telegram_contacts(params: dict = None) -> str:
    """Ab tak jitne bhi logon ne bot ko message kiya hai (aur save ho
    chuke hain) unki list dikhata hai."""
    contacts = _telegram_contacts_load()
    names = [
        info.get("name") or info.get("username") or chat_id
        for chat_id, info in contacts.items()
        if chat_id != "_meta"
    ]
    if not names:
        return (
            "Abhi tak koi contact save nahi hua. Jisko bhi msg karna hai "
            "usse bot ko ek baar /start karna hoga."
        )
    return "Saved contacts: " + ", ".join(names)


def _telegram_send_one(chat_id: str, message: str) -> tuple:
    """Ek chat_id ko message bhejta hai. Returns (success: bool, detail: str)."""
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=10)
        if resp.ok:
            return True, ""
        return False, resp.text
    except Exception as e:
        return False, str(e)


def send_telegram_message(params: dict) -> str:
    """Telegram Bot API se message bhejta hai. Setup ke liye .env mein:
    TELEGRAM_BOT_TOKEN=<BotFather se mila token>
    TELEGRAM_CHAT_ID=<default chat id, agar khaas kisi ko na bola ho>

    params options:
      - message: kya bhejna hai (required)
      - chat_id: seedha kisi chat id pe bhejna ho to
      - to: naam ya @username (contacts.json se auto-resolve hoga)
      - to_all: true -> saare saved contacts ko bhej dega (broadcast)
      - exclude: ["Raj", "Priya"] -> to_all ke sath, in logon ko chhodkar sabko bhejega
    """
    message = params.get("message", "")
    if not message:
        return "Kya message bhejna hai wo batao."
    if not config.TELEGRAM_BOT_TOKEN:
        return (
            "Telegram set up nahi hai. .env mein TELEGRAM_BOT_TOKEN aur "
            "TELEGRAM_CHAT_ID daalo (BotFather se bot banao)."
        )

    to_all = params.get("to_all", False)
    exclude = [e.strip().lower() for e in params.get("exclude", []) if e]

    # --- Broadcast: sabko (ya sabko-minus-exclude) bhejo ---
    if to_all:
        contacts = _telegram_contacts_load()
        targets = [
            (chat_id, info) for chat_id, info in contacts.items() if chat_id != "_meta"
        ]
        if not targets:
            return (
                "Koi saved contact nahi mila. Pehle logon ko bot ko /start "
                "karwao, phir 'contacts sync karo' bolo."
            )
        sent, skipped, failed = [], [], []
        for chat_id, info in targets:
            display = info.get("name") or info.get("username") or chat_id
            uname = str(info.get("username", "")).lower()
            if display.lower() in exclude or uname in exclude:
                skipped.append(display)
                continue
            ok, err = _telegram_send_one(chat_id, message)
            (sent if ok else failed).append(display)
        result = f"Bhej diya {len(sent)} logon ko: {', '.join(sent) if sent else '-'}."
        if skipped:
            result += f" Chhoda: {', '.join(skipped)}."
        if failed:
            result += f" Fail hua: {', '.join(failed)}."
        return result

    # --- Naam/username se resolve karke bhejo ---
    chat_id = params.get("chat_id", "")
    if not chat_id and params.get("to"):
        chat_id = _telegram_resolve_contact(params["to"])
        if not chat_id:
            return (
                f"'{params['to']}' naam ka koi saved contact nahi mila. "
                "Usse pehle bot ko /start karna hoga, phir 'contacts sync karo' bolo."
            )

    # --- Fallback: .env wali default id ---
    if not chat_id:
        chat_id = config.TELEGRAM_CHAT_ID

    if not chat_id:
        return "Kisko bhejna hai wo batao (naam bolo ya .env mein TELEGRAM_CHAT_ID set karo)."

    ok, err = _telegram_send_one(chat_id, message)
    if ok:
        return "Telegram pe message bhej diya."
    if "can't send messages to the bot" in err:
        return (
            "Ye error aa raha hai kyunki ye chat_id bot ki apni hai. Sahi "
            "user ki chat_id chahiye - usse pehle bot ko /start karna hoga."
        )
    return f"Telegram message bhejne mein error aaya: {err}"


def send_telegram_photo(params: dict) -> str:
    """Ek image file Telegram pe bhejta hai (jaise screenshot ya photo).
    params.to mein naam/@username bhi de sakte ho (contacts.json se resolve hoga)."""
    path = params.get("path", "")
    caption = params.get("caption", "")
    chat_id = params.get("chat_id", "")
    if not chat_id and params.get("to"):
        chat_id = _telegram_resolve_contact(params["to"])
        if not chat_id:
            return f"'{params['to']}' naam ka koi saved contact nahi mila."
    if not chat_id:
        chat_id = config.TELEGRAM_CHAT_ID

    if not path or not os.path.exists(path):
        return f"'{path}' file nahi mili."
    if not config.TELEGRAM_BOT_TOKEN or not chat_id:
        return "Telegram set up nahi hai - .env mein TELEGRAM_BOT_TOKEN aur TELEGRAM_CHAT_ID daalo."

    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
        with open(path, "rb") as f:
            resp = requests.post(
                url, data={"chat_id": chat_id, "caption": caption}, files={"photo": f}, timeout=20
            )
        if resp.ok:
            return "Telegram pe photo bhej diya."
        return f"Photo bhejne mein error aaya: {resp.text}"
    except Exception as e:
        return f"Photo bhejne mein error aaya: {e}"


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


def _with_com_initialized(fn):
    """pycaw COM objects use karta hai jo har thread mein alag se
    CoInitialize maangte hain. GUI mein voice loop aur commands ek background
    thread mein chalte hain (main thread nahi), isliye bina isके pycaw
    'CoInitialize has not been called' error deta tha - is wrapper se wo fix
    ho jata hai (already-initialized thread pe bhi safe hai, error ignore hota hai)."""
    import pythoncom

    try:
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        return fn()
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def volume_control(level: int) -> str:
    level = max(0, min(100, int(level)))
    system = platform.system()
    try:
        if system == "Windows":
            def _set():
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(level / 100, None)

            _with_com_initialized(_set)
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


def _get_current_volume_percent() -> int:
    def _get():
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return round(volume.GetMasterVolumeLevelScalar() * 100)

    return _with_com_initialized(_get)


def volume_up(params: dict) -> str:
    step = int(params.get("step", 10))
    try:
        current = _get_current_volume_percent()
    except Exception:
        current = 50
    return volume_control(current + step)


def volume_down(params: dict) -> str:
    step = int(params.get("step", 10))
    try:
        current = _get_current_volume_percent()
    except Exception:
        current = 50
    return volume_control(current - step)


def get_time() -> str:
    return f"Abhi time hai: {datetime.now().strftime('%I:%M %p')}"


def get_date() -> str:
    return f"Aaj ki date hai: {datetime.now().strftime('%d %B %Y, %A')}"


def type_text(params: dict) -> str:
    """Jahan bhi cursor active hai (Notepad, chat box, etc.) wahan text type karta hai.
    pyautogui.write() sirf ASCII (English) characters simulate kar sakta hai -
    Hindi/Devanagari ya koi bhi non-English text uससे type nahi hota. Isliye
    clipboard + Ctrl+V (paste) method use karte hain, jo har language/script
    ke saath kaam karta hai."""
    text = params.get("text", "")
    if not text:
        return "Kya type karna hai, batao."
    try:
        text.encode("ascii")
        pyautogui.write(text, interval=0.02)  # pure ASCII ho to seedha type karo (undo-friendly)
    except UnicodeEncodeError:
        previous_clipboard = pyperclip.paste()
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)
        try:
            pyperclip.copy(previous_clipboard)  # user ka pehle wala clipboard wapas rakh do
        except Exception:
            pass
    return "Type kar diya."


def copy_file(params: dict) -> str:
    import shutil
    src = params.get("source", "")
    dst = params.get("destination", "")
    if not src or not dst:
        return "Kis file ko kahan copy karna hai, dono path batao."
    try:
        shutil.copy(src, dst)
        return f"'{src}' ko '{dst}' mein copy kar diya."
    except Exception as e:
        return f"Copy nahi ho saka: {e}"


def move_file(params: dict) -> str:
    import shutil
    src = params.get("source", "")
    dst = params.get("destination", "")
    if not src or not dst:
        return "Kis file ko kahan move karna hai, dono path batao."
    try:
        shutil.move(src, dst)
        return f"'{src}' ko '{dst}' mein move kar diya."
    except Exception as e:
        return f"Move nahi ho saka: {e}"


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


def cancel_shutdown(params: dict = None) -> str:
    """Agar galti se shutdown/restart bol diya gaya tha, uska OS-level timer
    (5 second wala) cancel kar deta hai - GUI ke STOP button se automatically
    call hota hai. Agar koi shutdown/restart chalu hi nahi tha, ye safe/no-op
    hai (koi error nahi dega)."""
    system = platform.system()
    try:
        if system == "Windows":
            os.system("shutdown /a")
        else:
            os.system("shutdown -c")
        return "Shutdown/restart cancel kar diya (agar chalu tha to)."
    except Exception:
        return "Kuch cancel karne wala nahi mila."


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
    url = f"https://www.youtube.com/results?search_query={query}"
    if _youtube_state["active"] and _navigate_existing_browser(url):
        return f"Usi tab mein '{query}' search kar raha hoon."
    webbrowser.open(url)
    _youtube_state["active"] = True
    return f"YouTube pe '{query}' search kar raha hoon."


# Jab pehli baar YouTube khulta hai, iska flag True ho jata hai. Agli baar
# jab koi naya gaana/video maanga jaye, naya tab kholne ke bajaye isi flag
# ko check karke maujooda YouTube tab dhoondh ke usi mein navigate karte hain.
_youtube_state = {"active": False}


def _navigate_existing_browser(url: str) -> bool:
    """Agar YouTube ka tab pehle se khula hai, naya tab kholne ke bajaye
    usi browser window ko focus karke address bar (Ctrl+L) se naya URL
    navigate karta hai. Sirf Windows pe kaam karta hai (pywin32 chahiye).
    Return True = successfully usi tab mein navigate ho gaya.
    Return False = tab nahi mila, caller ko naya tab kholna chahiye."""
    if platform.system() != "Windows":
        return False
    try:
        import win32gui
        import win32con

        target_hwnd = None

        def _enum_handler(hwnd, _):
            nonlocal target_hwnd
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if "YouTube" in title and any(
                b in title for b in ("Chrome", "Edge", "Firefox", "Brave", "Opera")
            ):
                target_hwnd = hwnd

        win32gui.EnumWindows(_enum_handler, None)
        if not target_hwnd:
            return False

        win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(target_hwnd)
        time.sleep(0.4)
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.2)
        pyautogui.typewrite(url, interval=0.01)
        pyautogui.press("enter")
        return True
    except Exception:
        return False


def youtube_search_and_play(query: str) -> str:
    try:
        search_url = f"https://www.youtube.com/results?search_query={query}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(search_url, headers=headers, timeout=10)
        video_ids = re.findall(r"watch\?v=(\S{11})", response.text)
        if not video_ids:
            video_ids = re.findall(r'"videoId":"(.{11})"', response.text)

        target_url = f"https://www.youtube.com/watch?v={video_ids[0]}" if video_ids else search_url

        if _youtube_state["active"] and _navigate_existing_browser(target_url):
            if video_ids:
                return f"Pehla gaana band karke '{query}' play kar raha hoon usi tab mein."
            return f"Usi tab mein '{query}' ke search results khol diye."

        webbrowser.open(target_url)
        _youtube_state["active"] = True
        if video_ids:
            return f"'{query}' ka pehla video play kar raha hoon."
        return f"Pehla video nahi mila, search results khol diye '{query}' ke liye."
    except Exception as e:
        webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
        _youtube_state["active"] = True
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


# =====================================================================
# ADVANCED FEATURES
# =====================================================================

# ---- 1. KEYBOARD ACTIONS ----
_KEY_ALIASES = {
    "win": "win", "windows": "win", "super": "win",
    "ctrl": "ctrl", "control": "ctrl",
    "esc": "esc", "escape": "esc",
    "del": "delete", "delete": "delete",
    "enter": "enter", "return": "enter",
    "space": "space", "spacebar": "space",
    "tab": "tab", "backspace": "backspace",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "alt": "alt", "shift": "shift",
}


def _normalize_key(k: str) -> str:
    k = k.strip().lower()
    return _KEY_ALIASES.get(k, k)


def press_key(params: dict) -> str:
    """Special key ya combo press karta hai.
    Single key: {"key": "enter"}, {"key": "f5"}, {"key": "up"}
    Combo: {"key": "ctrl+c"}, {"key": "alt+f4"}, {"key": "win+d"}"""
    key = params.get("key", "").strip().lower()
    if not key:
        return "Kaunsi key press karni hai, batao."
    try:
        if "+" in key:
            keys = [_normalize_key(k) for k in key.split("+")]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(_normalize_key(key))
        return f"'{key}' key press kar di."
    except Exception as e:
        return f"Key press nahi ho saki: {e}"


# ---- 2. MOUSE ACTIONS ----
def mouse_click(params: dict) -> str:
    x, y = params.get("x"), params.get("y")
    try:
        if x is not None and y is not None:
            pyautogui.click(int(x), int(y))
            return f"({x}, {y}) par click kar diya."
        pyautogui.click()
        return "Click kar diya."
    except Exception as e:
        return f"Click nahi ho saka: {e}"


def mouse_double_click(params: dict) -> str:
    x, y = params.get("x"), params.get("y")
    try:
        if x is not None and y is not None:
            pyautogui.doubleClick(int(x), int(y))
        else:
            pyautogui.doubleClick()
        return "Double click kar diya."
    except Exception as e:
        return f"Double click nahi ho saka: {e}"


def mouse_right_click(params: dict) -> str:
    x, y = params.get("x"), params.get("y")
    try:
        if x is not None and y is not None:
            pyautogui.rightClick(int(x), int(y))
        else:
            pyautogui.rightClick()
        return "Right click kar diya."
    except Exception as e:
        return f"Right click nahi ho saka: {e}"


def drag_and_drop(params: dict) -> str:
    """{"from_x":100,"from_y":200,"to_x":500,"to_y":600,"duration":0.5}"""
    try:
        fx, fy = int(params.get("from_x")), int(params.get("from_y"))
        tx, ty = int(params.get("to_x")), int(params.get("to_y"))
        duration = float(params.get("duration", 0.5))
        pyautogui.moveTo(fx, fy)
        pyautogui.dragTo(tx, ty, duration=duration, button="left")
        return f"({fx},{fy}) se ({tx},{ty}) tak drag kar diya."
    except Exception as e:
        return f"Drag and drop nahi ho saka: {e}"


def mouse_scroll(params: dict) -> str:
    direction = params.get("direction", "down").lower()
    amount = int(params.get("amount", 10))
    try:
        pyautogui.scroll(amount if direction == "up" else -amount)
        return f"{direction} scroll kar diya."
    except Exception as e:
        return f"Scroll nahi ho saka: {e}"


# ---- 3. WINDOW MANAGEMENT ----
def _find_window(title: str):
    import pygetwindow as gw
    matches = gw.getWindowsWithTitle(title)
    return matches[0] if matches else None


def close_window(params: dict) -> str:
    title = params.get("title", "")
    try:
        win = _find_window(title)
        if not win:
            return f"'{title}' naam ki koi window nahi mili."
        win.close()
        return f"'{title}' window band kar di."
    except Exception as e:
        return f"Window band nahi ho saki: {e}"


def minimize_window(params: dict) -> str:
    title = params.get("title", "")
    try:
        win = _find_window(title)
        if not win:
            return f"'{title}' naam ki koi window nahi mili."
        win.minimize()
        return f"'{title}' minimize kar di."
    except Exception as e:
        return f"Minimize nahi ho saka: {e}"


def maximize_window(params: dict) -> str:
    title = params.get("title", "")
    try:
        win = _find_window(title)
        if not win:
            return f"'{title}' naam ki koi window nahi mili."
        win.maximize()
        return f"'{title}' maximize kar di."
    except Exception as e:
        return f"Maximize nahi ho saka: {e}"


def focus_window(params: dict) -> str:
    title = params.get("title", "")
    try:
        win = _find_window(title)
        if not win:
            return f"'{title}' naam ki koi window nahi mili."
        win.restore()
        win.activate()
        return f"'{title}' pe focus le aaya."
    except Exception as e:
        return f"Focus nahi ho saka: {e}"


# ---- 4. CLIPBOARD ADVANCED ----
def clipboard_copy_image(params: dict) -> str:
    """Ek image file ko clipboard mein daalta hai (jaise Ctrl+C kiya ho image pe)."""
    path = params.get("path", "")
    if not path or not os.path.exists(path):
        return f"'{path}' image nahi mili."
    system = platform.system()
    if system != "Windows":
        return "Image clipboard copy abhi sirf Windows par supported hai."
    try:
        import io
        from PIL import Image
        import win32clipboard

        image = Image.open(path)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # BMP header ke 14 bytes hata do (DIB format ke liye)
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        return f"'{path}' image clipboard mein copy kar di."
    except Exception as e:
        return f"Image copy nahi ho saki: {e}"


def clipboard_copy_file(params: dict) -> str:
    """File ko clipboard mein 'file object' ki tarah copy karta hai - jahan
    bhi paste karo (Explorer, email, chat), asli file paste hogi, sirf naam
    text nahi."""
    path = params.get("path", "")
    if not path or not os.path.exists(path):
        return f"'{path}' file nahi mili."
    system = platform.system()
    if system != "Windows":
        pyperclip.copy(os.path.abspath(path))
        return f"'{path}' ka path clipboard mein copy kar diya (text ke roop mein)."
    try:
        import win32clipboard
        import win32con

        abs_path = os.path.abspath(path)
        data = (abs_path + "\0\0").encode("utf-16-le")
        # DROPFILES struct: DWORD pFiles; POINT pt; BOOL fNC; BOOL fWide;
        dropfiles = struct.pack("<5i", 20, 0, 0, 0, 1)
        stream = dropfiles + data

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_HDROP, stream)
        win32clipboard.CloseClipboard()
        return f"'{abs_path}' file clipboard mein copy kar di, ab kahin bhi paste kar sakte ho."
    except Exception as e:
        pyperclip.copy(os.path.abspath(path))
        return f"File object copy nahi ho saka ({e}), path text ke roop mein copy kar diya."


# ---- 5. SYSTEM ACTIONS ----
def wifi_control(params: dict) -> str:
    state = params.get("state", "on").lower()
    turn_on = state in ("on", "enable", "true", "1")
    system = platform.system()
    try:
        if system == "Windows":
            admin_state = "enabled" if turn_on else "disabled"
            result = subprocess.run(
                ["netsh", "interface", "set", "interface", "Wi-Fi", f"admin={admin_state}"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return f"WiFi {'on' if turn_on else 'off'} kar diya."
            return f"WiFi control ke liye shayad admin rights chahiye: {result.stderr.strip()}"
        elif system == "Darwin":
            os.system(f"networksetup -setairportpower en0 {'on' if turn_on else 'off'}")
            return f"WiFi {'on' if turn_on else 'off'} kar diya."
        else:
            os.system(f"nmcli radio wifi {'on' if turn_on else 'off'}")
            return f"WiFi {'on' if turn_on else 'off'} kar diya."
    except Exception as e:
        return f"WiFi control nahi ho saka: {e}"


def bluetooth_control(params: dict) -> str:
    state = params.get("state", "on").lower()
    turn_on = state in ("on", "enable", "true", "1")
    system = platform.system()
    try:
        if system == "Windows":
            # Windows ke built-in "Windows.Devices.Radios" WinRT API se
            # Bluetooth radio ko seedha on/off kiya ja sakta hai - bina
            # settings page khole. WinRT ke async operations (IAsyncOperation)
            # PowerShell mein seedha .GetAwaiter() support nahi karte - isliye
            # System.Runtime.WindowsRuntime ke "AsTask" bridge se .NET Task
            # mein convert karke wait karna padta hai (Await helper neeche).
            ps_state = "On" if turn_on else "Off"
            ps_script = (
                "[Windows.Devices.Radios.Radio,Windows.System.Devices,"
                "ContentType=WindowsRuntime] | Out-Null; "
                "[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,"
                "ContentType=WindowsRuntime] | Out-Null; "
                "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
                "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
                "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
                "function Await($WinRtTask, $ResultType) { "
                "$asTask = $asTaskGeneric.MakeGenericMethod($ResultType); "
                "$netTask = $asTask.Invoke($null, @($WinRtTask)); "
                "$netTask.Wait(-1) | Out-Null; return $netTask.Result }; "
                "$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) "
                "([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]); "
                "$bt = $radios | Where-Object { $_.Kind -eq 'Bluetooth' }; "
                "if ($bt) { "
                f"Await ($bt.SetStateAsync([Windows.Devices.Radios.RadioState]::{ps_state})) "
                "([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null; exit 0 "
                "} else { exit 2 }"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return f"Bluetooth {'on' if turn_on else 'off'} kar diya."
            # Fallback - agar WinRT toggle kisi wajah se fail ho jaaye
            # (purana Windows build, driver issue, koi bluetooth radio hi
            # na mila, etc.) to settings khol do aur error bhi log karo
            # taaki debug ho sake.
            logging.error(
                f"bluetooth_control WinRT toggle fail (code {result.returncode}): "
                f"{result.stderr.strip()[:300]}"
            )
            os.startfile("ms-settings:bluetooth")
            return (
                "Bluetooth seedha toggle nahi kar paya, isliye settings khol di - "
                "waha se ek click mein on/off kar do."
            )
        elif system == "Darwin":
            os.system(f"blueutil --power {'1' if turn_on else '0'}")
            return f"Bluetooth {'on' if turn_on else 'off'} kar diya (blueutil installed hona chahiye)."
        else:
            os.system(f"bluetoothctl power {'on' if turn_on else 'off'}")
            return f"Bluetooth {'on' if turn_on else 'off'} kar diya."
    except Exception as e:
        return f"Bluetooth control nahi ho saka: {e}"


def night_mode(params: dict) -> str:
    """Dark/light mode toggle karta hai. {"state": "on"/"off"/"toggle"}"""
    state = params.get("state", "toggle").lower()
    system = platform.system()
    try:
        if system == "Windows":
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if state == "toggle":
                current, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                new_val = 0 if current == 1 else 1
            else:
                new_val = 0 if state in ("on", "dark", "enable") else 1
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new_val)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_val)
            winreg.CloseKey(key)
            return "Dark mode on kar diya." if new_val == 0 else "Light mode on kar diya."
        elif system == "Darwin":
            script = (
                'tell application "System Events" to tell appearance preferences '
                "to set dark mode to not dark mode"
            )
            os.system(f"osascript -e '{script}'")
            return "Dark/Light mode toggle kar diya."
        else:
            return "Night mode toggle is OS par directly supported nahi hai."
    except Exception as e:
        return f"Night mode set nahi ho saka: {e}"


def sleep_mode(params: dict = None) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        elif system == "Darwin":
            os.system("pmset sleepnow")
        else:
            os.system("systemctl suspend")
        return "Computer ko sleep mein bhej diya."
    except Exception as e:
        return f"Sleep mode set nahi ho saka: {e}"


def logout(params: dict = None) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            os.system("shutdown /l")
        elif system == "Darwin":
            os.system('osascript -e \'tell application "System Events" to log out\'')
        else:
            os.system("gnome-session-quit --logout --no-prompt")
        return "Logout kar rahe hain."
    except Exception as e:
        return f"Logout nahi ho saka: {e}"


# ---- 6. FILE/APP ----
def list_files(params: dict) -> str:
    path = os.path.expanduser(params.get("path", "."))
    try:
        entries = os.listdir(path)
        if not entries:
            return f"'{path}' folder khaali hai."
        top = entries[:30]
        more = f" (+{len(entries) - 30} aur)" if len(entries) > 30 else ""
        return f"'{path}' mein hai:\n" + "\n".join(top) + more
    except Exception as e:
        return f"Files list nahi ho saki: {e}"


def open_recent_file(params: dict) -> str:
    system = platform.system()
    if system != "Windows":
        return "Recent files list abhi sirf Windows par supported hai."
    recent_dir = os.path.join(os.environ.get("AppData", ""), "Microsoft", "Windows", "Recent")
    query = params.get("query", "")
    try:
        files = sorted(glob.glob(os.path.join(recent_dir, "*.lnk")), key=os.path.getmtime, reverse=True)
        if query:
            files = [f for f in files if query.lower() in os.path.basename(f).lower()]
        if not files:
            return "Koi matching recent file nahi mili."
        target = files[0]
        os.startfile(target)
        return f"Recent file khol di: {os.path.splitext(os.path.basename(target))[0]}"
    except Exception as e:
        return f"Recent file nahi khul saki: {e}"


def uninstall_app(params: dict) -> str:
    """Safety ke liye directly uninstall nahi karte - Apps & Features page khol
    dete hain jahan se user khud confirm karke uninstall kare."""
    app_name = params.get("app_name", "")
    system = platform.system()
    try:
        if system == "Windows":
            os.system("start ms-settings:appsfeatures")
            return f"Apps & Features khol di hai - '{app_name}' dhoondh ke uninstall kar do wahan se."
        elif system == "Darwin":
            subprocess.Popen(["open", "/Applications"])
            return f"Applications folder khol di - '{app_name}' ko Trash mein daal do."
        else:
            return f"'{app_name}' uninstall karne ke liye apna package manager use karo, jaise: sudo apt remove {app_name}"
    except Exception as e:
        return f"Uninstall page nahi khul saka: {e}"


def install_app(params: dict) -> str:
    app_name = params.get("app_name", "")
    if not app_name:
        return "Kaunsa app install karna hai, naam batao."
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["winget", "install", "-e", "--accept-source-agreements", "--accept-package-agreements", app_name])
            return f"'{app_name}' install karna shuru kar diya (winget) - terminal mein progress dikhega."
        elif system == "Darwin":
            subprocess.Popen(["brew", "install", app_name])
            return f"'{app_name}' install ho raha hai (Homebrew se)."
        else:
            return f"'{app_name}' install karne ke liye: sudo apt install {app_name}"
    except FileNotFoundError:
        return "Winget/Homebrew system mein nahi mila - pehle wo install karo."
    except Exception as e:
        return f"Install nahi ho saka: {e}"


# ---- 7. COMMUNICATION ----
def send_email(params: dict) -> str:
    """Email bhejta hai (.env mein SMTP_EMAIL, SMTP_PASSWORD - Gmail App
    Password - set hona chahiye)."""
    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")
    if not to or not body:
        return "Kisko aur kya email bhejni hai, dono batao."
    if not config.SMTP_EMAIL or not config.SMTP_PASSWORD:
        return "Email set up nahi hai - .env mein SMTP_EMAIL aur SMTP_PASSWORD (Gmail App Password) daalo."
    try:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body)
        msg["Subject"] = subject or "(No subject)"
        msg["From"] = config.SMTP_EMAIL
        msg["To"] = to
        with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
            server.send_message(msg)
        return f"{to} ko email bhej di."
    except Exception as e:
        return f"Email bhejne mein error aaya: {e}"


def make_call(params: dict) -> str:
    """tel: link kholta hai - kaam karega agar koi calling app (Phone Link,
    Skype) us protocol ke liye registered hai."""
    number = params.get("number", "")
    if not number:
        return "Kisko call karni hai, number batao."
    try:
        webbrowser.open(f"tel:{number}")
        return f"{number} ko call lagane ki koshish ki (calling app registered hona chahiye)."
    except Exception as e:
        return f"Call nahi lag saki: {e}"


def video_call(params: dict) -> str:
    """Naya Google Meet room khol deta hai video call ke liye."""
    contact = params.get("contact", "")
    try:
        webbrowser.open("https://meet.google.com/new")
        extra = f" - link {contact} ko bhej do." if contact else ""
        return f"Google Meet pe naya video call room khol diya.{extra}"
    except Exception as e:
        return f"Video call start nahi ho saka: {e}"


# ---- 8. PRODUCTIVITY ----
def calendar_event(params: dict) -> str:
    """Google Calendar mein event create page kholta hai, pehle se bhara hua.
    {"title": "Meeting", "date": "2026-09-10", "time": "15:00"}"""
    title = params.get("title", "Event")
    date_str = params.get("date", "")
    time_str = params.get("time", "")
    try:
        if date_str and time_str:
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(hours=1)
            dates = f"{start_dt.strftime('%Y%m%dT%H%M%S')}/{end_dt.strftime('%Y%m%dT%H%M%S')}"
            url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={quote(title)}&dates={dates}"
        else:
            url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={quote(title)}"
        webbrowser.open(url)
        return f"'{title}' event ke liye Google Calendar khol diya."
    except Exception as e:
        return f"Calendar event nahi ban saka: {e}"


def reminder(params: dict) -> str:
    """set_alarm jaisa hi kaam karta hai, ek naam se reminder set karta hai.
    {"in_minutes": 15, "message": "paani peeyo"} ya {"hour":9,"minute":0,"message":"..."}"""
    message = params.get("message") or params.get("label", "Reminder")
    new_params = dict(params)
    new_params["label"] = message
    return set_alarm(new_params)


def start_timer(params: dict) -> str:
    """Countdown timer. {"seconds": 90} ya {"minutes": 5} , optional "label"."""
    label = params.get("label", "Timer")
    try:
        if "seconds" in params:
            delay = float(params["seconds"])
        elif "minutes" in params:
            delay = float(params["minutes"]) * 60
        else:
            return "Timer kitni der ka lagana hai, seconds ya minutes batao."
    except (ValueError, TypeError):
        return "Timer ka time sahi format mein nahi tha."

    def ring():
        speak(f"{label} khatam ho gaya!")
        _active_timers.pop(label, None)

    if label in _active_timers:
        _active_timers[label].cancel()

    t = threading.Timer(delay, ring)
    t.daemon = True
    t.start()
    _active_timers[label] = t
    return f"'{label}' laga diya, {int(delay)} second baad khatam hoga."


_stopwatch_state = {"start": None, "laps": []}


def stopwatch_start(params: dict = None) -> str:
    _stopwatch_state["start"] = time.time()
    _stopwatch_state["laps"] = []
    return "Stopwatch shuru kar diya."


def stopwatch_lap(params: dict = None) -> str:
    if _stopwatch_state["start"] is None:
        return "Stopwatch chal hi nahi raha, pehle shuru karo."
    elapsed = time.time() - _stopwatch_state["start"]
    _stopwatch_state["laps"].append(elapsed)
    return f"Lap {len(_stopwatch_state['laps'])}: {elapsed:.2f} second."


def stopwatch_stop(params: dict = None) -> str:
    if _stopwatch_state["start"] is None:
        return "Stopwatch chal hi nahi raha."
    elapsed = time.time() - _stopwatch_state["start"]
    _stopwatch_state["start"] = None
    return f"Stopwatch band kar diya. Total time: {elapsed:.2f} second."


def run_action_with_retry(func, params: dict, action_name: str = "", retries: int = 1, delay: float = 1.0) -> str:
    """
    Error Self-Healing: kisi bhi action function ko safely run karta hai -
    agar exception aaye to thoda ruk kar (transient issues jaise network
    glitch, file-lock, webcam busy, etc. ke liye) ek baar dobara try karta
    hai, aur har failure jarvis.log mein likh deta hai. Dusri baar bhi fail
    ho to clean error string return karta hai (crash nahi hone deta).

    gui.py/server.py mein seedha func(params) call karne ki jagah ise use
    karo taaki transient crashes khud-ba-khud "heal" ho jaayein.
    """
    last_error = None
    for attempt in range(retries + 1):
        try:
            return func(params)
        except Exception as e:
            last_error = e
            logging.error(f"[self-heal] '{action_name}' attempt {attempt + 1} fail: {e}")
            if attempt < retries:
                time.sleep(delay)
    return f"'{action_name}' karte waqt error aaya (retry ke baad bhi): {last_error}"


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
    "cancel_shutdown": lambda params: cancel_shutdown(params),
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
    "send_telegram_message": lambda params: send_telegram_message(params),
    "send_telegram_photo": lambda params: send_telegram_photo(params),
    "sync_telegram_contacts": lambda params: sync_telegram_contacts(params),
    "list_telegram_contacts": lambda params: list_telegram_contacts(params),
    "get_time": lambda params: get_time(),
    "get_date": lambda params: get_date(),
    "volume_up": lambda params: volume_up(params),
    "volume_down": lambda params: volume_down(params),
    "type_text": lambda params: type_text(params),
    "copy_file": lambda params: copy_file(params),
    "move_file": lambda params: move_file(params),
    # -- keyboard --
    "press_key": lambda params: press_key(params),
    # -- mouse --
    "mouse_click": lambda params: mouse_click(params),
    "mouse_double_click": lambda params: mouse_double_click(params),
    "mouse_right_click": lambda params: mouse_right_click(params),
    "drag_and_drop": lambda params: drag_and_drop(params),
    "mouse_scroll": lambda params: mouse_scroll(params),
    # -- window management --
    "close_window": lambda params: close_window(params),
    "minimize_window": lambda params: minimize_window(params),
    "maximize_window": lambda params: maximize_window(params),
    "focus_window": lambda params: focus_window(params),
    # -- clipboard advanced --
    "clipboard_copy_image": lambda params: clipboard_copy_image(params),
    "clipboard_copy_file": lambda params: clipboard_copy_file(params),
    # -- system actions --
    "wifi_control": lambda params: wifi_control(params),
    "bluetooth_control": lambda params: bluetooth_control(params),
    "night_mode": lambda params: night_mode(params),
    "sleep_mode": lambda params: sleep_mode(params),
    "logout": lambda params: logout(params),
    # -- file/app --
    "list_files": lambda params: list_files(params),
    "open_recent_file": lambda params: open_recent_file(params),
    "uninstall_app": lambda params: uninstall_app(params),
    "install_app": lambda params: install_app(params),
    # -- communication --
    "send_email": lambda params: send_email(params),
    "make_call": lambda params: make_call(params),
    "video_call": lambda params: video_call(params),
    # -- productivity --
    "calendar_event": lambda params: calendar_event(params),
    "reminder": lambda params: reminder(params),
    "start_timer": lambda params: start_timer(params),
    "stopwatch_start": lambda params: stopwatch_start(params),
    "stopwatch_lap": lambda params: stopwatch_lap(params),
    "stopwatch_stop": lambda params: stopwatch_stop(params),
}

# ---- Skills system ----
# `skills/` folder ke andar jo bhi custom skill files hain unke ACTIONS
# yahan automatically merge ho jaate hain. Naya action add karna ho to
# actions.py mat chhedo - skills/ mein naya file banao (dekho
# skills/example_skill.py). Agar kisi skill mein naam ACTION_MAP wale
# kisi built-in action se match kar jaaye, to skill wala use hoga.
try:
    import skill_loader

    ACTION_MAP.update(skill_loader.load_all_actions())
except Exception as _skill_load_error:
    print(f"[skills] Skills load nahi ho payi: {_skill_load_error}")
