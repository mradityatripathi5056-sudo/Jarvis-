"""
config.py
Sab settings .env file se load hoti hain. Kabhi bhi key ko yahan
directly hardcode mat karna - hamesha os.getenv() se aayegi.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---- OpenRouter API settings ----
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.2:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

if not OPENROUTER_API_KEY:
    raise ValueError(
        "OPENROUTER_API_KEY nahi mili! .env file banao (jaise .env.example) "
        "aur usme apni real key daalo: OPENROUTER_API_KEY=sk-or-v1-xxxxx"
    )

# Reasoning OFF by default = FAST response. ON karne ke liye .env mein
# REASONING_ENABLED=true karo - Jarvis tab har command pe pehle "soch"
# ke (chain-of-thought) jawab dega, jo complex/multi-step commands aur
# tricky sawaalon ke liye zyada accurate hota hai (thoda slow hoga).
REASONING_ENABLED = os.getenv("REASONING_ENABLED", "false").lower() == "true"

# Reasoning kitni "deep" ho - sirf tab use hota hai jab REASONING_ENABLED=true.
# Options: "low" (thodi si soch, fast), "medium", "high" (sabse deep/strong
# thinking, thoda slow). .env mein: REASONING_EFFORT=high
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "high")
if REASONING_EFFORT not in ("low", "medium", "high"):
    REASONING_EFFORT = "high"

# ---- Voice (Text-to-Speech) ----
# Edge TTS ka neural voice - natural sunta hai. Alag try karne ke liye .env mein
# TTS_VOICE badlo. Kuch tagde options:
#   hi-IN-MadhurNeural     -> Hindi, male, deep (DEFAULT)
#   hi-IN-SwaraNeural      -> Hindi, female
#   en-US-ChristopherNeural -> English, male, calm/deep (Jarvis jaisa vibe)
#   en-GB-RyanNeural       -> English (British), male, deep
#   en-US-GuyNeural        -> English, male, energetic
# Poori list: edge-tts --list-voices
TTS_VOICE = os.getenv("TTS_VOICE", "hi-IN-MadhurNeural")

# Wake word (jab ye bola jaye tab hi assistant sunna start kare)
WAKE_WORD = "jarvis"

# Agar system mein multiple microphones hain (webcam mic, headset, etc.) aur
# wake word bilkul kaam nahi kar raha, to galat mic use ho sakta hai. Ye
# script chala ke sahi index dhoondo: python -c "from speech import list_microphones; list_microphones()"
# phir .env mein daalo: MIC_DEVICE_INDEX=2
_mic_index_env = os.getenv("MIC_DEVICE_INDEX", "")
MIC_DEVICE_INDEX = int(_mic_index_env) if _mic_index_env.strip().isdigit() else None

# Destructive actions ki list jinke liye voice confirmation chahiye
# Saari generated files (screenshots, camera photos, face enrollment
# samples, QR codes, AI-generated images) yahan save hoti hain - root
# folder mein bikhri hui nahi. Ye folder .gitignore mein hai, isliye
# "khud ko GitHub pe update kar do" (push_update) bolne pe ye kabhi
# upload nahi hoga - sirf actual code files hi jaayengi.
MEDIA_DIR = "jarvis_media"
os.makedirs(MEDIA_DIR, exist_ok=True)

DESTRUCTIVE_ACTIONS = [
    "delete_file", "shutdown", "restart", "kill_process", "empty_recycle_bin",
    "logout", "sleep_mode", "uninstall_app", "install_app",
]

# Phone se destructive action allow hai, lekin PIN confirm karna padega
# (isse koi bhi random device same-WiFi pe tumhara laptop shutdown nahi kar sakta)
# .env mein PHONE_PIN=1234 daal ke isko change kar sakte ho
PHONE_PIN = os.getenv("PHONE_PIN", "2580")

# ---- Telegram messaging ----
# BotFather (@BotFather Telegram pe) se ek bot banao, token milega.
# Apni chat_id maloom karne ke liye @userinfobot ko message karo.
# .env mein daalo: TELEGRAM_BOT_TOKEN=... aur TELEGRAM_CHAT_ID=...
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Jab koi naya user bot ko /start (ya kuch bhi) message karta hai, uska
# naam + username + chat_id yahan is JSON file mein automatically save
# ho jaata hai. Isse "Rohit ko msg karo" bolne par jarvis khud id dhoond
# leta hai - manually har baar chat_id dena nahi padta.
TELEGRAM_CONTACTS_FILE = os.getenv("TELEGRAM_CONTACTS_FILE", "telegram_contacts.json")

# ---- Email (send_email action) ----
# Gmail use kar rahe ho to normal password nahi chalega - App Password banao:
# Google Account -> Security -> 2-Step Verification -> App passwords
# .env mein daalo: SMTP_EMAIL=you@gmail.com aur SMTP_PASSWORD=<16-char app password>
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

# ---- Offline Mode Fallback (local LLM) ----
# Agar internet chala jaaye ya OpenRouter unreachable ho, Jarvis khud
# localhost pe chal rahe Ollama (https://ollama.com) se try karta hai -
# isse basic commands offline bhi kaam karte rehte hain (thoda kam
# smart, lekin bilkul dead hone se behtar).
# Setup (ek baar): Ollama install karo, phir "ollama pull llama3.2"
# chala do - baaki khud-ba-khud hoga jab bhi internet na ho.
OFFLINE_LLM_ENABLED = os.getenv("OFFLINE_LLM_ENABLED", "true").lower() == "true"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Logging
LOG_FILE = "jarvis.log"
