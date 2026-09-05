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
    # apply_update (git pull) local uncommitted changes overwrite kar
    # sakta hai isliye confirmation zaroori hai. push_update (apna khud ka
    # code apne hi GitHub pe bhejna) risky nahi hai - kabhi bhi git revert
    # ho sakta hai - isliye ise DESTRUCTIVE list mein nahi rakha. Pehle
    # dono destructive the, jiski wajah se "khud ko GitHub pe push kar do"
    # bolne pe har baar "Haan/Nahi" confirmation maangta tha, aur agar
    # voice se "haan" sahi se recognize na ho to chup-chaap cancel ho
    # jaata tha - isse push kabhi hota hi nahi dikhta tha.
    if "apply_update" not in config.DESTRUCTIVE_ACTIONS:
        config.DESTRUCTIVE_ACTIONS.append("apply_update")
except Exception:
    pass


def _run_git(args: list, timeout: int = 30):
    return subprocess.run(["git"] + args, capture_output=True, text=True, timeout=timeout)


def _current_branch() -> str:
    """Current branch ka naam deta hai (e.g. 'main'). PROBLEM: pehle
    code `git pull` (bina remote/branch bataye) aur `@{u}` (upstream)
    pe depend karta tha - lekin agar kabhi upstream tracking set na ho
    (jaise OneDrive .git corruption ke baad repo re-init hua ho), to
    Git error deta hai: "There is no tracking information for the
    current branch." Ab hum hamesha EXPLICITLY 'origin <branch>' bolte
    hain, tracking config pe depend nahi karte."""
    out = _run_git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    return out or "main"


def _ensure_upstream(branch: str):
    """Pull/push ke baad (ya pehle) upstream tracking set kar deta hai
    taaki aage se bhi plain 'git pull'/'git status' sahi se kaam kare
    aur ye tracking-missing error dubara na aaye. Fail ho to chup-chaap
    ignore karo - ye sirf convenience hai, critical nahi."""
    try:
        _run_git(["branch", "--set-upstream-to", f"origin/{branch}", branch])
    except Exception:
        pass


def check_for_updates(params: dict) -> str:
    """Naye changes hain ya nahi dekhta hai - kuch download/apply nahi karta."""
    try:
        status = _run_git(["rev-parse", "--is-inside-work-tree"])
        if status.returncode != 0:
            return "Ye folder Git repository nahi hai - self-update ke liye pehle 'git init' + GitHub remote add karna hoga."

        fetch = _run_git(["fetch", "origin"], timeout=30)
        if fetch.returncode != 0:
            return f"Update check nahi ho paya (internet/remote issue): {fetch.stderr.strip()[:300]}"

        branch = _current_branch()
        local = _run_git(["rev-parse", "HEAD"]).stdout.strip()
        # IMPORTANT: '@{u}' (upstream) ki jagah seedha 'origin/<branch>'
        # use kar rahe hain - agar upstream tracking set na ho (jaise
        # OneDrive .git corruption ke baad) to '@{u}' fail ho jaata tha,
        # 'origin/<branch>' hamesha kaam karta hai jab tak remote branch
        # exist karta ho.
        remote_ref = _run_git(["rev-parse", f"origin/{branch}"])
        if remote_ref.returncode != 0:
            return f"'origin/{branch}' branch nahi mila remote pe: {remote_ref.stderr.strip()[:200]}"
        remote = remote_ref.stdout.strip()
        _ensure_upstream(branch)
        if local == remote:
            return "Jarvis already latest version pe hai."
        log = _run_git(["log", "--oneline", f"{local}..{remote}"]).stdout.strip()
        return f"Naya update available hai! Changes:\n{log[:500]}\n\n'apply_update' bolo isse install karne ke liye."
    except FileNotFoundError:
        return "Git installed nahi hai iss system pe."
    except Exception as e:
        return f"Update check nahi ho paya: {e}"


