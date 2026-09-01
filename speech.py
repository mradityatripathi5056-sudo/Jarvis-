"""
speech.py
Voice input (Speech-to-Text) aur voice output (Text-to-Speech) yahan handle hota hai.
TTS Edge TTS (natural neural voice) use karta hai - agar internet na ho ya fail ho
jaye to purane pyttsx3 (offline, robotic) pe automatically switch ho jata hai.
"""

import asyncio
import os
import tempfile

import speech_recognition as sr
import pyttsx3
import edge_tts
from playsound import playsound

import config

engine = pyttsx3.init()
engine.setProperty("rate", 175)

recognizer = sr.Recognizer()

TEMP_AUDIO = os.path.join(tempfile.gettempdir(), "jarvis_speech.mp3")


def _speak_edge(text: str) -> bool:
    """Edge TTS se natural neural voice mein bolta hai. Internet chahiye.
    Voice config.py mein config.TTS_VOICE se aata hai (.env se change ho sakta hai)."""
    try:
        async def _generate():
            communicate = edge_tts.Communicate(text, config.TTS_VOICE)
            await communicate.save(TEMP_AUDIO)

        asyncio.run(_generate())
        playsound(TEMP_AUDIO)
        try:
            os.remove(TEMP_AUDIO)
        except OSError:
            pass
        return True
    except Exception as e:
        print(f"[Edge TTS fail, pyttsx3 (offline) pe switch]: {e}")
        return False


def speak(text: str):
    print(f"[Jarvis]: {text}")
    if not _speak_edge(text):
        engine.say(text)
        engine.runAndWait()


def listen(timeout: int = 5, phrase_time_limit: int = 8) -> str:
    with sr.Microphone() as source:
        print("[Sun raha hoon...]")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            return ""

    try:
        text = recognizer.recognize_google(audio, language="hi-IN")
        print(f"[Aapne bola]: {text}")
        return text.lower()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        print(f"[Speech recognition error]: {e}")
        return ""


def listen_for_wake_word(wake_word: str) -> bool:
    text = listen(timeout=3, phrase_time_limit=3)
    return wake_word in text
