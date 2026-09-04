"""
skills/example_skill.py
------------------------------------------------------------
YE EK EXAMPLE HAI - dikhata hai naya skill kaise likhte hain.
Ise copy karke apna naya skill file banao (jaise skills/weather_skill.py),
aur agar ye example nahi chahiye to is file ko delete kar do.

Har skill file mein bas 2 cheezein chahiye: ACTIONS aur DOCS.
------------------------------------------------------------
"""

import random
import requests


# ------------------------------------------------------------------
# 1) Har action ek function hai jo "params" dict leta hai aur
#    STRING return karta hai (jo Jarvis bolega).
# ------------------------------------------------------------------

def flip_coin(params: dict) -> str:
    return random.choice(["Heads aaya!", "Tails aaya!"])


def roll_dice(params: dict) -> str:
    sides = int(params.get("sides", 6))
    result = random.randint(1, sides)
    return f"Dice roll: {result} (out of {sides})"


def currency_convert(params: dict) -> str:
    """Example: kisi free API ko call karke live data laana."""
    amount = float(params.get("amount", 1))
    from_cur = params.get("from", "USD").upper()
    to_cur = params.get("to", "INR").upper()
    try:
        resp = requests.get(
            f"https://api.exchangerate-api.com/v4/latest/{from_cur}", timeout=8
        )
        rate = resp.json()["rates"][to_cur]
        converted = round(amount * rate, 2)
        return f"{amount} {from_cur} = {converted} {to_cur}"
    except Exception as e:
        return f"Currency convert nahi ho saka: {e}"


# ------------------------------------------------------------------
# 2) ACTIONS dict - action_name -> function. Jarvis ye dict
#    automatically read karke apne ACTION_MAP mein merge kar lega.
# ------------------------------------------------------------------

ACTIONS = {
    "flip_coin": flip_coin,
    "roll_dice": roll_dice,
    "currency_convert": currency_convert,
}


# ------------------------------------------------------------------
# 3) DOCS - LLM ko batata hai ye naye actions kaise/kab use karne
#    hain. Bilkul TOOLS_DEFINITION jaisa hi format rakho: action
#    name, params, aur ek chhota example.
# ------------------------------------------------------------------

DOCS = """
- flip_coin: {}  (sikka uchalta hai, heads/tails batata hai)
- roll_dice: {"sides": 6}  (dice roll karta hai, sides optional hai)
- currency_convert: {"amount": 100, "from": "USD", "to": "INR"}
    (live exchange rate se currency convert karta hai)

Example:
User: "ek sikka uchalo"
-> {"actions": [{"action": "flip_coin", "params": {}}]}

User: "100 dollar kitne rupaye hote hain"
-> {"actions": [{"action": "currency_convert", "params": {"amount": 100, "from": "USD", "to": "INR"}}]}
"""
