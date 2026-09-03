"""
skills/calendar_email_skill.py
------------------------------------------------------------
Gmail + Outlook (email) aur Google Calendar - REAL read/write access.

SETUP ZAROORI HAI (bina iske ye actions kaam nahi karenge):

GMAIL + GOOGLE CALENDAR:
1. pip install google-auth-oauthlib google-api-python-client google-auth-httplib2
2. https://console.cloud.google.com par jao -> naya project -> "Gmail API"
   aur "Google Calendar API" dono enable karo.
3. "OAuth consent screen" bana ke "Desktop app" type ka OAuth client banao,
   JSON download karo, isko jarvis folder mein `google_credentials.json`
   naam se rakho.
4. Pehli baar koi Gmail/Calendar action chalaoge to browser khulega, apne
   Google account se login/allow karo - ek `google_token.json` ban jayega
   (uske baad dobara login nahi maangega).

OUTLOOK (Microsoft Graph):
1. pip install msal
2. https://portal.azure.com -> Azure AD -> App registrations -> New
   registration ("Public client/native" type). Mail.Send, Mail.Read,
   Calendars.ReadWrite permissions add karo.
3. .env mein: MS_CLIENT_ID=<application id>
4. Pehli baar action chalaoge to terminal mein ek code + link milega,
   browser mein login karke device code enter karo (token cache ho jayega).

Dono setup na ho to ye actions error message denge (crash nahi karenge).
"""

import base64
import json
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText

GOOGLE_CREDS_FILE = "google_credentials.json"
GOOGLE_TOKEN_FILE = "google_token.json"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]

MS_TOKEN_CACHE_FILE = "ms_token_cache.json"
MS_SCOPES = ["Mail.Send", "Mail.Read", "Calendars.ReadWrite"]


# ---------------- Google (Gmail + Calendar) ----------------

def _get_google_service(api: str, version: str):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "Google libraries missing. Chalao: pip install google-auth-oauthlib "
            "google-api-python-client google-auth-httplib2"
        )

    if not os.path.exists(GOOGLE_CREDS_FILE):
        raise RuntimeError(
            f"'{GOOGLE_CREDS_FILE}' nahi mili. README ke Gmail/Calendar setup "
            "steps follow karo (Google Cloud Console se OAuth client banao)."
        )

    creds = None
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, GOOGLE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDS_FILE, GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(GOOGLE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build(api, version, credentials=creds)


def send_email_gmail(params: dict) -> str:
    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")
    if not to:
        return "Kisko email bhejni hai, address batao."
    try:
        service = _get_google_service("gmail", "v1")
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Gmail se '{to}' ko email bhej diya."
    except Exception as e:
        return f"Gmail email nahi bhej saka: {e}"


def read_emails_gmail(params: dict) -> str:
    count = int(params.get("count", 5))
    unread_only = bool(params.get("unread_only", False))
    try:
        service = _get_google_service("gmail", "v1")
        query = "is:unread" if unread_only else ""
        results = service.users().messages().list(userId="me", q=query, maxResults=count).execute()
        msgs = results.get("messages", [])
        if not msgs:
            return "Koi email nahi mili."
        lines = []
        for m in msgs:
            msg = service.users().messages().get(userId="me", id=m["id"], format="metadata",
                                                   metadataHeaders=["Subject", "From"]).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            lines.append(f"From {headers.get('From', '?')}: {headers.get('Subject', '(no subject)')}")
        return "Recent emails:\n" + "\n".join(lines)
    except Exception as e:
        return f"Gmail read nahi kar saka: {e}"


def create_calendar_event_google(params: dict) -> str:
    title = params.get("title", "Untitled event")
    start = params.get("start", "")  # ISO format: 2026-09-10T15:00:00
    end = params.get("end", "")
    if not start:
        return "Event ka start time do (ISO format, jaise 2026-09-10T15:00:00)."
    if not end:
        end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()
    try:
        service = _get_google_service("calendar", "v3")
        event = {
            "summary": title,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        service.events().insert(calendarId="primary", body=event).execute()
        return f"Google Calendar mein '{title}' event ban gaya."
    except Exception as e:
        return f"Calendar event nahi ban saka: {e}"


def list_calendar_events_google(params: dict) -> str:
    days = int(params.get("days", 7))
    try:
        service = _get_google_service("calendar", "v3")
        now = datetime.utcnow().isoformat() + "Z"
        later = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary", timeMin=now, timeMax=later,
            singleEvents=True, orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])
        if not events:
            return f"Agle {days} din mein koi event nahi hai."
        lines = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            lines.append(f"{start} - {e.get('summary', '(no title)')}")
        return "Upcoming events:\n" + "\n".join(lines)
    except Exception as e:
        return f"Calendar events nahi mil sake: {e}"


