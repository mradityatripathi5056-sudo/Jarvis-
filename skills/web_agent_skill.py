"""
skills/web_agent_skill.py
------------------------------------------------------------
GENERAL SOLUTION: "Flipkart pe kuch karo", "Amazon pe X order karo",
"is website pe Y karo" - in sabke liye ALAG-ALAG skill/selector code
likhne ki zaroorat khatam karne ke liye.

Ab tak: browser_automation_skill.py mein actions the (browser_click,
browser_fill_form) lekin unko EXACT CSS selector chahiye hota tha -
matlab har naye website ke liye Jarvis (ya tumhe) selector pehle se
pata hona chahiye tha.

Ab: ye skill EK hi generic action deti hai - `web_do_task`. Ye:
  1. Website kholta hai
  2. Page ke visible clickable/typeable elements (buttons, inputs,
     links) ko padhta hai (jaisa ek insaan screen dekh ke samajhta hai)
  3. LLM ko puchta hai "goal poora karne ke liye ab kya karna chahiye"
     (click karna hai? type karna hai? kahan?)
  4. Wo action perform karta hai, phir page dubara padhta hai, aur
     LOOP mein ye chalta rehta hai jab tak goal poora na ho jaaye ya
     max steps khatam na ho jaayein.

Isse Flipkart ho ya koi bhi naya site jo Jarvis ne kabhi nahi dekha,
usko selector pehle se coded na ho tab bhi kaam chal jaata hai - bilkul
waise jaise ek insaan naye website pe search box dhoond ke type kar
deta hai.

LIMITATION (ईमानदारी से): ye vision/reasoning-based approach hai, 100%
foolproof nahi hai - complex/bahut dynamic websites (heavy JS, captcha,
login-wall) pe fail ho sakta hai. Payment/order-confirm jaisa kuch bhi
karne se pehle ye khud ruk ke bata dega, aage khud nahi badhega
(safety ke liye).
"""

import json
import re

import requests

import config

MAX_STEPS = 8
_STOP_KEYWORDS = ("pay", "payment", "buy now", "place order", "confirm order", "checkout")

_browser = None
_context = None
_page = None


def _ensure_page():
    global _browser, _context, _page
    if _page is not None:
        return _page
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright missing. Chalao: pip install playwright && playwright install chromium")
    playwright = sync_playwright().start()
    _browser = playwright.chromium.launch(headless=False)
    _context = _browser.new_context()
    _page = _context.new_page()
    return _page


_EXTRACT_JS = """
() => {
  const selector = 'input, textarea, select, button, a, [role="button"], [onclick], [contenteditable="true"]';
  const els = Array.from(document.querySelectorAll(selector));
  const results = [];
  let idx = 0;
  for (const el of els) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) continue;
    const style = window.getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    el.setAttribute('data-jarvis-idx', String(idx));
    results.push({
      idx: idx,
      tag: el.tagName.toLowerCase(),
      type: el.type || '',
      placeholder: el.placeholder || '',
      ariaLabel: el.getAttribute('aria-label') || '',
      name: el.name || '',
      text: (el.innerText || el.value || '').trim().slice(0, 60),
    });
    idx++;
    if (idx >= 60) break;
  }
  return results;
}
"""

_SYSTEM_PROMPT = """Tum ek web-browsing agent ho. Tumhe ek GOAL diya jaayega aur
current webpage ke visible elements ki list (index ke saath). Tumhe
decide karna hai ki GOAL poora karne ke liye AGLA EK action kya hona
chahiye.

Sirf ek JSON object return karo, kuch aur text nahi:
- {"action": "click", "idx": 5}
- {"action": "type", "idx": 3, "text": "jo bhi type karna hai"}
- {"action": "press_enter"}
- {"action": "scroll"}
- {"action": "goto", "url": "https://..."}
- {"action": "done", "message": "goal poora ho gaya, ye mila/hua"}
- {"action": "stop_for_confirmation", "message": "ye payment/order-confirm jaisa
   sensitive step hai, user se pehle confirm lo"}

RULES:
- Payment, "buy now", "place order", "confirm order", login-with-password
  jaise sensitive steps par khud mat badho - "stop_for_confirmation" bhejo.
- Agar element list mein goal ke liye kuch samajh nahi aa raha (jaise
  search box dhoondna hai but list mein nahi hai), "scroll" bhejo ya
  "done" bhej ke bata do ki nahi mila.
- Har step mein sirf EK action bhejo.
"""


