import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from time import monotonic


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD), ("area", wintypes.RECT), ("work", wintypes.RECT),
        ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 32),
    ]


class DisplayDevice(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD), ("name", wintypes.WCHAR * 32),
        ("label", wintypes.WCHAR * 128), ("flags", wintypes.DWORD),
        ("path", wintypes.WCHAR * 128), ("registry_key", wintypes.WCHAR * 128),
    ]


@dataclass(frozen=True)
class Monitor:
    index: int
    name: str
    device_path: str
    label: str
    x: int
    y: int
    width: int
    height: int
    primary: bool


def enumerate_monitors() -> list[Monitor]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                     ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32.EnumDisplayMonitors.argtypes = (wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                          callback_type, wintypes.LPARAM)
    user32.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(MonitorInfo))
    user32.EnumDisplayDevicesW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD,
                                           ctypes.POINTER(DisplayDevice), wintypes.DWORD)
    monitors = []
    index = 0

    @callback_type
    def collect(handle, _dc, _rect, _data):
        nonlocal index
        # windows-capture usa EnumDisplayMonitors y un índice basado en 1.
        index += 1
        info = MonitorInfo(size=ctypes.sizeof(MonitorInfo))
        if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            return True
        display = DisplayDevice(size=ctypes.sizeof(DisplayDevice))
        user32.EnumDisplayDevicesW(info.name, 0, ctypes.byref(display), 1)
        area = info.area
        monitors.append(Monitor(index, info.name, display.path or info.name,
                                display.label or info.name, area.left, area.top,
                                area.right - area.left, area.bottom - area.top, bool(info.flags & 1)))
        return True

    if not user32.EnumDisplayMonitors(None, None, collect, 0):
        raise OSError("Windows no pudo enumerar los monitores.")
    return monitors


@dataclass(frozen=True)
class CaptureFrame:
    session_id: int
    frame_id: int
    captured_at_monotonic: float
    monitor_device_path: str
    width_px: int
    height_px: int
    pixels_bgra: object


class MonitorCapture:
    def __init__(self, monitor: Monitor, session_id: int, on_frame, on_error):
        from windows_capture import WindowsCapture

        self.control = None
        self.backend = WindowsCapture(monitor_index=monitor.index, cursor_capture=False)
        frame_id = 0

        @self.backend.event
        def on_frame_arrived(frame, control):
            nonlocal frame_id
            now = monotonic()
            try:
                if (frame.width, frame.height) != (monitor.width, monitor.height):
                    raise ValueError("Cambió la geometría del monitor activo. Volvé a iniciar la captura.")
                frame_id += 1
                on_frame(CaptureFrame(session_id, frame_id, now, monitor.device_path,
                                      frame.width, frame.height, frame.frame_buffer.copy()))
            except Exception as exc:
                on_error(session_id, str(exc))
                control.stop()

        @self.backend.event
        def on_closed():
            on_error(session_id, "Terminó la captura del monitor. Elegí un monitor o volvé a iniciar.")

    def start(self):
        self.control = self.backend.start_free_threaded()

    def close(self):
        if self.control is not None and not self.control.is_finished():
            self.control.stop()
        self.control = None
