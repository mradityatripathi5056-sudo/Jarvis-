"""
brain.py
OpenRouter API se baat karne ka logic. User ke command ko samajh kar
ek ya zyada actions (multi-step) mein convert karta hai.

SHARED MEMORY: gui.py, server.py, aur main.py teeno ALAG Python processes ho
sakte hain, isliye conversation history ek JSON file (jarvis_history.json)
mein save hoti hai - sab isi file se padhte/likhte hain.
"""

import json
import os
import re
import requests
import config
import actions
import skill_loader
from json_utils import safe_json_load, safe_json_save

HISTORY_FILE = "jarvis_history.json"
MAX_HISTORY = 10  # sirf last 10 messages rakho - speed ke liye


def _load_history() -> list:
    return safe_json_load(HISTORY_FILE, [])


def _save_history(history: list):
    safe_json_save(HISTORY_FILE, history[-MAX_HISTORY:])


TOOLS_DEFINITION = """Tum Jarvis ho, ek voice-controlled computer assistant. User ke command ko
samajh kar neeche diye actions mein se zaroori actions choose karo.

STRICT RULE: Hamesha is JSON format mein reply do, kuch aur nahi:
{"actions": [{"action": "action_name", "params": {...}}, ...]}

Agar command mein sirf ek kaam hai, to list mein ek hi action do.
Agar command mein multiple steps hain (jaise "X karo aur Y karo"),
to list mein saare steps sequence mein do.

Available actions:
- open_app: {"app_name": "chrome"}
- close_app: {"app_name": "chrome"}
- search_file: {"query": "resume.pdf"}
- create_file: {"path": "test.txt", "content": ""}
- delete_file: {"path": "test.txt"}
- system_info: {}
- volume_control: {"level": 50}
- brightness_control: {"level": 70}
- screenshot: {}
- web_search: {"query": "python tutorial"}
- shutdown: {}
- restart: {}
- cancel_shutdown: {}  (galti se shutdown/restart bol diya tha to usko cancel karta hai)
- clipboard_write: {"text": "hello"}
- clipboard_read: {}
- lock_screen: {}
- youtube_search_and_play: {"query": "hindi songs"}
- youtube_search: {"query": "lofi music"}
- open_website: {"url": "github.com"}
- open_folder: {"path": "C:\\\\Users"}
- take_note: {"content": "meeting at 5pm"}
- read_notes: {}
- list_running_apps: {}
- kill_process: {"app_name": "chrome"}
- battery_status: {}
- empty_recycle_bin: {}
- minimize_all_windows: {}
- media_play_pause: {}
- calculate: {"expression": "23*17+5"}
- disk_space: {}
- ip_address: {}
- mute_volume: {}
- set_alarm: {"hour": 7, "minute": 30, "label": "wake up"}  (specific time ke liye)
  YA {"in_minutes": 20, "label": "coffee"}  (X minute baad ke liye)
- cancel_alarm: {"label": "wake up"}  (label na do to SAARE alarms cancel ho jayenge)
- list_alarms: {}
- remember_fact: {"key": "school ka naam", "value": "DPS Ayodhya"}
    (jab user koi bhi personal info, preference, ya fact permanently yaad
    rakhne ko kahe - "yaad rakho", "note kar lo ye baat", "mera X hai" jaisa)
- recall_fact: {"key": "school ka naam"}  (key khaali chhodo to sab facts bata dega)
- list_facts: {}
- forget_fact: {"key": "school ka naam"}  (key khaali chhodo to SAB facts delete ho jayenge)
- open_camera: {}  (OS ka camera app kholta hai)
- take_photo: {}  (seedha webcam se photo khinch ke save karta hai, app khulne ki zaroorat nahi)
- rename_file: {"old_path": "test.txt", "new_path": "final.txt"}
- edit_file: {"path": "notes.txt", "mode": "append", "content": "naya text"}
    (mode "append" = end mein jodo, "replace" = poora content badal do)
- send_message: {"phone": "+919876543210", "message": "kal milte hain"}
    (WhatsApp ke through message bhejta hai - number country code ke saath.
    NOTE: agar user aage call bhi karne wala ho ya "naam se" bhejna ho
    (number nahi), to iski jagah whatsapp_web_send_message use karo -
    dekho CUSTOM SKILLS section neeche, wo same browser session
    reuse karta hai)
- send_telegram_message: {"message": "kal milte hain"}
    (Telegram pe message bhejta hai. WhatsApp se zyada reliable/fast hai)
    Kisko bhejna hai (in options mein se ek use karo):
      - kuch na do -> .env wali default chat_id ko jayega
      - {"to": "Rohit"} -> naam/username se saved contact ko bhejega
      - {"to_all": true} -> saare saved contacts ko bhej dega (broadcast)
      - {"to_all": true, "exclude": ["Raj"]} -> sabko bhejo, Raj ko chhodkar
      - {"chat_id": "123456789"} -> seedha kisi chat id pe
- send_telegram_photo: {"path": "screenshot.png", "caption": "dekho", "to": "Rohit"}
    (koi image file Telegram pe bhejta hai - "to" optional, naam se bhi bhej sakte ho)
- sync_telegram_contacts: {}
    (IMPORTANT: yeh Telegram APP nahi kholta - koi Telegram window open
    nahi hoti. Yeh sirf background mein Bot API se check karta hai ki
    kisne bhi bot ko naya message/start kiya hai, aur unka naam+chat_id
    save kar leta hai. Jab bhi command mein "contact" ya "contacts" word
    ho "telegram" ke saath, hamesha yeh action use karo, open_app nahi.
    Trigger phrases: "telegram contact sync karo", "contacts sync karo",
    "contacts update karo", "naye contacts check karo")
- list_telegram_contacts: {}
    (ab tak jitne logon ne bot ko message kiya hai unki list dikhata hai -
    yeh bhi Telegram app nahi kholta, sirf saved list dikhata hai)
- get_time: {}
- get_date: {}
- volume_up: {"step": 10}  (step optional, default 10)
- volume_down: {"step": 10}
- type_text: {"text": "jo bhi likhna hai"}  (jahan cursor hai wahan type karta hai)
- copy_file: {"source": "a.txt", "destination": "b.txt"}
- move_file: {"source": "a.txt", "destination": "folder/a.txt"}

KEYBOARD:
- press_key: {"key": "enter"}  (single: enter/tab/escape/backspace/delete/space/
    up/down/left/right/f1-f12) YA combo: {"key": "ctrl+c"}, {"key": "alt+f4"},
    {"key": "win+d"}

MOUSE:
- mouse_click: {"x": 500, "y": 300}  (x,y optional - na do to current position pe click)
- mouse_double_click: {"x": 500, "y": 300}
- mouse_right_click: {"x": 500, "y": 300}
- drag_and_drop: {"from_x": 100, "from_y": 200, "to_x": 500, "to_y": 600}
- mouse_scroll: {"direction": "up", "amount": 10}  (direction: up/down)

WINDOW MANAGEMENT (title = window ka naam ya partial naam):
- close_window: {"title": "Notepad"}
- minimize_window: {"title": "Chrome"}
- maximize_window: {"title": "Chrome"}
- focus_window: {"title": "Chrome"}

CLIPBOARD ADVANCED:
- clipboard_copy_image: {"path": "photo.png"}  (image ko clipboard mein daalta hai)
- clipboard_copy_file: {"path": "report.pdf"}  (file object copy karta hai, jahan paste karo wahan asli file jaayegi)

SYSTEM:
- wifi_control: {"state": "on"}  ya {"state": "off"}
- bluetooth_control: {"state": "on"}  ya {"state": "off"}
- night_mode: {"state": "on"}  (dark mode) / {"state": "off"} (light mode) / {"state": "toggle"}
- sleep_mode: {}
- logout: {}

FILE/APP:
- list_files: {"path": "C:\\\\Users\\\\Aditya\\\\Downloads"}
- open_recent_file: {"query": "resume"}  (query optional, sabse recent file khol dega)
- uninstall_app: {"app_name": "Spotify"}  (safety ke liye Apps&Features page kholta hai, direct uninstall nahi karta)
- install_app: {"app_name": "vlc"}  (winget/homebrew se install karta hai)

COMMUNICATION:
- send_email: {"to": "someone@gmail.com", "subject": "Hi", "body": "kaise ho"}
    (.env mein SMTP_EMAIL/SMTP_PASSWORD set hona chahiye)
- make_call: {"number": "+919876543210"}
- video_call: {"contact": "Rahul"}  (contact optional, Google Meet naya room kholta hai)

PRODUCTIVITY:
- calendar_event: {"title": "Team meeting", "date": "2026-09-10", "time": "15:00"}
    (date/time optional)
- reminder: {"message": "paani peeyo", "in_minutes": 30}  YA {"message": "...", "hour": 9, "minute": 0}
- start_timer: {"minutes": 5, "label": "chai"}  YA {"seconds": 90}
- stopwatch_start: {}
- stopwatch_lap: {}
- stopwatch_stop: {}

- general_chat: {"reply": "tumhara natural language jawab yaha"}
    (jab command kisi action se match na ho, normal baat-cheet/knowledge
    question ke liye ye use karo)

Sirf JSON do, koi explanation, markdown, ya extra text nahi.

EXAMPLES (in jaisi hi commands aa sakti hain, isi pattern se JSON banao):
User: "chrome khol do"
-> {"actions": [{"action": "open_app", "params": {"app_name": "chrome"}}]}

User: "screenshot le lo aur battery bhi batao"
-> {"actions": [{"action": "screenshot", "params": {}}, {"action": "battery_status", "params": {}}]}

User: "volume 70 kar do"
-> {"actions": [{"action": "volume_control", "params": {"level": 70}}]}

User: "mera naam Aditya hai, yaad rakhna"
-> {"actions": [{"action": "remember_fact", "params": {"key": "naam", "value": "Aditya"}}]}

User: "mera naam kya hai"
-> {"actions": [{"action": "recall_fact", "params": {"key": "naam"}}]}

User: "20 minute baad coffee ka alarm laga do"
-> {"actions": [{"action": "set_alarm", "params": {"in_minutes": 20, "label": "coffee"}}]}

User: "aaj mausam kaisa hai" (aisa sawaal jiska koi fixed action nahi hai)
-> {"actions": [{"action": "general_chat", "params": {"reply": "Mujhe live weather check karne ki ability nahi hai abhi, lekin..."}}]}

User: "23 plus 45 kitna hota hai"
-> {"actions": [{"action": "calculate", "params": {"expression": "23+45"}}]}

User: "camera khol do"
-> {"actions": [{"action": "open_camera", "params": {}}]}

User: "ek photo khinch lo"
-> {"actions": [{"action": "take_photo", "params": {}}]}

User: "Rahul ko WhatsApp pe bol do ki 5 minute mein aa raha hoon, number +919876543210"
-> {"actions": [{"action": "send_message", "params": {"phone": "+919876543210", "message": "5 minute mein aa raha hoon"}}]}

User: "Rohit ko telegram pe bhej do ki mai aa raha hoon"
-> {"actions": [{"action": "send_telegram_message", "params": {"to": "Rohit", "message": "Main aa raha hoon"}}]}

User: "sabko bata do meeting cancel ho gayi"
-> {"actions": [{"action": "send_telegram_message", "params": {"to_all": true, "message": "Meeting cancel ho gayi"}}]}

User: "sabko bol do kal chutti hai, bas Priya ko mat bhejo"
-> {"actions": [{"action": "send_telegram_message", "params": {"to_all": true, "exclude": ["Priya"], "message": "Kal chutti hai"}}]}

User: "Telegram contacts update karo"
-> {"actions": [{"action": "sync_telegram_contacts", "params": {}}]}

User: "telegram contact sync karo"
-> {"actions": [{"action": "sync_telegram_contacts", "params": {}}]}
(NOTE: is command mein "telegram" word hai lekin "contact/sync" bhi hai,
isliye ye open_app nahi hai - open_app sirf tab jab sirf app kholne ko
bola jaye, jaise "telegram khol do" - koi "contact/sync/update" word na ho)

User: "Telegram pe bhej do ki mai late hoon"
-> {"actions": [{"action": "send_telegram_message", "params": {"message": "Main late hoon"}}]}

User: "notes.txt file ka naam final.txt kar do"
-> {"actions": [{"action": "rename_file", "params": {"old_path": "notes.txt", "new_path": "final.txt"}}]}

User: "telegram khol do"
-> {"actions": [{"action": "open_app", "params": {"app_name": "telegram"}}]}

User: "abhi kitne baje hain"
-> {"actions": [{"action": "get_time", "params": {}}]}

User: "volume thoda badha do"
-> {"actions": [{"action": "volume_up", "params": {"step": 10}}]}

User: "hello type kar do"
-> {"actions": [{"action": "type_text", "params": {"text": "hello"}}]}

User: "ctrl c dabao"
-> {"actions": [{"action": "press_key", "params": {"key": "ctrl+c"}}]}

User: "chrome minimize kar do"
-> {"actions": [{"action": "minimize_window", "params": {"title": "Chrome"}}]}

User: "wifi band kar do"
-> {"actions": [{"action": "wifi_control", "params": {"state": "off"}}]}

User: "5 minute ka timer laga do"
-> {"actions": [{"action": "start_timer", "params": {"minutes": 5}}]}

User: "1 ghante baad paani peene ka reminder laga do"
-> {"actions": [{"action": "reminder", "params": {"in_minutes": 60, "message": "paani peeyo"}}]}

Agar command ambiguous lage ya kisi action se thoda bhi milta-julta ho,
best-guess action choose karo (khaali general_chat mat do jab tak sach mein
koi action fit hi na ho ya user sirf baat-cheet/knowledge sawaal pooch raha ho).

IMPORTANT - YouTube, Google, Gmail, Instagram, Facebook jaise naam WEBSITES
hain, installed APPS nahi (jab tak user khud "app" na bole) - inke liye
open_app mat use karo, balki:
- "youtube kholo" / "youtube pe X chalao" -> youtube_search ya youtube_search_and_play
- baaki websites (gmail, instagram, google, facebook, etc.) -> open_website
  with the correct url, e.g. {"action": "open_website", "params": {"url": "instagram.com"}}

Example: "instagram khol do"
-> {"actions": [{"action": "open_website", "params": {"url": "instagram.com"}}]}

Example: "youtube khol do"
-> {"actions": [{"action": "open_website", "params": {"url": "youtube.com"}}]}

IMPORTANT - "Notepad/kisi file mein likho" jaisi HAR request ke liye
(essay, letter, note, LIST, YA CODE/PROGRAM - kuch bhi ho, sirf essay tak
seemit mat raho):
Agar user "notepad pe likho", "notepad mein daalo", "file bana ke likho"
jaisa bole - CHAHE content essay ho ya Python/JS/C++ jaisa CODE ho - us
content ko kabhi bhi seedha chat reply (general_chat) mein mat likho.
Notepad khaali khulta hai agar sirf open_app karo - usme content apne aap
nahi aata. Isliye har baar ye hi pattern follow karo:
1. Pehle create_file action do - poora likha hua content (essay ho ya code,
   dono) usi mein daal do. CODE ke liye sahi extension use karo (jaise
   ".py" Python ke liye, ".js" JavaScript ke liye, ".html" HTML ke liye) -
   sirf ".txt" mat use karo agar code likha ja raha hai.
2. Fir open_app action do jisme app_name = WAHI FILE PATH ho (naam nahi jaise
   "notepad", balki file ka path) - isse woh file apne default app (Notepad
   ya jo bhi us extension se associated ho) mein khulegi aur content dikhega.

Example: "Notepad khol ke mere school pe essay likho"
-> {"actions": [
     {"action": "create_file", "params": {"path": "school_essay.txt", "content": "<poora essay yahan likho, kam se kam 100 words>"}},
     {"action": "open_app", "params": {"app_name": "school_essay.txt"}}
   ]}

Example: "Notepad pe python ka code likho jo 1 se 10 tak print kare"
-> {"actions": [
     {"action": "create_file", "params": {"path": "print_numbers.py", "content": "<poora, chalne wala Python code yahan>"}},
     {"action": "open_app", "params": {"app_name": "print_numbers.py"}}
   ]}

Sirf tab code chat mein (general_chat se) do jab user SIRF poochta hai
"ye code kaise likhein / samjhao" - "notepad pe likho" ya "file bana do"
jaisa koi bhi shabd ho to hamesha upar wala create_file + open_app pattern
use karo.

Content wale actions (create_file, take_note) mein content SUBSTANTIAL aur
COMPLETE likho - chhota ya adhoora content mat do jab tak user na kahe."""


