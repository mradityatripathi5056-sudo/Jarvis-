"""
main.py
CLI (terminal) version - GUI na chale to isko use karo.

Chalane ka tarika:
    python main.py              (dono voice + text - jo bhi pehle aaye)
    python main.py --text       (sirf text, voice bilkul band)
    python main.py --voice      (sirf voice)
"""

import sys
import threading
import time
import logging

import config
import brain
import actions
from speech import speak, listen, listen_for_wake_word

logging.basicConfig(
    filename=config.LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
)


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
            print(f"Jarvis: Kya aap sure hain '{action_name}' karna hai? (haan/nahi)")
            confirm = input("Aap: ").strip().lower()
            if "haan" not in confirm and "yes" not in confirm:
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


def text_mode():
    print("=" * 50)
    print("JARVIS - TEXT MODE")
    print("Type karke Enter dabao. 'exit' likh ke band karo.")
    print("=" * 50)

    while True:
        try:
            user_text = input("\nAap: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAlvida!")
            break

        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit", "band ho jao", "bye"):
            print("Jarvis: Alvida!")
            break

        reply = handle_command(user_text, speak_output=False)
        print(f"Jarvis: {reply}")


def voice_mode():
    speak("Jarvis online hai. Main sun raha hoon.")
    print("Jarvis online hai. 'Jarvis' bolke shuru karo. Ctrl+C se band karo.")

    while True:
        try:
            if not listen_for_wake_word(config.WAKE_WORD):
                continue

            speak("Ji boliye?")
            command = listen(timeout=6, phrase_time_limit=10)

            if not command:
                continue

            print(f"Aap: {command}")

            if "band ho jao" in command or "exit" in command or "stop" in command:
                speak("Theek hai, band ho raha hoon. Alvida!")
                break

            reply = handle_command(command)
            print(f"Jarvis: {reply}")

        except KeyboardInterrupt:
            speak("Manually band kiya gaya. Alvida!")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            print(f"Jarvis: Kuch gadbad ho gayi - {e}")


def both_mode():
    print("=" * 50)
    print("JARVIS - VOICE + TEXT DONO MODE")
    print("'Jarvis' bolo YA seedha type karke Enter dabao.")
    print("'exit' type karke ya Ctrl+C se band karo.")
    print("=" * 50)

    def voice_background():
        conversation_mode = False
        last_activity = time.time()

        while True:
            try:
                if not conversation_mode:
                    heard = listen_for_wake_word(config.WAKE_WORD)
                    if heard:
                        conversation_mode = True
                        last_activity = time.time()
                        speak("Ji boliye?")
                else:
                    command = listen(timeout=20, phrase_time_limit=10)
                    if not command:
                        if time.time() - last_activity > 20:
                            conversation_mode = False
                        continue
                    last_activity = time.time()
                    print(f"\n[Voice] Aap: {command}")
                    if "band ho jao" in command:
                        conversation_mode = False
                        continue
                    reply = handle_command(command)
                    print(f"[Voice] Jarvis: {reply}")
            except Exception:
                pass

    voice_thread = threading.Thread(target=voice_background, daemon=True)
    voice_thread.start()

    while True:
        try:
            user_text = input("\nAap (type): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAlvida!")
            break

        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            print("Jarvis: Alvida!")
            break

        reply = handle_command(user_text, speak_output=False)
        print(f"Jarvis: {reply}")


if __name__ == "__main__":
    if "--text" in sys.argv:
        text_mode()
    elif "--voice" in sys.argv:
        voice_mode()
    else:
        both_mode()
