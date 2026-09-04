"""
skills/cloud_files_skill.py
------------------------------------------------------------
Google Drive, OneDrive, Dropbox access + bulk local file operations
+ smart search (naam ke alawa file content ke andar bhi search).

SETUP:
Google Drive: calendar_email_skill.py wala hi google_credentials.json/
  google_token.json use hota hai (bas scope mein Drive add hoga -
  isliye pehli baar Drive action chalane par dobara login mangega).
OneDrive: calendar_email_skill.py wala hi Microsoft login (MS_CLIENT_ID)
  use hota hai, Files.ReadWrite permission add karo Azure app mein.
Dropbox: pip install dropbox, .env mein DROPBOX_ACCESS_TOKEN=...
  (dropbox.com/developers/apps se app banake generated access token)
"""

import os
import fnmatch


# ---------------- Google Drive ----------------

def _drive_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError("pip install google-auth-oauthlib google-api-python-client google-auth-httplib2")

    creds_file = "google_credentials.json"
    token_file = "google_drive_token.json"
    scopes = ["https://www.googleapis.com/auth/drive"]
    if not os.path.exists(creds_file):
        raise RuntimeError(f"'{creds_file}' nahi mili - calendar_email_skill.py ke setup steps follow karo.")

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, scopes)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def drive_search_file(params: dict) -> str:
    query = params.get("query", "")
    try:
        service = _drive_service()
        results = service.files().list(
            q=f"name contains '{query}'", pageSize=10, fields="files(id, name, mimeType)"
        ).execute()
        files = results.get("files", [])
        if not files:
            return f"Google Drive mein '{query}' se milti koi file nahi mili."
        return "Mila:\n" + "\n".join(f"{f['name']} ({f['id']})" for f in files)
    except Exception as e:
        return f"Drive search nahi ho saka: {e}"


def drive_upload_file(params: dict) -> str:
    path = params.get("path", "")
    if not os.path.exists(path):
        return f"'{path}' local file nahi mili."
    try:
        from googleapiclient.http import MediaFileUpload
        service = _drive_service()
        media = MediaFileUpload(path, resumable=True)
        file_metadata = {"name": os.path.basename(path)}
        file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        return f"'{path}' Google Drive pe upload ho gayi (id: {file.get('id')})."
    except Exception as e:
        return f"Drive upload nahi ho saka: {e}"


