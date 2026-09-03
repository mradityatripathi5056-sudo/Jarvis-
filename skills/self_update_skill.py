"""
skills/self_update_skill.py
------------------------------------------------------------
Self-Update Mechanism - Jarvis apne khud ke GitHub repo se naye
changes "git pull" karke apne aap ko update kar sakta hai.

Zaroorat: Jarvis ka poora code (jahan main.py/actions.py hai) ek Git
repository ke andar ho aur usme "origin" remote already set ho
(GitHub pe already hai to yahi kaafi hai).

check_for_updates -> sirf dekhta hai naye changes hain ya nahi (kuch
badalta nahi, safe hai).
apply_update -> asli "git pull" karta hai (isliye DESTRUCTIVE list mein
daala hai - confirmation lagegi). Pull ke baad Jarvis ko restart karna
padega naye code load karne ke liye (khud restart nahi karta, taaki
beech mein koi cheez chal rahi ho to disturb na ho).
"""

import subprocess
import config

try:
    for _action_name in ("apply_update", "push_update"):
        if _action_name not in config.DESTRUCTIVE_ACTIONS:
            config.DESTRUCTIVE_ACTIONS.append(_action_name)
except Exception:
    pass


def _run_git(args: list, timeout: int = 30):
    return subprocess.run(["git"] + args, capture_output=True, text=True, timeout=timeout)


def check_for_updates(params: dict) -> str:
    """Naye changes hain ya nahi dekhta hai - kuch download/apply nahi karta."""
    try:
        status = _run_git(["rev-parse", "--is-inside-work-tree"])
        if status.returncode != 0:
            return "Ye folder Git repository nahi hai - self-update ke liye pehle 'git init' + GitHub remote add karna hoga."

        fetch = _run_git(["fetch"], timeout=30)
        if fetch.returncode != 0:
            return f"Update check nahi ho paya (internet/remote issue): {fetch.stderr.strip()[:300]}"

        local = _run_git(["rev-parse", "HEAD"]).stdout.strip()
        remote = _run_git(["rev-parse", "@{u}"]).stdout.strip()
        if local == remote:
            return "Jarvis already latest version pe hai."
        log = _run_git(["log", "--oneline", f"{local}..{remote}"]).stdout.strip()
        return f"Naya update available hai! Changes:\n{log[:500]}\n\n'apply_update' bolo isse install karne ke liye."
    except FileNotFoundError:
        return "Git installed nahi hai iss system pe."
    except Exception as e:
        return f"Update check nahi ho paya: {e}"


def apply_update(params: dict) -> str:
    """Asli git pull karta hai - code update ho jaayega, restart chahiye hoga."""
    try:
        status = _run_git(["rev-parse", "--is-inside-work-tree"])
        if status.returncode != 0:
            return "Ye folder Git repository nahi hai."

        pull = _run_git(["pull"], timeout=60)
        output = (pull.stdout or "") + (pull.stderr or "")
        if pull.returncode != 0:
            return f"Update apply nahi ho paya: {output.strip()[:400]}"
        if "Already up to date" in output or "Already up-to-date" in output:
            return "Already latest version pe the, koi naya update nahi tha."
        return f"Update ho gaya! {output.strip()[:400]}\nAb Jarvis ko RESTART karo taaki naya code load ho."
    except FileNotFoundError:
        return "Git installed nahi hai iss system pe."
    except Exception as e:
        return f"Update apply nahi ho paya: {e}"


def push_update(params: dict) -> str:
    """Local changes ko GitHub pe push karta hai - 'git add -A' + 'git commit'
    + 'git push'. Agar kuch bhi badla hi nahi (working tree clean) to commit
    skip karke seedha bata deta hai. Commit message optional hai (na do to
    auto timestamp wala message ban jaata hai)."""
    try:
        status = _run_git(["rev-parse", "--is-inside-work-tree"])
        if status.returncode != 0:
            return "Ye folder Git repository nahi hai - pehle 'git init' + GitHub remote add karna hoga."

        # Kuch badla hai ya nahi check karo (staged ya unstaged, dono)
        status_check = _run_git(["status", "--porcelain"])
        if not status_check.stdout.strip():
            return "Koi local changes nahi hain jo push karne ho - working tree already clean hai."

        # Double-safety: jarvis_media/ (screenshots, photos, face data,
        # QR/AI images) ko explicitly exclude karo, chahe .gitignore
        # kisi wajah se kaam na kare - "khud ko GitHub pe update kar do"
        # bolne pe sirf ASLI CODE jaana chahiye, generated media nahi.
        add = _run_git(["add", "-A", "--", ".", ":!jarvis_media", ":!*.png", ":!*.jpg", ":!*.jpeg"])
        if add.returncode != 0:
            return f"'git add' fail ho gaya: {add.stderr.strip()[:300]}"

        staged = _run_git(["diff", "--cached", "--name-only"]).stdout.strip()
        if not staged:
            return "Koi code-level changes nahi mile push karne ko (sirf generated media/screenshots badle the shayad, wo kabhi push nahi hote)."
        staged_count = len(staged.splitlines())

        message = params.get("message", "").strip() or "Jarvis auto-update"
        import datetime
        message = f"{message} ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})"

        commit = _run_git(["commit", "-m", message])
        commit_output = (commit.stdout or "") + (commit.stderr or "")
        if commit.returncode != 0 and "nothing to commit" not in commit_output.lower():
            return f"'git commit' fail ho gaya: {commit_output.strip()[:300]}"

        push = _run_git(["push"], timeout=60)
        push_output = (push.stdout or "") + (push.stderr or "")
        if push.returncode != 0:
            return f"Commit ho gaya lekin 'git push' fail ho gaya (internet/auth check karo): {push_output.strip()[:400]}"

        return (
            f"Changes GitHub pe push ho gaye! ({staged_count} file(s) - screenshots/photos "
            f"exclude karke) Commit message: '{message}'.\n{push_output.strip()[:300]}"
        )
    except FileNotFoundError:
        return "Git installed nahi hai iss system pe."
    except Exception as e:
        return f"Push nahi ho paya: {e}"


ACTIONS = {
    "check_for_updates": check_for_updates,
    "apply_update": apply_update,
    "push_update": push_update,
}

DOCS = """
- check_for_updates: {}  (GitHub repo pe naye changes hain ya nahi, sirf check karta hai - safe)
- apply_update: {}  (asli update install karta hai 'git pull' se - restart chahiye hoga baad mein)
- push_update: {}  YA {"message": "naya feature X add kiya"}
    (local code changes ko GitHub pe bhej deta hai - 'git add -A' + 'git commit'
    + 'git push'. Message optional hai, na do to auto message ban jaata hai.
    Agar kuch badla hi nahi hai to seedha bata dega "kuch push karne ko nahi hai".)

Example:
User: "koi naya update hai kya apna"
-> {"actions": [{"action": "check_for_updates", "params": {}}]}

User: "khud ko update kar lo"
-> {"actions": [{"action": "apply_update", "params": {}}]}

User: "apne changes GitHub pe push kar do"
-> {"actions": [{"action": "push_update", "params": {}}]}

User: "code push kar do GitHub pe, message likh dena 'bug fix'"
-> {"actions": [{"action": "push_update", "params": {"message": "bug fix"}}]}
"""
