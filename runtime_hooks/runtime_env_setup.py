import os
import sys
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

base_dir = None
if getattr(sys, "frozen", False):
    base_dir = Path(getattr(sys, "_MEIPASS", ""))
    if not base_dir.exists():
        base_dir = Path(sys.executable).resolve().parent / "_internal"

if base_dir and base_dir.exists():
    try:
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(base_dir))
    except OSError:
        pass
    os.environ["PATH"] = f"{base_dir};{os.environ.get('PATH', '')}"
