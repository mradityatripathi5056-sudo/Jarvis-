"""
skills/network_tools_skill.py
------------------------------------------------------------
Ping, traceroute, speedtest, port scan, WiFi diagnostics, VPN
connect/disconnect.

NOTE (port scan): Sirf apne khud ke devices/network pe hi port scan
karo - kisi doosre ke network pe bina permission scan karna kai
jagah illegal hai. Ye tool sirf localhost/apne LAN devices ke liye
use karna.

SETUP: pip install speedtest-cli (speedtest ke liye)
VPN: OpenVPN/WireGuard CLI installed hona chahiye aur ek profile
(.ovpn / wireguard config) already configured hona chahiye - Jarvis
sirf usko launch/stop karta hai, naya VPN account nahi banata.
"""

import platform
import socket
import subprocess

IS_WINDOWS = platform.system() == "Windows"


def ping_host(params: dict) -> str:
    host = params.get("host", "8.8.8.8")
    count = params.get("count", 4)
    try:
        cmd = ["ping", "-n" if IS_WINDOWS else "-c", str(count), host]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (result.stdout or result.stderr).strip()[:1500]
    except Exception as e:
        return f"Ping fail: {e}"


def traceroute_host(params: dict) -> str:
    host = params.get("host", "8.8.8.8")
    try:
        cmd = ["tracert", host] if IS_WINDOWS else ["traceroute", host]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (result.stdout or result.stderr).strip()[:2000]
    except Exception as e:
        return f"Traceroute fail (Mac/Linux pe 'traceroute' installed hona chahiye): {e}"


def speedtest_run(params: dict) -> str:
    try:
        import speedtest
    except ImportError:
        return "speedtest-cli missing. Chalao: pip install speedtest-cli"
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        download = st.download() / 1_000_000
        upload = st.upload() / 1_000_000
        ping = st.results.ping
        return f"Download: {download:.1f} Mbps | Upload: {upload:.1f} Mbps | Ping: {ping:.0f} ms"
    except Exception as e:
        return f"Speedtest fail: {e}"


def port_scan(params: dict) -> str:
    host = params.get("host", "127.0.0.1")
    start_port = int(params.get("start_port", 1))
    end_port = int(params.get("end_port", 1024))
    if end_port - start_port > 3000:
        return "Ek baar mein max 3000 ports scan karo (zyada slow ho jayega)."
    open_ports = []
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((host, port)) == 0:
                open_ports.append(port)
    if not open_ports:
        return f"{host} pe {start_port}-{end_port} range mein koi open port nahi mila."
    return f"{host} pe open ports: {', '.join(map(str, open_ports))}"


def wifi_diagnostics(params: dict) -> str:
    try:
        if IS_WINDOWS:
            result = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10)
        else:
            result = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=10)
        return (result.stdout or result.stderr).strip()[:1500]
    except Exception as e:
        return f"WiFi diagnostics nahi mila: {e}"


def ip_config_full(params: dict) -> str:
    try:
        cmd = ["ipconfig", "/all"] if IS_WINDOWS else ["ifconfig"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (result.stdout or result.stderr).strip()[:2500]
    except Exception as e:
        return f"IP config nahi mila: {e}"


def vpn_connect(params: dict) -> str:
    profile = params.get("profile", "")
    if not profile:
        return "VPN profile ka naam/path batao (.ovpn file ya WireGuard config)."
    try:
        if profile.endswith(".ovpn"):
            subprocess.Popen(["openvpn", "--config", profile])
            return f"OpenVPN '{profile}' se connect ho raha hai (background mein)."
        else:
            result = subprocess.run(["wg-quick", "up", profile], capture_output=True, text=True, timeout=15)
            return (result.stdout or result.stderr).strip() or f"WireGuard '{profile}' connect ho gaya."
    except FileNotFoundError:
        return "OpenVPN/WireGuard CLI installed nahi lag raha."
    except Exception as e:
        return f"VPN connect nahi ho saka: {e}"


def vpn_disconnect(params: dict) -> str:
    profile = params.get("profile", "")
    try:
        if profile and not profile.endswith(".ovpn"):
            result = subprocess.run(["wg-quick", "down", profile], capture_output=True, text=True, timeout=15)
            return (result.stdout or result.stderr).strip() or "WireGuard disconnect ho gaya."
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/IM", "openvpn.exe", "/F"], capture_output=True, text=True, timeout=10)
        else:
            subprocess.run(["pkill", "openvpn"], capture_output=True, text=True, timeout=10)
        return "VPN disconnect kar diya."
    except Exception as e:
        return f"VPN disconnect nahi ho saka: {e}"


ACTIONS = {
    "ping_host": ping_host,
    "traceroute_host": traceroute_host,
    "speedtest_run": speedtest_run,
    "port_scan": port_scan,
    "wifi_diagnostics": wifi_diagnostics,
    "ip_config_full": ip_config_full,
    "vpn_connect": vpn_connect,
    "vpn_disconnect": vpn_disconnect,
}

DOCS = """
- ping_host: {"host": "google.com", "count": 4}
- traceroute_host: {"host": "google.com"}
- speedtest_run: {}  (internet speed test - download/upload/ping)
- port_scan: {"host": "127.0.0.1", "start_port": 1, "end_port": 1024}
    (SIRF apne khud ke device/LAN pe use karo, doosron ke network pe nahi)
- wifi_diagnostics: {}  (signal strength, SSID, etc.)
- ip_config_full: {}  (poora network config)
- vpn_connect: {"profile": "myvpn.ovpn"}  (pehle se configured VPN profile chahiye)
- vpn_disconnect: {"profile": ""}

Example:
User: "internet speed check karo"
-> {"actions": [{"action": "speedtest_run", "params": {}}]}
"""