def drive_download_file(params: dict) -> str:
    file_id = params.get("file_id", "")
    save_path = params.get("save_path", "downloaded_file")
    try:
        from googleapiclient.http import MediaIoBaseDownload
        import io
        service = _drive_service()
        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(save_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return f"Drive file '{save_path}' mein download ho gayi."
    except Exception as e:
        return f"Drive download nahi ho saka: {e}"


# ---------------- Dropbox ----------------

def _dropbox_client():
    try:
        import dropbox
    except ImportError:
        raise RuntimeError("pip install dropbox")
    token = os.getenv("DROPBOX_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError(".env mein DROPBOX_ACCESS_TOKEN set nahi hai.")
    return dropbox.Dropbox(token)


def dropbox_upload_file(params: dict) -> str:
    path = params.get("path", "")
    if not os.path.exists(path):
        return f"'{path}' local file nahi mili."
    try:
        dbx = _dropbox_client()
        with open(path, "rb") as f:
            dbx.files_upload(f.read(), "/" + os.path.basename(path), mute=True)
        return f"'{path}' Dropbox pe upload ho gayi."
    except Exception as e:
        return f"Dropbox upload nahi ho saka: {e}"


def dropbox_list_files(params: dict) -> str:
    folder = params.get("folder", "")
    try:
        dbx = _dropbox_client()
        result = dbx.files_list_folder(folder)
        names = [entry.name for entry in result.entries]
        return "Dropbox files:\n" + "\n".join(names) if names else "Dropbox folder khaali hai."
    except Exception as e:
        return f"Dropbox list nahi ho saka: {e}"


# ---------------- OneDrive (Microsoft Graph) ----------------

def _ms_token():
    try:
        from skills.calendar_email_skill import _get_ms_token
    except Exception:
        raise RuntimeError("calendar_email_skill.py setup pehle karo (MS_CLIENT_ID).")
    return _get_ms_token()


def onedrive_list_files(params: dict) -> str:
    folder = params.get("folder", "")
    try:
        import requests
        token = _ms_token()
        path = f"/me/drive/root:/{folder}:/children" if folder else "/me/drive/root/children"
        resp = requests.get(f"https://graph.microsoft.com/v1.0{path}",
                             headers={"Authorization": f"Bearer {token}"}, timeout=15)
        items = resp.json().get("value", [])
        names = [item["name"] for item in items]
        return "OneDrive files:\n" + "\n".join(names) if names else "OneDrive folder khaali hai."
    except Exception as e:
        return f"OneDrive list nahi ho saka: {e}"


def onedrive_upload_file(params: dict) -> str:
    path = params.get("path", "")
    if not os.path.exists(path):
        return f"'{path}' local file nahi mili."
    try:
        import requests
        token = _ms_token()
        filename = os.path.basename(path)
        with open(path, "rb") as f:
            resp = requests.put(
                f"https://graph.microsoft.com/v1.0/me/drive/root:/{filename}:/content",
                headers={"Authorization": f"Bearer {token}"}, data=f.read(), timeout=30,
            )
        if resp.status_code in (200, 201):
            return f"'{path}' OneDrive pe upload ho gayi."
        return f"OneDrive upload fail: {resp.status_code}"
    except Exception as e:
        return f"OneDrive upload nahi ho saka: {e}"


# ---------------- Local bulk ops + smart search ----------------

def bulk_rename_files(params: dict) -> str:
    folder = params.get("folder", "")
    pattern = params.get("pattern", "*")
    prefix = params.get("prefix", "")
    if not os.path.isdir(folder):
        return f"'{folder}' folder nahi mila."
    count = 0
    for name in os.listdir(folder):
        if fnmatch.fnmatch(name, pattern):
            os.rename(os.path.join(folder, name), os.path.join(folder, f"{prefix}{name}"))
            count += 1
    return f"{count} files ka naam badal diya '{folder}' mein."


def smart_search_files(params: dict) -> str:
    """Naam se ya (chhoti text files mein) content se search karta hai."""
    folder = params.get("folder", ".")
    query = params.get("query", "").lower()
    search_content = bool(params.get("search_content", False))
    matches = []
    for root, _, files in os.walk(folder):
        for name in files:
            full_path = os.path.join(root, name)
            if query in name.lower():
                matches.append(full_path)
                continue
            if search_content and name.lower().endswith((".txt", ".md", ".py", ".js", ".json")):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        if query in f.read().lower():
                            matches.append(full_path)
                except Exception:
                    pass
            if len(matches) >= 30:
                break
    if not matches:
        return f"'{query}' se koi file nahi mili."
    return f"{len(matches)} files mile:\n" + "\n".join(matches[:30])


ACTIONS = {
    "drive_search_file": drive_search_file,
    "drive_upload_file": drive_upload_file,
    "drive_download_file": drive_download_file,
    "dropbox_upload_file": dropbox_upload_file,
    "dropbox_list_files": dropbox_list_files,
    "onedrive_list_files": onedrive_list_files,
    "onedrive_upload_file": onedrive_upload_file,
    "bulk_rename_files": bulk_rename_files,
    "smart_search_files": smart_search_files,
}

DOCS = """
- drive_search_file: {"query": "resume"}  (Google Drive mein search)
- drive_upload_file: {"path": "report.pdf"}
- drive_download_file: {"file_id": "...", "save_path": "report.pdf"}
- dropbox_upload_file: {"path": "report.pdf"}
- dropbox_list_files: {"folder": ""}
- onedrive_list_files: {"folder": ""}
- onedrive_upload_file: {"path": "report.pdf"}
- bulk_rename_files: {"folder": "C:\\\\Users\\\\Aditya\\\\Downloads", "pattern": "*.jpg", "prefix": "trip_"}
- smart_search_files: {"folder": "C:\\\\Users\\\\Aditya", "query": "invoice", "search_content": true}
    (naam ke alawa file ke andar text bhi search kar sakta hai)

Example:
User: "Downloads folder ki saari jpg files ko trip_ prefix se rename karo"
-> {"actions": [{"action": "bulk_rename_files", "params": {"folder": "Downloads", "pattern": "*.jpg", "prefix": "trip_"}}]}
"""
