"""
skills/smart_home_skill.py
------------------------------------------------------------
Lights, AC, smart plugs, cameras control - Home Assistant (universal
hub, RECOMMENDED - ek baar setup karo to sab brands isi se chal jaate
hain) ke through, ya seedha Philips Hue / TP-Link Kasa-Tapo se.

SETUP (Home Assistant - recommended, sabse universal):
1. Home Assistant already chal raha ho (local ya cloud) - Settings ->
   Devices -> apne lights/plugs/AC/cameras add karo (unke brand ke
   integration se - HA khud hi Hue, Kasa, Tapo, Google Nest, Alexa,
   IR-AC sab support karta hai).
2. Settings -> "Long-lived access token" banao.
3. .env mein: HA_URL=http://<home-assistant-ip>:8123, HA_TOKEN=...

SETUP (seedha Philips Hue, HA ke bina):
.env mein: HUE_BRIDGE_IP=..., HUE_USERNAME=...
(username Hue bridge ke button dabake generate hota hai - Philips
Hue API docs dekho: developers.meethue.com)

SETUP (seedha TP-Link Kasa/Tapo):
pip install python-kasa
"""

import os


# ---------------- Home Assistant (universal - lights/AC/plugs/cameras) ----------------

def _ha_request(method: str, path: str, json_body: dict = None):
    import requests
    url = os.getenv("HA_URL", "")
    token = os.getenv("HA_TOKEN", "")
    if not url or not token:
        raise RuntimeError(".env mein HA_URL aur HA_TOKEN set karo (Home Assistant setup pehle karo).")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return requests.request(method, f"{url.rstrip('/')}/api{path}", headers=headers, json=json_body, timeout=10)


def smart_device_on(params: dict) -> str:
    entity_id = params.get("entity_id", "")  # jaise light.living_room
    if not entity_id:
        return "Kaunsa device on karna hai, entity_id batao (jaise light.living_room)."
    try:
        domain = entity_id.split(".")[0]
        resp = _ha_request("POST", f"/services/{domain}/turn_on", {"entity_id": entity_id})
        return f"'{entity_id}' on kar diya." if resp.ok else f"Fail: {resp.text[:200]}"
    except Exception as e:
        return f"Device on nahi ho saka: {e}"


def smart_device_off(params: dict) -> str:
    entity_id = params.get("entity_id", "")
    if not entity_id:
        return "Kaunsa device off karna hai, entity_id batao."
    try:
        domain = entity_id.split(".")[0]
        resp = _ha_request("POST", f"/services/{domain}/turn_off", {"entity_id": entity_id})
        return f"'{entity_id}' off kar diya." if resp.ok else f"Fail: {resp.text[:200]}"
    except Exception as e:
        return f"Device off nahi ho saka: {e}"


def smart_device_status(params: dict) -> str:
    entity_id = params.get("entity_id", "")
    try:
        resp = _ha_request("GET", f"/states/{entity_id}")
        if not resp.ok:
            return f"Status nahi mila: {resp.text[:200]}"
        data = resp.json()
        return f"{entity_id}: {data.get('state')}"
    except Exception as e:
        return f"Status check nahi ho saka: {e}"


def smart_device_list(params: dict) -> str:
    try:
        resp = _ha_request("GET", "/states")
        if not resp.ok:
            return f"List nahi mili: {resp.text[:200]}"
        entities = [item["entity_id"] for item in resp.json()]
        return "Devices:\n" + "\n".join(entities[:50])
    except Exception as e:
        return f"Device list nahi mili: {e}"


def ac_set_temperature(params: dict) -> str:
    entity_id = params.get("entity_id", "climate.ac")
    temperature = params.get("temperature", 24)
    try:
        resp = _ha_request("POST", "/services/climate/set_temperature",
                            {"entity_id": entity_id, "temperature": temperature})
        return f"AC temperature {temperature} degree set kar diya." if resp.ok else f"Fail: {resp.text[:200]}"
    except Exception as e:
        return f"AC set nahi ho saka: {e}"


