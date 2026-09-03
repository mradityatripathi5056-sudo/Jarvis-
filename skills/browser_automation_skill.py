"""
skills/browser_automation_skill.py
------------------------------------------------------------
Selenium/Playwright level deep browser control - form filling,
scraping (sirf public/allowed pages pe - kisi site ke terms/robots.txt
todna avoid karo), multi-tab management.

SETUP:
  pip install playwright
  playwright install chromium

Ye ek hi persistent browser session maintain karta hai (jab tak
Jarvis chal raha hai) taaki "naya tab kholo", "pichle tab pe jao"
jaisi multi-tab commands kaam kar sakein.
"""

_browser = None
_context = None
_pages = []  # open tabs
_current_index = 0


def _ensure_browser():
    global _browser, _context
    if _browser is not None:
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright missing. Chalao: pip install playwright && playwright install chromium")
    playwright = sync_playwright().start()
    _browser = playwright.chromium.launch(headless=False)
    _context = _browser.new_context()


def _current_page():
    global _current_index
    if not _pages:
        _ensure_browser()
        page = _context.new_page()
        _pages.append(page)
        _current_index = 0
    return _pages[_current_index]


def browser_open_page(params: dict) -> str:
    url = params.get("url", "")
    if not url:
        return "Kaunsa URL kholna hai, batao."
    if not url.startswith("http"):
        url = "https://" + url
    try:
        _ensure_browser()
        page = _current_page()
        page.goto(url, timeout=20000)
        return f"'{url}' khol diya browser mein."
    except Exception as e:
        return f"Page open nahi ho saka: {e}"


def browser_new_tab(params: dict) -> str:
    url = params.get("url", "")
    try:
        _ensure_browser()
        page = _context.new_page()
        _pages.append(page)
        global _current_index
        _current_index = len(_pages) - 1
        if url:
            if not url.startswith("http"):
                url = "https://" + url
            page.goto(url, timeout=20000)
        return f"Naya tab khul gaya ({len(_pages)} tabs total)."
    except Exception as e:
        return f"Naya tab nahi khul saka: {e}"


def browser_switch_tab(params: dict) -> str:
    index = params.get("index")
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


def browser_close_tab(params: dict) -> str:
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


def browser_fill_form(params: dict) -> str:
    """fields: {"css_selector": "value ya text", ...}, submit_selector optional."""
    fields = params.get("fields", {})
    submit_selector = params.get("submit_selector", "")
    if not fields:
        return "Kaunse fields fill karne hain, selector aur value batao."
    try:
        page = _current_page()
        for selector, value in fields.items():
            page.fill(selector, str(value), timeout=8000)
        if submit_selector:
            page.click(submit_selector, timeout=8000)
        return "Form fill (aur submit) kar diya."
    except Exception as e:
        return f"Form fill nahi ho saka: {e}"


def browser_click(params: dict) -> str:
    selector = params.get("selector", "")
    if not selector:
        return "Kis element pe click karna hai, CSS selector batao."
    try:
        page = _current_page()
        page.click(selector, timeout=8000)
        return f"'{selector}' pe click kar diya."
    except Exception as e:
        return f"Click nahi ho saka: {e}"


def browser_scrape_text(params: dict) -> str:
    """Ek page ke text/selector-matched content ko nikalta hai."""
    url = params.get("url", "")
    selector = params.get("selector", "body")
    try:
        _ensure_browser()
        page = _current_page()
        if url:
            if not url.startswith("http"):
                url = "https://" + url
            page.goto(url, timeout=20000)
        elements = page.query_selector_all(selector)
        texts = [el.inner_text().strip() for el in elements if el.inner_text().strip()]
        combined = "\n".join(texts)[:2500]
        return combined if combined else "Kuch text nahi mila is selector mein."
    except Exception as e:
        return f"Scrape nahi ho saka: {e}"


def browser_screenshot_page(params: dict) -> str:
    path = params.get("path", "page_screenshot.png")
    try:
        page = _current_page()
        page.screenshot(path=path, full_page=True)
        return f"Page screenshot save ho gaya: {path}"
    except Exception as e:
        return f"Screenshot nahi ho saka: {e}"


def browser_close_all(params: dict) -> str:
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


ACTIONS = {
    "browser_open_page": browser_open_page,
    "browser_new_tab": browser_new_tab,
    "browser_switch_tab": browser_switch_tab,
    "browser_close_tab": browser_close_tab,
    "browser_fill_form": browser_fill_form,
    "browser_click": browser_click,
    "browser_scrape_text": browser_scrape_text,
    "browser_screenshot_page": browser_screenshot_page,
    "browser_close_all": browser_close_all,
}

DOCS = """
- browser_open_page: {"url": "example.com"}  (deep-automation browser mein page kholta hai)
- browser_new_tab: {"url": "example.com"}  (naya tab, url optional)
- browser_switch_tab: {"index": 0}  (index optional, na do to next tab)
- browser_close_tab: {}
- browser_fill_form: {"fields": {"#email": "a@b.com", "#name": "Aditya"}, "submit_selector": "button[type=submit]"}
- browser_click: {"selector": "#login-button"}
- browser_scrape_text: {"url": "example.com", "selector": "body"}
    (sirf public/allowed pages scrape karo, kisi site ke terms na todo)
- browser_screenshot_page: {"path": "page.png"}
- browser_close_all: {}
    (isse alag browser khulta hai jo "open_website" wale se independent hai
    - ye Selenium/Playwright level control ke liye hai)

Example:
User: "example.com ka form fill karo email a@b.com daal ke"
-> {"actions": [{"action": "browser_fill_form", "params": {"fields": {"#email": "a@b.com"}, "submit_selector": "button[type=submit]"}}]}
"""
