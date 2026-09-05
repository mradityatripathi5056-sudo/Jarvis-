"""
server.py
Laptop pe ek local web server chalata hai jisse phone browser se Jarvis
ko control kar sake.

Chalane ka tarika:
    python server.py
Fir phone ke browser mein: http://<laptop-ka-IP>:5000
"""

import socket
import threading
import time
from flask import Flask, render_template_string, request, jsonify

import config
import brain
import actions

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jarvis - Remote Control</title>
<style>
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; height: 100%; font-family: 'Segoe UI', sans-serif;
    background: #0a0e14; color: #e6edf3;
  }
  body { display: flex; flex-direction: column; }
  header {
    background: #131820; padding: 16px 20px; display: flex;
    align-items: center; justify-content: space-between; flex-shrink: 0;
  }
  header h1 { font-size: 20px; color: #00d4ff; margin: 0; }
  .status { font-size: 12px; color: #8b949e; }
  #chat {
    flex: 1; overflow-y: auto; padding: 16px; background: #0a0e14;
  }
  .msg { margin-bottom: 14px; }
  .msg .sender { font-weight: bold; font-size: 13px; }
  .msg.user .sender { color: #00d4ff; }
  .msg.jarvis .sender { color: #3fb950; }
  .msg .text { margin-top: 3px; font-size: 15px; line-height: 1.4; white-space: pre-wrap; }
  .quick-actions {
    display: flex; gap: 8px; padding: 10px 16px; overflow-x: auto;
    background: #0a0e14; flex-shrink: 0;
  }
  .quick-actions button {
    background: #1c2330; color: #e6edf3; border: none; border-radius: 8px;
    padding: 8px 14px; font-size: 13px; white-space: nowrap;
  }
  .input-bar {
    display: flex; gap: 8px; padding: 14px 16px; background: #131820;
    flex-shrink: 0;
  }
  .input-bar input {
    flex: 1; background: #1c2330; border: none; border-radius: 10px;
    padding: 14px; color: #e6edf3; font-size: 15px; outline: none;
  }
  .input-bar button {
    border: none; border-radius: 10px; padding: 0 18px; font-size: 16px;
  }
  #sendBtn { background: #00d4ff; color: #0a0e14; font-weight: bold; }
  #micBtn { background: #1c2330; color: #e6edf3; }
  #micBtn.listening { background: #f85149; color: white; }
</style>
</head>
<body>

<header>
  <h1>JARVIS</h1>
  <div class="status" id="status">Ready</div>
</header>

<div class="quick-actions">
  <button onclick="quickAction('screenshot le lo')">Screenshot</button>
  <button onclick="quickAction('battery kitni hai')">Battery</button>
  <button onclick="quickAction('system info batao')">System Info</button>
  <button onclick="quickAction('chal rahe apps dikhao')">Apps</button>
  <button onclick="clearChat()">Clear</button>
</div>

<div id="chat"></div>

<div class="input-bar">
  <button id="micBtn" onclick="toggleMic()">Mic</button>
  <input type="text" id="textInput" placeholder="Command likho ya bolo..."
         onkeypress="if(event.key==='Enter') sendCommand()">
  <button id="sendBtn" onclick="sendCommand()">Send</button>
</div>

<script>
const chat = document.getElementById('chat');
const statusEl = document.getElementById('status');
const textInput = document.getElementById('textInput');

function addMessage(sender, text) {
  const div = document.createElement('div');
  div.className = 'msg ' + (sender === 'Aap' ? 'user' : 'jarvis');
  const senderDiv = document.createElement('div');
  senderDiv.className = 'sender';
  senderDiv.textContent = sender;
  const textDiv = document.createElement('div');
  textDiv.className = 'text';
  textDiv.textContent = text;
  div.appendChild(senderDiv);
  div.appendChild(textDiv);
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function clearChat() {
  chat.innerHTML = '';
}

function speakReply(text) {
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'hi-IN';
  speechSynthesis.speak(utterance);
}

async function sendCommand(overrideText) {
  const text = overrideText || textInput.value.trim();
  if (!text) return;
  textInput.value = '';
  addMessage('Aap', text);
  statusEl.innerText = 'Soch raha hoon...';

  try {
    const res = await fetch('/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    });
    const data = await res.json();
    addMessage('Jarvis', data.reply);
    speakReply(data.reply);
  } catch (e) {
    addMessage('Jarvis', 'Laptop se connect nahi ho paya. Same WiFi par ho check karo.');
  }
  statusEl.innerText = 'Ready';
}

function quickAction(cmd) {
  sendCommand(cmd);
}

let recognition;
let isListening = false;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = 'hi-IN';
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    sendCommand(transcript);
  };
  recognition.onend = () => {
    isListening = false;
    document.getElementById('micBtn').classList.remove('listening');
  };
  recognition.onerror = () => {
    isListening = false;
    document.getElementById('micBtn').classList.remove('listening');
  };
} else {
  document.getElementById('micBtn').style.display = 'none';
}

function toggleMic() {
  if (!recognition) return;
  if (isListening) {
    recognition.stop();
  } else {
    recognition.start();
    isListening = true;
    document.getElementById('micBtn').classList.add('listening');
  }
}

addMessage('Jarvis', 'Namaste! Phone se laptop control karne ke liye ready hoon. Type karo ya mic button dabao.');
</script>

</body>
</html>
"""


_pending_destructive = {"action": None, "params": None}


def _process_new_command(user_text: str) -> str:
    global _pending_destructive

    action_list = brain.ask_llm(user_text)
    results = []

    for decision in action_list:
        action_name = decision.get("action")
        params = decision.get("params", {})

        if action_name == "general_chat":
            results.append(params.get("reply", "Samajh nahi paya, dobara boliye."))
            continue

        if action_name in config.DESTRUCTIVE_ACTIONS:
            _pending_destructive = {"action": action_name, "params": params}
            results.append(f"'{action_name}' pakka karna hai? PIN bhejo confirm karne ke liye.")
            break  # jab tak confirm na ho, aage ke steps ruk jaayein

        func = actions.ACTION_MAP.get(action_name)
        if func:
            result = actions.run_action_with_retry(func, params, action_name)
        else:
            result = f"'{action_name}' command samajh nahi aaya."
        results.append(result)

    brain.save_action_results(results)
    return " ".join(r for r in results if r)


def handle_command(user_text: str) -> str:
    """LLM se action(s) decide karke execute karta hai - GUI jaisa hi logic.
    Destructive actions (shutdown/restart/delete/etc) phone se allowed hain,
    lekin ek PIN confirm karna padta hai - safety ke liye taaki koi aur
    same-WiFi device galti se ya jaan-boojh kar laptop shutdown na kar de."""
    global _pending_destructive

    if _pending_destructive["action"]:
        entered = user_text.strip()
        action_name = _pending_destructive["action"]
        params = _pending_destructive["params"]
        _pending_destructive = {"action": None, "params": None}

        if entered == config.PHONE_PIN:
            func = actions.ACTION_MAP.get(action_name)
            if not func:
                result = f"'{action_name}' command samajh nahi aaya."
                brain.save_action_results([result])
                return result
            result = actions.run_action_with_retry(func, params, action_name)
            brain.save_action_results([result])
            return result

        # PROBLEM jo fix ho raha hai: pehle yahan PIN galat/na-diya jaane
        # par seedha "PIN galat tha, cancel kar diya" bol ke ruk jaata tha -
        # agar user ne actually ek bilkul NAYA command bhej diya tha (PIN
        # maangne ke baad, jaise "autopilot band karo"), wo command kabhi
        # process hi nahi hota tha, chup-chaap nigal liya jaata tha. Ab
        # purana destructive action safely cancel ho jaata hai (execute
        # NAHI hota), lekin jo bhi naya text aaya hai use turant normal
        # command ki tarah process kiya jaata hai.
        return _process_new_command(user_text)

    return _process_new_command(user_text)


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


@app.route("/command", methods=["POST"])
def command():
    data = request.get_json()
    user_text = data.get("text", "").strip()
    if not user_text:
        return jsonify({"reply": "Kuch bola nahi gaya."})
    reply = handle_command(user_text)
    return jsonify({"reply": reply})


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _telegram_contacts_background():
    """Har 30 second mein Telegram check karke naye contacts (jinhon ne
    bot ko /start kiya) apne aap save karta rehta hai."""
    while True:
        try:
            if config.TELEGRAM_BOT_TOKEN:
                actions.sync_telegram_contacts()
        except Exception:
            pass
        time.sleep(30)


if __name__ == "__main__":
    local_ip = get_local_ip()
    print("=" * 50)
    print("JARVIS SERVER STARTED")
    print("Phone ke browser mein ye URL kholo (same WiFi zaroori hai):")
    print(f"   http://{local_ip}:5000")
    print("=" * 50)
    threading.Thread(target=_telegram_contacts_background, daemon=True).start()

    # Agar server pichli baar band hone se pehle koi screen-watch chala
    # raha tha (aur wo expire nahi hua), khud-ba-khud resume kar do -
    # user ko dobara "screen dekho" bolna nahi padega.
    try:
        func = actions.ACTION_MAP.get("_resume_screen_watch_internal")
        resumed = func({}) if func else ""
        if resumed:
            print(f"[Screen watch auto-resumed] {resumed}")
    except Exception as e:
        print(f"[Screen watch resume error] {e}")

    app.run(host="0.0.0.0", port=5000, debug=False)
