"""SIGAP-TPA: Entry point utama dasbor prakiraan bahaya kebakaran TPA."""
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

os.chdir(str(APP_DIR))

import runpy
runpy.run_path(str(APP_DIR / "app.py"), run_name="__main__")

