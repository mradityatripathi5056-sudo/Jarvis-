"""
speech.py
Voice input (Speech-to-Text) aur voice output (Text-to-Speech) yahan handle hota hai.
TTS Edge TTS (natural neural voice) use karta hai - agar internet na ho ya fail ho
jaye to purane pyttsx3 (offline, robotic) pe automatically switch ho jata hai.
"""

import asyncio
import logging
import os
import platform
import tempfile
import threading
import time

import speech_recognition as sr
import pyttsx3
import edge_tts
from playsound import playsound

import config

engine = pyttsx3.init()
engine.setProperty("rate", 175)

_IS_WINDOWS = platform.system() == "Windows"
if _IS_WINDOWS:
    import winsound

# GUI ke STOP button se set hota hai - chalu bol rahi awaaz ko turant
# rokne ke liye (jaise galti se bola gaya command sunte hi cancel karna).
stop_speaking_event = threading.Event()

recognizer = sr.Recognizer()
# Default se recognizer bahut jaldi "chup" maan leta hai ya ambient noise ke
# hisaab se threshold bahut high set kar leta hai jisse halki awaaz miss ho
# jaati hai - inko thoda tune kar diya taaki wake word zyada reliably pakde.
recognizer.pause_threshold = 0.6
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 300  # baseline - adjust_for_ambient_noise isko refine karega

TEMP_AUDIO = os.path.join(tempfile.gettempdir(), "jarvis_speech.mp3")

# adjust_for_ambient_noise() khud 0.5 sec ka fixed delay lagata hai - agar
# ye HAR listen() call pe (matlab wake-word ke continuous loop mein bhi)
# chale to "Jarvis" bolne ke baad response mein noticeable lag feel hota
# hai. Fix: recalibrate sirf pehli baar aur phir har 20 sec mein ek baar
# (room ka noise level itni jaldi nahi badalta) - baaki saari calls
# turant seedha sunna shuru kar deti hain, isliye response fast lagta hai.
_last_calibration_time = 0.0
_CALIBRATION_INTERVAL = 20  # seconds


def list_microphones() -> str:
    """Sab available microphones (naam + index) print/return karta hai.
    Agar wake word bilkul kaam nahi kar raha, sabse pehla check ye hai ki
    sahi mic use ho raha hai - .env mein MIC_DEVICE_INDEX=<number> set karo."""
    names = sr.Microphone.list_microphone_names()
    lines = [f"{i}: {name}" for i, name in enumerate(names)]
    result = "\n".join(lines) if lines else "Koi microphone detect nahi hua."
    print("[Available microphones]\n" + result)
    return result


def _get_microphone():
    if config.MIC_DEVICE_INDEX is not None:
        return sr.Microphone(device_index=config.MIC_DEVICE_INDEX)
    return sr.Microphone()


def _estimate_duration_seconds(path: str) -> float:
    """MP3 ki exact length nikalne ke liye extra library (mutagen) chahiye
    hoti - isse avoid karne ke liye file size se rough estimate karte hain
    (Edge TTS ~24kbps ke aaspaas hota hai). Thoda kam/zyada ho sakta hai,
    lekin STOP button phir bhi turant kaam karta hai (SND_PURGE se) - ye
    estimate sirf normal (bina-stop) case mein 'kab tak wait karna hai'
    decide karne ke liye hai."""
    try:
        size_bytes = os.path.getsize(path)
        return max(1.0, size_bytes / (24 * 1024 / 8))
    except Exception:
        return 4.0


def _play_audio_interruptible(path: str):
    """Windows pe async play karta hai aur estimated duration tak chhoti
    chhoti sleeps mein wait karta hai, taaki beech mein stop_speaking()
    call hone par turant (bina baaki clip sune) ruk jaaye. Non-Windows pe
    abhi ye guarantee nahi hai (playsound blocking hai, poora clip bajega -
    isliye STOP button Mac/Linux pe TTS ko turant nahi kaat payega, sirf
    aage ke commands cancel karega)."""
    stop_speaking_event.clear()
    if _IS_WINDOWS:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        duration = _estimate_duration_seconds(path)
        waited = 0.0
        while waited < duration and not stop_speaking_event.is_set():
            time.sleep(0.1)
            waited += 0.1
        if stop_speaking_event.is_set():
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
    else:
        playsound(path)


def stop_speaking() -> bool:
    """GUI ke STOP button se call hota hai - chalu awaaz turant band karta
    hai. Windows pe reliably kaam karta hai; Mac/Linux pe abhi guarantee
    nahi (playsound wahan blocking hai). Return: True agar turant ruk gaya."""
    stop_speaking_event.set()
    if _IS_WINDOWS:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        return True
    try:
        engine.stop()
    except Exception:
        pass
    return False


