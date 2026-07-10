from pathlib import Path
import os

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPECPATH)
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

datas = []
binaries = []
hiddenimports = []
for package in ("mlx", "mlx_whisper", "parakeet_mlx", "silero_vad"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hidden)
hiddenimports.extend(["pynput.keyboard._darwin", "pynput.mouse._darwin"])

analysis = Analysis(
    [str(ROOT / "scripts" / "vox_terminal_app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "torch.cuda",
        "torch.distributed",
        "torch.testing",
        "torch.utils.tensorboard",
    ],
    noarchive=False,
)
python_archive = PYZ(analysis.pure)
executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Vox Terminal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch="arm64",
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="Vox Terminal",
)
app = BUNDLE(
    collection,
    name="Vox Terminal.app",
    icon=str(ROOT / "build" / "VoxTerminal.icns"),
    bundle_identifier="com.jaswanth.voxterminal",
    info_plist={
        "CFBundleDisplayName": "Vox Terminal",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": (
            "Vox Terminal records speech only while dictation is active. "
            "Audio stays on this Mac."
        ),
    },
)
