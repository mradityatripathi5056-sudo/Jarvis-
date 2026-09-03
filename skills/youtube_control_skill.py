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
"""

_browser = None
_context = None
_page = None


def _ensure_page():
    """Chalu YouTube tab return karta hai. Agar band ho gaya ho ya kabhi
    khula hi na ho, naya bana deta hai."""
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


def yt_play(params: dict) -> str:
    """YouTube pe search karke pehla video usi (yaad rakhe hue) tab mein play karta hai."""
    query = params.get("query", "").strip()
    if not query:
        return "Kya play karna hai, naam batao."
    try:
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
    except Exception as e:
        return f"Play nahi ho saka: {e}"


def yt_like(params: dict) -> str:
    """Chalu tab ke video ko like karta hai (agar already liked hai to bata deta hai)."""
    if _page is None:
        return "Pehle koi video play karo, phir like karna."
    try:
        btn = _page.wait_for_selector(
            "button[aria-label*='like this video' i], ytd-menu-renderer #segmented-like-button button",
            timeout=6000,
        )
        if (btn.get_attribute("aria-pressed") or "").lower() == "true":
            return "Ye video already liked hai."
        btn.click()
        return "Video like kar diya!"
    except Exception as e:
        return f"Like nahi ho saka (login check karo): {e}"


def yt_subscribe(params: dict) -> str:
    """Chalu tab ke channel ko subscribe karta hai."""
    if _page is None:
        return "Pehle koi video play karo, phir subscribe karna."
    try:
        btn = _page.wait_for_selector(
            "ytd-subscribe-button-renderer button, #subscribe-button button",
            timeout=6000,
        )
        if "subscribed" in (btn.inner_text() or "").strip().lower():
            return "Ye channel already subscribed hai."
        btn.click()
        return "Channel subscribe kar diya!"
    except Exception as e:
        return f"Subscribe nahi ho saka (login check karo): {e}"

def yt_pause_resume(params: dict) -> str:
    """Chalu video ka play/pause toggle karta hai."""
    if _page is None:
        return "Koi video khula hi nahi hai."
    try:
        _page.keyboard.press("k")
        return "Play/pause toggle kar diya."
    except Exception as e:
        return f"Nahi ho saka: {e}"


def yt_next(params: dict) -> str:
    """Agla suggested/queue video pe jaata hai."""
    if _page is None:
        return "Koi video khula hi nahi hai."
    try:
        _page.keyboard.press("shift+n")
        return "Next video pe gaya."
    except Exception as e:
        return f"Nahi ho saka: {e}"


def yt_mute_toggle(params: dict) -> str:
    """Video mute/unmute toggle karta hai."""
    if _page is None:
        return "Koi video khula hi nahi hai."
    try:
        _page.keyboard.press("m")
        return "Mute/unmute toggle kar diya."
    except Exception as e:
        return f"Nahi ho saka: {e}"


def yt_fullscreen_toggle(params: dict) -> str:
    """Fullscreen on/off toggle karta hai."""
    if _page is None:
        return "Koi video khula hi nahi hai."
    try:
        _page.keyboard.press("f")
        return "Fullscreen toggle kar diya."
    except Exception as e:
        return f"Nahi ho saka: {e}"


def yt_close(params: dict) -> str:
    """YouTube tab/browser poori tarah band karta hai (agli baar 'play karo' se naya khulega)."""
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
