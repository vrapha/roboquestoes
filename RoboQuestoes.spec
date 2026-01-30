# -*- mode: python ; coding: utf-8 -*-
# RoboQuestoes.spec

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# ✅ mais robusto que Path.cwd()
# (pega o diretório onde o .spec está)
ROOT = Path(__spec__.origin).resolve().parent if "__spec__" in globals() and __spec__ and __spec__.origin else Path.cwd().resolve()

def add_folder_as_datas(folder: Path, prefix: str):
    """
    Retorna lista de datas no formato (src, dest_dir).
    Mantém a estrutura interna da pasta.
    """
    out = []
    if not folder.exists():
        return out

    for f in folder.rglob("*"):
        if f.is_file():
            rel_dir = f.parent.relative_to(folder)
            dest_dir = prefix if str(rel_dir) == "." else f"{prefix}/{rel_dir.as_posix()}"
            out.append((str(f), dest_dir))
    return out


# -------------------------------------------------------------------
# Copia pastas do projeto para dentro do dist/RoboQuestoes/...
# -------------------------------------------------------------------
datas = []
datas += add_folder_as_datas(ROOT / "scripts", "scripts")
datas += add_folder_as_datas(ROOT / "inputs", "inputs")
# datas += add_folder_as_datas(ROOT / "debug", "debug") # REMOVED FOR SECURITY (SENSITIVE DATA)

# se você usa a pasta tools/ no projeto, mantenha:
datas += add_folder_as_datas(ROOT / "tools", "tools")

binaries = []

hiddenimports = [
    # GUI
    "customtkinter",

    # matching
    "rapidfuzz",
    "rapidfuzz.process",
    "rapidfuzz.fuzz",

    # PDF / parsing
    "fitz",          # PyMuPDF
    "unidecode",

    # dados (evita surpresa)
    "pandas",
    "numpy",
]

# ✅ Coleta pacotes mais chatos
for pkg in ["playwright", "rapidfuzz", "customtkinter"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# rapidfuzz extra
hiddenimports += collect_submodules("rapidfuzz")

a = Analysis(
    ["gui_app.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RoboQuestoes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RoboQuestoes",
)