def _build_payload(messages: list) -> dict:
    """Request body banata hai. REASONING_ENABLED false ho to reasoning
    bilkul bhej hi nahi rahe (kai free models is field pe hi 400 error de
    dete hain) - true ho to "effort" style bhejte hain (OpenRouter ka
    zyada widely-supported unified format, "enabled" bool se better
    kaam karta hai zyadatar reasoning models ke saath)."""
    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": 1500,  # essay/note jaisa lamba content bhi fit ho sake
    }
    if config.REASONING_ENABLED:
        payload["reasoning"] = {"effort": config.REASONING_EFFORT}
    return payload


def _call_ollama(messages: list) -> str | None:
    """
    Offline Mode Fallback: OpenRouter (cloud) tak internet na pahunche to
    localhost pe chal rahe Ollama se try karta hai. Ollama chal hi na raha
    ho (ya OFFLINE_LLM_ENABLED=false ho) to seedha None return karta hai,
    taaki caller apna normal 'internet check karo' error de de.
    Return: raw content string (ya None agar ye bhi fail ho jaaye).
    """
    if not config.OFFLINE_LLM_ENABLED:
        return None
    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={"model": config.OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip() or None
    except Exception:
        return None


def _call_openrouter(messages: list) -> dict:
    """Ek raw API call - retry logic isko dobara call kar sakta hai."""
    response = requests.post(
        url=config.OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(_build_payload(messages)),
        timeout=40 if config.REASONING_ENABLED else 25,
    )
    return response


def ask_llm(user_input: str) -> list:
    """
    User ka command OpenRouter ko bhejta hai aur actions ki LIST wapas deta hai.
    Har item: {"action": "...", "params": {...}}
    Agar pehli baar JSON parse fail ho jaye, ek baar retry karta hai (stricter
    reminder ke saath) - isse "samajh nahi paya" wale cases kam ho jaate hain.
    """
    conversation_history = _load_history()
    conversation_history.append({"role": "user", "content": user_input})
    trimmed_history = conversation_history[-MAX_HISTORY:]

    memory_context = actions.get_memory_context()
    system_prompt = TOOLS_DEFINITION + skill_loader.load_all_docs()
    if memory_context:
        system_prompt += "\n\n" + memory_context

    messages = [{"role": "system", "content": system_prompt}] + trimmed_history

    try:
        response = _call_openrouter(messages)

        if response.status_code == 429:
            _save_history(conversation_history[:-1])
            return [
                {
                    "action": "general_chat",
                    "params": {
                        "reply": "Free model ki rate limit lag gayi hai. Thodi der (10-15 min) "
                        "baad try karo, ya .env mein OPENROUTER_MODEL badal ke doosra "
                        "free model use karo."
                    },
                }
            ]

        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]
        content = message.get("content", "").strip()

        parsed = _extract_json(content)

        # Pehli try fail hui - ek dobara try, is baar strict reminder ke saath.
        # Free models kabhi-kabhi JSON ke aage-peeche extra text jod dete hain.
        if not parsed or ("actions" not in parsed and "action" not in parsed):
            retry_messages = messages + [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": "Tumhara pichla jawab valid JSON nahi tha. SIRF is format mein "
                    'reply do, kuch aur text nahi: {"actions": [{"action": "...", "params": {}}]}',
                },
            ]
            retry_response = _call_openrouter(retry_messages)
            if retry_response.ok:
                retry_data = retry_response.json()
                retry_content = retry_data["choices"][0]["message"].get("content", "").strip()
                retry_parsed = _extract_json(retry_content)
                if retry_parsed:
                    parsed = retry_parsed
                    content = retry_content

        conversation_history.append({"role": "assistant", "content": content})
        _save_history(conversation_history)

        if parsed and "actions" in parsed and isinstance(parsed["actions"], list):
            return parsed["actions"]
        elif parsed and "action" in parsed:
            return [parsed]
        else:
            # Dono try fail hui to bhi raw content user ko dikha do, khaali
            # "samajh nahi aaya" bolne se behtar hai.
            return [{"action": "general_chat", "params": {"reply": content}}]

    except requests.exceptions.RequestException as e:
        # Offline Mode Fallback - internet/OpenRouter unreachable hai,
        # local Ollama try karo isse pehle ki hume up karna pade.
        offline_content = _call_ollama(messages)
        if offline_content:
            parsed = _extract_json(offline_content)
            conversation_history.append({"role": "assistant", "content": offline_content})
            _save_history(conversation_history)
            if parsed and "actions" in parsed and isinstance(parsed["actions"], list):
                return parsed["actions"]
            elif parsed and "action" in parsed:
                return [parsed]
            return [{"action": "general_chat", "params": {"reply": f"[Offline mode] {offline_content}"}}]

        return [
            {
                "action": "general_chat",
                "params": {"reply": f"Mujhe LLM se connect karne mein dikkat aa rahi hai: {e}"},
            }
        ]


