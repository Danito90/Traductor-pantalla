# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / "src/traductor_pantalla/__main__.py")],
    pathex=[str(root / "src")],
    binaries=collect_dynamic_libs("onnxruntime") + collect_dynamic_libs("ctranslate2"),
    datas=collect_data_files("rapidocr", excludes=["models/**"]) + [
        (str(root / "models/assets"), "models"),
        (str(root / "packaging/THIRD-PARTY-NOTICES.txt"), "licenses"),
        (str(root / "build/third-party-licenses"), "licenses/packages"),
    ],
    hiddenimports=["onnxruntime", "rapidocr.inference_engine.onnxruntime"],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="TraductorPantalla",
          console=False, upx=False)
app = COLLECT(exe, analysis.binaries, analysis.datas, upx=False, name="TraductorPantalla")
