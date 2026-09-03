"""
skills/whatsapp_web_skill.py
------------------------------------------------------------
WhatsApp Web (web.whatsapp.com) ko Playwright se control karta hai.

Ye purane `send_message` (actions.py, pywhatkit-based) se alag hai -
usme phone number + country code (jaise +91...) dena zaroori tha.
Yahan sirf NAAM se message bhej sakte ho (WhatsApp Web ke apne search
box se dhoondta hai - jaise tum khud UI mein type karte ho), aur
voice/video call bhi start kar sakte ho (pywhatkit isse bilkul nahi
kar sakta tha - usme sirf message bhejna possible tha).

SETUP:
  pip install playwright
  playwright install chromium

PEHLI BAAR:
  Jab pehli baar koi whatsapp_* action chalega, ek Chromium window
  khulega web.whatsapp.com ke saath - apne phone se QR scan karo
  (WhatsApp -> Settings -> Linked Devices -> Link a Device). Uske
  baad session `whatsapp_browser_profile/` folder mein save rehta
  hai, dobara QR scan nahi karna padega jab tak wahan se logout na
  karo ya wo folder delete na karo.

LIMITATION: WhatsApp Web apna HTML/CSS structure kabhi-kabhi badalta
rehta hai, isliye agar Meta kuch UI update kare to selectors yahan
bhi update karne padenge (error message mein clue mil jayega).
"""

import os
import time

_PROFILE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "whatsapp_browser_profile"
)

_context = None
_page = None


def _ensure_page():
    global _context, _page

    # Pehle purani page check karo - agar zinda hai to wahi use karo.
    if _page is not None:
        try:
            _page.title()
            return _page
        except Exception:
            _page = None

    # Purana context bhi mar chuka ho sakta hai (jaise user ne Chromium
    # window manually band kar di, ya browser crash ho gaya) - aisi
    # halat mein new_page() bhi fail karta hai ("Target page, context or
    # browser has been closed"). Isliye context ko bhi health-check karo,
    # aur mara hua ho to poora fresh context banao.
    if _context is not None:
        try:
            _ = _context.pages  # agar context dead hai to ye bhi exception dega
        except Exception:
            _context = None

    if _context is None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright missing hai. Chalao: pip install playwright && playwright install chromium"
            )
        playwright = sync_playwright().start()
        _context = playwright.chromium.launch_persistent_context(_PROFILE_DIR, headless=False)

    try:
        _page = _context.pages[0] if _context.pages else _context.new_page()
    except Exception:
        # Context tootа hua nikla (rare race condition) - ek baar poora
        # fresh bana ke retry karo, bina chup-chaap crash hue.
        _context = None
        from playwright.sync_api import sync_playwright
        playwright = sync_playwright().start()
        _context = playwright.chromium.launch_persistent_context(_PROFILE_DIR, headless=False)
        _page = _context.new_page()

    _page.goto("https://web.whatsapp.com", timeout=30000)
    _page.wait_for_timeout(2000)
    return _page


def _open_chat_by_name(page, name: str) -> bool:
    """WhatsApp ke apne search box mein naam type karke top result kholta hai."""
    search = page.wait_for_selector(
        'div[contenteditable="true"][data-tab="3"], div[aria-label="Search input textbox"]',
        timeout=20000,
    )
    search.click()
    search.fill("")
    search.type(name, delay=40)
    page.wait_for_timeout(1200)
    try:
        result = page.wait_for_selector(
            'div[aria-label="Search result"], span[dir="auto"][title]', timeout=6000
        )
    except Exception:
        return False
    result.click()
    page.wait_for_timeout(800)
    return True


def whatsapp_open(params: dict) -> str:
    """WhatsApp Web kholta hai. Pehli baar QR scan karna hoga phone se."""
    try:
        _ensure_page()
        return "WhatsApp Web khol diya. Agar QR code dikhe to phone se scan kar lo."
    except Exception as e:
        return f"WhatsApp Web nahi khul saka: {e}"


def send_whatsapp_message_by_name(params: dict) -> str:
    """Sirf NAAM se WhatsApp message bhejta hai (phone number nahi chahiye)."""
    name = params.get("name", "").strip()
    message = params.get("message", "").strip()
    if not name or not message:
        return "Kisko aur kya message bhejna hai, dono batao."
    try:
        page = _ensure_page()
        if not _open_chat_by_name(page, name):
            return f"'{name}' naam ka contact WhatsApp mein nahi mila - naam check karo."
        box = page.wait_for_selector(
            'div[contenteditable="true"][data-tab="10"], footer div[contenteditable="true"]',
            timeout=8000,
        )
        box.click()
        box.type(message, delay=15)
        page.keyboard.press("Enter")
        return f"'{name}' ko WhatsApp pe message bhej diya."
    except Exception as e:
        return f"Message nahi bhej saka: {e}"


def whatsapp_voice_call(params: dict) -> str:
    """Naam se WhatsApp VOICE call start karta hai."""
    name = params.get("name", "").strip()
    if not name:
        return "Kisko call karna hai, naam batao."
    try:
        page = _ensure_page()
        if not _open_chat_by_name(page, name):
            return f"'{name}' naam ka contact WhatsApp mein nahi mila."
        btn = page.wait_for_selector(
            'span[data-icon="audio-call"], span[data-icon="audio-call-refreshed"], '
            'button[aria-label="Voice call"], span[aria-label="Voice call"]',
            timeout=8000,
        )
        btn.click()
        return f"'{name}' ko WhatsApp voice call kar raha hoon."
    except Exception as e:
        return f"Call nahi ho saka (WhatsApp ka UI update ho sakta hai): {e}"