def _extract_json(text: str) -> dict | None:
    """Response text mein se JSON object nikalta hai, agar extra text ya
    ```json ... ``` jaisi markdown code-fence ho to bhi (free/local models
    bade content (jaise pura HTML/CSS) generate karte waqt kabhi-kabhi
    JSON ko code-fence mein wrap kar dete hain - fence hataye bina
    json.loads() fail ho jaata tha aur raw JSON hi user ko bol/dikha diya
    jaata tha, koi action execute nahi hota tha)."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def reset_conversation():
    """Conversation history clear karo (naya session shuru karne ke liye)."""
    if os.path.exists(HISTORY_FILE):
        try:
            os.remove(HISTORY_FILE)
        except IOError:
            pass


def save_action_results(results: list) -> None:
    """
    Pichle actions ka ASLI result (success/error/kaunsi file bani, etc.)
    history mein add karta hai.

    PEHLE ka bug: ask_llm() sirf apna khud ka JSON output history mein
    save karta tha ("maine ye action bola"), lekin us action ka REAL
    outcome (jaise "Bluetooth settings khol di" ya "error aaya: ...")
    kabhi history mein nahi jaata tha. Isliye agle turn mein LLM ko
    pata hi nahi hota ki uska pichla kaam kaamyaab hua ya nahi, ya
    exactly kya hua - isse wo "bhool" jaata tha aur same task ko aage
    continue karne mein galtiyan karta tha.

    Ise gui.py/server.py se, actions execute karne ke turant baad,
    results ki list ke saath call karo.
    """
    if not results:
        return
    history = _load_history()
    summary = " | ".join(str(r) for r in results)[:800]
    history.append(
        {
            "role": "user",
            "content": f"[System note - pichle action(s) ka actual result: {summary}. "
            f"Agar main isi kaam ko aage continue karne ko kahoon, is result ko "
            f"dhyan mein rakh kar aage badhna, bhoolna mat.]",
        }
    )
    _save_history(history)