def _speak_edge(text: str) -> bool:
    """Edge TTS se natural neural voice mein bolta hai. Internet chahiye.
    Voice config.py mein config.TTS_VOICE se aata hai (.env se change ho sakta hai).
    Ek baar transient network glitch pe retry karta hai (isse robotic
    pyttsx3 fallback bahut kam lagega), aur fail hone pe exact reason
    jarvis.log mein likh deta hai - Jarvis pythonw.exe (bina console) se
    chalta hai isliye print() kabhi dikhta hi nahi, log file check karke
    hi asli wajah pata chal sakti hai."""
    last_error = None
    for attempt in range(2):
        try:
            async def _generate():
                communicate = edge_tts.Communicate(text, config.TTS_VOICE)
                await communicate.save(TEMP_AUDIO)

            asyncio.run(_generate())
            _play_audio_interruptible(TEMP_AUDIO)
            try:
                os.remove(TEMP_AUDIO)
            except OSError:
                pass
            return True
        except Exception as e:
            last_error = e
    print(f"[Edge TTS 2 baar fail hua, pyttsx3 (offline, robotic) pe switch]: {last_error}")
    logging.error(f"Edge TTS fail (2 attempts) - pyttsx3 fallback pe switch: {last_error}")
    return False


def speak(text: str):
    if config.IS_MUTED:
        print(f"[Muted - nahi bola]: {text}")
        return
    stop_speaking_event.clear()
    print(f"[Jarvis]: {text}")
    if not _speak_edge(text):
        engine.say(text)
        engine.runAndWait()


def listen(timeout: int = 5, phrase_time_limit: int = 8, language: str = "hi-IN") -> str:
    global _last_calibration_time
    with _get_microphone() as source:
        print("[Sun raha hoon...]")
        now = time.time()
        if now - _last_calibration_time > _CALIBRATION_INTERVAL:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            _last_calibration_time = now
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            print("[Kuch suna nahi (timeout) - mic sahi kaam kar raha hai ya nahi check karo]")
            return ""

    try:
        text = recognizer.recognize_google(audio, language=language)
        print(f"[Aapne bola]: {text}")
        return text.lower()
    except sr.UnknownValueError:
        print("[Awaaz suni lekin samajh nahi paya - clearly bolo ya mic ke paas jaao]")
        return ""
    except sr.RequestError as e:
        print(f"[Speech recognition error - internet check karo]: {e}")
        return ""


# "Jarvis" jaisa English naam hi-IN (Hindi) recognition mode mein kabhi kabhi
# Devanagari script mein transcribe ho jata hai (jaise "जार्विस"), isliye seedha
# "jarvis" in text check fail ho jata tha. Yahan wake word ko en-IN (English)
# mode mein sunte hain (jisme naam Latin letters mein sahi aata hai), aur agar
# wo bhi Devanagari mein aa jaye to common spelling variants se bhi match karte hain.
WAKE_WORD_VARIANTS_DEVANAGARI = [
    "जार्विस", "जारविस", "जार्वि", "जार्बिस", "जरविस", "जार्भिस",
]

# Google STT accent/noise ki wajah se "jarvis" ko aksar in jaisa sunta/likhta
# hai - inko bhi match karte hain taaki halka sa mis-hear hone par bhi
# wake word miss na ho.
WAKE_WORD_MISHEARS = [
    "jarvis", "jarvish", "jervis", "jarvi", "jarves", "javis", "charvis",
    "zarvis", "harvis", "jarbis", "jarwis", "service", "servis",
]


def listen_for_wake_word(wake_word: str) -> bool:
    text = listen(timeout=3, phrase_time_limit=4, language="en-IN")
    if not text:
        return False
    if wake_word in text:
        return True
    if any(variant in text for variant in WAKE_WORD_VARIANTS_DEVANAGARI):
        return True
    # exact substring na mile to har word ko mishear-list aur khud wake_word
    # se fuzzy (character-similarity) compare karo - halka accent/noise wale
    # mis-transcriptions bhi pakad lega.
    import difflib

    words = text.replace(",", " ").split()
    candidates = WAKE_WORD_MISHEARS + [wake_word]
    for word in words:
        for candidate in candidates:
            if difflib.SequenceMatcher(None, word, candidate).ratio() >= 0.75:
                print(f"[Wake word fuzzy match]: '{word}' ~ '{candidate}'")
                return True
    print(f"[Wake word nahi mila is text mein]: '{text}'")
    return False