def whatsapp_video_call(params: dict) -> str:
    """Naam se WhatsApp VIDEO call start karta hai."""
    name = params.get("name", "").strip()
    if not name:
        return "Kisko video call karna hai, naam batao."
    try:
        page = _ensure_page()
        if not _open_chat_by_name(page, name):
            return f"'{name}' naam ka contact WhatsApp mein nahi mila."
        btn = page.wait_for_selector(
            'span[data-icon="video-call"], span[data-icon="video-call-refreshed"], '
            'button[aria-label="Video call"], span[aria-label="Video call"]',
            timeout=8000,
        )
        btn.click()
        return f"'{name}' ko WhatsApp video call kar raha hoon."
    except Exception as e:
        return f"Video call nahi ho saka (WhatsApp ka UI update ho sakta hai): {e}"


def _last_incoming_message_text(page):
    """Currently khuli chat mein sabse aakhri INCOMING (unke bheje hue)
    message ka text - apne khud ke bheje hue (message-out) ko ignore
    karta hai, taaki apna hi message 'naya reply' na samjha jaaye."""
    bubbles = page.query_selector_all("div.message-in")
    if not bubbles:
        return None
    last = bubbles[-1]
    text_el = last.query_selector("span.selectable-text")
    return text_el.inner_text().strip() if text_el else None


def whatsapp_wait_for_reply(params: dict) -> str:
    """Chat khuli rakh ke us insaan ke NAYE reply ka wait karta hai - jab
    tak reply na aaye ya timeout na ho jaaye, window band nahi hoti. Isko
    use karo jab user kahe 'reply dena/batana', 'reply ka wait karo', ya
    'jab wo reply kare to batana' - is case mein whatsapp_close BILKUL mat
    bulana, sirf yahi action bulao."""
    name = params.get("name", "").strip()
    timeout = int(params.get("timeout_seconds", 120))
    try:
        page = _ensure_page()
        if name:
            if not _open_chat_by_name(page, name):
                return f"'{name}' naam ka contact WhatsApp mein nahi mila."

        baseline = _last_incoming_message_text(page)
        start = time.time()
        while time.time() - start < timeout:
            page.wait_for_timeout(2000)
            try:
                current = _last_incoming_message_text(page)
            except Exception:
                # Beech mein browser/page band ho gaya (jaise koi galti se
                # Chromium window close kar de) - ek baar dobara kholne ki
                # koshish karo, taaki poora wait crash na ho jaaye.
                try:
                    page = _ensure_page()
                    if name:
                        _open_chat_by_name(page, name)
                    continue
                except Exception as reopen_err:
                    return f"Wait ke beech mein WhatsApp window band ho gayi thi, dobara kholne mein bhi error: {reopen_err}"
            if current and current != baseline:
                who = f"{name} ka" if name else ""
                return f'{who} reply aa gaya: "{current}"'.strip()
        return f"{timeout} second tak koi naya reply nahi aaya, wait band kar diya."
    except Exception as e:
        return f"Reply ka wait karte waqt error aaya: {e}"


def whatsapp_close(params: dict) -> str:
    """WhatsApp Web ka browser band kar deta hai (session profile mein save rehta hai)."""
    global _context, _page
    try:
        if _context:
            _context.close()
    except Exception:
        pass
    _context = None
    _page = None
    return "WhatsApp Web band kar diya."


ACTIONS = {
    "whatsapp_open": whatsapp_open,
    "send_whatsapp_message_by_name": send_whatsapp_message_by_name,
    "whatsapp_voice_call": whatsapp_voice_call,
    "whatsapp_video_call": whatsapp_video_call,
    "whatsapp_wait_for_reply": whatsapp_wait_for_reply,
    "whatsapp_close": whatsapp_close,
}

DOCS = """
- whatsapp_open: {}  (WhatsApp Web kholta hai, pehli baar QR scan karna hoga)
- send_whatsapp_message_by_name: {"name": "Rohit", "message": "Kal milte hain"}
    (phone number NAHI chahiye - seedha naam se, WhatsApp ke apne search se)
- whatsapp_voice_call: {"name": "Rohit"}  (WhatsApp voice call start karta hai)
- whatsapp_video_call: {"name": "Rohit"}  (WhatsApp video call start karta hai)
- whatsapp_wait_for_reply: {"name": "Rohit"}  YA {"name": "Rohit", "timeout_seconds": 180}
    (chat khuli rakh ke uske NAYE reply ka wait karta hai, aate hi bata deta
    hai - timeout_seconds optional hai, default 120. IMPORTANT: jab user
    "reply dena/batana/wait karo" jaisa kuch bole, hamesha ye action use
    karo - whatsapp_close KABHI mat bulana jab tak user khud "band karo"
    na bole, warna chat/window band ho jaayegi aur reply kabhi capture
    nahi hoga.)
- whatsapp_close: {}  (WhatsApp Web browser band karo - SIRF jab user
    explicitly "band karo"/"close karo" bole, kisi aur case mein nahi)

Example:
User: "Rohit ko WhatsApp pe bhejo ki main late hoon"
-> {"actions": [{"action": "send_whatsapp_message_by_name", "params": {"name": "Rohit", "message": "Main late hoon"}}]}

User: "Rohit ko whatsapp pe call karo"
-> {"actions": [{"action": "whatsapp_voice_call", "params": {"name": "Rohit"}}]}

User: "Rohit ko bhej do ki main late hoon aur uska reply aate hi batana"
-> {"actions": [
     {"action": "send_whatsapp_message_by_name", "params": {"name": "Rohit", "message": "Main late hoon"}},
     {"action": "whatsapp_wait_for_reply", "params": {"name": "Rohit"}}
   ]}
"""