def camera_snapshot(params: dict) -> str:
    entity_id = params.get("entity_id", "")
    save_path = params.get("save_path", "camera_snapshot.jpg")
    try:
        import requests
        url = os.getenv("HA_URL", "")
        token = os.getenv("HA_TOKEN", "")
        resp = requests.get(f"{url.rstrip('/')}/api/camera_proxy/{entity_id}",
                             headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if resp.ok:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return f"Camera snapshot save ho gaya: {save_path}"
        return f"Snapshot fail: {resp.status_code}"
    except Exception as e:
        return f"Camera snapshot nahi le saka: {e}"


# ---------------- Philips Hue direct (bina Home Assistant ke) ----------------

def hue_light_control(params: dict) -> str:
    light_id = params.get("light_id", "1")
    state = params.get("state", "on")  # on/off
    brightness = params.get("brightness")  # 0-254 optional
    bridge_ip = os.getenv("HUE_BRIDGE_IP", "")
    username = os.getenv("HUE_USERNAME", "")
    if not bridge_ip or not username:
        return ".env mein HUE_BRIDGE_IP aur HUE_USERNAME set karo."
    try:
        import requests
        body = {"on": state == "on"}
        if brightness is not None:
            body["bri"] = int(brightness)
        resp = requests.put(f"http://{bridge_ip}/api/{username}/lights/{light_id}/state", json=body, timeout=8)
        return f"Hue light {light_id} '{state}' kar diya." if resp.ok else f"Fail: {resp.text[:200]}"
    except Exception as e:
        return f"Hue control nahi ho saka: {e}"


# ---------------- TP-Link Kasa/Tapo direct ----------------

def kasa_plug_control(params: dict) -> str:
    ip = params.get("ip", "")
    state = params.get("state", "on")
    if not ip:
        return "Smart plug ka IP address batao."
    try:
        import asyncio
        from kasa import SmartPlug
    except ImportError:
        return "python-kasa missing. Chalao: pip install python-kasa"
    try:
        async def _run():
            plug = SmartPlug(ip)
            await plug.update()
            if state == "on":
                await plug.turn_on()
            else:
                await plug.turn_off()
        asyncio.run(_run())
        return f"Smart plug ({ip}) '{state}' kar diya."
    except Exception as e:
        return f"Kasa plug control nahi ho saka: {e}"


ACTIONS = {
    "smart_device_on": smart_device_on,
    "smart_device_off": smart_device_off,
    "smart_device_status": smart_device_status,
    "smart_device_list": smart_device_list,
    "ac_set_temperature": ac_set_temperature,
    "camera_snapshot": camera_snapshot,
    "hue_light_control": hue_light_control,
    "kasa_plug_control": kasa_plug_control,
}

DOCS = """
- smart_device_on / smart_device_off: {"entity_id": "light.living_room"}  (Home Assistant ke through)
- smart_device_status: {"entity_id": "light.living_room"}
- smart_device_list: {}  (sab connected smart devices dikhata hai)
- ac_set_temperature: {"entity_id": "climate.ac", "temperature": 24}
- camera_snapshot: {"entity_id": "camera.front_door", "save_path": "snap.jpg"}
- hue_light_control: {"light_id": "1", "state": "on", "brightness": 200}
    (Home Assistant ke bina, seedha Philips Hue bridge se)
- kasa_plug_control: {"ip": "192.168.1.50", "state": "on"}
    (TP-Link Kasa/Tapo smart plug, seedha - Home Assistant ke bina)

Ye sab actions .env mein HA_URL/HA_TOKEN (ya HUE_*) set hone par hi
kaam karenge - README mein setup steps hain.

Example:
User: "living room ki light on kar do"
-> {"actions": [{"action": "smart_device_on", "params": {"entity_id": "light.living_room"}}]}
"""
