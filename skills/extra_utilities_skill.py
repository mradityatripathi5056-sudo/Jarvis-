"""
skills/extra_utilities_skill.py
------------------------------------------------------------
Chhoti-chhoti roz kaam aane wali utilities jo actions.py ya baaki
skills/ mein already nahi thi: weather, translation, wikipedia,
news headlines, QR code, unit conversion, password generator,
dictionary lookup.

Free/no-key APIs use kiye hain jahan possible tha, isliye zyada
setup nahi chahiye. Kuch (qrcode) ke liye ek extra pip package
lagega - README/requirements mein note kar dena.
"""

import random
import string

import requests


def get_weather(params: dict) -> str:
    """Kisi bhi city ka current weather batata hai (free wttr.in API)."""
    city = params.get("city", "").strip()
    if not city:
        return "Kaunse city ka weather chahiye, naam batao."
    try:
        resp = requests.get(f"https://wttr.in/{city}?format=%C+%t+(feels+%f)+humidity:%h+wind:%w", timeout=8)
        return f"{city}: {resp.text.strip()}"
    except Exception as e:
        return f"Weather nahi mil saka: {e}"


def translate_text(params: dict) -> str:
    """Text ko doosri language mein translate karta hai (free Google endpoint)."""
    text = params.get("text", "").strip()
    target = params.get("to", "en").strip()
    if not text:
        return "Kya translate karna hai, text batao."
    try:
        resp = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text},
            timeout=8,
        )
        data = resp.json()
        translated = "".join(chunk[0] for chunk in data[0])
        return translated
    except Exception as e:
        return f"Translate nahi ho saka: {e}"


def wiki_summary(params: dict) -> str:
    """Kisi topic ka short Wikipedia summary laata hai."""
    topic = params.get("topic", "").strip()
    if not topic:
        return "Kis topic ka summary chahiye, naam batao."
    try:
        resp = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ', '_')}",
            timeout=8,
        )
        data = resp.json()
        extract = data.get("extract")
        return extract if extract else f"'{topic}' pe kuch nahi mila Wikipedia pe."
    except Exception as e:
        return f"Wikipedia summary nahi mil saka: {e}"


def get_news_headlines(params: dict) -> str:
    """Google News RSS se top headlines laata hai (topic optional)."""
    topic = params.get("topic", "").strip()
    try:
        import xml.etree.ElementTree as ET

        url = (
            f"https://news.google.com/rss/search?q={topic}&hl=en-IN&gl=IN&ceid=IN:en"
            if topic
            else "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        )
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        titles = [item.find("title").text for item in root.findall(".//item")[:5]]
        if not titles:
            return "Koi headlines nahi mili."
        return "Top headlines:\n" + "\n".join(f"- {t}" for t in titles)
    except Exception as e:
        return f"News nahi mil saki: {e}"


def generate_qr_code(params: dict) -> str:
    """Diye gaye text/URL ka QR code image bana ke save karta hai."""
    data = params.get("data", "").strip()
    path = params.get("path", "qr_code.png")
    if not data:
        return "QR code mein kya daalna hai, text ya URL batao."
    try:
        import qrcode

        img = qrcode.make(data)
        img.save(path)
        return f"QR code ban gaya: {path}"
    except ImportError:
        return "QR banane ke liye pehle ye install karo: pip install qrcode[pil]"
    except Exception as e:
        return f"QR code nahi ban saka: {e}"


def unit_convert(params: dict) -> str:
    """Common length/weight/temperature units ke beech convert karta hai."""
    value = float(params.get("value", 0))
    from_unit = params.get("from", "").lower()
    to_unit = params.get("to", "").lower()

    factors = {
        # length (metres se relative)
        "m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
        "mile": 1609.34, "miles": 1609.34, "yard": 0.9144, "ft": 0.3048, "feet": 0.3048, "inch": 0.0254,
        # weight (kg se relative)
        "kg": 1.0, "g": 0.001, "lb": 0.453592, "lbs": 0.453592, "oz": 0.0283495,
    }

    try:
        if from_unit in ("c", "celsius") or to_unit in ("c", "celsius") or \
           from_unit in ("f", "fahrenheit") or to_unit in ("f", "fahrenheit"):
            if from_unit in ("c", "celsius") and to_unit in ("f", "fahrenheit"):
                result = value * 9 / 5 + 32
            elif from_unit in ("f", "fahrenheit") and to_unit in ("c", "celsius"):
                result = (value - 32) * 5 / 9
            else:
                return "Temperature ke liye 'c'/'celsius' ya 'f'/'fahrenheit' use karo."
            return f"{value} {from_unit} = {round(result, 2)} {to_unit}"

        if from_unit not in factors or to_unit not in factors:
            return f"Ye units support nahi karta abhi: {from_unit} -> {to_unit}"
        base = value * factors[from_unit]
        result = base / factors[to_unit]
        return f"{value} {from_unit} = {round(result, 4)} {to_unit}"
    except Exception as e:
        return f"Convert nahi ho saka: {e}"


def generate_password(params: dict) -> str:
    """Random strong password generate karta hai."""
    length = int(params.get("length", 16))
    length = max(4, min(length, 128))
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    password = "".join(random.choice(chars) for _ in range(length))
    return f"Generated password: {password}"


def define_word(params: dict) -> str:
    """Kisi English word ki meaning/definition batata hai (free dictionaryapi.dev)."""
    word = params.get("word", "").strip()
    if not word:
        return "Kaunse word ki meaning chahiye?"
    try:
        resp = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=8)
        data = resp.json()
        if isinstance(data, dict) and data.get("title") == "No Definitions Found":
            return f"'{word}' ki definition nahi mili."
        meaning = data[0]["meanings"][0]["definitions"][0]["definition"]
        return f"{word}: {meaning}"
    except Exception as e:
        return f"Definition nahi mil saki: {e}"


ACTIONS = {
    "get_weather": get_weather,
    "translate_text": translate_text,
    "wiki_summary": wiki_summary,
    "get_news_headlines": get_news_headlines,
    "generate_qr_code": generate_qr_code,
    "unit_convert": unit_convert,
    "generate_password": generate_password,
    "define_word": define_word,
}

DOCS = """
- get_weather: {"city": "Ayodhya"}  (current weather batata hai)
- translate_text: {"text": "hello", "to": "hi"}  (language auto-detect, target language code do)
- wiki_summary: {"topic": "Ayodhya"}  (short Wikipedia summary)
- get_news_headlines: {"topic": "cricket"}  (topic optional, top 5 headlines)
- generate_qr_code: {"data": "https://example.com", "path": "qr.png"}
- unit_convert: {"value": 10, "from": "km", "to": "miles"}  (length/weight/temperature)
- generate_password: {"length": 16}  (random strong password)
- define_word: {"word": "ephemeral"}  (English dictionary meaning)

Example:
User: "Ayodhya ka weather batao"
-> {"actions": [{"action": "get_weather", "params": {"city": "Ayodhya"}}]}
"""
