"""
skills/webcam_vision_skill.py
------------------------------------------------------------
Webcam Object Detection - "Jarvis, ye kya hai?" jaisa sawaal poochne
par webcam se ek frame capture karke usme dikh rahi cheezein
pehchanta hai (80 common COCO objects: laptop, cup, chair, phone,
bottle, person, etc.)

Uses: OpenCV (webcam capture, already requirements.txt mein hai) +
YOLOv8n via `ultralytics` package (lightweight, accurate).

Setup:
    pip install ultralytics
Pehli baar chalne par ye khud "yolov8n.pt" model (~6MB) internet se
download karega - us waqt internet chahiye hoga, uske baad offline
kaam karta hai.
"""

import cv2

try:
    from ultralytics import YOLO
    _YOLO_OK = True
except ImportError:
    _YOLO_OK = False

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = YOLO("yolov8n.pt")
    return _model


def detect_objects_webcam(params: dict) -> str:
    """Webcam se ek frame lekar usme dikh rahi cheezein pehchanta hai."""
    if not _YOLO_OK:
        return "ultralytics package missing. Chalao: pip install ultralytics"
    confidence_threshold = float(params.get("confidence", 0.4))
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "Webcam access nahi mil paya - shayad kisi doosri app mein use ho raha hai ya permission nahi hai."
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return "Webcam se frame capture nahi ho paya."

        model = _get_model()
        results = model(frame, verbose=False)
        names = model.names
        detected = {}
        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf < confidence_threshold:
                    continue
                label = names[int(box.cls[0])]
                detected[label] = max(detected.get(label, 0), conf)

        if not detected:
            return "Webcam mein koi pehchana jaane wala object nahi mila."
        sorted_items = sorted(detected.items(), key=lambda kv: -kv[1])
        items_text = ", ".join(name for name, _ in sorted_items)
        return f"Webcam mein ye dikh raha hai: {items_text}."
    except Exception as e:
        return f"Object detection fail: {e}"


ACTIONS = {
    "detect_objects_webcam": detect_objects_webcam,
}

DOCS = """
- detect_objects_webcam: {}  (webcam se dekh kar batata hai saamne kya cheezein hain)

Example:
User: "Jarvis, ye kya hai?"
-> {"actions": [{"action": "detect_objects_webcam", "params": {}}]}

User: "webcam se dekho room mein kya kya hai"
-> {"actions": [{"action": "detect_objects_webcam", "params": {}}]}
"""