def _call_llm(goal: str, elements: list, history: list) -> dict:
    elements_text = "\n".join(
        f"{e['idx']}: <{e['tag']}> type={e.get('type','')} placeholder=\"{e.get('placeholder','')}\" "
        f"aria=\"{e.get('ariaLabel','')}\" text=\"{e.get('text','')}\""
        for e in elements
    )
    history_text = "\n".join(history[-5:]) or "(koi step abhi tak nahi)"
    user_content = (
        f"GOAL: {goal}\n\nAB TAK KE STEPS:\n{history_text}\n\n"
        f"CURRENT PAGE ELEMENTS:\n{elements_text}\n\nAgla action JSON mein do:"
    )
    resp = requests.post(
        config.OPENROUTER_URL,
        headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
        json={
            "model": config.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        },
        timeout=45,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return {"action": "done", "message": "LLM se valid response nahi mila."}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {"action": "done", "message": "LLM ka response samajh nahi aaya."}


def web_do_task(params: dict) -> str:
    """params: {"url": "flipkart.com", "goal": "wireless mouse search karo aur pehla result kholo"}"""
    url = (params.get("url") or "").strip()
    goal = (params.get("goal") or "").strip()
    if not goal:
        return "Kya karna hai (goal) batao - jaise 'wireless mouse search karo'."

    try:
        page = _ensure_page()
    except Exception as e:
        return str(e)

    if not config.OPENROUTER_API_KEY:
        return "OPENROUTER_API_KEY set nahi hai, is generic web-agent ko LLM chahiye kaam karne ke liye."

    if url:
        if not url.startswith("http"):
            url = "https://" + url
        try:
            page.goto(url, timeout=20000)
        except Exception as e:
            return f"'{url}' khul nahi paya: {e}"

    history = []
    for step in range(MAX_STEPS):
        try:
            page.wait_for_timeout(800)
            elements = page.evaluate(_EXTRACT_JS)
        except Exception as e:
            return f"Page padhne mein error: {e}"

        decision = _call_llm(goal, elements, history)
        action = decision.get("action")

        if action == "done":
            return decision.get("message", "Kaam ho gaya.")
        if action == "stop_for_confirmation":
            return (
                "Ruk gaya - " + decision.get("message", "ye sensitive step hai, confirm karo pehle.")
                + " (Aage badhne ke liye khud manually confirm karo.)"
            )

        try:
            if action == "click":
                idx = decision.get("idx")
                page.click(f'[data-jarvis-idx="{idx}"]', timeout=8000)
                history.append(f"click(idx={idx})")
            elif action == "type":
                idx = decision.get("idx")
                text = decision.get("text", "")
                page.fill(f'[data-jarvis-idx="{idx}"]', text, timeout=8000)
                history.append(f"type(idx={idx}, text='{text}')")
            elif action == "press_enter":
                page.keyboard.press("Enter")
                history.append("press_enter")
            elif action == "scroll":
                page.mouse.wheel(0, 800)
                history.append("scroll")
            elif action == "goto":
                new_url = decision.get("url", "")
                if new_url:
                    page.goto(new_url, timeout=20000)
                    history.append(f"goto({new_url})")
            else:
                history.append(f"unknown_action({action})")
        except Exception as e:
            history.append(f"FAILED: {action} ({e})")

    return (
        f"{MAX_STEPS} steps try kar liye, goal pura shayad nahi hua "
        "(website complex hai ya kuch element nahi mila). Browser window mein "
        "dekh ke manually complete kar sakte ho."
    )


ACTIONS = {
    "web_do_task": web_do_task,
}

DOCS = """
- web_do_task: {"url": "flipkart.com", "goal": "wireless mouse search karo aur pehla result kholo"}
    (GENERIC action - KISI BHI website pe kaam karne ke liye, bina us site
    ke liye pehle se selector/code likhe. "url" optional hai (agar browser
    already sahi page pe hai to na do). Ye action screen padh ke khud
    decide karta hai kahan click/type karna hai - naye/anjaan websites ke
    liye bhi kaam karta hai. Payment/order-confirm jaisa sensitive step
    aane par khud ruk jaata hai, confirm maangta hai.
    IMPORTANT: jab bhi user kisi SPECIFIC website (Flipkart, Amazon, koi
    bhi naya site) pe multi-step kaam karne ko bole ("X search karo",
    "Y order karo", "Z form fill karo"), aur koi dedicated action na ho,
    to YE generic action use karo - naya skill likhne ki zaroorat nahi.

Example:
User: "flipkart pe wireless mouse search karke pehla result khol do"
-> {"actions": [{"action": "web_do_task", "params": {"url": "flipkart.com", "goal": "wireless mouse search karo aur pehla result kholo"}}]}

User: "amazon.in pe jaake bluetooth headphones dhoondo"
-> {"actions": [{"action": "web_do_task", "params": {"url": "amazon.in", "goal": "bluetooth headphones search karo"}}]}
"""
