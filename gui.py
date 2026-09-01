"""
gui.py
Jarvis ka GUI version - MAIN FILE, isko chalao (python gui.py).
"""

import threading
import time
import queue
import tkinter as tk
from tkinter import scrolledtext, font as tkfont
from datetime import datetime

import config
import brain
import actions
from speech import speak, listen, listen_for_wake_word

CONVERSATION_TIMEOUT = 20

ui_queue = queue.Queue()
is_running = True
is_muted = False

BG_DARK = "#0a0e14"
BG_PANEL = "#131820"
BG_INPUT = "#1c2330"
ACCENT = "#00d4ff"
ACCENT_GREEN = "#3fb950"
ACCENT_YELLOW = "#e3b341"
TEXT_MAIN = "#e6edf3"
TEXT_DIM = "#8b949e"


class JarvisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("JARVIS - AI Assistant")
        self.root.geometry("580x700")
        self.root.configure(bg=BG_DARK)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        title_font = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        status_font = tkfont.Font(family="Segoe UI", size=10)

        header = tk.Frame(root, bg=BG_PANEL, height=70)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="JARVIS", bg=BG_PANEL, fg=ACCENT, font=title_font).pack(side="left", padx=20)

        self.status_var = tk.StringVar(value="Starting...")
        status_container = tk.Frame(header, bg=BG_PANEL)
        status_container.pack(side="left", padx=10)
        self.status_dot = tk.Canvas(status_container, width=14, height=14, bg=BG_PANEL, highlightthickness=0)
        self.status_dot.pack(side="left")
        self.dot = self.status_dot.create_oval(2, 2, 12, 12, fill="gray", outline="")
        tk.Label(status_container, textvariable=self.status_var, bg=BG_PANEL, fg=TEXT_DIM, font=status_font).pack(side="left", padx=8)

        self.mute_btn = tk.Button(
            header, text="Mute", command=self.toggle_mute, bg="#21262d", fg=TEXT_MAIN,
            relief="flat", padx=12, pady=6, font=status_font, activebackground="#30363d", bd=0
        )
        self.mute_btn.pack(side="right", padx=20)

        quick_frame = tk.Frame(root, bg=BG_DARK)
        quick_frame.pack(fill="x", padx=15, pady=(12, 5))

        quick_actions = [
            ("Screenshot", "screenshot le lo"),
            ("Battery", "battery kitni hai"),
            ("Apps", "chal rahe apps dikhao"),
            ("Clear Chat", "__clear__"),
        ]
        for label, cmd in quick_actions:
            tk.Button(
                quick_frame, text=label, bg=BG_INPUT, fg=TEXT_MAIN, relief="flat",
                padx=8, pady=6, font=("Segoe UI", 9), activebackground="#2d3644", bd=0,
                command=lambda c=cmd: self.quick_action(c)
            ).pack(side="left", padx=4, fill="x", expand=True)

        chat_container = tk.Frame(root, bg=BG_DARK)
        chat_container.pack(fill="both", expand=True, padx=15, pady=10)

        self.chat_log = scrolledtext.ScrolledText(
            chat_container, wrap=tk.WORD, bg=BG_PANEL, fg=TEXT_MAIN,
            font=("Segoe UI", 10), relief="flat", padx=15, pady=15, bd=0
        )
        self.chat_log.pack(fill="both", expand=True)
        self.chat_log.config(state="disabled")
        self.chat_log.tag_config("user", foreground=ACCENT, font=("Segoe UI", 10, "bold"))
        self.chat_log.tag_config("jarvis", foreground=ACCENT_GREEN, font=("Segoe UI", 10, "bold"))
        self.chat_log.tag_config("dim", foreground=TEXT_DIM, font=("Segoe UI", 8))

        input_frame = tk.Frame(root, bg=BG_DARK)
        input_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.text_input = tk.Entry(
            input_frame, bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
            font=("Segoe UI", 11), relief="flat"
        )
        self.text_input.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 8))
        self.text_input.bind("<Return>", self.send_typed_command)
        self.text_input.focus()

        tk.Button(
            input_frame, text="Send", command=self.send_typed_command,
            bg=ACCENT, fg="#0a0e14", relief="flat", padx=18, font=("Segoe UI", 10, "bold"), bd=0
        ).pack(side="right")

        self.log("Jarvis", "Namaste! Main aapka assistant hoon. 'Jarvis' bolke shuru karo, ya neeche type karo.")
        self.root.after(200, self.poll_queue)

    def log(self, sender: str, text: str):
        self.chat_log.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M")
        tag = "user" if sender == "Aap" else "jarvis"
        self.chat_log.insert(tk.END, f"{sender}  ", tag)
        self.chat_log.insert(tk.END, f"{timestamp}\n", "dim")
        self.chat_log.insert(tk.END, f"{text}\n\n")
        self.chat_log.see(tk.END)
        self.chat_log.config(state="disabled")

    def clear_chat(self):
        self.chat_log.config(state="normal")
        self.chat_log.delete("1.0", tk.END)
        self.chat_log.config(state="disabled")

    def set_status(self, text: str, color: str):
        self.status_var.set(text)
        self.status_dot.itemconfig(self.dot, fill=color)

    def toggle_mute(self):
        global is_muted
        is_muted = not is_muted
        self.mute_btn.config(text="Unmute" if is_muted else "Mute")
        self.set_status("Muted" if is_muted else "Ready", ACCENT_YELLOW if is_muted else "gray")

    def quick_action(self, cmd: str):
        if cmd == "__clear__":
            self.clear_chat()
            return
        self.log("Aap", cmd)
        threading.Thread(target=process_command_thread, args=(cmd,), daemon=True).start()

    def send_typed_command(self, event=None):
        text = self.text_input.get().strip()
        if not text:
            return
        self.text_input.delete(0, tk.END)
        self.log("Aap", text)
        threading.Thread(target=process_command_thread, args=(text,), daemon=True).start()

    def poll_queue(self):
        try:
            while True:
                msg_type, payload = ui_queue.get_nowait()
                if msg_type == "status":
                    text, color = payload
                    self.set_status(text, color)
                elif msg_type == "user_said":
                    self.log("Aap", payload)
                elif msg_type == "jarvis_said":
                    self.log("Jarvis", payload)
        except queue.Empty:
            pass
        self.root.after(200, self.poll_queue)

    def on_close(self):
        global is_running
        is_running = False
        self.root.destroy()