def apply_update(params: dict) -> str:
    """Asli git pull karta hai - code update ho jaayega, restart chahiye hoga.

    FIX (local uncommitted changes wali error): Jarvis folder mein aksar
    generated project files (jaise client website .html files) bhi padi
    rehti hain jinhe kabhi commit nahi kiya - Git in changes ko dekh ke
    pull REFUSE kar deta tha ("local changes... would be overwritten by
    merge"), taaki kuch overwrite/lose na ho. Ab agar aise uncommitted
    changes mile to pehle unhe 'git stash' se safely alag rakh dete hain,
    phir pull karte hain, phir stash wapas apply kar dete hain - matlab
    koi bhi local kaam lose nahi hota aur update bhi ho jaata hai."""
    try:
        status = _run_git(["rev-parse", "--is-inside-work-tree"])
        if status.returncode != 0:
            return "Ye folder Git repository nahi hai."

        branch = _current_branch()

        # Local uncommitted changes hain kya - agar hain to unhe stash
        # karo taaki pull unke wajah se block na ho.
        dirty = _run_git(["status", "--porcelain"]).stdout.strip()
        stashed = False
        if dirty:
            stash = _run_git(["stash", "push", "-u", "-m", "jarvis-auto-update-stash"], timeout=30)
            if stash.returncode == 0 and "No local changes to save" not in (stash.stdout or ""):
                stashed = True
            elif stash.returncode != 0:
                return (
                    "Update apply nahi ho paya: local changes hain jo pull ke wajah se "
                    f"overwrite ho sakte the, aur unhe safely stash bhi nahi kar paya: "
                    f"{(stash.stderr or '').strip()[:300]}"
                )

        # FIX: plain 'git pull' upstream tracking info maangta hai, jo
        # missing ho sakta hai (see _current_branch docstring). Ab
        # explicitly 'origin <branch>' de rahe hain isliye tracking
        # config par depend nahi karta.
        pull = _run_git(["pull", "origin", branch], timeout=60)
        output = (pull.stdout or "") + (pull.stderr or "")

        if pull.returncode != 0:
            if stashed:
                # Pull bhi fail ho gaya, stashed changes wapas de do taaki
                # kuch lose na ho.
                _run_git(["stash", "pop"])
            return f"Update apply nahi ho paya: {output.strip()[:400]}"

        _ensure_upstream(branch)  # aage ke liye tracking set kar do

        pop_note = ""
        if stashed:
            pop = _run_git(["stash", "pop"], timeout=30)
            if pop.returncode != 0:
                pop_note = (
                    "\n\nNOTE: pull ho gaya, lekin tumhare local (unsaved) changes "
                    "wapas apply karte waqt conflict aa gaya - wo changes 'git stash list' "
                    "mein safe pade hain, khud jaake manually resolve/apply karna padega "
                    "(kuch delete nahi hua)."
                )

        if "Already up to date" in output or "Already up-to-date" in output:
            return "Already latest version pe the, koi naya update nahi tha." + pop_note
        return (
            f"Update ho gaya! {output.strip()[:400]}\n"
            f"Ab Jarvis ko RESTART karo taaki naya code load ho.{pop_note}"
        )
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
        # QR/AI images), work/ (client project files), aur stray html/
        # png/jpg kabhi push na hon. PEHLE yahan 'git add -A -- . :!jarvis_media
        # :!*.png ...' jaisi manual pathspec-exclusion thi, lekin jab koi
        # path pehle se .gitignore mein bhi ho AUR command-line pe explicitly
        # naam se diya jaaye (chahe exclude ':!'  ke saath hi), Git kabhi-kabhi
        # "paths are ignored by .gitignore" error de deta hai (ye ek Git
        # quirk hai). FIX: manual exclusion hataya - .gitignore khud hi
        # (ab work/, *.html, jarvis_media, *.png/jpg/jpeg sab cover karta
        # hai) plain 'git add -A' se automatically sab skip kar deta hai,
        # isliye alag se exclude bolne ki zaroorat hi nahi.
        add = _run_git(["add", "-A"])
        if add.returncode != 0:
            return f"'git add' fail ho gaya: {add.stderr.strip()[:300]}"

        staged = _run_git(["diff", "--cached", "--name-only"]).stdout.strip()
        if not staged:
            return "Koi code-level changes nahi mile push karne ko (sirf generated media/screenshots badle the shayad, wo kabhi push nahi hote)."

        # SAFETY NET: agar koi jarvis_media/work/html/media file kisi
        # purani wajah se (jaise pehle force-add ho chuki ho) abhi bhi
        # staged hai, use yahin unstage kar do taaki wo GitHub pe kabhi
        # na jaaye - .gitignore future ke liye hai, ye existing tracked
        # files ke liye extra safety hai.
        blocked_prefixes = ("jarvis_media/", "work/")
        blocked_exts = (".png", ".jpg", ".jpeg")
        to_unstage = [
            f for f in staged.splitlines()
            if f.startswith(blocked_prefixes) or f.lower().endswith(blocked_exts)
        ]
        if to_unstage:
            _run_git(["reset", "--"] + to_unstage)
            staged = _run_git(["diff", "--cached", "--name-only"]).stdout.strip()
            if not staged:
                return "Koi code-level changes nahi mile push karne ko (sirf media/work files badle the, wo kabhi push nahi hote)."

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
