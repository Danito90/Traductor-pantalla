import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch

import numpy as np

from traductor_pantalla.capture import CaptureFrame
from traductor_pantalla.ocr import OCRLine
from traductor_pantalla.session import OverlayBlock, SessionWorker, TranslationCache, fingerprint, visible_blocks
from traductor_pantalla.settings import Settings, load_settings, save_settings


def frame(session=1, number=1, value=0):
    return CaptureFrame(session, number, 0, "monitor", 8, 8, np.full((8, 8, 4), value, dtype=np.uint8))


class Translator:
    def __init__(self):
        self.calls = []

    def translate(self, values):
        if values:
            self.calls.append(values)
        return [f"ES {value}" for value in values]


class ConfigurationTests(unittest.TestCase):
    def test_round_trip_and_invalid_json(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            settings = Settings("monitor", "Ctrl+Alt+1", "Ctrl+Alt+2")
            save_settings(path, settings)
            self.assertEqual(set(json.loads(path.read_text(encoding="utf-8"))), set(vars(settings)))
            self.assertEqual(load_settings(path), (settings, None))
            path.write_text("[]", encoding="utf-8")
            restored, error = load_settings(path)
            self.assertEqual(restored, Settings())
            self.assertIsNotNone(error)

    def test_reordered_modifiers_are_a_duplicate(self):
        with self.assertRaises(ValueError):
            Settings(None, "Ctrl+Alt+F8", "Alt+Ctrl+F8").hotkeys()


class SessionTests(unittest.TestCase):
    def test_changed_regions_are_removed_and_unchanged_regions_remain(self):
        initial = frame()
        bounds = ((0, 0, 4, 4), (4, 4, 8, 8))
        blocks = tuple(OverlayBlock(1, 1, area, fingerprint(initial, area), str(area)) for area in bounds)
        latest = frame(number=2)
        latest.pixels_bgra[1, 1, 0] = 40
        self.assertEqual(visible_blocks(latest, blocks), (blocks[1],))
        self.assertFalse(visible_blocks(frame(session=2), blocks))

    def test_translation_cache_deduplicates_and_stays_bounded(self):
        translator = Translator()
        cache = TranslationCache()
        cache.translate(translator, ["One  line", "One line"])
        cache.translate(translator, ["One line"])
        self.assertEqual(translator.calls, [["One line"]])
        cache.translate(translator, [str(number) for number in range(520)])
        self.assertEqual(len(cache.values), 512)
        self.assertNotIn("One line", cache.values)

    def test_pause_discards_in_flight_recognition_and_uses_latest_frame(self):
        started = Event()
        release = Event()
        completed = Event()
        calls = []

        class OCR:
            def read(self, value):
                calls.append((value.session_id, value.frame_id))
                if value.session_id == 1:
                    started.set()
                    release.wait(3)
                return [OCRLine((0, 0, 4, 4), "Hello", 0.9)]

        class TrackingTranslator(Translator):
            def translate(self, values):
                completed.set()
                return super().translate(values)

        with patch("traductor_pantalla.session.ScreenOCR", return_value=OCR()), patch(
                "traductor_pantalla.session.LocalTranslator", return_value=TrackingTranslator()):
            worker = SessionWorker(Path("models"))
            try:
                worker.reset(1)
                worker.push(frame())
                worker.start_inference()
                self.assertTrue(started.wait(3))
                worker.reset(2)
                worker.push(frame(session=2, number=1))
                worker.push(frame(session=2, number=2))
                worker.start_inference()
                release.set()
                self.assertTrue(completed.wait(3))
                self.assertEqual(calls, [(1, 1), (2, 2)])
            finally:
                release.set()
                worker.close()
                worker.thread.join(3)


if __name__ == "__main__":
    unittest.main()
