"""
setup_autostart.py
Ek baar chalao - ye Windows Startup folder mein DO shortcuts bana dega:
1. Jarvis GUI
2. Jarvis Server (phone control)

Chalane ka tarika:
    python setup_autostart.py
"""

import os
import sys
import winshell
from win32com.client import Dispatch


def create_shortcut(script_name: str, shortcut_name: str):
    startup_folder = winshell.startup()
    project_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = sys.executable
    script_path = os.path.join(project_dir, script_name)

    pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw_exe):
        pythonw_exe = python_exe

    shortcut_path = os.path.join(startup_folder, f"{shortcut_name}.lnk")

    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = pythonw_exe
    shortcut.Arguments = f'"{script_path}"'
    shortcut.WorkingDirectory = project_dir
    shortcut.IconLocation = pythonw_exe
    shortcut.save()

    print(f"Shortcut ban gaya: {shortcut_path}")


def create_startup_shortcuts():
    print("Jarvis GUI aur Server dono ke liye startup shortcuts bana raha hoon...\n")
    create_shortcut("gui.py", "Jarvis GUI")
    create_shortcut("server.py", "Jarvis Server")
    print("\nDone! Ab jab bhi laptop on/restart hoga, dono automatically chalu ho jayenge.")
    print("Hatane ke liye: Win+R -> shell:startup -> in dono files ko delete kar do.")


if __name__ == "__main__":
    create_startup_shortcuts()
