# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import os

from PyInstaller.utils.hooks import collect_all

block_cipher = None

project_dir = os.path.abspath(".")

binaries = []
ffmpeg_path = os.path.join(project_dir, "bin", "ffmpeg.exe")
ffprobe_path = os.path.join(project_dir, "bin", "ffprobe.exe")
if os.path.exists(ffmpeg_path):
    binaries.append((ffmpeg_path, "bin"))
if os.path.exists(ffprobe_path):
    binaries.append((ffprobe_path, "bin"))

fw_datas, fw_binaries, fw_hidden = collect_all("faster_whisper")
ct_datas, ct_binaries, ct_hidden = collect_all("ctranslate2")
tok_datas, tok_binaries, tok_hidden = collect_all("tokenizers")

datas = [(os.path.join("app", "ui", "styles.qss"), os.path.join("app", "ui"))]
datas += fw_datas + ct_datas + tok_datas

binaries += fw_binaries + ct_binaries + tok_binaries

hiddenimports = fw_hidden + ct_hidden + tok_hidden

runtime_hooks = [os.path.join("runtime_hooks", "runtime_env_setup.py")]

from PyInstaller.building.build_main import Analysis, EXE, PYZ, COLLECT  # noqa: E402

a = Analysis(
    ["run_app.py"],
    pathex=[project_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=runtime_hooks,
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HebrewSubtitleGUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HebrewSubtitleGUI",
)
