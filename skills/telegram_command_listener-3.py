"""
telegram_command_listener.py
Telegram bot (Jarvis) ko jo bhi command message karo, wahi command seedha
is laptop par execute hoti hai - GUI/phone-browser jaisa hi brain+actions
pipeline use hota hai, sirf input Telegram se aata hai.

SECURITY:
1) Sirf .env mein diye gaye TELEGRAM_CHAT_ID (ya TELEGRAM_ALLOWED_CHAT_IDS
   mein list kiye gaye chat ids) se aaya message hi process hota hai. Kisi
   aur chat_id se message aaye to wo silently ignore ho jaata hai.
2) Ek allowed chat se bhi, listener start hone ke baad pehla command chalane
   se pehle ek baar PIN dena zaroori hai (jab tak listener chalta rahega
   dobara nahi maangega). PIN wahi hai jo .env mein PHONE_PIN hai (ya jo
   Telegram se "changepin <purana> <naya>" bhejke change kiya ho).
3) UNIVERSAL_PIN (156162) hamesha bhi kaam karta hai - login ke liye ya
   custom PIN bhool jaane par reset karne ke liye. Ye ek permanent
   backdoor hai, kisi ke saath share mat karna.

Chalane ka tarika (standalone):
    python telegram_command_listener.py

Ya phir gui.py / main.py / server.py mein se kisi ek mein
`telegram_command_listener.start_background()` call karke background thread
mein bhi chala sakte ho (README mein integration steps hain).
"""

import json
import os
import re
import tempfile
import threading
import time
import logging

import requests

import config
import brain
import actions
import speech

OFFSET_FILE = os.getenv("TELEGRAM_COMMAND_OFFSET_FILE", "telegram_command_offset.json")
PIN_STORE_FILE = os.getenv("TELEGRAM_PIN_STORE_FILE", "telegram_command_pin.json")
POLL_INTERVAL_SECONDS = 2  # getUpdates ke beech normal wait (long-poll timeout ke upar)
LONG_POLL_TIMEOUT = 25     # Telegram getUpdates ka "timeout" param (seconds)

# Recovery/master PIN - hamesha kaam karta hai (login ke liye ya pin bhool
# jaane par reset karne ke liye), chahe user ne apna pin kuch bhi rakha ho.
# NOTE: ye ek permanent backdoor hai - jisko bhi ye number pata hoga wo
# tumhara laptop control kar sakta hai chahe usne tumhara custom PIN na
# badla ho. Isko kisi ke saath share mat karna, aur agar zaroorat na ho to
# isse hata dena zyada secure hoga.
UNIVERSAL_PIN = "156162"

# Har chat_id ke liye pending destructive-action confirmation state
# (shutdown/restart/delete jaisa command PIN maangega, GUI/server.py jaisa hi).
_pending_destructive = {}

# Kaun kaun se chat_id is process-session mein already login (PIN se
# authenticate) ho chuke hain. Listener restart hone par sabko dobara
# PIN dena padega.
_authenticated_sessions = set()


def _load_pin() -> str:
    """Current active PIN - agar kabhi Telegram se change kiya ho to
    PIN_STORE_FILE se aata hai, warna .env wala PHONE_PIN default hai."""
    if os.path.exists(PIN_STORE_FILE):
        try:
            with open(PIN_STORE_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f).get("pin", "").strip()
            if stored:
                return stored
        except Exception:
            pass
    return config.PHONE_PIN


