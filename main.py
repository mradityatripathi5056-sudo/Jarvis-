import sys
import threading
import time
import logging

import config
import brain
import actions
from skills.whatsapp_web_skill import WhatsAppSuperSkill
from skills.web_actions_skill import UniversalWebEngine
from speech import speak, listen, listen_for_wake_word

logging.basicConfig(
    filename=config.LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# Active page instance from actions
page = getattr(actions, 'page', None)
wa_skill = WhatsAppSuperSkill(page) if page else None
web_engine = UniversalWebEngine(page) if page else None


def handle_command(command, speak_output=True):
    cmd = command.lower()
    reply = ""

    try:
        # 1. WHATSAPP AUTOMATION
        if "whatsapp" in cmd:
            if ("message" in cmd or "bhej" in cmd) and wa_skill:
                reply = wa_skill.send_message("Contact", command)
            elif "call" in cmd and wa_skill:
                reply = wa_skill.make_voice_call("Contact")
            else:
                reply = actions.process(command)

        # 2. YOUTUBE AUTOMATION
        elif ("youtube" in cmd or "song" in cmd or "play" in cmd) and web_engine:
            reply = web_engine.yt_play_and_skip_ads(command)

        # 3. DIRECT UI CLICKS & AD SKIP
        elif ("skip" in cmd or "ad" in cmd or "click" in cmd) and web_engine:
            target = command.replace("click", "").replace("par", "").strip()
            reply = web_engine.click_element(target if target else "skip ad")

        # 4. DEFAULT SYSTEM COMMANDS
        else:
            reply = actions.process(command)

    except Exception as e:
        reply = f"Command error: {str(e)}"

    if speak_output and reply:
        speak(reply)
    return reply


def voice_loop():
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


def text_mode():
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


if name == "main":
    if hasattr(actions, 'telegram_contacts_background'):
        threading.Thread(target=actions.telegram_contacts_background, daemon=True).start()

    if "--text" in sys.argv:
        text_mode()
    elif "--voice" in sys.argv:
        voice_loop()
    else:
        # Background voice monitoring with clean main process
        threading.Thread(target=voice_loop, daemon=True).start()
        text_mode()