"""
skills/face_security_skill.py
------------------------------------------------------------
Face Recognition Security + Stealth Mode.

Jaanbojh kar `face_recognition`/`dlib` NAHI use kiya - Windows par
dlib compile karna (CMake + C++ build tools) bahut jhanjhat wala hai.
Iske bajaye plain OpenCV (jo already requirements.txt mein hai) ka
built-in LBPH face recognizer use kiya hai - pure pip install se
chal jaata hai:
    pip install opencv-contrib-python
(NOTE: agar sirf "opencv-python" installed hai to "cv2.face" module
nahi milega - "opencv-contrib-python" chahiye. Dono ek saath install
mat karna, conflict hota hai - pehle `pip uninstall opencv-python`
phir `pip install opencv-contrib-python`.)

Kaise use karein:
1. enroll_face: apni 20-30 photos webcam se capture karke "known
   face" ke roop mein save/train karta hai. Ek hi baar karna hai
   (dubara enroll karne se pehle wala overwrite ho jaata hai).
2. check_face_security: webcam se dekh kar batata hai ki saamne
   wala known hai ya unknown.
3. stealth_mode_guard: agar unknown/koi face na mile to browser
   windows minimize kar deta hai + screen lock kar deta hai. Agar
   apna (known) face mile to kuch nahi karta.

Data yahan save hota hai: face_data/ folder (local hi rehta hai,
kahin upload nahi hota).
"""

import os
import time

import cv2
import numpy as np

import config

FACE_DIR = os.path.join(config.MEDIA_DIR, "face_data")
MODEL_PATH = os.path.join(FACE_DIR, "trained_model.yml")
LABELS_PATH = os.path.join(FACE_DIR, "labels.txt")
CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

os.makedirs(FACE_DIR, exist_ok=True)


def _has_cv2_face() -> bool:
    return hasattr(cv2, "face")


def _detect_face_gray(frame) -> np.ndarray | None:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = CASCADE.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])  # sabse bada face
    return cv2.resize(gray[y : y + h, x : x + w], (200, 200))


def enroll_face(params: dict) -> str:
    """Webcam se 20-30 photos lekar ek face ko 'known' ke roop mein
    register/train karta hai. name na diya jaaye to 'owner' use hoga."""
    if not _has_cv2_face():
        return "cv2.face missing. Chalao: pip uninstall opencv-python, phir pip install opencv-contrib-python"
    name = params.get("name", "owner").strip() or "owner"
    samples_needed = int(params.get("samples", 25))

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Webcam access nahi mil paya."

    person_dir = os.path.join(FACE_DIR, name)
    os.makedirs(person_dir, exist_ok=True)
    collected = 0
    attempts = 0
    while collected < samples_needed and attempts < samples_needed * 6:
        attempts += 1
        ret, frame = cap.read()
        if not ret:
            continue
        face = _detect_face_gray(frame)
        if face is not None:
            cv2.imwrite(os.path.join(person_dir, f"{collected}.png"), face)
            collected += 1
        time.sleep(0.15)
    cap.release()

    if collected < 5:
        return f"Sirf {collected} face samples mil paye - saaf roshni mein, camera ke saamne seedha dekh kar dobara try karo."

    _train_model()
    return f"'{name}' ke {collected} face samples enroll ho gaye aur model train ho gaya."


def _train_model() -> None:
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    images, labels, label_names = [], [], []
    for idx, person in enumerate(sorted(os.listdir(FACE_DIR))):
        person_path = os.path.join(FACE_DIR, person)
        if not os.path.isdir(person_path):
            continue
        label_names.append(person)
        for fname in os.listdir(person_path):
            img = cv2.imread(os.path.join(person_path, fname), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                images.append(img)
                labels.append(idx)
    if not images:
        return
    recognizer.train(images, np.array(labels))
    recognizer.save(MODEL_PATH)
    with open(LABELS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(label_names))


def _load_model():
    if not os.path.exists(MODEL_PATH) or not os.path.exists(LABELS_PATH):
        return None, []
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(MODEL_PATH)
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        label_names = [line.strip() for line in f if line.strip()]
    return recognizer, label_names


def check_face_security(params: dict) -> str:
    """Webcam se dekh kar batata hai saamne wala KNOWN hai ya UNKNOWN."""
    if not _has_cv2_face():
        return "cv2.face missing. Chalao: pip uninstall opencv-python, phir pip install opencv-contrib-python"
    recognizer, label_names = _load_model()
    if recognizer is None:
        return "Abhi tak koi face enroll nahi hui. Pehle 'enroll_face' action se apna face register karo."

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Webcam access nahi mil paya."
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return "Webcam se frame capture nahi ho paya."

    face = _detect_face_gray(frame)
    if face is None:
        return "UNKNOWN: koi face detect nahi hua."

    label_id, confidence = recognizer.predict(face)
    # LBPH mein LOWER confidence = better match. ~70 se neeche generally
    # reliable match maana jaata hai.
    threshold = float(params.get("threshold", 70))
    if confidence < threshold and label_id < len(label_names):
        return f"KNOWN: {label_names[label_id]} pehchana gaya (match strength: {round(100 - confidence, 1)}%)."
    return f"UNKNOWN face detect hua (koi registered face se match nahi hua)."


def stealth_mode_guard(params: dict) -> str:
    """Agar KNOWN face na mile (ya koi face na mile) to PEHLE user se
    voice confirmation maangta hai - "haan"/"yes" bolne par hi browser
    windows minimize karke screen lock karta hai. Confirmation na mile
    (timeout ya "nahi") to kuch nahi karta."""
    import actions  # lazy import - circular import se bachne ke liye
    from speech import speak, listen

    result = check_face_security(params)
    if result.startswith("KNOWN"):
        return f"Sab thik hai - {result}"

    speak(f"{result}. Kya browser hide karke screen lock kar doon? Haan ya nahi boliye.")
    confirm_text = listen(timeout=6, phrase_time_limit=3)
    if not confirm_text or not ("haan" in confirm_text or "yes" in confirm_text or "kar do" in confirm_text):
        return f"{result} - lekin confirmation nahi mila, isliye kuch nahi kiya."

    hidden_count = 0
    try:
        import pygetwindow as gw
        browser_keywords = ("chrome", "edge", "firefox", "brave", "opera")
        for win in gw.getAllWindows():
            title_lower = win.title.lower()
            if any(b in title_lower for b in browser_keywords):
                try:
                    win.minimize()
                    hidden_count += 1
                except Exception:
                    pass
    except ImportError:
        pass

    lock_result = actions.lock_screen()
    return f"{result} - confirm mila, {hidden_count} browser window(s) minimize kiye aur {lock_result}"


ACTIONS = {
    "enroll_face": enroll_face,
    "check_face_security": check_face_security,
    "stealth_mode_guard": stealth_mode_guard,
}

DOCS = """
- enroll_face: {"name": "owner"}
    (webcam se apna face register/train karta hai - EK BAAR karna hai, setup step)
- check_face_security: {}  (webcam se dekh kar batata hai saamne wala known hai ya unknown)
- stealth_mode_guard: {}
    (agar KNOWN face na mile to PEHLE voice se puchega "haan/nahi" -
    "haan" bolne par hi browser windows minimize + screen lock karega)

Example:
User: "mera face register karo security ke liye"
-> {"actions": [{"action": "enroll_face", "params": {"name": "owner"}}]}

User: "dekho koi anjaan to nahi baitha mere saamne"
-> {"actions": [{"action": "stealth_mode_guard", "params": {}}]}
"""
