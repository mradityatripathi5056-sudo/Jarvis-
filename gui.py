"""
gui.py
Jarvis ka GUI version - MAIN FILE, isko chalao (python gui.py).
Iron Man / J.A.R.V.I.S. HUD-style theme: glowing arc-reactor indicator,
dark cockpit color scheme, monospace HUD text.
"""

import threading
import time
import queue
import logging
import math
import re
import webbrowser
import tkinter as tk
from tkinter import scrolledtext, font as tkfont
from datetime import datetime

import config
import brain
import actions
import speech
from speech import speak, listen, listen_for_wake_word

logging.basicConfig(
    filename=config.LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
)

CONVERSATION_TIMEOUT = 20

ui_queue = queue.Queue()
is_running = True
is_muted = False

# Galti se koi command bol/type ho jaaye to STOP button ye set kar deta hai -
# handle_command() har action se pehle ise check karta hai aur baaki queued
# actions cancel kar deta hai (jo action already chal chuka hai wo ruk nahi
# sakta, lekin agla nahi chalega).
stop_event = threading.Event()

# Pichla destructive/self-upgrade action jiske liye confirmation maangi gayi
# thi (jab tak user "haan"/"yes" na bole, ye set rehta hai).
_pending_confirm = {"action": None, "params": None}

# ---- Iron Man HUD color palette ----
BG_DARK = "#04070c"
BG_PANEL = "#0a1018"
BG_INPUT = "#0f1824"
ACCENT = "#00d4ff"        # arc-reactor cyan
ACCENT_DIM = "#5a7a8c"    # idle/dim cyan-grey
ACCENT_RED = "#ff3b3b"    # repulsor red / alert
ACCENT_GREEN = "#39ff9d"  # listening green
ACCENT_YELLOW = "#ffcc33" # thinking amber
TEXT_MAIN = "#d6f3ff"
TEXT_DIM = "#5f7d8c"
HUD_FONT = ("Consolas", 10)
HUD_FONT_BOLD = ("Consolas", 10, "bold")

# ---- Selectable color themes ----
# "theme ko red/green/purple/gold/white kar do" jaisa bolne pe accent
# color badal jaata hai (background/layout same rehta hai, sirf glow/
# highlight color badalta hai). Status colors (listening=green, thinking=
# amber, stop=red) semantic hain isliye inhe theme se nahi chheda.
THEMES = {
    "cyan": "#00d4ff",
    "red": "#ff3b6b",
    "green": "#39ff9d",
    "purple": "#b366ff",
    "gold": "#ffcc33",
    "white": "#e8f4ff",
}