# ---------------- Outlook (Microsoft Graph) ----------------

def _get_ms_token():
    try:
        import msal
        import requests as _requests
    except ImportError:
        raise RuntimeError("msal missing. Chalao: pip install msal")

    import config
    client_id = os.getenv("MS_CLIENT_ID", "")
    if not client_id:
        raise RuntimeError("'.env' mein MS_CLIENT_ID set nahi hai. README ke Outlook setup steps dekho.")

    cache = msal.SerializableTokenCache()
    if os.path.exists(MS_TOKEN_CACHE_FILE):
        cache.deserialize(open(MS_TOKEN_CACHE_FILE, "r").read())

    app = msal.PublicClientApplication(
        client_id, authority="https://login.microsoftonline.com/common", token_cache=cache
    )
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(MS_SCOPES, account=accounts[0])
    if not result:
        flow = app.initiate_device_flow(scopes=MS_SCOPES)
        print(flow["message"])  # user ko terminal mein code/link dikhega
        result = app.acquire_token_by_device_flow(flow)

    with open(MS_TOKEN_CACHE_FILE, "w") as f:
        f.write(cache.serialize())

    if "access_token" not in result:
        raise RuntimeError(f"Microsoft login fail: {result.get('error_description', result)}")
    return result["access_token"]


def send_email_outlook(params: dict) -> str:
    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")
    if not to:
        return "Kisko email bhejni hai, address batao."
    try:
        import requests
        token = _get_ms_token()
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            }
        }
        resp = requests.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=15,
        )
        if resp.status_code in (200, 202):
            return f"Outlook se '{to}' ko email bhej diya."
        return f"Outlook email fail: {resp.status_code} {resp.text[:200]}"
    except Exception as e:
        return f"Outlook email nahi bhej saka: {e}"


def read_emails_outlook(params: dict) -> str:
    count = int(params.get("count", 5))
    try:
        import requests
        token = _get_ms_token()
        resp = requests.get(
            f"https://graph.microsoft.com/v1.0/me/messages?$top={count}&$select=subject,from",
            headers={"Authorization": f"Bearer {token}"}, timeout=15,
        )
        data = resp.json()
        msgs = data.get("value", [])
        if not msgs:
            return "Koi email nahi mili."
        lines = [f"From {m['from']['emailAddress']['address']}: {m['subject']}" for m in msgs]
        return "Recent Outlook emails:\n" + "\n".join(lines)
    except Exception as e:
        return f"Outlook read nahi kar saka: {e}"


def create_calendar_event_outlook(params: dict) -> str:
    title = params.get("title", "Untitled event")
    start = params.get("start", "")
    end = params.get("end", "")
    if not start:
        return "Event ka start time do (ISO format)."
    if not end:
        end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()
    try:
        import requests
        token = _get_ms_token()
        payload = {
            "subject": title,
            "start": {"dateTime": start, "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end, "timeZone": "Asia/Kolkata"},
        }
        resp = requests.post(
            "https://graph.microsoft.com/v1.0/me/events",
            headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=15,
        )
        if resp.status_code in (200, 201):
            return f"Outlook Calendar mein '{title}' event ban gaya."
        return f"Outlook event fail: {resp.status_code} {resp.text[:200]}"
    except Exception as e:
        return f"Outlook calendar event nahi ban saka: {e}"


ACTIONS = {
    "send_email_gmail": send_email_gmail,
    "read_emails_gmail": read_emails_gmail,
    "create_calendar_event_google": create_calendar_event_google,
    "list_calendar_events_google": list_calendar_events_google,
    "send_email_outlook": send_email_outlook,
    "read_emails_outlook": read_emails_outlook,
    "create_calendar_event_outlook": create_calendar_event_outlook,
}

DOCS = """
- send_email_gmail: {"to": "x@gmail.com", "subject": "Hi", "body": "..."}
- read_emails_gmail: {"count": 5, "unread_only": true}
- create_calendar_event_google: {"title": "Meeting", "start": "2026-09-10T15:00:00", "end": "2026-09-10T16:00:00"}
- list_calendar_events_google: {"days": 7}
- send_email_outlook: {"to": "x@outlook.com", "subject": "Hi", "body": "..."}
- read_emails_outlook: {"count": 5}
- create_calendar_event_outlook: {"title": "Meeting", "start": "2026-09-10T15:00:00"}
    (Gmail/Google Calendar actions ke liye google_credentials.json chahiye,
    Outlook ke liye .env mein MS_CLIENT_ID chahiye - README dekho)

Example:
User: "Rahul ko email karo ki kal miss ho jayega"
-> {"actions": [{"action": "send_email_gmail", "params": {"to": "rahul@gmail.com", "subject": "Kal ki meeting", "body": "Kal miss ho jayega"}}]}
"""
