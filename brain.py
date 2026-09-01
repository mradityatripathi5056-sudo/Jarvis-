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
import requests
import config
import actions

HISTORY_FILE = "jarvis_history.json"
MAX_HISTORY = 10  # sirf last 10 messages rakho - speed ke liye


def _load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_history(history: list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)
    except IOError:
        pass


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
    (WhatsApp ke through message bhejta hai - number country code ke saath)
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

User: "notes.txt file ka naam final.txt kar do"
-> {"actions": [{"action": "rename_file", "params": {"old_path": "notes.txt", "new_path": "final.txt"}}]}

Agar command ambiguous lage ya kisi action se thoda bhi milta-julta ho,
best-guess action choose karo (khaali general_chat mat do jab tak sach mein
koi action fit hi na ho ya user sirf baat-cheet/knowledge sawaal pooch raha ho).

IMPORTANT - "Notepad khol ke essay/letter/note likho" jaisi request ke liye:
Notepad khaali khulta hai agar sirf open_app karo - usme content apne aap nahi
aata. Isliye is pattern ko follow karo:
1. Pehle create_file action do - poora likha hua content usi mein daal do
   (path jaise "essay.txt", content mein PURA likha hua matter)
2. Fir open_app action do jisme app_name = WAHI FILE PATH ho (naam nahi jaise
   "notepad", balki file ka path) - isse woh file apne default app (Notepad)
   mein khulegi aur content dikhega.

Example: "Notepad khol ke mere school pe essay likho"
-> {"actions": [
     {"action": "create_file", "params": {"path": "school_essay.txt", "content": "<poora essay yahan likho, kam se kam 100 words>"}},
     {"action": "open_app", "params": {"app_name": "school_essay.txt"}}
   ]}

Content wale actions (create_file, take_note) mein content SUBSTANTIAL aur
COMPLETE likho - chhota ya adhoora content mat do jab tak user na kahe."""


def _call_openrouter(messages: list) -> dict:
    """Ek raw API call - retry logic isko dobara call kar sakta hai."""
    response = requests.post(
        url=config.OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": config.OPENROUTER_MODEL,
                "messages": messages,
                "reasoning": {"enabled": config.REASONING_ENABLED},
                "max_tokens": 1200,  # essay/note jaisa lamba content bhi fit ho sake
            }
        ),
        timeout=25,
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
    system_prompt = TOOLS_DEFINITION
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
        return [
            {
                "action": "general_chat",
                "params": {"reply": f"Mujhe LLM se connect karne mein dikkat aa rahi hai: {e}"},
            }
        ]


def _extract_json(text: str) -> dict | None:
    """Response text mein se JSON object nikalta hai, agar extra text ho to bhi."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
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
