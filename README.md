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
- **Telegram message**: "Telegram pe bhej do X" (Bot API se seedha bhejta hai, browser ki zaroorat nahi). Setup: BotFather se bot banao (`TELEGRAM_BOT_TOKEN`), @userinfobot se apni chat id lo (`TELEGRAM_CHAT_ID`), dono `.env` mein daal do.
- **YouTube tab reuse**: "gaana band karke dusra bajao" bolne pe naya browser tab kholne ke bajaye maujooda YouTube tab ko hi navigate karta hai (Windows-only, `pywin32` use karta hai).
- **Phone se destructive actions ab allowed hain (PIN ke saath)**: shutdown/restart/delete jaisa command phone se bhejo to Jarvis PIN maangega. Default PIN `.env` mein `PHONE_PIN=2580` hai - **isko turant apna khud ka PIN bana lo**, warna same-WiFi pe koi bhi tumhara laptop shutdown kar sakta hai.
- **Iron Man / J.A.R.V.I.S. HUD UI** (`gui.py`): animated arc-reactor status indicator, dark cockpit theme, monospace HUD text.

## Permanent Memory (Naya)
Jarvis ab facts/preferences permanently yaad rakh sakta hai (`jarvis_memory.json`
mein save hote hain, app band karne ke baad bhi rahenge):
- "mera naam Aditya hai, yaad rakhna" -> save
- "mera naam kya hai" -> recall
- "mujhe kya kya yaad hai" -> sab facts list
- "X bhula do" -> ek fact delete
Ye facts har request ke system prompt mein automatically inject hote hain,
isliye bina bataye bhi Jarvis ko context milta rehta hai.

Iske alawa `jarvis_history.json` mein last 10 conversation turns bhi save
hote hain (gui.py/main.py/server.py teeno shared file use karte hain), isliye
multi-step commands jaise "isko band karke dusra bajao" ka context Jarvis ko
pehle se hi pata hota hai.

## Destructive Actions (Confirmation Maangega)
`delete_file`, `shutdown`, `restart`, `kill_process`, `empty_recycle_bin`

Phone se ye actions disabled hain (safety ke liye) - sirf laptop GUI se hote hain.

## STOP Button (Naya - Galti se bola command rokna)
GUI ke header mein ab ek red **STOP** button hai (MUTE ke bagal mein).
Isse ye hota hai:
1. Chalu bol rahi TTS awaaz turant kaat deta hai (Windows pe reliably;
   Mac/Linux pe best-effort, `pyttsx3` fallback pe `engine.stop()` try karta hai).
2. Us command mein jo actions abhi tak nahi chale, unhe cancel kar deta hai.
3. Safety net: agar galti se "shutdown" ya "restart" bol diya tha, uska
   5-second wala OS timer bhi cancel karne ki koshish karta hai (`cancel_shutdown`
   action) - kuch chalu nahi tha to ye harmless hai, error nahi dega.

Note: jo action already poora execute ho chuka hai (jaise file delete ho
gayi), usko STOP wapas nahi kar sakta - ye sirf "abhi jo ho raha hai /
aage jo hone wala hai" usko rokta hai.

## Advanced Skills (Naye - Big Feature Pack)
`skills/` folder mein ye naye skill files hain, sab automatically load
hote hain (koi extra setup code nahi likhna padega):

| Skill file | Kya karta hai |
|---|---|
| `calendar_email_skill.py` | Gmail + Outlook email read/send, Google/Outlook Calendar |
| `code_exec_skill.py` | Python/Node code aur shell commands run karna |
| `browser_automation_skill.py` | Playwright se deep browser control - form fill, scraping, multi-tab |
| `cloud_files_skill.py` | Google Drive/OneDrive/Dropbox + bulk rename + smart file search |
| `system_admin_skill.py` | Registry edit, services, scheduled tasks, startup programs (Windows) |
| `network_tools_skill.py` | Ping, traceroute, speedtest, port scan, WiFi diagnostics, VPN |
| `smart_home_skill.py` | Lights/AC/plugs/cameras (Home Assistant / Hue / Kasa-Tapo) |
| `vision_skill.py` | Screen dekh ke samajhna (vision), OCR, AI image generation |
| `integrations_skill.py` | Spotify, Slack, Notion, GitHub, Jira, AWS, Docker, MySQL, MongoDB |
| `memory_context_skill.py` | Lambi project context yaad rakhna, usage pattern summary |
| `security_skill.py` | Startup audit, suspicious-process heuristic check, active connections |
| `youtube_control_skill.py` | YouTube tab yaad rakh ke play/like/subscribe/next/mute - sab usi tab pe |
| `extra_utilities_skill.py` | Weather, translate, Wikipedia summary, news, QR code, unit convert, password, dictionary |
| `whatsapp_web_skill.py` | Naam se (phone number nahi) WhatsApp message + real voice/video call |

