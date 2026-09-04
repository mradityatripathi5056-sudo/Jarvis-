"""
skills/self_learning_skill.py
------------------------------------------------------------
"Jarvis khud ko train kar le" ka REALISTIC/achievable version.

Asli ML training (TensorFlow, model weights update karna) is scale ke
liye practical nahi hai - usme hazaron examples, GPU, ghanton ka time
chahiye, aur result bhi cloud LLM se better nahi hoga.

Iske bajaye ye skill "learning by correction" karti hai - jab bhi user
Jarvis ko sahi/galat batata hai ya koi permanent preference batata hai,
wo yahan save ho jaata hai, aur AGLI BAAR se har command ke system
prompt mein automatically inject hota hai (brain.py mein) - taaki
Jarvis wahi galti dobara na kare, bina kisi model retrain kiye.

Isko "prompt-level learning" kehte hain - halka, turant effect dikhata
hai, aur samajhna/dekhna/delete karna bhi aasan hai (kisi black-box
model weights ke bajaye plain readable text hai).
"""

import threading
from datetime import datetime

from json_utils import safe_json_load, safe_json_save

LEARNED_FILE = "jarvis_learned.json"
_lock = threading.Lock()
MAX_CORRECTIONS = 50  # bahut zyada ho jayein to purani sabse kam relevant hata dete hain


def _load() -> list:
    data = safe_json_load(LEARNED_FILE, {"corrections": []})
    return data.get("corrections", [])


def _save(corrections: list):
    with _lock:
        safe_json_save(LEARNED_FILE, {"corrections": corrections})


def learn_correction(params: dict) -> str:
    """User ne bataya ki aage se kuch alag/sahi karna hai - permanently
    yaad rakhta hai, agli baar se system prompt mein include hoga."""
    correction = (params.get("correction") or "").strip()
    if not correction:
        return "Kya seekhna hai, batao - jaise 'aage se X ke bajaye Y karna'."
    corrections = _load()
    corrections.append({"text": correction, "learned_on": datetime.now().strftime("%Y-%m-%d %H:%M")})
    if len(corrections) > MAX_CORRECTIONS:
        corrections = corrections[-MAX_CORRECTIONS:]  # sabse purani hata do
    _save(corrections)
    return f"Yaad rakh liya: '{correction}'. Aage se isi hisaab se karunga."


def list_learned(params: dict) -> str:
    corrections = _load()
    if not corrections:
        return "Abhi tak koi correction/learning save nahi hai."
    lines = [f"{i + 1}. {c['text']} ({c['learned_on']})" for i, c in enumerate(corrections)]
    return "Ab tak seekhi gayi cheezein:\n" + "\n".join(lines)


def forget_learned(params: dict) -> str:
    """{"index": 2} - specific correction bhula do, ya {"all": true} - sab bhula do."""
    if params.get("all"):
        count = len(_load())
        _save([])
        return f"Saari seekhi hui cheezein bhula di ({count} thi)."
    index = params.get("index")
    corrections = _load()
    if index is None:
        return "Kaunsi correction bhulani hai (index number), ya sab bhulani hain, batao."
    idx = int(index) - 1
    if not (0 <= idx < len(corrections)):
        return "Wo index nahi mila."
    removed = corrections.pop(idx)
    _save(corrections)
    return f"Bhula diya: '{removed['text']}'"


def get_learned_prompt_text() -> str:
    """brain.py ke system prompt mein inject karne ke liye - agar koi
    corrections nahi hain to khaali string deta hai (prompt mein extra
    clutter na ho)."""
    corrections = _load()
    if not corrections:
        return ""
    lines = "\n".join(f"- {c['text']}" for c in corrections)
    return (
        "\n\nUSER NE YE CORRECTIONS/PREFERENCES SIKHAYI HAIN (hamesha follow karo, "
        "jab tak user khud inhe na badle):\n" + lines
    )


ACTIONS = {
    "learn_correction": learn_correction,
    "list_learned": list_learned,
    "forget_learned": forget_learned,
}

DOCS = """
- learn_correction: {"correction": "jab main 'gaana bajao' bolun to hamesha Spotify use karo, YouTube nahi"}
    (user permanently kuch sikhata/correct karta hai - "aage se aisa karna",
    "hamesha ye tarika use karo", "galat kiya, sahi ye hai" jaisa kuch bole
    to ye use karo. Agli baar se Jarvis ye yaad rakhega aur follow karega.)
- list_learned: {}  (ab tak kya-kya seekha hai dikhata hai)
- forget_learned: {"index": 2} (specific cheez bhulana) ya {"all": true} (sab bhulana)

Examples:
User: "aage se jab main flipkart bolun to hamesha chrome mein khulna, edge mein nahi"
-> {"actions": [{"action": "learn_correction", "params": {"correction": "Flipkart hamesha Chrome mein kholna, Edge nahi"}}]}
User: "tumne galat kiya, sahi tarika ye hai ki pehle confirm poochna phir delete karna"
-> {"actions": [{"action": "learn_correction", "params": {"correction": "File delete karne se pehle hamesha confirm poochna"}}]}
"""
