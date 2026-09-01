# Jarvis - OpenRouter-Powered Voice Assistant

Python-based voice assistant (GUI + phone control) jo **OpenRouter API**
(model: `minimax/minimax-m3:free`) use karta hai.

## Setup

### 1. Dependencies Install Karo
```bash
pip install -r requirements.txt
```
Agar PyAudio error aaye: `pip install pipwin && pipwin install pyaudio`

### 2. API Key Setup
1. `.env.example` ko copy karke `.env` banao
2. Apni OpenRouter key daalo (openrouter.ai/keys se milegi):
   ```
   OPENROUTER_API_KEY=sk-or-v1-yaha-apni-real-key
   OPENROUTER_MODEL=minimax/minimax-m3:free
   REASONING_ENABLED=false
   ```

### 3. Chalao

**Laptop GUI (main app):**
```bash
python gui.py
```

**Phone se control (same WiFi zaroori):**
```bash
python server.py
```
Terminal mein IP address print hoga (jaise `http://192.168.1.5:5000`) -
phone ke Chrome browser mein wahi URL kholo.

**Terminal/CLI fallback:**
```bash
python main.py --text     # sirf typing
python main.py --voice    # sirf voice
python main.py            # dono
```

### 4. Auto-Start (Optional)
```bash
python setup_autostart.py
```
Laptop on hote hi GUI + Server dono background mein chalu ho jayenge.

---

## Model Badalna Ho To
`.env` file mein sirf ye line change karo:
```
OPENROUTER_MODEL=koi-bhi-doosra-model:free
```
Available free models yahan dekho: https://openrouter.ai/models

## Example Commands
- "Chrome khol do"
- "Screenshot le lo aur battery bhi batao" (multi-step)
- "YouTube kholo aur lofi music search karke pehla wala play karo"
- "23 plus 45 kitna hota hai"
- "System info batao"
- "Note likh lo - kal meeting hai"
- "Volume 70 kar do"

## Voice Pack (Naya - Natural Neural Voice)
Ab Jarvis Edge TTS ka natural neural voice use karta hai (pehle wala robotic
pyttsx3 sirf internet na hone pe fallback ke taur pe chalega). Voice change
karne ke liye `.env` mein `TTS_VOICE` badlo:
```
TTS_VOICE=hi-IN-MadhurNeural       # Hindi male, deep (default)
TTS_VOICE=en-US-ChristopherNeural  # English male, calm/deep - Jarvis vibe
TTS_VOICE=en-GB-RyanNeural         # English (British), deep
```
Sab voices dekhne ke liye: `edge-tts --list-voices`

## Naye Features (Advance Update)
- **Camera**: "camera khol do" (app kholta hai) ya "photo khinch lo" (seedha webcam se save karta hai, phone se bhi chalega)
- **File rename/edit**: "notes.txt ka naam final.txt kar do", "notes.txt mein ye line jodo"
- **WhatsApp message**: "Rahul ko WhatsApp pe bol do X, number +91..." (`pywhatkit` use karta hai, default browser mein WhatsApp Web login hona chahiye)
- **Phone se destructive actions ab allowed hain (PIN ke saath)**: shutdown/restart/delete jaisa command phone se bhejo to Jarvis PIN maangega. Default PIN `.env` mein `PHONE_PIN=2580` hai - **isko turant apna khud ka PIN bana lo**, warna same-WiFi pe koi bhi tumhara laptop shutdown kar sakta hai.

## Permanent Memory (Naya)
Jarvis ab facts/preferences permanently yaad rakh sakta hai (`jarvis_memory.json`
mein save hote hain, app band karne ke baad bhi rahenge):
- "mera naam Aditya hai, yaad rakhna" -> save
- "mera naam kya hai" -> recall
- "mujhe kya kya yaad hai" -> sab facts list
- "X bhula do" -> ek fact delete
Ye facts har request ke system prompt mein automatically inject hote hain,
isliye bina bataye bhi Jarvis ko context milta rehta hai.

## Destructive Actions (Confirmation Maangega)
`delete_file`, `shutdown`, `restart`, `kill_process`, `empty_recycle_bin`

Phone se ye actions disabled hain (safety ke liye) - sirf laptop GUI se hote hain.

## Naya Command Add Karna Ho To
1. `actions.py` mein naya function likho + `ACTION_MAP` mein register karo
2. `brain.py` ke `TOOLS_DEFINITION` mein description add karo

## Project Structure
```
jarvis/
├── .env                    (real key - kisi ko mat dena)
├── .env.example
├── .gitignore
├── requirements.txt
├── config.py               (OpenRouter settings)
├── speech.py
├── brain.py                (OpenRouter API, multi-step actions, shared memory)
├── actions.py
├── gui.py                  (MAIN FILE)
├── server.py                (phone control)
├── main.py                 (CLI - text/voice fallback)
├── setup_autostart.py
└── README.md
```

## Troubleshooting
- **Rate limit**: free model ki limit lag sakti hai - `.env` mein
  `OPENROUTER_MODEL` badal ke doosra free model try karo, ya thodi der wait karo
- **Voice na sune**: internet check karo, mic permission Windows Settings mein check karo
- **Phone connect na ho**: same WiFi confirm karo, Windows Firewall popup mein "Allow" dabaya tha check karo
- **"OPENROUTER_API_KEY nahi mili" error**: `.env` file sahi jagah hai aur usme key hai, confirm karo (`type .env` command se)
