"""
skills/youtube_control_skill.py
------------------------------------------------------------
Ek dedicated, PERSISTENT YouTube tab control karta hai (Playwright se).

Flow: "youtube khol ke X play karo" -> yt_play chalega, ek tab khulega aur
wahi tab yaad rakha jayega. Uske baad "isko like kar do", "subscribe kar do",
"next karo", "pause karo" jaisi commands USI TAB pe chalengi - naya tab ya
naya search nahi hoga jab tak khud dobara "play karo" na bolo.

SETUP:
  pip install playwright
  playwright install chromium

NOTE: Like/Subscribe ke liye jarvis jis Chromium profile mein YouTube khol
raha hai, usme tumhara Google account login hona chahiye (ek baar manually
login kar lo, phir wahi session persist rahega jab tak browser band na ho).

THREADING FIX (zaroor padhna):
Jarvis har command (bola ya type kiya) ek NAYE thread mein process karta
hai (gui.py). Playwright ki sync API sirf usi thread se kaam karti hai
jisne use start kiya - isliye "play karo" ek thread mein browser khole
aur baad mein "pause karo"/"like karo" doosre (naye) thread se aaye to
"Cannot switch to a different thread" crash hota tha. Ab saare Playwright
calls `browser_worker.run_in_browser_thread(...)` ke zariye ek hi fixed
background thread mein bhejte hain, chahe command kisi bhi thread se aaye.
"""

from browser_worker import run_in_browser_thread

_browser = None
_context = None
_page = None


def _ensure_page():
    """Chalu YouTube tab return karta hai. Agar band ho gaya ho ya kabhi
    khula hi na ho, naya bana deta hai. IMPORTANT: ye function hamesha
    browser-worker thread ke andar hi call hona chahiye."""
    global _browser, _context, _page
    if _page is not None:
        try:
            _ = _page.title()
            return _page
        except Exception:
            _page = None

    if _browser is None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright missing hai. Chalao: pip install playwright && playwright install chromium"
            )
        playwright = sync_playwright().start()
        _browser = playwright.chromium.launch(headless=False)
        _context = _browser.new_context()

    _page = _context.new_page()
    return _page


# ------------------------------------------------------------------
# Internal implementations - ye sab sirf browser-worker thread ke
# andar chalti hain (run_in_browser_thread ke zariye).
# ------------------------------------------------------------------

def _yt_play_impl(query: str) -> str:
    page = _ensure_page()
    page.goto(f"https://www.youtube.com/results?search_query={query}", timeout=20000)
    video = page.wait_for_selector("ytd-video-renderer a#video-title", timeout=10000)
    video.click()
    page.wait_for_timeout(2500)
    try:
        skip = page.wait_for_selector(
            ".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-skip-button-container",
            timeout=3000,
        )
        if skip:
            skip.click()
    except Exception:
        pass
    return f"'{query}' play kar raha hoon YouTube pe."


def _yt_like_impl() -> str:
    if _page is None:
        return "Pehle koi video play karo, phir like karna."
    # state="attached" use kiya hai "visible" ki jagah - YouTube ka like
    # button kabhi player-overlay ki wajah se Playwright ko "visible" nahi
    # dikhta jab tak use hover/scroll na kiya jaye, jisse pehle timeout
    # ho jaata tha even though button DOM mein maujood aur clickable hota hai.
    btn = _page.wait_for_selector(
        "ytd-menu-renderer #segmented-like-button button, button[aria-label*='like this video' i]",
        timeout=8000,
        state="attached",
    )
    btn.scroll_into_view_if_needed()
    if (btn.get_attribute("aria-pressed") or "").lower() == "true":
        return "Ye video already liked hai."
    try:
        btn.click(timeout=5000)
    except Exception:
        # Normal click fail ho (overlay/covered element) to seedha DOM
        # click event fire karo - ye visibility check ko bypass kar deta hai.
        btn.evaluate("el => el.click()")
    return "Video like kar diya!"


def _yt_subscribe_impl() -> str:
    if _page is None:
        return "Pehle koi video play karo, phir subscribe karna."
    btn = _page.wait_for_selector(
        "ytd-subscribe-button-renderer button, #subscribe-button button",
        timeout=8000,
        state="attached",
    )
    btn.scroll_into_view_if_needed()
    if "subscribed" in (btn.inner_text() or "").strip().lower():
        return "Ye channel already subscribed hai."
    try:
        btn.click(timeout=5000)
    except Exception:
        btn.evaluate("el => el.click()")
    return "Channel subscribe kar diya!"


