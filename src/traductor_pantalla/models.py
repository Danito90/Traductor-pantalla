import sys
from pathlib import Path


MODEL_FILES = (
    "ocr/detector.onnx", "ocr/recognizer.onnx", "ocr/classifier.onnx", "ocr/character.txt", "translation/model.bin",
    "translation/config.json", "translation/source.spm", "translation/target.spm",
)


def model_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "models"
    return Path(__file__).resolve().parents[2] / "models" / "assets"


def require_models(root: Path) -> None:
    for filename in MODEL_FILES:
        path = root / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"Falta el archivo de modelo {filename}. Reinstalá la aplicación.")
    if not (root / "translation" / "shared_vocabulary.json").is_file():
        for filename in ("source_vocabulary.json", "target_vocabulary.json"):
            if not (root / "translation" / filename).is_file():
                raise FileNotFoundError(f"Falta el vocabulario {filename}. Reinstalá la aplicación.")