def _lighten(hex_color: str, factor: float = 0.6) -> str:
    """Hex color ko white ki taraf blend karta hai (glow/core effect ke liye)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


class ArcReactor(tk.Canvas):
    """Chhota rotating HUD indicator - Iron Man ke arc reactor jaisa dikhta
    hai. Rang aur speed status ke hisaab se badalte hain (idle/listening/
    thinking/error). Idle mein ek halka "breathing" pulse bhi hota hai
    (core glow bada-chhota hota rehta hai) - taaki bilkul static/simple na
    lage."""

    def __init__(self, parent, size=64, bg=BG_PANEL):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size
        self.angle = 0
        self.color = ACCENT_DIM
        self.speed = 2
        self._pulse_t = 0.0
        self._running = True
        self._draw()
        self.after(40, self._animate)

    def set_color(self, color: str, speed: int = 3):
        self.color = color
        self.speed = speed

    def stop(self):
        self._running = False

    def _animate(self):
        if not self._running:
            return
        self.angle = (self.angle + self.speed) % 360
        self._pulse_t += 0.12
        self._draw()
        self.after(40, self._animate)

    def _draw(self):
        self.delete("all")
        s = self.size
        cx, cy = s / 2, s / 2
        r_outer = s / 2 - 3
        r_mid = s / 2 - 12
        r_core_base = s / 2 - 21
        pulse = 1.0 + 0.12 * math.sin(self._pulse_t)  # 0.88x - 1.12x breathing
        r_core = r_core_base * pulse
        glow = _lighten(self.color, 0.55)

        for i in range(8):
            start = self.angle + i * 45
            self.create_arc(
                cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
                start=start, extent=22, style="arc", outline=self.color, width=2,
            )
        for i in range(6):
            start = -(self.angle * 1.6) + i * 60
            self.create_arc(
                cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid,
                start=start, extent=28, style="arc", outline=glow, width=2,
            )
        self.create_oval(
            cx - r_core, cy - r_core, cx + r_core, cy + r_core,
            fill=self.color, outline=glow, width=1,
        )
        self.create_oval(
            cx - r_core * 0.45, cy - r_core * 0.45, cx + r_core * 0.45, cy + r_core * 0.45,
            fill=glow, outline="",
        )


class JarvisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("J.A.R.V.I.S. — AI ASSISTANT")
        self.root.geometry("620x740")
        self.root.configure(bg=BG_DARK)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Har (widget, {prop: "accent"/"accent_dim"}) yahan register hota
        # hai jaise widget banta hai - apply_theme() isi list ko loop karke
        # live re-color kar deta hai, bina GUI restart kiye.
        self.theme_widgets = []

        title_font = tkfont.Font(family="Consolas", size=20, weight="bold")
        subtitle_font = tkfont.Font(family="Consolas", size=8)

        # ---- Header (arc reactor + title) ----
        header = tk.Frame(root, bg=BG_PANEL, height=90, highlightbackground=ACCENT_DIM, highlightthickness=1)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        self.theme_widgets.append((header, {"highlightbackground": "accent_dim"}))

        self.reactor = ArcReactor(header, size=64, bg=BG_PANEL)
        self.reactor.pack(side="left", padx=(18, 10), pady=10)

        title_block = tk.Frame(header, bg=BG_PANEL)
        title_block.pack(side="left", pady=10)
        title_label = tk.Label(
            title_block, text="J . A . R . V . I . S .", bg=BG_PANEL, fg=ACCENT, font=title_font
        )
        title_label.pack(anchor="w")
        self.theme_widgets.append((title_label, {"fg": "accent"}))
        self.status_var = tk.StringVar(value="INITIALIZING...")
        tk.Label(
            title_block, textvariable=self.status_var, bg=BG_PANEL, fg=TEXT_DIM, font=subtitle_font
        ).pack(anchor="w")

        self.mute_btn = tk.Button(
            header, text="MUTE", command=self.toggle_mute, bg="#101a24", fg=ACCENT,
            relief="flat", padx=14, pady=6, font=HUD_FONT_BOLD, activebackground="#182634",
            activeforeground=ACCENT, bd=1, highlightbackground=ACCENT_DIM, highlightthickness=1,
        )
        self.mute_btn.pack(side="right", padx=20)
        self.theme_widgets.append((self.mute_btn, {"fg": "accent", "activeforeground": "accent", "highlightbackground": "accent_dim"}))

        self.stop_btn = tk.Button(
            header, text="STOP", command=self.emergency_stop, bg="#2a0a0a", fg=ACCENT_RED,
            relief="flat", padx=14, pady=6, font=HUD_FONT_BOLD, activebackground="#3a1010",
            activeforeground=ACCENT_RED, bd=1, highlightbackground=ACCENT_RED, highlightthickness=1,
        )
        self.stop_btn.pack(side="right", padx=(0, 8))

        self.dev_btn = tk.Button(
            header, text="DEV", command=self.show_dev_info, bg="#101a24", fg=ACCENT,
            relief="flat", padx=14, pady=6, font=HUD_FONT_BOLD, activebackground="#182634",
            activeforeground=ACCENT, bd=1, highlightbackground=ACCENT_DIM, highlightthickness=1,
        )
        self.dev_btn.pack(side="right", padx=(0, 8))
        self.theme_widgets.append((self.dev_btn, {"fg": "accent", "activeforeground": "accent", "highlightbackground": "accent_dim"}))

        # ---- Quick actions ----
        quick_frame = tk.Frame(root, bg=BG_DARK)
        quick_frame.pack(fill="x", padx=15, pady=(12, 5))
        quick_row1 = tk.Frame(quick_frame, bg=BG_DARK)
        quick_row1.pack(fill="x")
        quick_row2 = tk.Frame(quick_frame, bg=BG_DARK)
        quick_row2.pack(fill="x", pady=(4, 0))

        quick_actions = [
            ("SCREENSHOT", "screenshot le lo"),
            ("BATTERY", "battery kitni hai"),
            ("APPS", "chal rahe apps dikhao"),
            ("WIFI", "wifi/network status batao"),
            ("LOCK", "screen lock kar do"),
            ("VOL+", "volume 10 percent badhao"),
            ("VOL-", "volume 10 percent kam karo"),
            ("MUSIC", "gaana bajao"),
            ("YOUTUBE", "youtube khol do"),
            ("SYSINFO", "system info batao"),
            ("CLEAR", "__clear__"),
        ]
        mid = (len(quick_actions) + 1) // 2
        for i, (label, cmd) in enumerate(quick_actions):
            target_row = quick_row1 if i < mid else quick_row2
            btn = tk.Button(
                target_row, text=label, bg=BG_INPUT, fg=ACCENT, relief="flat",
                padx=8, pady=7, font=("Consolas", 9, "bold"), activebackground="#182634",
                activeforeground=ACCENT, bd=1, highlightbackground=ACCENT_DIM, highlightthickness=1,
                command=lambda c=cmd: self.quick_action(c),
            )
            btn.pack(side="left", padx=4, fill="x", expand=True)
            self.theme_widgets.append((btn, {"fg": "accent", "activeforeground": "accent", "highlightbackground": "accent_dim"}))

        # ---- Chat / HUD log ----
        chat_container = tk.Frame(root, bg=BG_DARK, highlightbackground=ACCENT_DIM, highlightthickness=1)
        chat_container.pack(fill="both", expand=True, padx=15, pady=10)
        self.theme_widgets.append((chat_container, {"highlightbackground": "accent_dim"}))

        self.chat_log = scrolledtext.ScrolledText(
            chat_container, wrap=tk.WORD, bg=BG_PANEL, fg=TEXT_MAIN,
            font=HUD_FONT, relief="flat", padx=15, pady=15, bd=0, insertbackground=ACCENT,
        )
        self.chat_log.pack(fill="both", expand=True)
        self.chat_log.config(state="disabled")
        self.chat_log.tag_config("user", foreground=ACCENT, font=HUD_FONT_BOLD)
        self.chat_log.tag_config("jarvis", foreground=ACCENT_GREEN, font=HUD_FONT_BOLD)
        self.chat_log.tag_config("dim", foreground=TEXT_DIM, font=("Consolas", 8))
        self.theme_widgets.append((self.chat_log, {"insertbackground": "accent"}))

        # ---- Input ----
        input_frame = tk.Frame(root, bg=BG_DARK)
        input_frame.pack(fill="x", padx=15, pady=(0, 15))

        entry_wrap = tk.Frame(input_frame, bg=BG_INPUT, highlightbackground=ACCENT_DIM, highlightthickness=1)
        entry_wrap.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.theme_widgets.append((entry_wrap, {"highlightbackground": "accent_dim"}))
        self.text_input = tk.Entry(
            entry_wrap, bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=ACCENT,
            font=HUD_FONT, relief="flat",
        )
        self.text_input.pack(fill="both", expand=True, ipady=10, padx=8)
        self.text_input.bind("<Return>", self.send_typed_command)
        self.text_input.focus()
        self.theme_widgets.append((self.text_input, {"insertbackground": "accent"}))

        self.send_btn = tk.Button(
            input_frame, text="SEND", command=self.send_typed_command,
            bg=ACCENT, fg="#03070b", relief="flat", padx=20, font=HUD_FONT_BOLD, bd=0,
            activebackground=_lighten(ACCENT, 0.3),
        )
        self.send_btn.pack(side="right")
        self.theme_widgets.append((self.send_btn, {"bg": "accent"}))

        self.log("JARVIS", "System online. 'Jarvis' bolke shuru karo, ya neeche type karo.")
        self.root.after(200, self.poll_queue)

    def show_dev_info(self):
        win = tk.Toplevel(self.root)
        win.title("Developer Info")
        win.configure(bg=BG_PANEL)
        win.geometry("360x200")
        win.resizable(False, False)
        win.transient(self.root)

        tk.Label(
            win, text="J . A . R . V . I . S .", bg=BG_PANEL, fg=ACCENT,
            font=("Consolas", 14, "bold"),
        ).pack(pady=(18, 4))
        tk.Label(
            win, text="Developer: Aditya Tripathi", bg=BG_PANEL, fg=TEXT_MAIN,
            font=HUD_FONT_BOLD,
        ).pack(pady=(6, 2))
        tk.Label(
            win, text="SoftCode Studios", bg=BG_PANEL, fg=TEXT_DIM, font=HUD_FONT,
        ).pack()

        repo_url = "https://github.com/mradityatripathi5056-sudo/Jarvis-"
        link = tk.Label(
            win, text=repo_url, bg=BG_PANEL, fg=ACCENT, font=("Consolas", 9, "underline"),
            cursor="hand2",
        )
        link.pack(pady=(14, 4))
        link.bind("<Button-1>", lambda e: webbrowser.open(repo_url))

        tk.Button(
            win, text="CLOSE", command=win.destroy, bg=BG_INPUT, fg=ACCENT, relief="flat",
            padx=14, pady=4, font=HUD_FONT_BOLD, bd=1, highlightbackground=ACCENT_DIM,
            highlightthickness=1,
        ).pack(pady=10)

    def apply_theme(self, name: str):
        """Live GUI re-theme - color-role based widgets ko naye accent
        color se reconfigure karta hai. Status colors (listening/thinking/
        stop) semantic hain, badalte nahi."""
        global ACCENT, ACCENT_DIM
        new_accent = THEMES.get(name)
        if not new_accent:
            return
        ACCENT = new_accent
        ACCENT_DIM = self._dim(new_accent)

        for widget, props in self.theme_widgets:
            try:
                kwargs = {}
                for prop, role in props.items():
                    kwargs[prop] = ACCENT if role == "accent" else ACCENT_DIM
                widget.config(**kwargs)
            except Exception:
                pass
        try:
            self.chat_log.tag_config("user", foreground=ACCENT)
            self.send_btn.config(activebackground=_lighten(ACCENT, 0.3))
        except Exception:
            pass
        self.log("JARVIS", f"Theme '{name}' laga diya.")

    @staticmethod
    def _dim(hex_color: str) -> str:
        """Accent color ka desaturated/muted variant banata hai (dim/idle
        border ke liye) - white ki taraf blend karne ke bajaye grey ki
        taraf halka blend karta hai."""
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        grey = (r + g + b) / 3
        r = int(r + (grey - r) * 0.55)
        g = int(g + (grey - g) * 0.55)
        b = int(b + (grey - b) * 0.55)
        return f"#{r:02x}{g:02x}{b:02x}"

    def log(self, sender: str, text: str):
        self.chat_log.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = "user" if sender == "AAP" else "jarvis"
        self.chat_log.insert(tk.END, f"[{timestamp}] {sender} :: ", tag)
        if sender == "JARVIS":
            # Typewriter effect - JARVIS ke jawab letter-by-letter aate hain
            # (sci-fi HUD jaisa feel) - user ka apna text turant dikhta hai.
            self.chat_log.see(tk.END)
            self.chat_log.config(state="disabled")
            self._type_out(text, 0)
        else:
            self.chat_log.insert(tk.END, f"{text}\n\n")
            self.chat_log.see(tk.END)
            self.chat_log.config(state="disabled")

    def _type_out(self, text: str, index: int):
        # Bahut lambe messages animate karne mein waqt na lage isliye
        # limit ke baad chunk-size badha dete hain.
        chunk = 3 if len(text) > 200 else 1
        self.chat_log.config(state="normal")
        self.chat_log.insert(tk.END, text[index:index + chunk])
        self.chat_log.see(tk.END)
        if index + chunk < len(text):
            self.chat_log.config(state="disabled")
            self.root.after(12, lambda: self._type_out(text, index + chunk))
        else:
            self.chat_log.insert(tk.END, "\n\n")
            self.chat_log.see(tk.END)
            self.chat_log.config(state="disabled")

    def clear_chat(self):
        self.chat_log.config(state="normal")
        self.chat_log.delete("1.0", tk.END)
        self.chat_log.config(state="disabled")

    def set_status(self, text: str, color: str):
        self.status_var.set(text.upper())
        speed_map = {ACCENT_GREEN: 8, ACCENT_YELLOW: 10, ACCENT_RED: 1, "red": 1, "gray": 2}
        color_map = {"gray": ACCENT_DIM, "red": ACCENT_RED}
        resolved = color_map.get(color, color)
        self.reactor.set_color(resolved, speed_map.get(color, 3))

    def toggle_mute(self):
        global is_muted
        is_muted = not is_muted
        config.IS_MUTED = is_muted
        self.mute_btn.config(text="UNMUTE" if is_muted else "MUTE")
        self.set_status("Muted" if is_muted else "Ready", ACCENT_YELLOW if is_muted else "gray")

    def emergency_stop(self):
        """STOP button - galti se bola/type kiya command turant rok deta hai:
        1) chalu TTS awaaz kaat deta hai (Windows pe turant, Mac/Linux pe best-effort)
        2) baaki queued actions is command ke cancel kar deta hai
        3) safety net: agar galti se shutdown/restart bol diya tha, uska
           5-second OS timer bhi cancel karne ki koshish karta hai (agar
           kuch chalu nahi tha, ye harmless no-op hai)"""
        stop_event.set()
        speech.stop_speaking()
        try:
            actions.cancel_shutdown({})
        except Exception:
            pass
        self.log("JARVIS", "Rok diya! Chalu command cancel kar diya.")
        self.set_status("Stopped", ACCENT_RED)

    def quick_action(self, cmd: str):
        if cmd == "__clear__":
            self.clear_chat()
            return
        self.log("AAP", cmd)
        threading.Thread(target=process_command_thread, args=(cmd,), daemon=True).start()

    def send_typed_command(self, event=None):
        text = self.text_input.get().strip()
        if not text:
            return
        self.text_input.delete(0, tk.END)
        self.log("AAP", text)
        threading.Thread(target=process_command_thread, args=(text,), daemon=True).start()

    def poll_queue(self):
        try:
            while True:
                msg_type, payload = ui_queue.get_nowait()
                if msg_type == "status":
                    text, color = payload
                    self.set_status(text, color)
                elif msg_type == "user_said":
                    self.log("AAP", payload)
                elif msg_type == "jarvis_said":
                    self.log("JARVIS", payload)
        except queue.Empty:
            pass
        if config.PENDING_THEME:
            self.apply_theme(config.PENDING_THEME)
            config.PENDING_THEME = None
        self.root.after(200, self.poll_queue)

    def on_close(self):
        global is_running
        is_running = False
        self.reactor.stop()
        self.root.destroy()


def process_command_thread(text: str):
    ui_queue.put(("status", ("Soch raha hoon...", ACCENT_YELLOW)))
    try:
        result_text = handle_command(text, speak_output=False)
    except Exception as e:
        # SAFETY NET: agar handle_command ke andar koi na-socha-hua error
        # bach jaaye, to ye thread chup-chaap crash ho jaata tha aur UI
        # "Soch raha hoon..." pe hamesha ke liye atki reh jaati thi, user ko
        # kabhi koi jawab nahi milta. Ab hamesha ek reply milega.
        logging.error(f"[gui] process_command_thread error: {e}")
        result_text = f"Kuch galat ho gaya, lekin main chalta rahunga: {e}"
    ui_queue.put(("jarvis_said", result_text))
    speak(result_text)
    ui_queue.put(("status", ("Ready", "gray")))


def handle_command(user_text: str, speak_output: bool = True) -> str:
    global _pending_confirm
    stop_event.clear()

    # Pichli baar koi destructive/self-upgrade action confirm karne ke liye
    # pucha gaya tha - to iss baar jo bhi bola/type kiya gaya hai (chahe
    # voice se ho ya text box se) wahi uska jawab maana jaayega.
    if _pending_confirm["action"]:
        action_name = _pending_confirm["action"]
        params = _pending_confirm["params"]
        _pending_confirm = {"action": None, "params": None}

        lowered = user_text.strip().lower()
        confirmed = re.search(r"\b(haan|ha|yes|yeah|yup|sure|ok|okay)\b", lowered) is not None

        if not confirmed:
            result_text = "Theek hai, cancel kar diya."
        else:
            func = actions.ACTION_MAP.get(action_name)
            if func:
                result_text = actions.run_action_with_retry(func, params, action_name)
            else:
                result_text = f"'{action_name}' command samajh nahi aaya."

        brain.save_action_results([result_text])
        return result_text

    action_list = brain.ask_llm(user_text)
    results = []

    for decision in action_list:
        if stop_event.is_set():
            results.append("Rok diya gaya - baaki commands cancel kar diye.")
            break

        action_name = decision.get("action")
        params = decision.get("params", {})

        if action_name == "general_chat":
            results.append(params.get("reply", "Samajh nahi paya, dobara boliye."))
            continue

        if action_name in config.DESTRUCTIVE_ACTIONS:
            _pending_confirm = {"action": action_name, "params": params}
            results.append(f"Kya aap sure hain {action_name} karna hai? Haan ya Nahi boliye.")
            break  # agla jo bhi bolo/type karo, wahi confirmation ka jawab maana jaayega

        func = actions.ACTION_MAP.get(action_name)
        if func:
            result = actions.run_action_with_retry(func, params, action_name)
        else:
            result = f"'{action_name}' command samajh nahi aaya."
        results.append(result)

    brain.save_action_results(results)

    final_text = " ".join(results)
    if speak_output and not stop_event.is_set():
        speak(final_text)
    return final_text


def voice_loop():
    conversation_mode = False
    last_activity = time.time()

    ui_queue.put(("status", ("Jarvis online - 'Jarvis' bolo", "gray")))
    speak("Jarvis online hai. Main sun raha hoon.")

    while is_running:
        try:
            if is_muted:
                time.sleep(0.5)
                continue

            if not conversation_mode:
                ui_queue.put(("status", ("'Jarvis' bolne ka wait...", "gray")))
                heard = listen_for_wake_word(config.WAKE_WORD)
                if heard:
                    conversation_mode = True
                    last_activity = time.time()
                    ui_queue.put(("status", ("Sun raha hoon", ACCENT_GREEN)))
                    speak("Ji boliye?")
            else:
                ui_queue.put(("status", ("Sun raha hoon...", ACCENT_GREEN)))
                command = listen(timeout=CONVERSATION_TIMEOUT, phrase_time_limit=10)

                if not command:
                    if time.time() - last_activity > CONVERSATION_TIMEOUT:
                        conversation_mode = False
                        ui_queue.put(("status", ("'Jarvis' bolne ka wait...", "gray")))
                    continue

                last_activity = time.time()
                ui_queue.put(("user_said", command))

                if any(word in command for word in ["band ho jao", "so jao", "chup ho jao", "bas karo"]):
                    speak("Theek hai, conversation band kar raha hoon.")
                    conversation_mode = False
                    continue

                ui_queue.put(("status", ("Soch raha hoon...", ACCENT_YELLOW)))
                reply = handle_command(command)
                ui_queue.put(("jarvis_said", reply))
                last_activity = time.time()
        except Exception as e:
            logging.error(f"voice_loop error: {e}")
            ui_queue.put(("status", (f"Error: {e}", "red")))
            conversation_mode = False
            time.sleep(1)


def telegram_contacts_background():
    """Har 30 second mein Telegram check karke naye contacts (jinhon ne
    bot ko /start kiya) apne aap save karta rehta hai."""
    while True:
        try:
            if config.TELEGRAM_BOT_TOKEN:
                actions.sync_telegram_contacts()
        except Exception:
            pass
        time.sleep(30)


def main():
    root = tk.Tk()
    app = JarvisGUI(root)
    voice_thread = threading.Thread(target=voice_loop, daemon=True)
    voice_thread.start()
    threading.Thread(target=telegram_contacts_background, daemon=True).start()

    # Telegram remote-control listener bhi Jarvis GUI ke saath hi turant
    # start ho jaaye - alag se "python telegram_command_listener.py"
    # manually chalane ki zaroorat nahi. Chunki setup_autostart.py already
    # gui.py ko Windows Startup mein daal deta hai, isliye laptop on hote
    # hi Telegram automatically connect ho jayega.
    try:
        import telegram_command_listener
        if telegram_command_listener.start_background():
            logging.info("Telegram listener background mein start ho gaya.")
        else:
            logging.info("Telegram listener start nahi hua - TELEGRAM_BOT_TOKEN ya allowed chat ID .env mein set nahi hai.")
    except Exception as e:
        logging.error(f"Telegram listener start karte waqt error: {e}")

    root.mainloop()


if __name__ == "__main__":
    main()
