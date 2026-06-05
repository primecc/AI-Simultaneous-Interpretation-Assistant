# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_root = Path(SPECPATH).resolve().parent
src_dir = project_root / "src"
system32_dir = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32"

vc_runtime_names = (
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
)
vc_runtime_binaries = [
    (str(system32_dir / filename), ".")
    for filename in vc_runtime_names
    if (system32_dir / filename).exists()
]
bundled_model_dir = project_root / "models" / "faster-whisper-tiny.en"

datas = [
    (str(src_dir / "simultaneous_interpreter" / "static"), "simultaneous_interpreter/static"),
    (str(src_dir / "simultaneous_interpreter" / "assets"), "simultaneous_interpreter/assets"),
    (str(project_root / "docs"), "docs"),
    (str(project_root / "README.md"), "."),
    (str(project_root / ".env.example"), "."),
] + collect_data_files("faster_whisper", includes=["assets/*"])

if (bundled_model_dir / "model.bin").exists():
    datas.append((str(bundled_model_dir), "models/faster-whisper-tiny.en"))

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("multipart")
    + collect_submodules("pyaudiowpatch")
    + collect_submodules("faster_whisper")
    + collect_submodules("deep_translator")
    + collect_submodules("ctranslate2")
    + collect_submodules("huggingface_hub")
    + collect_submodules("tokenizers")
    + collect_submodules("av")
    + [
        "simultaneous_interpreter.main",
        "simultaneous_interpreter.desktop_overlay",
        "simultaneous_interpreter.services.system_audio_translator",
        "simultaneous_interpreter.services.media_interpreter",
        "uvicorn.lifespan.on",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.websockets_impl",
    ]
)

a = Analysis(
    [str(src_dir / "simultaneous_interpreter" / "desktop_launcher.py")],
    pathex=[str(src_dir)],
    binaries=vc_runtime_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["openai", "soundcard", "sounddevice"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI-Simultaneous-Interpreter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(src_dir / "simultaneous_interpreter" / "assets" / "app-icon.ico"),
    version=str(project_root / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AI-Simultaneous-Interpreter",
)
