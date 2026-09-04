"""
main.py
------------------------------------------------------------
CLI fallback (text/voice) - GUI ke bina bhi Jarvis chalane ka tarika.
    python main.py --text     (sirf typing)
    python main.py --voice    (sirf voice)
    python main.py            (dono - background voice + text)

NOTE (fix): pehle ye file skills/whatsapp_web_skill.WhatsAppSuperSkill aur
skills/web_actions_skill.UniversalWebEngine import karti thi - ye dono
class/file kabhi exist hi nahi karte the (project WhatsApp/YouTube/web
control ab dedicated function-based skills se karta hai - dekho
skills/whatsapp_web_skill.py, skills/youtube_control_skill.py,
skills/web_agent_skill.py, skills/screen_click_skill.py), isliye
`python main.py` chalate hi seedha ImportError se crash ho jaata tha.
Iske alawa neeche `if name == "main":` bhi tha (`__name__`/`__main__` ki
jagah) jo NameError deta - matlab ye file kabhi run hi nahi ho payi hogi.
Ab isko gui.py/server.py jaisa hi asli pipeline (brain.ask_llm +
actions.ACTION_MAP, saath mein destructive-action confirmation) use karne
ke liye theek kar diya hai.
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
    format="%(asctime)s - %(message)s"
)

_pending_confirm = {"action": None, "params": None}


def handle_command(command: str, speak_output: bool = True) -> str:
    """GUI (gui.py) jaisa hi logic: brain.ask_llm se action-list decide
    karta hai, ACTION_MAP se execute karta hai, destructive actions ke
    liye 'haan/nahi' confirm maangta hai. Poora function try/except mein
    hai taaki koi bhi anexpected error CLI ko crash na kar sake - hamesha
    ek clean reply string milega."""
    global _pending_confirm

    try:
        if _pending_confirm["action"]:
            action_name = _pending_confirm["action"]
            params = _pending_confirm["params"]
            _pending_confirm = {"action": None, "params": None}

            confirmed = command.strip().lower() in (
                "haan", "ha", "yes", "yeah", "yup", "sure", "ok", "okay",
            )
            if not confirmed:
                reply = "Theek hai, cancel kar diya."
            else:
                func = actions.ACTION_MAP.get(action_name)
                if func:
                    reply = actions.run_action_with_retry(func, params, action_name)
                else:
                    reply = f"'{action_name}' command samajh nahi aaya."
            brain.save_action_results([reply])

        else:
            action_list = brain.ask_llm(command)
            results = []
            for decision in action_list:
                action_name = decision.get("action")
                params = decision.get("params", {})

                if action_name == "general_chat":
                    results.append(params.get("reply", "Samajh nahi paya, dobara boliye."))
                    continue

                if action_name in config.DESTRUCTIVE_ACTIONS:
                    _pending_confirm = {"action": action_name, "params": params}
                    results.append(f"Kya aap sure hain {action_name} karna hai? Haan ya Nahi boliye.")
                    break

                func = actions.ACTION_MAP.get(action_name)
                if func:
                    result = actions.run_action_with_retry(func, params, action_name)
                else:
                    result = f"'{action_name}' command samajh nahi aaya."
                results.append(result)

            brain.save_action_results(results)
            reply = " ".join(r for r in results if r)

    except Exception as e:
        # Safety net: brain/actions ke andar ka koi bhi na-socha-hua error
        # yahan pakda jaayega - CLI kabhi crash nahi hogi, hamesha ek jawab
        # milega.
        logging.error(f"[main] handle_command error: {e}")
        reply = f"Kuch galat ho gaya, lekin main chalta rahunga: {e}"

    if speak_output and reply:
        try:
            speak(reply)
        except Exception as e:
            logging.error(f"[main] speak() error: {e}")

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
                if "band ho jao" in command.lower():
                    conversation_mode = False
                    continue
                reply = handle_command(command)
                print(f"[Voice] Jarvis: {reply}")
        except Exception as e:
            # Ek command/loop-iteration ka error poori voice_loop ko kabhi
            # nahi maarna chahiye - log karke agle iteration pe chale jao.
            logging.error(f"[main] voice_loop error: {e}")
            time.sleep(1)


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


if __name__ == "__main__":
    if hasattr(actions, "telegram_contacts_background"):
        try:
            threading.Thread(target=actions.telegram_contacts_background, daemon=True).start()
        except Exception as e:
            logging.error(f"[main] telegram_contacts_background start fail: {e}")

    if "--text" in sys.argv:
        text_mode()
    elif "--voice" in sys.argv:
        voice_loop()
    else:
        threading.Thread(target=voice_loop, daemon=True).start()
        text_mode()
