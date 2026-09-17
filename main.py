"""
Scholly — desk robot entry point.

    python main.py
"""

import sys

# Some consoles (default Windows PowerShell/cmd) use a legacy codepage that
# can't encode the arrows and other unicode used in the app's log messages.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

from src.task_manager import TaskManager

if __name__ == "__main__":
    TaskManager().run()
