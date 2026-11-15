import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

from .settings import Settings


WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
HOTKEY_IDS = (0x1C01, 0x1C02)


class GlobalHotkeys(QAbstractNativeEventFilter):
    def __init__(self, toggle_translation, toggle_original):
        super().__init__()
        self.callbacks = dict(zip(HOTKEY_IDS, (toggle_translation, toggle_original), strict=True))
        self.bindings = {}
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        self.user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)

    def _register(self, identifier, combination) -> bool:
        modifiers, key = combination
        if not self.user32.RegisterHotKey(None, identifier, modifiers | MOD_NOREPEAT, key):
            return False
        self.bindings[identifier] = combination
        return True

    def configure(self, settings: Settings, *, initial=False) -> list[int]:
        desired = dict(zip(HOTKEY_IDS, settings.hotkeys(), strict=True))
        prior = self.bindings.copy()
        for identifier, combination in prior.items():
            if desired[identifier] != combination:
                self.user32.UnregisterHotKey(None, identifier)
                del self.bindings[identifier]
        failures = [i for i, combo in desired.items() if i not in self.bindings and not self._register(i, combo)]
        if failures and not initial:
            for identifier, combination in tuple(self.bindings.items()):
                if prior.get(identifier) != combination:
                    self.user32.UnregisterHotKey(None, identifier)
                    del self.bindings[identifier]
            for identifier, combination in prior.items():
                if identifier not in self.bindings:
                    self._register(identifier, combination)
        return failures

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            event = wintypes.MSG.from_address(int(message))
            if event.message == WM_HOTKEY and event.wParam in self.bindings:
                self.callbacks[event.wParam]()
                return True, 0
        return False, 0

    def close(self):
        for identifier in self.bindings:
            self.user32.UnregisterHotKey(None, identifier)
        self.bindings.clear()
