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
    thinking/error)."""

    def __init__(self, parent, size=64, bg=BG_PANEL):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size
        self.angle = 0
        self.color = ACCENT_DIM
        self.speed = 2
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
        self._draw()
        self.after(40, self._animate)

    def _draw(self):
        self.delete("all")
        s = self.size
        cx, cy = s / 2, s / 2
        r_outer = s / 2 - 3
        r_mid = s / 2 - 12
        r_core = s / 2 - 21
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

        title_font = tkfont.Font(family="Consolas", size=20, weight="bold")
        subtitle_font = tkfont.Font(family="Consolas", size=8)

        # ---- Header (arc reactor + title) ----
        header = tk.Frame(root, bg=BG_PANEL, height=90, highlightbackground=ACCENT_DIM, highlightthickness=1)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        self.reactor = ArcReactor(header, size=64, bg=BG_PANEL)
        self.reactor.pack(side="left", padx=(18, 10), pady=10)

        title_block = tk.Frame(header, bg=BG_PANEL)
        title_block.pack(side="left", pady=10)
        tk.Label(
            title_block, text="J . A . R . V . I . S .", bg=BG_PANEL, fg=ACCENT, font=title_font
        ).pack(anchor="w")
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

        self.stop_btn = tk.Button(
            header, text="STOP", command=self.emergency_stop, bg="#2a0a0a", fg=ACCENT_RED,
            relief="flat", padx=14, pady=6, font=HUD_FONT_BOLD, activebackground="#3a1010",
            activeforeground=ACCENT_RED, bd=1, highlightbackground=ACCENT_RED, highlightthickness=1,
        )
        self.stop_btn.pack(side="right", padx=(0, 8))

        # ---- Quick actions ----
        quick_frame = tk.Frame(root, bg=BG_DARK)
        quick_frame.pack(fill="x", padx=15, pady=(12, 5))

        quick_actions = [
            ("SCREENSHOT", "screenshot le lo"),
            ("BATTERY", "battery kitni hai"),
            ("APPS", "chal rahe apps dikhao"),
            ("CLEAR", "__clear__"),
        ]
        for label, cmd in quick_actions:
            tk.Button(
                quick_frame, text=label, bg=BG_INPUT, fg=ACCENT, relief="flat",
                padx=8, pady=7, font=("Consolas", 9, "bold"), activebackground="#182634",
                activeforeground=ACCENT, bd=1, highlightbackground=ACCENT_DIM, highlightthickness=1,
                command=lambda c=cmd: self.quick_action(c),
            ).pack(side="left", padx=4, fill="x", expand=True)

        # ---- Chat / HUD log ----
        chat_container = tk.Frame(root, bg=BG_DARK, highlightbackground=ACCENT_DIM, highlightthickness=1)
        chat_container.pack(fill="both", expand=True, padx=15, pady=10)

        self.chat_log = scrolledtext.ScrolledText(
            chat_container, wrap=tk.WORD, bg=BG_PANEL, fg=TEXT_MAIN,
            font=HUD_FONT, relief="flat", padx=15, pady=15, bd=0, insertbackground=ACCENT,
        )
        self.chat_log.pack(fill="both", expand=True)
        self.chat_log.config(state="disabled")
        self.chat_log.tag_config("user", foreground=ACCENT, font=HUD_FONT_BOLD)
        self.chat_log.tag_config("jarvis", foreground=ACCENT_GREEN, font=HUD_FONT_BOLD)
        self.chat_log.tag_config("dim", foreground=TEXT_DIM, font=("Consolas", 8))

        # ---- Input ----
        input_frame = tk.Frame(root, bg=BG_DARK)
        input_frame.pack(fill="x", padx=15, pady=(0, 15))

        entry_wrap = tk.Frame(input_frame, bg=BG_INPUT, highlightbackground=ACCENT_DIM, highlightthickness=1)
        entry_wrap.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.text_input = tk.Entry(
            entry_wrap, bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=ACCENT,
            font=HUD_FONT, relief="flat",
        )
        self.text_input.pack(fill="both", expand=True, ipady=10, padx=8)
        self.text_input.bind("<Return>", self.send_typed_command)
        self.text_input.focus()

        tk.Button(
            input_frame, text="SEND", command=self.send_typed_command,
            bg=ACCENT, fg="#03070b", relief="flat", padx=20, font=HUD_FONT_BOLD, bd=0,
            activebackground=_lighten(ACCENT, 0.3),
        ).pack(side="right")

        self.log("JARVIS", "System online. 'Jarvis' bolke shuru karo, ya neeche type karo.")
        self.root.after(200, self.poll_queue)

    def log(self, sender: str, text: str):
        self.chat_log.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = "user" if sender == "AAP" else "jarvis"
        self.chat_log.insert(tk.END, f"[{timestamp}] {sender} :: ", tag)
        self.chat_log.insert(tk.END, f"{text}\n\n")
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
        self.root.after(200, self.poll_queue)

    def on_close(self):
        global is_running
        is_running = False
        self.reactor.stop()
        self.root.destroy()


def process_command_thread(text: str):
    ui_queue.put(("status", ("Soch raha hoon...", ACCENT_YELLOW)))
    result_text = handle_command(text, speak_output=False)
    ui_queue.put(("jarvis_said", result_text))
    speak(result_text)
    ui_queue.put(("status", ("Ready", "gray")))


def handle_command(user_text: str, speak_output: bool = True) -> str:
    stop_event.clear()
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
            ui_queue.put(("jarvis_said", f"Kya aap sure hain {action_name} karna hai? Haan ya Nahi boliye."))
            speak(f"Kya aap sure hain {action_name} karna hai? Haan ya Nahi boliye.")
            confirm_text = listen(timeout=5, phrase_time_limit=3)
            if stop_event.is_set() or not ("haan" in confirm_text or "yes" in confirm_text):
                results.append("Theek hai, cancel kar diya.")
                continue

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
    root.mainloop()


if __name__ == "__main__":
    main()
