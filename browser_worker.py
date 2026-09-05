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

# ---- Shared Playwright browser/tab state ----
# browser_automation_skill.py aur web_agent_skill.py dono skills/ folder
# mein alag-alag dynamically load hote hain (skill_loader.py), isliye
# unke apne top-level globals SHARE nahi hote (har skill file apni khud
# ki separate module-copy hoti hai) - agar dono apna-apna _browser rakhte
# to ek skill se khula tab dusri skill ko dikhta hi nahi ("already open
# tab pe kaam karo" fail hota). Is module (browser_worker.py) ko dono
# NORMAL `import browser_worker` se import karte hain (skill_loader se
# nahi), isliye ye hamesha EK hi shared singleton object hai - is wajah
# se ye sahi jagah hai shared browser state rakhne ke liye.
_browser = None
_context = None
_pages = []  # open tabs
_current_index = 0


def _worker_loop():
    # DEFENSIVE FIX: agar kisi wajah se is thread mein koi asyncio event
    # loop "current" set ho gaya ho (chahe kahin se bhi aaya ho), Playwright
    # ki sync API "Sync API inside the asyncio loop" error de deti hai.
    # Ek naye thread mein normally koi loop set nahi hota, lekin ye explicit
    # reset safety ke liye hai taaki chahe kuch bhi ho jaaye, is DEDICATED
    # thread mein Playwright hamesha bina rukawat ke chal sake.
    import asyncio
    try:
        asyncio.set_event_loop(None)
    except Exception:
        pass

    while True:
        fn, result_queue = _job_queue.get()
        try:
            result = fn()
            result_queue.put(("ok", result))
        except Exception as e:  # noqa: BLE001 - error ko caller tak wapas bhejna hai
            import logging
            import traceback
            # Pehle sirf error object wapas jaata tha, poora traceback kahin
            # log nahi hota tha - agla error aaye to root-cause dhoondna
            # mushkil tha. Ab jarvis.log mein pura traceback bhi likha
            # jaayega (user ko sirf clean message dikhta hai, log mein
            # detail rehta hai).
            logging.error(f"[browser_worker] job failed: {e}\n{traceback.format_exc()}")
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


def _wire_page(page):
    """Har naye page/tab pe ek 'popup' listener laga deta hai. PROBLEM
    jo ye fix karta hai: Flipkart jaisi sites pe product/review links
    aksar target="_blank" ke saath khulte hain - matlab click karte hi
    Playwright ek ALAG popup Page bana deta hai jiske baare mein humein
    pehle pata hi nahi chalta tha (_pages list mein add hi nahi hota
    tha). Isse do symptoms aate the: (1) 'review khol do' bolne pe
    review nahi khulta tha kyunki hum purane (search-results wale) page
    par hi read/click karte reh jaate the, jabki asli review naye
    background tab mein khula padha rehta tha; (2) wahi click baar-baar
    retry hota tha isliye HAR baar ek naya tab khul jaata tha ('bar bar
    new tab open ho jaana').

    Fix: jaise hi koi popup/naya tab khule, usse turant _pages mein add
    karo AUR usi ko current active tab bana do - taaki agla read/click
    turant sahi (naye khule) tab par ho, purane stale tab par nahi."""
    def _on_popup(popup):
        global _current_index
        try:
            _pages.append(popup)
            _current_index = len(_pages) - 1
            _wire_page(popup)  # popup se bhi aage popup khul sakta hai
        except Exception:
            pass
    try:
        page.on("popup", _on_popup)
    except Exception:
        pass


def get_current_page():
    """Current active tab ka Playwright Page object deta hai - agar koi
    tab khula nahi hai to naya bana deta hai. IMPORTANT: ye function
    hamesha browser-worker thread ke andar hi call hona chahiye (matlab
    run_in_browser_thread() se wrap kiye gaye fn ke andar se)."""
    global _browser, _context, _pages, _current_index
    if _browser is None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("Playwright missing. Chalao: pip install playwright && playwright install chromium")
        playwright = sync_playwright().start()
        _browser = playwright.chromium.launch(headless=False)
        _context = _browser.new_context()

    if not _pages:
        page = _context.new_page()
        _wire_page(page)
        _pages.append(page)
        _current_index = 0
    else:
        try:
            _ = _pages[_current_index].title()
        except Exception:
            try:
                _pages.pop(_current_index)
            except Exception:
                pass
            if not _pages:
                page = _context.new_page()
                _pages.append(page)
                _current_index = 0
            else:
                _current_index = min(_current_index, len(_pages) - 1)
    return _pages[_current_index]


def new_tab(url: str = ""):
    global _current_index
    get_current_page()  # ensures browser/context exist
    page = _context.new_page()
    _wire_page(page)
    _pages.append(page)
    _current_index = len(_pages) - 1
    if url:
        page.goto(url, timeout=20000)
    return page


def switch_tab(index=None) -> str:
    global _current_index
    if not _pages:
        return "Koi tab khula hi nahi hai abhi."
    if index is None:
        _current_index = (_current_index + 1) % len(_pages)
    else:
        idx = int(index)
        if idx < 0 or idx >= len(_pages):
            return f"Sirf {len(_pages)} tabs hain, tab {idx} nahi hai."
        _current_index = idx
    try:
        _pages[_current_index].bring_to_front()
    except Exception:
        pass
    return f"Tab {_current_index + 1}/{len(_pages)} pe switch kar diya."


def close_current_tab() -> str:
    global _current_index
    if not _pages:
        return "Koi tab khula nahi hai."
    page = _pages.pop(_current_index)
    try:
        page.close()
    except Exception:
        pass
    _current_index = max(0, _current_index - 1)
    return f"Tab band kar diya ({len(_pages)} tabs bache)."


def tab_count() -> int:
    return len(_pages)


def close_all_browsers() -> str:
    global _browser, _context, _pages, _current_index
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    _browser = None
    _context = None
    _pages = []
    _current_index = 0
    return "Poora automation browser band kar diya."