**Har skill ke top comment mein poora setup likha hai** (kaunsi
library install karo, kaunsi `.env` key ya credentials file chahiye).
Jo setup nahi kiya hoga uske actions bas clear error bolenge ("X
missing, ye install/setup karo") - Jarvis crash nahi karega.

Sab optional Python packages ek jagah: `requirements-optional.txt`
(sab ek saath install: `pip install -r requirements-optional.txt`,
ya sirf jo chahiye wahi ek-ek karke).

### Jo jaan-bujh kar NAHI banaya, aur kyun
- **Voice cloning / "real J.A.R.V.I.S. voice"**: Movie wali J.A.R.V.I.S.
  (Paul Bettany) ki awaaz copyrighted character hai, aur real logon
  ki awaaz clone karna aajkal fraud/impersonation scams mein misuse
  hota hai - isliye ye skill pack voice cloning implement nahi karta.
  Sabse paas wala free alternative already `.env` mein hai:
  `TTS_VOICE=en-US-ChristopherNeural` (calm/deep male, "Jarvis jaisa
  vibe") ya `en-GB-RyanNeural`. Poori list: `edge-tts --list-voices`.
- **Real antivirus/malware engine**: `security_skill.py` sirf basic
  heuristic checks deta hai (startup audit, unusual processes) - ye
  Windows Defender ya kisi trusted AV ka replacement NAHI hai, sirf
  ek quick extra signal hai.
- **True multi-device (mobile+laptop+watch) real-time sync**: Isके
  liye ek hosted backend server chahiye hota hai (jo har jagah se
  reachable ho). Abhi jo hai - `jarvis_memory.json`/`jarvis_context.json`
  ek hi machine ke andar gui.py/main.py/server.py teeno mein already
  shared hain, aur `server.py` phone ko same-WiFi pe control deta hai.
  Agar tumhe sach mein alag-alag physical devices (jaise dusre shehar
  se phone) se sync chahiye, uske liye ek chhota cloud backend
  (Supabase real-time jaisa - jo tum "For Future" app mein already use
  kar rahe ho) banana padega, jo ek alag bada project hoga.

## Naya Command Add Karna Ho To
1. `actions.py` mein naya function likho + `ACTION_MAP` mein register karo
2. `brain.py` ke `TOOLS_DEFINITION` mein description add karo

## Skills System (Naya - Modular Way)
Ab naya action add karne ke liye `actions.py` ya `brain.py` chhedna
zaroori NAHI hai. Bas `skills/` folder ke andar ek naya `.py` file
banao (jaise `skills/weather_skill.py`) aur usme do cheezein define
karo:
```python
ACTIONS = {"action_name": function}   # function(params) -> string
DOCS = "..."                          # LLM ko action samjhaane wala text
```
Jarvis restart karte hi naya skill automatically load ho jayega.
Poora working example `skills/example_skill.py` mein hai (coin flip,
dice roll, currency convert) - usko copy karke apna skill banao, ya
delete kar do agar nahi chahiye.

## Strong Thinking (Reasoning) On Karna Ho To
`.env` mein:
```
REASONING_ENABLED=true
REASONING_EFFORT=high   # low / medium / high
```
Isse Jarvis complex ya multi-step commands pe pehle "soch" ke
(chain-of-thought) jawab dega - zyada accurate hoga par thoda slow.
Note: sab free models reasoning support nahi karte - agar koi error
aaye to `OPENROUTER_MODEL` ko kisi reasoning-capable model (jaise
`deepseek/deepseek-r1:free`) se badal ke dekho.

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
