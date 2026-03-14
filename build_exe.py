# NVX Dashboard - Windows EXE Builder
# Run with: python build_exe.py

import os
import sys
import shutil
import subprocess
from pathlib import Path

APP_NAME   = "NVX_Dashboard"
SCRIPT     = "app.py"
OUTPUT_DIR = Path("dist") / APP_NAME
SEP        = os.pathsep  # ; on Windows, : on Linux

EXTRA_FILES = [
    "devices.json",
    "settings.json",
    "install_ffmpeg.ps1",
    "START_DASHBOARD.bat",
    "README.md",
]

def check_pyinstaller():
    if shutil.which("pyinstaller") is None:
        print("PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("PyInstaller installed.")

def clean_previous():
    for folder in ["build", str(OUTPUT_DIR)]:
        p = Path(folder)
        if p.exists():
            shutil.rmtree(p)
            print("Removed: " + folder)
    spec = Path(APP_NAME + ".spec")
    if spec.exists():
        spec.unlink()

def build():
    print("")
    print("Building " + APP_NAME + ".exe ...")
    print("")

    cmd = [
        "pyinstaller",
        "--name",          APP_NAME,
        "--onedir",
        "--console",
        "--clean",
        "--add-data",      "static" + SEP + "static",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.asyncio",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "fastapi",
        "--hidden-import", "starlette",
        "--hidden-import", "starlette.routing",
        "--hidden-import", "starlette.staticfiles",
        "--hidden-import", "anyio",
        "--hidden-import", "anyio._backends._asyncio",
        SCRIPT,
    ]

    icon = Path("icon.ico")
    if icon.exists():
        cmd.extend(["--icon", "icon.ico"])

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("")
        print("BUILD FAILED - see errors above.")
        sys.exit(1)

    print("")
    print("Build succeeded.")

def copy_extras():
    print("")
    print("Copying config files...")
    for filename in EXTRA_FILES:
        src = Path(filename)
        dst = OUTPUT_DIR / filename
        if src.exists():
            shutil.copy2(src, dst)
            print("  Copied: " + filename)
        else:
            print("  Skipped (not found): " + filename)

    ffmpeg_dir = OUTPUT_DIR / "ffmpeg"
    ffmpeg_dir.mkdir(exist_ok=True)

    note = ffmpeg_dir / "PUT_FFMPEG_EXE_HERE.txt"
    note.write_text(
        "Place ffmpeg.exe in this folder.\n"
        "\n"
        "Option A - winget:\n"
        "  winget install --id=Gyan.FFmpeg -e\n"
        "\n"
        "Option B - manual download:\n"
        "  https://www.gyan.dev/ffmpeg/builds/\n"
        "  Download ffmpeg-release-essentials.zip\n"
        "  Extract and copy ffmpeg.exe into this folder\n",
        encoding="utf-8"
    )

def print_summary():
    exe      = OUTPUT_DIR / (APP_NAME + ".exe")
    out_abs  = OUTPUT_DIR.resolve()
    total_mb = sum(
        f.stat().st_size for f in OUTPUT_DIR.rglob("*") if f.is_file()
    ) / 1048576

    print("")
    print("=" * 54)
    print("  BUILD COMPLETE")
    print("=" * 54)
    print("  Folder : " + str(out_abs))
    print("  Exe    : " + exe.name)
    print("  Size   : ~" + str(round(total_mb)) + " MB")
    print("")
    print("  NEXT STEPS:")
    print("  1. Edit  devices.json  with your NVX device IPs")
    print("  2. Copy  ffmpeg.exe    into the ffmpeg/ folder")
    print("  3. Run   " + exe.name)
    print("")
    print("  TO SHARE WITH ANOTHER PC:")
    print("  Zip the entire output folder and send it.")
    print("  No Python needed on the other machine.")
    print("=" * 54)
    print("")

if __name__ == "__main__":
    check_pyinstaller()
    clean_previous()
    build()
    copy_extras()
    print_summary()
