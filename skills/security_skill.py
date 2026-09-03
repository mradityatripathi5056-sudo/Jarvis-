"""
skills/security_skill.py
------------------------------------------------------------
Security diagnostics: startup/autorun audit, suspicious-process
heuristic check, active network connections.

IMPORTANT/HONEST NOTE: Ye ek REAL antivirus/malware-scanner ka
replacement NAHI hai - ye sirf kuch basic heuristic checks karta hai
(jaise: unusual location se chal rahe processes, high resource use,
bahut saare naye startup entries) taaki tumhe kuch "dhyaan dene
laayak" dikh jaaye. Real protection ke liye Windows Defender (already
built-in aur free) ya kisi trusted paid AV ko hi primary rakho - isko
sirf ek quick extra check samjho.
"""

import os
import platform
import subprocess

import psutil

IS_WINDOWS = platform.system() == "Windows"

SUSPICIOUS_LOCATIONS = ["temp", "appdata\\local\\temp", "downloads", "tmp"]


def startup_audit(params: dict) -> str:
    """Startup mein kya-kya chalne wala set hai, ek jagah dikhata hai
    (Registry Run key + Startup folder)."""
    findings = []
    if IS_WINDOWS:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        findings.append(f"[Registry] {name}: {value}")
                        i += 1
                    except OSError:
                        break
        except Exception:
            pass
        startup_folder = os.path.join(os.getenv("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
        if os.path.isdir(startup_folder):
            for f in os.listdir(startup_folder):
                findings.append(f"[Startup folder] {f}")
    if not findings:
        return "Koi startup program set nahi mila (ya ye check sirf Windows pe kaam karta hai)."
    return f"{len(findings)} startup entries mile:\n" + "\n".join(findings[:30])


def suspicious_process_check(params: dict) -> str:
    """Heuristic check - REAL malware scan nahi hai, sirf red-flag-jaisi
    cheezein highlight karta hai (unusual location, high CPU, no name)."""
    flags = []
    for proc in psutil.process_iter(["pid", "name", "exe", "cpu_percent"]):
        try:
            info = proc.info
            exe = (info.get("exe") or "").lower()
            name = info.get("name") or "(unknown)"
            cpu = proc.cpu_percent(interval=0.05)
            reasons = []
            if any(loc in exe for loc in SUSPICIOUS_LOCATIONS):
                reasons.append("temp/downloads jaisi jagah se chal raha hai")
            if cpu > 60:
                reasons.append(f"high CPU use ({cpu:.0f}%)")
            if reasons:
                flags.append(f"{name} (PID {info.get('pid')}): {', '.join(reasons)}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not flags:
        return ("Koi obvious red flag nahi mila is basic check mein. (Yaad rakho - ye Windows " +
                "Defender/real antivirus ka replacement nahi hai, sirf ek quick extra check hai.)")
    return "Dhyaan dene layak processes:\n" + "\n".join(flags[:15]) + \
        "\n\n(Ye sirf heuristic hai, false-positive bhi ho sakta hai - Windows Defender se bhi full scan karo.)"


def active_network_connections(params: dict) -> str:
    """Kaun se apps abhi internet/network pe connected hain."""
    lines = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == "ESTABLISHED" and conn.raddr:
                try:
                    proc_name = psutil.Process(conn.pid).name() if conn.pid else "?"
                except Exception:
                    proc_name = "?"
                lines.append(f"{proc_name}: {conn.raddr.ip}:{conn.raddr.port}")
    except Exception as e:
        return f"Network connections nahi mile (shayad admin rights chahiye): {e}"
    if not lines:
        return "Abhi koi active outbound connection nahi mila."
    unique = list(dict.fromkeys(lines))
    return f"{len(unique)} active connections:\n" + "\n".join(unique[:25])


ACTIONS = {
    "startup_audit": startup_audit,
    "suspicious_process_check": suspicious_process_check,
    "active_network_connections": active_network_connections,
}

DOCS = """
- startup_audit: {}  (kya-kya startup pe automatically chalta hai, list karta hai)
- suspicious_process_check: {}
    (HEURISTIC check hai, real antivirus nahi - unusual processes highlight
    karta hai, Windows Defender ke saath complement ki tarah use karo)
- active_network_connections: {}  (abhi kaun se apps internet pe connected hain)

Example:
User: "check karo koi suspicious process to nahi chal raha"
-> {"actions": [{"action": "suspicious_process_check", "params": {}}]}
"""
