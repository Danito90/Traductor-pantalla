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


def verify_local_inference(root: Path) -> str:
    import cv2
    import numpy as np

    from .capture import CaptureFrame
    from .ocr import ScreenOCR
    from .translation import LocalTranslator

    require_models(root)
    pixels = np.full((240, 800, 4), 255, dtype=np.uint8)
    cv2.putText(pixels, "Save changes", (30, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.5,
                (0, 0, 0, 255), 2, cv2.LINE_AA)
    frame = CaptureFrame(1, 1, 0, "test", 800, 240, pixels)
    lines = ScreenOCR(root / "ocr").read(frame)
    text = " ".join(line.text for line in lines)
    if "save changes" not in text.casefold():
        raise RuntimeError("Los modelos OCR no pudieron reconocer el texto de prueba.")
    translation, = LocalTranslator(root / "translation").translate([text])
    if "cambios" not in translation.casefold():
        raise RuntimeError("El modelo de traducción no produjo la salida esperada en español.")
    return translation
