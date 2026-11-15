import os
from dataclasses import dataclass
from math import ceil, floor
from pathlib import Path


@dataclass(frozen=True)
class OCRLine:
    bounds_px: tuple[int, int, int, int]
    text: str
    confidence: float


class ScreenOCR:
    def __init__(self, root: Path):
        from rapidocr import EngineType, OCRVersion, RapidOCR

        font = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf"
        self.engine = RapidOCR(params={
            "Global.use_cls": False,
            "Global.max_side_len": 2400,
            "Global.text_score": 0.65,
            "Global.font_path": str(font),
            "Det.engine_type": EngineType.ONNXRUNTIME,
            "Cls.engine_type": EngineType.ONNXRUNTIME,
            "Rec.engine_type": EngineType.ONNXRUNTIME,
            "Det.ocr_version": OCRVersion.PPOCRV4,
            "Rec.ocr_version": OCRVersion.PPOCRV4,
            "Det.model_path": str(root / "detector.onnx"),
            "Cls.model_path": str(root / "classifier.onnx"),
            "Rec.model_path": str(root / "recognizer.onnx"),
            "Rec.rec_keys_path": str(root / "character.txt"),
        })

    def read(self, frame) -> list[OCRLine]:
        result = self.engine(frame.pixels_bgra[:, :, :3].copy(), use_cls=False)
        if result.boxes is None or not result.txts:
            return []
        lines = []
        for polygon, text, confidence in zip(result.boxes, result.txts, result.scores, strict=True):
            text = " ".join(text.split())
            if confidence < 0.65 or not any(character.isascii() and character.isalpha() for character in text):
                continue
            left = max(0, floor(min(polygon[:, 0])))
            top = max(0, floor(min(polygon[:, 1])))
            right = min(frame.width_px, ceil(max(polygon[:, 0])))
            bottom = min(frame.height_px, ceil(max(polygon[:, 1])))
            if right > left and bottom > top:
                lines.append(OCRLine((left, top, right, bottom), text, float(confidence)))
        return lines