def process_command_thread(text: str):
    ui_queue.put(("status", ("Soch raha hoon...", ACCENT_YELLOW)))
    result_text = handle_command(text, speak_output=False)
    ui_queue.put(("jarvis_said", result_text))
    speak(result_text)
    ui_queue.put(("status", ("Ready", "gray")))


def handle_command(user_text: str, speak_output: bool = True) -> str:
    action_list = brain.ask_llm(user_text)
    results = []

    for decision in action_list:
        action_name = decision.get("action")
        params = decision.get("params", {})

        if action_name == "general_chat":
            results.append(params.get("reply", "Samajh nahi paya, dobara boliye."))
            continue

        if action_name in config.DESTRUCTIVE_ACTIONS:
            ui_queue.put(("jarvis_said", f"Kya aap sure hain {action_name} karna hai? Haan ya Nahi boliye."))
            speak(f"Kya aap sure hain {action_name} karna hai? Haan ya Nahi boliye.")
            confirm_text = listen(timeout=5, phrase_time_limit=3)
            if not ("haan" in confirm_text or "yes" in confirm_text):
                results.append("Theek hai, cancel kar diya.")
                continue

        func = actions.ACTION_MAP.get(action_name)
        if func:
            try:
                result = func(params)
            except Exception as e:
                result = f"'{action_name}' karte waqt error aaya: {e}"
        else:
            result = f"'{action_name}' command samajh nahi aaya."
        results.append(result)

    final_text = " ".join(results)
    if speak_output:
        speak(final_text)
    return final_text


def voice_loop():
    conversation_mode = False
    last_activity = time.time()

    ui_queue.put(("status", ("Jarvis online - 'Jarvis' bolo", "gray")))
    speak("Jarvis online hai. Main sun raha hoon.")

    while is_running:
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


def main():
    root = tk.Tk()
    app = JarvisGUI(root)
    voice_thread = threading.Thread(target=voice_loop, daemon=True)
    voice_thread.start()
    root.mainloop()


if __name__ == "__main__":
    main()
