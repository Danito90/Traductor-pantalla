import ctypes
from ctypes import wintypes
from math import floor

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QTextOption
from PySide6.QtWidgets import QWidget


PROBE_COLORS = ((241, 43, 173), (34, 224, 179), (250, 199, 51))
PROBE_SIZE = 12
PROBE_OFFSET = 16


def probe_present(frame) -> bool:
    for index, rgb in enumerate(PROBE_COLORS):
        x = PROBE_OFFSET + index * PROBE_SIZE + PROBE_SIZE // 2
        y = PROBE_OFFSET + PROBE_SIZE // 2
        if x >= frame.width_px or y >= frame.height_px:
            return False
        pixel = frame.pixels_bgra[y, x]
        if any(abs(int(value) - wanted) > 12 for value, wanted in zip(pixel[:3], reversed(rgb))):
            return False
    return True


class Overlay(QWidget):
    def __init__(self, monitor, screen):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.monitor = monitor
        self.blocks = ()
        self.probing = True
        self.checked_handle = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.SetWindowDisplayAffinity.argtypes = (wintypes.HWND, wintypes.DWORD)
        self.user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
        self.winId()
        self.windowHandle().setScreen(screen)
        self.setGeometry(screen.geometry())

    def _exclude(self):
        handle = int(self.winId())
        if not self.user32.SetWindowDisplayAffinity(handle, 0x11):
            raise ctypes.WinError(ctypes.get_last_error())
        self.checked_handle = handle

    def open(self):
        self._exclude()
        self.show()
        self.validate_handle()
        monitor = self.monitor
        if not self.user32.SetWindowPos(self.checked_handle, -1, monitor.x, monitor.y,
                                       monitor.width, monitor.height, 0x0010):
            raise ctypes.WinError(ctypes.get_last_error())
        self.repaint()
        ctypes.WinDLL("dwmapi").DwmFlush()

    def validate_handle(self):
        if self.checked_handle != int(self.winId()):
            self._exclude()

    def set_blocks(self, blocks):
        if self.blocks != blocks or self.probing:
            self.probing = False
            self.blocks = blocks
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        scale = self.devicePixelRatioF()
        if self.probing:
            for index, rgb in enumerate(PROBE_COLORS):
                x = PROBE_OFFSET + index * PROBE_SIZE
                painter.fillRect(QRectF(x / scale, PROBE_OFFSET / scale, PROBE_SIZE / scale,
                                        PROBE_SIZE / scale), QColor(*rgb))
            return
        options = QTextOption(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        options.setWrapMode(QTextOption.WrapMode.WordWrap)
        for block in self.blocks:
            left, top, right, bottom = block.bounds_px
            cover = QRectF(left / scale, top / scale, (right - left) / scale, (bottom - top) / scale)
            text_area = cover.adjusted(1, 0, -1, 0)
            font = QFont("Segoe UI")
            for size in range(min(36, floor(text_area.height())), 8, -1):
                font.setPixelSize(size)
                painter.setFont(font)
                bounds = painter.boundingRect(text_area, block.translated_text, options)
                if bounds.width() <= text_area.width() and bounds.height() <= text_area.height():
                    painter.fillRect(cover, QColor("#17212b"))
                    painter.setPen(QColor("#ffffff"))
                    painter.drawText(text_area, block.translated_text, options)
                    break
