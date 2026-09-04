"""
skills/integrations_skill.py
------------------------------------------------------------
Spotify, Slack, Notion, GitHub, Jira, AWS, Docker, MySQL/MongoDB.

Har integration ka apna .env key chahiye - jo set nahi hai uske
actions bas ek clear "setup karo" message denge, baaki sab normal
chalta rahega.

.env keys jo add karne honge (jo use karne hain sirf wahi):
  SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET   (spotipy OAuth)
  SLACK_BOT_TOKEN                             (xoxb-... token)
  NOTION_TOKEN, NOTION_DATABASE_ID            (Notion integration)
  GITHUB_TOKEN                                (personal access token)
  JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
  MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
  MONGO_URI
"""

import os
import requests


# ---------------- Spotify ----------------

def _spotify_client():
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        raise RuntimeError("pip install spotipy")
    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError(".env mein SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET set karo (developer.spotify.com se app banao).")
    auth = SpotifyOAuth(client_id=client_id, client_secret=client_secret,
                         redirect_uri="http://localhost:8888/callback",
                         scope="user-modify-playback-state user-read-playback-state")
    return spotipy.Spotify(auth_manager=auth)


def spotify_play(params: dict) -> str:
    query = params.get("query", "")
    try:
        sp = _spotify_client()
        if query:
            results = sp.search(q=query, type="track", limit=1)
            tracks = results["tracks"]["items"]
            if not tracks:
                return f"'{query}' Spotify pe nahi mila."
            sp.start_playback(uris=[tracks[0]["uri"]])
            return f"Spotify pe '{tracks[0]['name']}' play kar diya."
        sp.start_playback()
        return "Spotify play kar diya."
    except Exception as e:
        return f"Spotify play nahi ho saka: {e}"


def spotify_pause(params: dict) -> str:
    try:
        sp = _spotify_client()
        sp.pause_playback()
        return "Spotify pause kar diya."
    except Exception as e:
        return f"Spotify pause nahi ho saka: {e}"


def spotify_next(params: dict) -> str:
    try:
        sp = _spotify_client()
        sp.next_track()
        return "Agla gaana play ho raha hai."
    except Exception as e:
        return f"Next track nahi chal saka: {e}"


# ---------------- Slack ----------------

def slack_send_message(params: dict) -> str:
    channel = params.get("channel", "")
    text = params.get("text", "")
    token = os.getenv("SLACK_BOT_TOKEN", "")
    if not token:
        return ".env mein SLACK_BOT_TOKEN set karo (api.slack.com/apps se bot banao)."
    try:
        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": text}, timeout=10,
        )
        data = resp.json()
        return f"Slack pe '{channel}' mein message bhej diya." if data.get("ok") else f"Slack fail: {data.get('error')}"
    except Exception as e:
        return f"Slack message nahi bhej saka: {e}"


# ---------------- Notion ----------------

