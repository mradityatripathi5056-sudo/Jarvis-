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

# Reasoning OFF by default = FAST response.
REASONING_ENABLED = os.getenv("REASONING_ENABLED", "false").lower() == "true"

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

# Destructive actions ki list jinke liye voice confirmation chahiye
DESTRUCTIVE_ACTIONS = ["delete_file", "shutdown", "restart", "kill_process", "empty_recycle_bin"]

# Phone se destructive action allow hai, lekin PIN confirm karna padega
# (isse koi bhi random device same-WiFi pe tumhara laptop shutdown nahi kar sakta)
# .env mein PHONE_PIN=1234 daal ke isko change kar sakte ho
PHONE_PIN = os.getenv("PHONE_PIN", "2580")

# Logging
LOG_FILE = "jarvis.log"
