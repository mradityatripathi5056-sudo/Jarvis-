"""
skills/system_admin_skill.py
------------------------------------------------------------
Registry edit, Windows services control, scheduled tasks, startup
programs manage karna. Zyadatar Windows-specific hai (winreg, sc,
schtasks built-in Windows commands hain, extra install nahi chahiye).

DANGER: registry_set_value aur service_stop/kill jaisi cheezein system
ko break kar sakti hain agar galat key/value diya jaaye. Isliye
registry_set_value aur service actions DESTRUCTIVE list mein add ho
jaate hain (confirmation maangega, phone se disabled rahenge).
"""

import platform
import subprocess

try:
    import config
    for _a in ("registry_set_value", "registry_delete_value", "service_stop", "service_start", "startup_program_remove"):
        if _a not in config.DESTRUCTIVE_ACTIONS:
            config.DESTRUCTIVE_ACTIONS.append(_a)
except Exception:
    pass

IS_WINDOWS = platform.system() == "Windows"


def _require_windows() -> str | None:
    if not IS_WINDOWS:
        return "Ye action sirf Windows pe kaam karta hai."
    return None


# ---------------- Registry ----------------

def registry_read_value(params: dict) -> str:
    err = _require_windows()
    if err:
        return err
    import winreg
    hive_name = params.get("hive", "HKEY_CURRENT_USER")
    key_path = params.get("key_path", "")
    value_name = params.get("value_name", "")
    hive = getattr(winreg, hive_name, None)
    if hive is None:
        return f"'{hive_name}' hive pehchana nahi gaya."
    try:
        with winreg.OpenKey(hive, key_path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return f"{key_path}\\{value_name} = {value}"
    except Exception as e:
        return f"Registry read nahi ho saka: {e}"


def registry_set_value(params: dict) -> str:
    err = _require_windows()
    if err:
        return err
    import winreg
    hive_name = params.get("hive", "HKEY_CURRENT_USER")
    key_path = params.get("key_path", "")
    value_name = params.get("value_name", "")
    value = params.get("value", "")
    value_type = params.get("value_type", "REG_SZ")
    hive = getattr(winreg, hive_name, None)
    reg_type = getattr(winreg, value_type, winreg.REG_SZ)
    if hive is None:
        return f"'{hive_name}' hive pehchana nahi gaya."
    try:
        with winreg.CreateKey(hive, key_path) as key:
            winreg.SetValueEx(key, value_name, 0, reg_type, value)
        return f"Registry set: {key_path}\\{value_name} = {value}"
    except Exception as e:
        return f"Registry set nahi ho saka: {e}"


def registry_delete_value(params: dict) -> str:
    err = _require_windows()
    if err:
        return err
    import winreg
    hive_name = params.get("hive", "HKEY_CURRENT_USER")
    key_path = params.get("key_path", "")
    value_name = params.get("value_name", "")
    hive = getattr(winreg, hive_name, None)
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, value_name)
        return f"Registry value delete ho gayi: {key_path}\\{value_name}"
    except Exception as e:
        return f"Registry delete nahi ho saka: {e}"


# ---------------- Services ----------------

