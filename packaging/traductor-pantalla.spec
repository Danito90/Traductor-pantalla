# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


root = Path(SPECPATH).resolve().parent
models = root / "models/assets"
licenses = root / "build/third-party-licenses"

if not (models / "manifest.json").is_file():
    raise SystemExit("Prepará los modelos con packaging/prepare_models.py antes de compilar.")
if not licenses.is_dir():
    raise SystemExit("Prepará las licencias con packaging/prepare_licenses.py antes de compilar.")

# Reduce la búsqueda de DLL a Windows y al entorno usado para compilar.
# Los hooks de PyInstaller agregan los directorios nativos de cada paquete.
windows = Path(os.environ["SystemRoot"])
os.environ["PATH"] = os.pathsep.join(map(str, (Path(sys.executable).parent, windows / "System32", windows)))

analysis = Analysis(
    [str(root / "src/traductor_pantalla/__main__.py")],
    pathex=[str(root / "src")],
    binaries=collect_dynamic_libs("onnxruntime") + collect_dynamic_libs("ctranslate2"),
    datas=collect_data_files("rapidocr", excludes=["models/**"]) + [
        (str(models), "models"),
        (str(root / "packaging/THIRD-PARTY-NOTICES.txt"), "licenses"),
        (str(licenses), "licenses/packages"),
    ],
    hiddenimports=["onnxruntime", "rapidocr.inference_engine.onnxruntime"],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="TraductorPantalla",
          console=False, upx=False)
app = COLLECT(exe, analysis.binaries, analysis.datas, upx=False, name="TraductorPantalla")
