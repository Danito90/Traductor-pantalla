from collections import OrderedDict
from dataclasses import dataclass
from hashlib import blake2b
from threading import Condition, Thread

from .capture import CaptureFrame
from .ocr import ScreenOCR
from .translation import LocalTranslator


@dataclass(frozen=True)
class TextBlock:
    session_id: int
    frame_id: int
    bounds_px: tuple[int, int, int, int]
    source_text: str
    ocr_confidence: float
    region_fingerprint: bytes


@dataclass(frozen=True)
class OverlayBlock:
    session_id: int
    frame_id: int
    bounds_px: tuple[int, int, int, int]
    region_fingerprint: bytes
    translated_text: str


def fingerprint(frame: CaptureFrame, bounds=None) -> bytes:
    pixels = frame.pixels_bgra
    if bounds is not None:
        left, top, right, bottom = bounds
        pixels = pixels[top:bottom, left:right, :3]
    return blake2b(pixels if pixels.flags.c_contiguous else pixels.tobytes(), digest_size=16).digest()


def visible_blocks(frame, blocks) -> tuple[OverlayBlock, ...]:
    if frame is None:
        return ()
    return tuple(block for block in blocks if block.session_id == frame.session_id
                 and block.bounds_px[2] <= frame.width_px and block.bounds_px[3] <= frame.height_px
                 and fingerprint(frame, block.bounds_px) == block.region_fingerprint)


class TranslationCache:
    def __init__(self):
        self.values = OrderedDict()

    def translate(self, translator, texts):
        keys = list(dict.fromkeys(" ".join(text.split()) for text in texts))
        results = {}
        missing = []
        for key in keys:
            if key in self.values:
                self.values.move_to_end(key)
                results[key] = self.values[key]
            else:
                missing.append(key)
        for key, translation in zip(missing, translator.translate(missing), strict=True):
            self.values[key] = translation
            results[key] = translation
        while len(self.values) > 512:
            self.values.popitem(last=False)
        return results


class SessionWorker:
    def __init__(self, root):
        self.root = root
        self.condition = Condition()
        self.session_id = None
        self.latest = None
        self.enabled = False
        self.last_started = 0
        self.blocks = ()
        self.error = None
        self.closed = False
        self.thread = Thread(target=self._run, name="Traducción local", daemon=True)
        self.thread.start()

    def reset(self, session_id=None):
        with self.condition:
            self.session_id = session_id
            self.latest = None
            self.enabled = False
            self.last_started = 0
            self.blocks = ()
            self.error = None
            self.condition.notify()

    def push(self, frame):
        with self.condition:
            if frame.session_id == self.session_id:
                self.latest = frame
                self.condition.notify()

    def start_inference(self):
        with self.condition:
            self.enabled = True
            self.condition.notify()

    def fail(self, session_id, error):
        with self.condition:
            if session_id == self.session_id and self.error is None:
                self.error = error

    def snapshot(self):
        with self.condition:
            return self.latest, self.blocks, self.error

    def close(self):
        with self.condition:
            self.closed = True
            self.session_id = None
            self.latest = None
            self.blocks = ()
            self.condition.notify()

    def _has_work(self):
        return self.enabled and self.error is None and self.latest is not None and self.latest.frame_id > self.last_started

    def _run(self):
        ocr = translator = cache = None
        previous_session = previous_fingerprint = None
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self._has_work())
                if self.closed:
                    return
                frame = self.latest
                self.last_started = frame.frame_id
            try:
                if previous_session != frame.session_id:
                    cache = TranslationCache()
                    previous_session = frame.session_id
                    previous_fingerprint = None
                digest = fingerprint(frame)
                if digest == previous_fingerprint:
                    continue
                previous_fingerprint = digest
                if ocr is None:
                    ocr = ScreenOCR(self.root / "ocr")
                if translator is None:
                    translator = LocalTranslator(self.root / "translation")
                blocks = self._process(frame, ocr, translator, cache)
                with self.condition:
                    if frame.session_id == self.session_id and not self.closed:
                        self.blocks = blocks
            except Exception as exc:
                ocr = translator = None
                self.fail(frame.session_id, f"No se pudo ejecutar la traducción local. {exc}")
            finally:
                del frame

    def _process(self, frame, ocr, translator, cache):
        lines = ocr.read(frame)
        blocks = [TextBlock(frame.session_id, frame.frame_id, line.bounds_px, line.text,
                            line.confidence, fingerprint(frame, line.bounds_px)) for line in lines]
        with self.condition:
            if frame.session_id != self.session_id or self.closed:
                return ()
        translations = cache.translate(translator, [block.source_text for block in blocks])
        return tuple(OverlayBlock(block.session_id, block.frame_id, block.bounds_px,
                                  block.region_fingerprint, translations[block.source_text])
                     for block in blocks if translations[block.source_text]
                     and translations[block.source_text] != block.source_text)