def notion_create_page(params: dict) -> str:
    title = params.get("title", "Untitled")
    content = params.get("content", "")
    token = os.getenv("NOTION_TOKEN", "")
    database_id = os.getenv("NOTION_DATABASE_ID", "")
    if not token or not database_id:
        return ".env mein NOTION_TOKEN aur NOTION_DATABASE_ID set karo."
    try:
        resp = requests.post(
            "https://api.notion.com/v1/pages",
            headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
            json={
                "parent": {"database_id": database_id},
                "properties": {"Name": {"title": [{"text": {"content": title}}]}},
                "children": [{"object": "block", "type": "paragraph",
                              "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}}] if content else [],
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return f"Notion mein '{title}' page ban gaya."
        return f"Notion fail: {resp.text[:200]}"
    except Exception as e:
        return f"Notion page nahi ban saka: {e}"


# ---------------- GitHub ----------------

def github_create_issue(params: dict) -> str:
    repo = params.get("repo", "")  # "owner/repo"
    title = params.get("title", "")
    body = params.get("body", "")
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return ".env mein GITHUB_TOKEN set karo (github.com/settings/tokens se personal access token banao)."
    try:
        resp = requests.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers={"Authorization": f"token {token}"},
            json={"title": title, "body": body}, timeout=10,
        )
        if resp.status_code == 201:
            return f"GitHub issue ban gaya: {resp.json().get('html_url')}"
        return f"GitHub fail: {resp.text[:200]}"
    except Exception as e:
        return f"GitHub issue nahi ban saka: {e}"


def github_list_open_prs(params: dict) -> str:
    repo = params.get("repo", "")
    token = os.getenv("GITHUB_TOKEN", "")
    try:
        resp = requests.get(f"https://api.github.com/repos/{repo}/pulls",
                             headers={"Authorization": f"token {token}"} if token else {}, timeout=10)
        prs = resp.json()
        if not isinstance(prs, list) or not prs:
            return f"'{repo}' mein koi open PR nahi hai."
        return "Open PRs:\n" + "\n".join(f"#{p['number']}: {p['title']}" for p in prs)
    except Exception as e:
        return f"PR list nahi mili: {e}"


# ---------------- Jira ----------------

def jira_create_issue(params: dict) -> str:
    project_key = params.get("project_key", "")
    summary = params.get("summary", "")
    description = params.get("description", "")
    jira_url = os.getenv("JIRA_URL", "")
    email = os.getenv("JIRA_EMAIL", "")
    api_token = os.getenv("JIRA_API_TOKEN", "")
    if not (jira_url and email and api_token):
        return ".env mein JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN set karo."
    try:
        resp = requests.post(
            f"{jira_url.rstrip('/')}/rest/api/2/issue",
            auth=(email, api_token),
            json={"fields": {"project": {"key": project_key}, "summary": summary,
                              "description": description, "issuetype": {"name": "Task"}}},
            timeout=10,
        )
        if resp.status_code == 201:
            return f"Jira issue ban gaya: {resp.json().get('key')}"
        return f"Jira fail: {resp.text[:200]}"
    except Exception as e:
        return f"Jira issue nahi ban saka: {e}"


# ---------------- AWS ----------------

def aws_list_s3_buckets(params: dict) -> str:
    try:
        import boto3
    except ImportError:
        return "pip install boto3"
    try:
        client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        buckets = client.list_buckets().get("Buckets", [])
        return "S3 Buckets:\n" + "\n".join(b["Name"] for b in buckets) if buckets else "Koi S3 bucket nahi mila."
    except Exception as e:
        return f"AWS S3 list nahi mili: {e}"


def aws_list_ec2_instances(params: dict) -> str:
    try:
        import boto3
    except ImportError:
        return "pip install boto3"
    try:
        client = boto3.client("ec2", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        reservations = client.describe_instances().get("Reservations", [])
        lines = []
        for r in reservations:
            for i in r["Instances"]:
                lines.append(f"{i['InstanceId']}: {i['State']['Name']}")
        return "EC2 Instances:\n" + "\n".join(lines) if lines else "Koi EC2 instance nahi mila."
    except Exception as e:
        return f"AWS EC2 list nahi mili: {e}"


# ---------------- Docker ----------------

def docker_list_containers(params: dict) -> str:
    try:
        import docker
    except ImportError:
        return "pip install docker"
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        return "Containers:\n" + "\n".join(f"{c.name}: {c.status}" for c in containers) if containers else "Koi container nahi mila."
    except Exception as e:
        return f"Docker list nahi mili: {e}"


def docker_start_container(params: dict) -> str:
    name = params.get("name", "")
    try:
        import docker
        client = docker.from_env()
        client.containers.get(name).start()
        return f"Container '{name}' start ho gaya."
    except Exception as e:
        return f"Container start nahi ho saka: {e}"


def docker_stop_container(params: dict) -> str:
    name = params.get("name", "")
    try:
        import docker
        client = docker.from_env()
        client.containers.get(name).stop()
        return f"Container '{name}' stop ho gaya."
    except Exception as e:
        return f"Container stop nahi ho saka: {e}"


# ---------------- MySQL / MongoDB ----------------

def mysql_run_query(params: dict) -> str:
    query = params.get("query", "")
    try:
        import mysql.connector
    except ImportError:
        return "pip install mysql-connector-python"
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", ""),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", ""),
        )
        cursor = conn.cursor()
        cursor.execute(query)
        if query.strip().lower().startswith("select"):
            rows = cursor.fetchall()[:20]
            return "\n".join(str(r) for r in rows) if rows else "Koi result nahi mila."
        conn.commit()
        return f"Query chal gayi, {cursor.rowcount} rows affected."
    except Exception as e:
        return f"MySQL query fail: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def mongo_find(params: dict) -> str:
    collection_name = params.get("collection", "")
    filter_query = params.get("filter", {})
    database_name = params.get("database", "")
    try:
        from pymongo import MongoClient
    except ImportError:
        return "pip install pymongo"
    uri = os.getenv("MONGO_URI", "")
    if not uri:
        return ".env mein MONGO_URI set karo."
    try:
        client = MongoClient(uri)
        db = client[database_name]
        docs = list(db[collection_name].find(filter_query).limit(10))
        for d in docs:
            d["_id"] = str(d["_id"])
        return json_dumps_safe(docs) if docs else "Koi document nahi mila."
    except Exception as e:
        return f"Mongo query fail: {e}"


def json_dumps_safe(data) -> str:
    import json
    try:
        return json.dumps(data, indent=2, default=str)[:2500]
    except Exception:
        return str(data)[:2500]


ACTIONS = {
    "spotify_play": spotify_play,
    "spotify_pause": spotify_pause,
    "spotify_next": spotify_next,
    "slack_send_message": slack_send_message,
    "notion_create_page": notion_create_page,
    "github_create_issue": github_create_issue,
    "github_list_open_prs": github_list_open_prs,
    "jira_create_issue": jira_create_issue,
    "aws_list_s3_buckets": aws_list_s3_buckets,
    "aws_list_ec2_instances": aws_list_ec2_instances,
    "docker_list_containers": docker_list_containers,
    "docker_start_container": docker_start_container,
    "docker_stop_container": docker_stop_container,
    "mysql_run_query": mysql_run_query,
    "mongo_find": mongo_find,
}

DOCS = """
- spotify_play: {"query": "lofi hip hop"}  (query optional - khaali ho to jo pehle se paused hai wahi resume)
- spotify_pause: {}
- spotify_next: {}
- slack_send_message: {"channel": "#general", "text": "..."}
- notion_create_page: {"title": "Meeting Notes", "content": "..."}
- github_create_issue: {"repo": "owner/repo", "title": "Bug X", "body": "..."}
- github_list_open_prs: {"repo": "owner/repo"}
- jira_create_issue: {"project_key": "PROJ", "summary": "...", "description": "..."}
- aws_list_s3_buckets: {}
- aws_list_ec2_instances: {}
- docker_list_containers: {}
- docker_start_container / docker_stop_container: {"name": "my_container"}
- mysql_run_query: {"query": "SELECT * FROM users LIMIT 5"}
- mongo_find: {"database": "mydb", "collection": "users", "filter": {}}
    (Sab .env mein alag-alag API keys/credentials maangte hain - jo
    setup nahi hai wo clear error dega, README mein sab keys ki list hai)
"""