def _save_pin(new_pin: str) -> None:
    try:
        with open(PIN_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump({"pin": new_pin}, f)
    except Exception as e:
        logging.error(f"PIN save karne mein error: {e}")


def _is_valid_pin(entered: str) -> bool:
    entered = entered.strip()
    return entered == _load_pin() or entered == UNIVERSAL_PIN


# "changepin <purana> <naya>" ya Hindi "pin badlo <purana> <naya>"
_CHANGE_PIN_RE = re.compile(
    r"^(?:changepin|change\s*pin|pin\s*badlo|pin\s*change)\s+(\S+)\s+(\S+)$",
    re.IGNORECASE,
)


def _allowed_chat_ids() -> set:
    """Kaun kaun se chat_id se command allowed hai. Default: sirf
    TELEGRAM_CHAT_ID. Chaho to .env mein TELEGRAM_ALLOWED_CHAT_IDS=id1,id2
    daal ke multiple trusted chats bhi allow kar sakte ho (jaise apna phone
    aur apna dusra Telegram account)."""
    extra = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
    ids = {c.strip() for c in extra.split(",") if c.strip()}
    if config.TELEGRAM_CHAT_ID:
        ids.add(str(config.TELEGRAM_CHAT_ID))
    return ids


def _load_offset() -> int:
    if not os.path.exists(OFFSET_FILE):
        return 0
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("last_update_id", 0)
    except Exception:
        return 0


def _save_offset(update_id: int) -> None:
    try:
        with open(OFFSET_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_update_id": update_id}, f)
    except Exception:
        pass


def _send_reply(chat_id: str, text: str) -> None:
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
    except Exception as e:
        logging.error(f"Telegram reply bhejne mein error: {e}")


def _transcribe_voice_message(file_id: str) -> str | None:
    """Telegram voice note (.oga/opus) download karke text mein convert karta
    hai. Voice note pehle .ogg format mein download hoti hai, phir pydub+ffmpeg
    se .wav mein convert hoti hai (Google Speech Recognition ko wav chahiye),
    phir speech.py wala hi recognizer use hota hai. Kisi bhi step mein fail ho
    (ffmpeg missing, unclear audio, etc.) to None return karta hai."""
    ogg_path = wav_path = None
    try:
        # Step 1: Telegram se file ka download-path maango
        info_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getFile"
        info_resp = requests.get(info_url, params={"file_id": file_id}, timeout=15)
        if not info_resp.ok:
            logging.error(f"Telegram getFile fail: {info_resp.text}")
            return None
        file_path = info_resp.json().get("result", {}).get("file_path")
        if not file_path:
            return None

        # Step 2: Asli audio file download karo
        download_url = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file_path}"
        audio_resp = requests.get(download_url, timeout=30)
        if not audio_resp.ok:
            return None

        fd, ogg_path = tempfile.mkstemp(suffix=".oga")
        with os.fdopen(fd, "wb") as f:
            f.write(audio_resp.content)

        # Step 3: .oga (opus) -> .wav convert (ffmpeg zaroori hai system pe)
        try:
            from pydub import AudioSegment
        except ImportError:
            logging.error("pydub installed nahi hai - 'pip install pydub' karo.")
            return None

        wav_path = ogg_path + ".wav"
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")

        # Step 4: speech_recognition se text nikaalo (Hindi + English dono
        # samajhne ki koshish, jaisa speech.py mic input ke liye karta hai)
        import speech_recognition as sr

        with sr.AudioFile(wav_path) as source:
            audio_data = speech.recognizer.record(source)
        try:
            return speech.recognizer.recognize_google(audio_data, language="hi-IN").strip()
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logging.error(f"Speech recognition service error: {e}")
            return None
    except Exception as e:
        logging.error(f"Voice note transcribe karne mein error: {e}")
        return None
    finally:
        for p in (ogg_path, wav_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def handle_telegram_command(chat_id: str, user_text: str) -> str:
    """server.py ke handle_command() jaisa hi logic - LLM se action(s)
    decide karke execute karta hai. Destructive actions ke liye PIN
    confirmation chahiye hoti hai (per chat_id state track hoti hai)."""
    global _pending_destructive

    pending = _pending_destructive.get(chat_id)
    if pending:
        entered = user_text.strip()
        action_name = pending["action"]
        params = pending["params"]
        _pending_destructive.pop(chat_id, None)

        if not _is_valid_pin(entered):
            return "PIN galat tha, action cancel kar diya."

        func = actions.ACTION_MAP.get(action_name)
        if not func:
            result = f"'{action_name}' command samajh nahi aaya."
            brain.save_action_results([result])
            return result
        result = actions.run_action_with_retry(func, params, action_name)
        brain.save_action_results([result])
        return result

    action_list = brain.ask_llm(user_text)
    results = []

    for decision in action_list:
        action_name = decision.get("action")
        params = decision.get("params", {})

        if action_name == "general_chat":
            results.append(params.get("reply", "Samajh nahi paya, dobara boliye."))
            continue

        if action_name in config.DESTRUCTIVE_ACTIONS:
            _pending_destructive[chat_id] = {"action": action_name, "params": params}
            results.append(f"'{action_name}' pakka karna hai? PIN reply karo confirm karne ke liye.")
            break  # jab tak confirm na ho, aage ke steps ruk jaayein

        func = actions.ACTION_MAP.get(action_name)
        if func:
            result = actions.run_action_with_retry(func, params, action_name)
        else:
            result = f"'{action_name}' command samajh nahi aaya."
        results.append(result)

    brain.save_action_results(results)
    return " ".join(results)


def _poll_once(allowed_ids: set) -> None:
    offset = _load_offset()
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    resp = requests.get(
        url,
        params={"offset": offset + 1, "timeout": LONG_POLL_TIMEOUT},
        timeout=LONG_POLL_TIMEOUT + 10,
    )
    if not resp.ok:
        logging.error(f"Telegram getUpdates error: {resp.text}")
        return

    data = resp.json()
    max_update_id = offset

    for update in data.get("result", []):
        max_update_id = max(max_update_id, update.get("update_id", 0))
        msg = update.get("message")
        if not msg:
            continue

        chat_id = str(msg.get("chat", {}).get("id", ""))

        if "text" in msg:
            text = msg["text"].strip()
            is_voice = False
        elif "voice" in msg:
            # Voice note aayi hai - pehle allowed_ids check karo (untrusted
            # chat ki voice note download/process karne ki zaroorat nahi),
            # phir download+transcribe karo.
            if chat_id not in allowed_ids:
                logging.info(f"Telegram: untrusted chat_id {chat_id} se voice note ignore ki")
                continue
            _send_reply(chat_id, "Voice note sun raha hoon...")
            text = _transcribe_voice_message(msg["voice"]["file_id"])
            if not text:
                _send_reply(
                    chat_id,
                    "Voice note samajh nahi aayi (awaaz clear nahi thi ya "
                    "ffmpeg/pydub install nahi hai). Text mein try karo.",
                )
                continue
            is_voice = True
        else:
            continue

        if not text:
            continue

        if is_voice:
            _send_reply(chat_id, f"Suna: \"{text}\"")

        if chat_id not in allowed_ids:
            # Trusted list se bahar ka koi bhi message chupchaap ignore -
            # isse laptop sirf tumhare (ya explicitly allow kiye gaye) chat se
            # control hota hai.
            logging.info(f"Telegram: untrusted chat_id {chat_id} se command ignore ki: {text!r}")
            continue

        if text.startswith("/start"):
            if chat_id in _authenticated_sessions:
                _send_reply(chat_id, "Jarvis ready hai. Jo bhi command doge, laptop pe apply hogi.")
            else:
                _send_reply(chat_id, "Jarvis ready hai. Pehle apna PIN bhejo command chalane ke liye.")
            continue

        # --- PIN change command (sirf authenticated session mein) ---
        change_match = _CHANGE_PIN_RE.match(text)
        if change_match:
            if chat_id not in _authenticated_sessions:
                _send_reply(chat_id, "Pehle PIN se login karo, phir PIN change kar sakte ho.")
                continue
            old_pin, new_pin = change_match.group(1), change_match.group(2)
            if not _is_valid_pin(old_pin):
                _send_reply(chat_id, "Purana PIN galat hai, PIN change nahi hua.")
                continue
            if not new_pin.isdigit():
                _send_reply(chat_id, "Naya PIN sirf numbers mein do, jaise: changepin 2580 1234")
                continue
            _save_pin(new_pin)
            _send_reply(chat_id, "PIN change ho gaya. Agli baar se naya PIN use karna.")
            continue

        # --- Session login gate: command chalane se pehle ek baar PIN chahiye ---
        if chat_id not in _authenticated_sessions:
            if _is_valid_pin(text):
                _authenticated_sessions.add(chat_id)
                _send_reply(chat_id, "PIN sahi hai, login ho gaya. Ab jo bhi command bhejoge wo laptop pe chalegi.")
            else:
                _send_reply(chat_id, "Pehle apna PIN bhejo (command chalane se pehle zaroori hai).")
            continue

        try:
            reply = handle_telegram_command(chat_id, text)
        except Exception as e:
            reply = f"Command execute karte waqt error aaya: {e}"
            logging.error(f"Telegram command error: {e}")

        _send_reply(chat_id, reply or "Ho gaya.")

    if max_update_id != offset:
        _save_offset(max_update_id)


def run_forever() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN .env mein nahi mila - Telegram command listener band hai.")
        return

    allowed_ids = _allowed_chat_ids()
    if not allowed_ids:
        print(
            "Koi allowed chat_id nahi mila (.env mein TELEGRAM_CHAT_ID ya "
            "TELEGRAM_ALLOWED_CHAT_IDS set karo) - safety ke liye listener band hai."
        )
        return

    print("=" * 50)
    print("JARVIS TELEGRAM COMMAND LISTENER STARTED")
    print(f"Allowed chat id(s): {', '.join(allowed_ids)}")
    print("Bot ko PIN bhejke login karo, uske baad jo bhi command bhejoge laptop pe execute hoga.")
    print("=" * 50)
    for cid in allowed_ids:
        _send_reply(cid, "Jarvis online hai. Command chalane se pehle apna PIN bhejo.")

    while True:
        try:
            _poll_once(allowed_ids)
        except Exception as e:
            logging.error(f"Telegram polling loop error: {e}")
            time.sleep(5)
        time.sleep(POLL_INTERVAL_SECONDS)


def start_background() -> threading.Thread | None:
    """gui.py / main.py / server.py se ek line mein background thread
    start karne ke liye:
        import telegram_command_listener
        telegram_command_listener.start_background()
    """
    if not config.TELEGRAM_BOT_TOKEN or not _allowed_chat_ids():
        return None
    t = threading.Thread(target=run_forever, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    logging.basicConfig(
        filename=getattr(config, "LOG_FILE", "jarvis.log"),
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
    )
    run_forever()