def service_status(params: dict) -> str:
    name = params.get("name", "")
    try:
        cmd = ["sc", "query", name] if IS_WINDOWS else ["systemctl", "status", name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (result.stdout or result.stderr).strip()[:1500]
    except Exception as e:
        return f"Service status nahi mila: {e}"


def service_start(params: dict) -> str:
    name = params.get("name", "")
    try:
        cmd = ["sc", "start", name] if IS_WINDOWS else ["sudo", "systemctl", "start", name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (result.stdout or result.stderr).strip() or f"'{name}' service start kar diya."
    except Exception as e:
        return f"Service start nahi ho saka: {e}"


def service_stop(params: dict) -> str:
    name = params.get("name", "")
    try:
        cmd = ["sc", "stop", name] if IS_WINDOWS else ["sudo", "systemctl", "stop", name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (result.stdout or result.stderr).strip() or f"'{name}' service stop kar diya."
    except Exception as e:
        return f"Service stop nahi ho saka: {e}"


def list_services(params: dict) -> str:
    try:
        cmd = ["sc", "query", "type=", "service", "state=", "all"] if IS_WINDOWS else ["systemctl", "list-units", "--type=service"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (result.stdout or "")[:2500]
    except Exception as e:
        return f"Services list nahi mili: {e}"


# ---------------- Scheduled tasks (Windows: schtasks) ----------------

def scheduled_task_create(params: dict) -> str:
    err = _require_windows()
    if err:
        return "Scheduled tasks sirf Windows pe (schtasks se) support hain."
    name = params.get("name", "JarvisTask")
    command = params.get("command", "")
    schedule = params.get("schedule", "DAILY")  # DAILY/WEEKLY/ONCE/ONLOGON
    time_str = params.get("time", "09:00")
    try:
        cmd = ["schtasks", "/Create", "/TN", name, "/TR", command, "/SC", schedule, "/ST", time_str, "/F"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (result.stdout or result.stderr).strip()
    except Exception as e:
        return f"Scheduled task nahi ban saka: {e}"


def scheduled_task_list(params: dict) -> str:
    err = _require_windows()
    if err:
        return "Sirf Windows pe support hai."
    try:
        result = subprocess.run(["schtasks", "/Query", "/FO", "LIST"], capture_output=True, text=True, timeout=15)
        return (result.stdout or "")[:2500]
    except Exception as e:
        return f"Task list nahi mili: {e}"


def scheduled_task_delete(params: dict) -> str:
    err = _require_windows()
    if err:
        return "Sirf Windows pe support hai."
    name = params.get("name", "")
    try:
        result = subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"], capture_output=True, text=True, timeout=15)
        return (result.stdout or result.stderr).strip()
    except Exception as e:
        return f"Task delete nahi ho saka: {e}"


# ---------------- Startup programs ----------------

STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_program_list(params: dict) -> str:
    err = _require_windows()
    if err:
        return err
    import winreg
    try:
        entries = []
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY) as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    entries.append(f"{name}: {value}")
                    i += 1
                except OSError:
                    break
        return "Startup programs:\n" + "\n".join(entries) if entries else "Koi startup program set nahi hai."
    except Exception as e:
        return f"Startup list nahi mili: {e}"


def startup_program_add(params: dict) -> str:
    err = _require_windows()
    if err:
        return err
    import winreg
    name = params.get("name", "")
    path = params.get("path", "")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, path)
        return f"'{name}' startup mein add kar diya."
    except Exception as e:
        return f"Startup add nahi ho saka: {e}"


def startup_program_remove(params: dict) -> str:
    err = _require_windows()
    if err:
        return err
    import winreg
    name = params.get("name", "")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
        return f"'{name}' startup se hata diya."
    except Exception as e:
        return f"Startup remove nahi ho saka: {e}"


ACTIONS = {
    "registry_read_value": registry_read_value,
    "registry_set_value": registry_set_value,
    "registry_delete_value": registry_delete_value,
    "service_status": service_status,
    "service_start": service_start,
    "service_stop": service_stop,
    "list_services": list_services,
    "scheduled_task_create": scheduled_task_create,
    "scheduled_task_list": scheduled_task_list,
    "scheduled_task_delete": scheduled_task_delete,
    "startup_program_list": startup_program_list,
    "startup_program_add": startup_program_add,
    "startup_program_remove": startup_program_remove,
}

DOCS = """
- registry_read_value: {"hive": "HKEY_CURRENT_USER", "key_path": "Software\\\\X", "value_name": "Y"}
- registry_set_value: {"hive": "HKEY_CURRENT_USER", "key_path": "Software\\\\X", "value_name": "Y", "value": "Z"}
- registry_delete_value: {"hive": "HKEY_CURRENT_USER", "key_path": "...", "value_name": "..."}
- service_status / service_start / service_stop: {"name": "wuauserv"}
- list_services: {}
- scheduled_task_create: {"name": "Backup", "command": "python backup.py", "schedule": "DAILY", "time": "22:00"}
- scheduled_task_list: {}
- scheduled_task_delete: {"name": "Backup"}
- startup_program_list: {}
- startup_program_add: {"name": "MyApp", "path": "C:\\\\path\\\\to\\\\app.exe"}
- startup_program_remove: {"name": "MyApp"}
    (Registry edit aur service stop/start jaisi cheezein risky hain,
    isliye confirmation maangega. Sirf Windows pe kaam karta hai.)
"""
