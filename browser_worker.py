"""
browser_worker.py
------------------------------------------------------------
PROBLEM: Playwright ki sync API sirf usi OS thread se use ho sakti hai
jisne use start kiya tha. Jarvis ka gui.py har voice/typed command ke
liye ek NAYA thread banata hai (`threading.Thread(target=process_command_thread,...)`).
Isliye agar "youtube pe X play karo" thread A mein browser khole, aur
"pause karo"/"like karo" thread B (naya command = naya thread) se aaye,
to Playwright error deta hai: "Cannot switch to a different thread".

FIX: Ek hi DEDICATED background thread banao jisme Playwright hamesha
chalta rehta hai. Koi bhi calling thread (chahe kitne bhi alag threads
kyun na hon) ek zero-arg function is worker ko queue ke zariye bhejta
hai aur result/exception wapas apne hi thread mein blocking tarike se
paata hai - jaise ek internal RPC call.

Ye module browser_automation_skill.py aur youtube_control_skill.py
dono use karte hain taaki unka Playwright state hamesha ek hi thread
mein rahe.
"""

import queue
import threading

_job_queue = queue.Queue()
_worker_thread = None
_worker_lock = threading.Lock()


def _worker_loop():
    while True:
        fn, result_queue = _job_queue.get()
        try:
            result = fn()
            result_queue.put(("ok", result))
        except Exception as e:  # noqa: BLE001 - error ko caller tak wapas bhejna hai
            result_queue.put(("error", e))


def _ensure_worker():
    global _worker_thread
    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = threading.Thread(
                target=_worker_loop, daemon=True, name="jarvis-browser-worker"
            )
            _worker_thread.start()


def run_in_browser_thread(fn, timeout: int = 60):
    """`fn` (Playwright calls karne wala zero-arg callable) ko dedicated
    browser-worker thread mein chalata hai aur result/exception calling
    thread ko blocking tarike se wapas deta hai.

    Isse koi bhi skill function kisi bhi thread se call ho, Playwright
    ke saare calls hamesha ek hi consistent thread mein hi jaate hain.
    """
    _ensure_worker()
    result_queue: "queue.Queue" = queue.Queue()
    _job_queue.put((fn, result_queue))
    try:
        status, value = result_queue.get(timeout=timeout)
    except queue.Empty:
        raise TimeoutError(f"Browser worker {timeout}s mein respond nahi hua.")
    if status == "error":
        raise value
    return value
