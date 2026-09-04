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

THREADING FIX (zaroor padhna):
Jarvis har command (bola ya type kiya) ek NAYE thread mein process
karta hai (gui.py). Playwright ki sync API sirf usi thread se kaam
karti hai jisne use start kiya - isliye pehle "flipkart kholo" ek
thread mein browser khol deta tha, aur agla command ("earbuds search
karo") ek NAYE thread se aata tha -> Playwright error deta tha:
"cannot switch to a different thread (which happens to have exited)".

Ab saare Playwright calls `browser_worker.run_in_browser_thread(...)`
ke zariye ek hi fixed background thread mein bhejte hain, chahe
command kisi bhi thread se aaye - bilkul youtube_control_skill.py
jaise hi pattern se.
"""

import os

import config
import browser_worker
from browser_worker import run_in_browser_thread


# ------------------------------------------------------------------
# Internal implementations - ye sab SIRF browser-worker thread ke
# andar chalti hain (run_in_browser_thread ke zariye call hoti hain).
# Actual browser/tab state ab browser_worker.py mein shared hai (isi
# module ko web_agent_skill.py bhi use karta hai) - taaki "already open
# tab pe kaam karo" jaisa command sahi (same) tab pe kaam kare, chahe
# wo tab kisi bhi skill se khula ho.
# ------------------------------------------------------------------


def _browser_open_page_impl(url: str) -> str:
    page = browser_worker.get_current_page()
    page.goto(url, timeout=20000)
    return f"'{url}' khol diya browser mein."


def _browser_new_tab_impl(url: str) -> str:
    browser_worker.new_tab(url)
    return f"Naya tab khul gaya ({browser_worker.tab_count()} tabs total)."


def _browser_switch_tab_impl(index):
    return browser_worker.switch_tab(index)


def _browser_close_tab_impl() -> str:
    return browser_worker.close_current_tab()


def _browser_fill_form_impl(fields: dict, submit_selector: str) -> str:
    page = browser_worker.get_current_page()
    for selector, value in fields.items():
        page.fill(selector, str(value), timeout=8000)
    if submit_selector:
        page.click(submit_selector, timeout=8000)
    return "Form fill (aur submit) kar diya."


def _browser_click_impl(selector: str) -> str:
    page = browser_worker.get_current_page()
    page.click(selector, timeout=8000)
    return f"'{selector}' pe click kar diya."


def _browser_scrape_text_impl(url: str, selector: str) -> str:
    page = browser_worker.get_current_page()
    if url:
        page.goto(url, timeout=20000)
    elements = page.query_selector_all(selector)
    texts = [el.inner_text().strip() for el in elements if el.inner_text().strip()]
    combined = "\n".join(texts)[:2500]
    return combined if combined else "Kuch text nahi mila is selector mein."


def _browser_screenshot_page_impl(path: str) -> str:
    page = browser_worker.get_current_page()
    page.screenshot(path=path, full_page=True)
    return f"Page screenshot save ho gaya: {path}"


def _browser_close_all_impl() -> str:
    return browser_worker.close_all_browsers()
    _current_index = 0
    return "Poora automation browser band kar diya."


# ------------------------------------------------------------------
# Public ACTIONS - ye kisi bhi thread se call ho sakte hain, andar se
# hamesha browser-worker thread pe hi kaam hota hai.
# ------------------------------------------------------------------

def browser_open_page(params: dict) -> str:
    url = params.get("url", "")
    if not url:
        return "Kaunsa URL kholna hai, batao."
    if not url.startswith("http"):
        url = "https://" + url
    try:
        return run_in_browser_thread(lambda: _browser_open_page_impl(url))
    except Exception as e:
        return f"Page open nahi ho saka: {e}"


def browser_new_tab(params: dict) -> str:
    url = params.get("url", "")
    if url and not url.startswith("http"):
        url = "https://" + url
    try:
        return run_in_browser_thread(lambda: _browser_new_tab_impl(url))
    except Exception as e:
        return f"Naya tab nahi khul saka: {e}"


def browser_switch_tab(params: dict) -> str:
    index = params.get("index")
    try:
        return run_in_browser_thread(lambda: _browser_switch_tab_impl(index))
    except Exception as e:
        return f"Tab switch nahi ho saka: {e}"


def browser_close_tab(params: dict) -> str:
    try:
        return run_in_browser_thread(_browser_close_tab_impl)
    except Exception as e:
        return f"Tab band nahi ho saka: {e}"


def browser_fill_form(params: dict) -> str:
    """fields: {"css_selector": "value ya text", ...}, submit_selector optional."""
    fields = params.get("fields", {})
    submit_selector = params.get("submit_selector", "")
    if not fields:
        return "Kaunse fields fill karne hain, selector aur value batao."
    try:
        return run_in_browser_thread(lambda: _browser_fill_form_impl(fields, submit_selector))
    except Exception as e:
        return f"Form fill nahi ho saka: {e}"


def browser_click(params: dict) -> str:
    selector = params.get("selector", "")
    if not selector:
        return "Kis element pe click karna hai, CSS selector batao."
    try:
        return run_in_browser_thread(lambda: _browser_click_impl(selector))
    except Exception as e:
        return f"Click nahi ho saka: {e}"


def browser_scrape_text(params: dict) -> str:
    """Ek page ke text/selector-matched content ko nikalta hai."""
    url = params.get("url", "")
    selector = params.get("selector", "body")
    if url and not url.startswith("http"):
        url = "https://" + url
    try:
        return run_in_browser_thread(lambda: _browser_scrape_text_impl(url, selector))
    except Exception as e:
        return f"Scrape nahi ho saka: {e}"


def browser_screenshot_page(params: dict) -> str:
    path = params.get("path", "page_screenshot.png")
    if not os.path.isabs(path) and os.path.dirname(path) == "":
        path = os.path.join(config.MEDIA_DIR, path)
    try:
        return run_in_browser_thread(lambda: _browser_screenshot_page_impl(path))
    except Exception as e:
        return f"Screenshot nahi ho saka: {e}"


def browser_close_all(params: dict) -> str:
    try:
        return run_in_browser_thread(_browser_close_all_impl)
    except Exception as e:
        return f"Band nahi ho saka: {e}"


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
