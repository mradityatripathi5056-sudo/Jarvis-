"""
skills/code_exec_skill.py
------------------------------------------------------------
Python/Node code aur scripts run karne ki ability - automation,
data processing, file conversion ke liye.

SAFETY: run_python_code, run_node_code, aur run_shell_command teeno
DESTRUCTIVE list mein add ho jaate hain (is file ke load hote hi) -
matlab GUI se chalane par voice confirmation maangega, aur PHONE se
ye 3 actions bilkul allowed NAHI hain (gui.py/server.py ka existing
safety logic already isko handle karta hai, kyunki ye naam
config.DESTRUCTIVE_ACTIONS mein add ho jaate hain).

Har run ka timeout hai (default 20s) taaki koi infinite loop Jarvis
ko hang na kar de.
"""

import subprocess
import sys
import tempfile
import os
import re

try:
    import config
    for _action_name in ("run_python_code", "run_shell_command", "run_node_code"):
        if _action_name not in config.DESTRUCTIVE_ACTIONS:
            config.DESTRUCTIVE_ACTIONS.append(_action_name)
except Exception:
    pass


def _run_and_capture(cmd: list, timeout: int) -> str:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        parts = []
        if output:
            parts.append(f"Output:\n{output}")
        if error:
            parts.append(f"Errors/Warnings:\n{error}")
        if not parts:
            return "Code chal gaya, koi output nahi mila."
        return "\n".join(parts)[:3000]  # bahut lamba na ho
    except subprocess.TimeoutExpired:
        return f"Code {timeout} second mein complete nahi hua, ruk gaya (timeout)."
    except Exception as e:
        return f"Run nahi ho saka: {e}"


def run_python_code(params: dict) -> str:
    code = params.get("code", "")
    timeout = int(params.get("timeout", 20))
    if not code.strip():
        return "Kaunsa code chalana hai, batao."
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        return _run_and_capture([sys.executable, path], timeout)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def run_node_code(params: dict) -> str:
    code = params.get("code", "")
    timeout = int(params.get("timeout", 20))
    if not code.strip():
        return "Kaunsa Node.js code chalana hai, batao."
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        return _run_and_capture(["node", path], timeout)
    except FileNotFoundError:
        return "Node.js installed nahi lag raha (nodejs.org se install karo)."
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def run_script_file(params: dict) -> str:
    path = params.get("path", "")
    timeout = int(params.get("timeout", 30))
    if not path or not os.path.exists(path):
        return f"'{path}' file nahi mili."
    interpreter = sys.executable if path.endswith(".py") else "node"
    return _run_and_capture([interpreter, path], timeout)


def run_shell_command(params: dict) -> str:
    """Raw shell/terminal command chalata hai (Windows: cmd, Linux/Mac: bash)."""
    command = params.get("command", "")
    timeout = int(params.get("timeout", 20))
    if not command.strip():
        return "Kaunsa command chalana hai, batao."

    # GUARD: LLM (khaas kar free models) kabhi-kabhi prompt-instructions
    # bhool ke git pull/push/commit/rebase/merge jaisa command yahan se
    # seedha chalane ki koshish karta hai - jo dedicated
    # self_update_skill.py (jo missing-tracking, uncommitted-changes,
    # non-fast-forward jaise edge-cases khud handle karta hai) ko bypass
    # kar deta hai aur user ko raw confusing git error/conflict dikhta
    # hai. PEHLE ye check sirf command ke SHURUAAT mein "git pull" dhoondta
    # tha, isliye chained commands jaise "git stash && git pull --rebase"
    # miss ho jaate the (jinse repo beech-rebase-mein-conflict jaisi
    # risky state mein phas sakta hai). Ab poore command STRING mein
    # KAHIN BHI ye git subcommands dhoondte hain (chained/&&/;/| sab
    # cover ho jaate hain), aur rebase/merge/stash bhi block list mein
    # add kiye hain kyunki wo bhi history-changing/conflict-prone hain.
    _cmd_lower = command.strip().lower()
    if re.search(r"\bgit\s+(pull|push|commit|rebase|merge)\b", _cmd_lower) or \
       re.search(r"\bgit\s+stash\s+pop\b", _cmd_lower):
        return (
            "Ye git pull/push/commit/rebase/merge jaisa (history-changing) command hai - "
            "iske liye run_shell_command use nahi hota, iske bajaye check_for_updates / "
            "apply_update / push_update action use karo (ye edge-cases khud safely handle "
            "karte hain)."
        )

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        output = (result.stdout or "").strip() + ("\n" + result.stderr if result.stderr else "")
        return output.strip()[:3000] or "Command chal gaya, koi output nahi mila."
    except subprocess.TimeoutExpired:
        return f"Command {timeout} second mein complete nahi hua."
    except Exception as e:
        return f"Command run nahi ho saka: {e}"


ACTIONS = {
    "run_python_code": run_python_code,
    "run_node_code": run_node_code,
    "run_script_file": run_script_file,
    "run_shell_command": run_shell_command,
}

DOCS = """
- run_python_code: {"code": "print(2+2)", "timeout": 20}
    (Python code run karta hai aur output deta hai - automation/data
    processing/file conversion ke liye)
- run_node_code: {"code": "console.log(2+2)", "timeout": 20}
- run_script_file: {"path": "script.py", "timeout": 30}
- run_shell_command: {"command": "dir", "timeout": 20}
    (raw terminal command - CAREFUL, ye system pe kuch bhi kar sakta
    hai, isliye confirmation maangega)

Example:
User: "ek python script chalao jo 1 se 10 tak sum nikale"
-> {"actions": [{"action": "run_python_code", "params": {"code": "print(sum(range(1,11)))"}}]}
"""