def _yt_pause_resume_impl() -> str:
    if _page is None:
        return "Koi video khula hi nahi hai."
    _page.keyboard.press("k")
    return "Play/pause toggle kar diya."


def _yt_next_impl() -> str:
    if _page is None:
        return "Koi video khula hi nahi hai."
    _page.keyboard.press("shift+N")
    return "Next video pe gaya."


def _yt_mute_toggle_impl() -> str:
    if _page is None:
        return "Koi video khula hi nahi hai."
    _page.keyboard.press("m")
    return "Mute/unmute toggle kar diya."


def _yt_fullscreen_toggle_impl() -> str:
    if _page is None:
        return "Koi video khula hi nahi hai."
    _page.keyboard.press("f")
    return "Fullscreen toggle kar diya."


def _yt_close_impl() -> str:
    global _browser, _context, _page
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    _browser = None
    _context = None
    _page = None
    return "YouTube tab/browser band kar diya."


# ------------------------------------------------------------------
# Public ACTIONS - ye kisi bhi thread se call ho sakte hain, andar se
# hamesha browser-worker thread pe hi kaam hota hai.
# ------------------------------------------------------------------

def yt_play(params: dict) -> str:
    query = params.get("query", "").strip()
    if not query:
        return "Kya play karna hai, naam batao."
    try:
        return run_in_browser_thread(lambda: _yt_play_impl(query))
    except Exception as e:
        return f"Play nahi ho saka: {e}"


def yt_like(params: dict) -> str:
    try:
        return run_in_browser_thread(_yt_like_impl)
    except Exception as e:
        return f"Like nahi ho saka (login check karo): {e}"


def yt_subscribe(params: dict) -> str:
    try:
        return run_in_browser_thread(_yt_subscribe_impl)
    except Exception as e:
        return f"Subscribe nahi ho saka (login check karo): {e}"


def yt_pause_resume(params: dict) -> str:
    try:
        return run_in_browser_thread(_yt_pause_resume_impl)
    except Exception as e:
        return f"Nahi ho saka: {e}"


def yt_next(params: dict) -> str:
    try:
        return run_in_browser_thread(_yt_next_impl)
    except Exception as e:
        return f"Nahi ho saka: {e}"


def yt_mute_toggle(params: dict) -> str:
    try:
        return run_in_browser_thread(_yt_mute_toggle_impl)
    except Exception as e:
        return f"Nahi ho saka: {e}"


def yt_fullscreen_toggle(params: dict) -> str:
    try:
        return run_in_browser_thread(_yt_fullscreen_toggle_impl)
    except Exception as e:
        return f"Nahi ho saka: {e}"


def yt_close(params: dict) -> str:
    try:
        return run_in_browser_thread(_yt_close_impl)
    except Exception as e:
        return f"Nahi ho saka: {e}"


ACTIONS = {
    "yt_play": yt_play,
    "yt_like": yt_like,
    "yt_subscribe": yt_subscribe,
    "yt_pause_resume": yt_pause_resume,
    "yt_next": yt_next,
    "yt_mute_toggle": yt_mute_toggle,
    "yt_fullscreen_toggle": yt_fullscreen_toggle,
    "yt_close": yt_close,
}

DOCS = """
- yt_play: {"query": "lofi song"}
    (YouTube khol ke pehla result play karta hai. Ye tab yaad rakha jaata
    hai - isके baad wale yt_* commands isi tab pe chalte hain.)
- yt_like: {}  (chalu tab ke video ko like karta hai)
- yt_subscribe: {}  (chalu tab ke channel ko subscribe karta hai)
- yt_pause_resume: {}  (play/pause toggle)
- yt_next: {}  (agla video)
- yt_mute_toggle: {}  (mute/unmute)
- yt_fullscreen_toggle: {}  (fullscreen on/off)
- yt_close: {}  (YouTube tab/browser band karo)

Example:
User: "youtube khol ke koi lofi gaana play karo"
-> {"actions": [{"action": "yt_play", "params": {"query": "lofi song"}}]}

(usi conversation ke aage) User: "ise like kar do"
-> {"actions": [{"action": "yt_like", "params": {}}]}

User: "channel subscribe kar do"
-> {"actions": [{"action": "yt_subscribe", "params": {}}]}
"""
