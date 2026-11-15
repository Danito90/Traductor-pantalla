from contextlib import ExitStack
from dataclasses import replace
from enum import Enum, auto
from time import monotonic

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QActionGroup, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                               QLineEdit, QMenu, QMessageBox, QSystemTrayIcon)

from .capture import MonitorCapture, enumerate_monitors
from .hotkeys import GlobalHotkeys
from .models import model_root, require_models
from .overlay import Overlay, probe_present
from .session import SessionWorker, visible_blocks
from .settings import load_settings, save_settings, settings_path
from .startup import read_startup_entry, startup_command, write_startup_entry


class State(Enum):
    PAUSED = auto()
    STARTING = auto()
    TRANSLATING = auto()
    SHOWING_ORIGINAL = auto()
    ERROR = auto()


def _icon(color: str) -> QIcon:
    image = QPixmap(32, 32)
    image.fill(QColor(color))
    painter = QPainter(image)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    painter.drawText(3, 22, "ES")
    painter.end()
    return QIcon(image)


def _settings_icon() -> QIcon:
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setPen(QColor("#347ac1"))
    font = QFont("Segoe UI Symbol")
    font.setPixelSize(27)
    painter.setFont(font)
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "⚙")
    painter.end()
    return QIcon(image)


class TrayController(QObject):
    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self.path = settings_path()
        self.settings, settings_warning = load_settings(self.path)
        self.monitors = enumerate_monitors()
        monitor = next((m for m in self.monitors if m.device_path == self.settings.monitor_device_path),
                       next((m for m in self.monitors if m.primary), None))
        self.selected_path = monitor.device_path if monitor else None
        self.state = State.PAUSED
        self.root = model_root()
        self.worker = SessionWorker(self.root)
        self.session_id = 0
        self.capture = self.overlay = None
        self.deadline = 0.0
        self.rendered = None
        self.session_monitor = None
        self.settings_dialog = None

        self.tray = QSystemTrayIcon(self)
        self.menu = QMenu()
        self.status_action = self.menu.addAction("")
        self.status_action.setEnabled(False)
        self.menu.addSeparator()
        self.toggle_action = self.menu.addAction("Iniciar traducción", self.toggle_capture)
        self.original_action = self.menu.addAction("Mostrar original", self.toggle_original)
        self.monitor_menu = self.menu.addMenu("Monitor")
        self.monitor_group = None
        self.settings_action = self.menu.addAction(_settings_icon(), "Configuración…", self.open_settings)
        self.settings_action.setIconVisibleInMenu(True)
        self.menu.addSeparator()
        self.menu.addAction("Salir", app.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)

        self.hotkeys = GlobalHotkeys(self.toggle_capture, self.toggle_original)
        app.installNativeEventFilter(self.hotkeys)
        unavailable = self.hotkeys.configure(self.settings, initial=True)
        app.screenAdded.connect(self._screen_added)
        app.screenRemoved.connect(self.refresh_monitors)
        for screen in app.screens():
            self._watch_screen(screen)
        app.aboutToQuit.connect(self.close)

        self.timer = QTimer(self)
        self.timer.setInterval(35)
        self.timer.timeout.connect(self._poll)
        self._populate_monitors()
        self._set_state(State.PAUSED)
        self.tray.show()
        if settings_warning:
            self._notify(settings_warning)
        if unavailable:
            self._notify("Windows no pudo registrar uno o más atajos. Podés usar el menú de la bandeja o cambiar los atajos.")

    def _notify(self, message):
        self.tray.showMessage("Traductor de pantalla", message, QSystemTrayIcon.MessageIcon.Warning)

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    def _watch_screen(self, screen):
        screen.geometryChanged.connect(self.refresh_monitors)
        screen.logicalDotsPerInchChanged.connect(self.refresh_monitors)

    def _screen_added(self, screen):
        self._watch_screen(screen)
        self.refresh_monitors()

    def refresh_monitors(self, *_):
        try:
            self.monitors = enumerate_monitors()
        except OSError as exc:
            self._fail(str(exc))
            return
        current = self._selected_monitor()
        if self.session_monitor is not None:
            previous = self.session_monitor
            if current is None or replace(current, index=previous.index) != previous:
                self._fail("El monitor cambió o se desconectó. Elegí un monitor y volvé a iniciar.")
        self._populate_monitors()

    def _selected_monitor(self):
        return next((m for m in self.monitors if m.device_path == self.selected_path), None)

    def _populate_monitors(self):
        self.monitor_menu.clear()
        if self.monitor_group is not None:
            self.monitor_group.deleteLater()
        group = QActionGroup(self.monitor_menu)
        group.setExclusive(True)
        self.monitor_group = group
        for monitor in self.monitors:
            label = f"{monitor.name.split(chr(92))[-1]} · {monitor.label} · {monitor.width} × {monitor.height}"
            action = self.monitor_menu.addAction(label)
            group.addAction(action)
            action.setCheckable(True)
            action.setChecked(monitor.device_path == self.selected_path)
            action.triggered.connect(lambda checked, path=monitor.device_path: self.select_monitor(path))
        if not self.monitors:
            self.monitor_menu.addAction("Sin monitores disponibles").setEnabled(False)

    def _screen_for(self, monitor):
        screens = self.app.screens()
        for screen in screens:
            if screen.name().casefold() == monitor.name.casefold():
                return screen
        # En Windows Qt conserva el origen físico de cada pantalla y escala su tamaño.
        for screen in screens:
            area = screen.geometry()
            scale = screen.devicePixelRatio()
            if ((area.x(), area.y()) == (monitor.x, monitor.y)
                    and abs(area.width() * scale - monitor.width) <= 2
                    and abs(area.height() * scale - monitor.height) <= 2):
                return screen
        raise RuntimeError("Qt no pudo vincular el monitor de Windows con la superposición.")

    def select_monitor(self, path):
        settings = replace(self.settings, monitor_device_path=path)
        changed = self.selected_path != path
        try:
            save_settings(self.path, settings)
        except OSError as exc:
            self._notify(f"No se pudo guardar el monitor. {exc}")
            self._populate_monitors()
            return
        self.settings = settings
        self.selected_path = path
        if changed and self.capture is not None:
            self._stop_capture()
            self._start_capture()
        elif changed and self.state is State.ERROR:
            self._set_state(State.PAUSED)

    def open_settings(self):
        if self.settings_dialog is not None:
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        dialog = QDialog()
        dialog.setWindowTitle("Configuración del traductor")
        dialog.setWindowIcon(self.settings_action.icon())
        form = QFormLayout(dialog)
        launch_at_login = QCheckBox("Iniciar con Windows")
        launch_at_login.setToolTip("Abre el traductor en pausa al iniciar sesión en Windows.")
        startup_entry = None
        try:
            startup_entry = read_startup_entry()
            launch_at_login.setChecked(startup_entry is not None)
        except OSError as exc:
            launch_at_login.setEnabled(False)
            launch_at_login.setToolTip(f"No se pudo leer el inicio automático de Windows. {exc}")
        form.addRow(launch_at_login)
        translate = QLineEdit(self.settings.toggle_translation_hotkey)
        original = QLineEdit(self.settings.toggle_original_hotkey)
        translate.setPlaceholderText("Ctrl+Alt+F8")
        original.setPlaceholderText("Ctrl+Alt+F9")
        form.addRow("Iniciar o pausar", translate)
        form.addRow("Alternar original", original)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(dialog.reject)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        form.addRow(buttons)

        def apply():
            candidate = replace(self.settings, toggle_translation_hotkey=translate.text().strip(),
                                toggle_original_hotkey=original.text().strip())
            change_hotkeys = candidate != self.settings
            enable_startup = launch_at_login.isChecked()
            change_startup = launch_at_login.isEnabled() and enable_startup != (startup_entry is not None)
            try:
                candidate.hotkeys()
                with ExitStack() as rollback:
                    if change_hotkeys:
                        if self.hotkeys.configure(candidate):
                            raise ValueError("Windows indicó que al menos un atajo no está disponible.")
                        rollback.callback(self.hotkeys.configure, self.settings)
                    if change_startup:
                        write_startup_entry(startup_command() if enable_startup else None)
                        rollback.callback(write_startup_entry, startup_entry)
                    if change_hotkeys:
                        save_settings(self.path, candidate)
                    rollback.pop_all()
            except (ValueError, OSError) as exc:
                QMessageBox.warning(dialog, "No se pudo guardar la configuración", str(exc))
                return
            self.settings = candidate
            dialog.accept()

        buttons.accepted.connect(apply)
        self.settings_dialog = dialog
        try:
            dialog.exec()
        finally:
            self.settings_dialog = None

    def _set_state(self, state, detail=None):
        self.state = state
        states = {
            State.PAUSED: ("En pausa", "#405066"),
            State.STARTING: ("Verificando captura…", "#806118"),
            State.TRANSLATING: ("Traduciendo", "#067961"),
            State.SHOWING_ORIGINAL: ("Mostrando original", "#335c8f"),
            State.ERROR: (detail or "Error de captura", "#9d263d"),
        }
        label, color = states[state]
        self.tray.setIcon(_icon(color))
        self.tray.setToolTip(f"Traductor de pantalla · {label}")
        self.status_action.setText(label)
        active = state in (State.STARTING, State.TRANSLATING, State.SHOWING_ORIGINAL)
        self.toggle_action.setText("Pausar traducción" if active else "Iniciar traducción")
        self.original_action.setEnabled(state in (State.TRANSLATING, State.SHOWING_ORIGINAL))
        self.original_action.setText("Mostrar traducción" if state is State.SHOWING_ORIGINAL else "Mostrar original")

    def toggle_capture(self):
        if self.capture is not None:
            self._stop_capture()
            self._set_state(State.PAUSED)
        else:
            self._start_capture()

    def toggle_original(self):
        if self.state is State.TRANSLATING:
            self.overlay.hide()
            self._set_state(State.SHOWING_ORIGINAL)
        elif self.state is State.SHOWING_ORIGINAL:
            try:
                frame, blocks, error = self.worker.snapshot()
                if error:
                    raise RuntimeError(error)
                self.overlay.set_blocks(visible_blocks(frame, blocks))
                self.overlay.validate_handle()
                self.overlay.show()
                self.overlay.validate_handle()
                self._set_state(State.TRANSLATING)
            except (RuntimeError, OSError) as exc:
                self._fail(str(exc))

    def _start_capture(self):
        try:
            self.refresh_monitors()
            monitor = self._selected_monitor()
            if monitor is None:
                raise RuntimeError("Elegí un monitor conectado desde la bandeja.")
            require_models(self.root)
            self.session_id += 1
            self.worker.reset(self.session_id)
            self.session_monitor = monitor
            self.overlay = Overlay(monitor, self._screen_for(monitor))
            self.overlay.open()
            self.capture = MonitorCapture(monitor, self.session_id, self.worker.push, self.worker.fail)
            self.capture.start()
            self.deadline = monotonic() + 4
            self._set_state(State.STARTING)
            self.timer.start()
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            self._fail(str(exc))

    def _poll(self):
        frame, blocks, error = self.worker.snapshot()
        if error:
            self._fail(error)
            return
        try:
            self.overlay.validate_handle()
        except OSError as exc:
            self._fail(f"No se pudo excluir la superposición de la captura. {exc}")
            return
        if self.state is State.STARTING:
            if frame is None:
                if monotonic() > self.deadline:
                    self._fail("Windows no entregó un fotograma del monitor seleccionado.")
                return
            if probe_present(frame):
                self._fail("La superposición apareció en la captura. Se detuvo la sesión.")
                return
            self.overlay.set_blocks(())
            self.worker.start_inference()
            self._set_state(State.TRANSLATING)
        if self.state is State.TRANSLATING and frame is not None:
            rendered = (frame.frame_id, blocks)
            if rendered != self.rendered:
                self.overlay.set_blocks(visible_blocks(frame, blocks))
                self.rendered = rendered

    def _stop_capture(self):
        self.timer.stop()
        self.worker.reset()
        self.session_monitor = None
        self.rendered = None
        if self.overlay is not None:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None
        if self.capture is not None:
            capture, self.capture = self.capture, None
            try:
                capture.close()
            except (RuntimeError, OSError):
                pass

    def _fail(self, message):
        self._stop_capture()
        self._set_state(State.ERROR, message)
        self._notify(message)

    def close(self):
        self._stop_capture()
        self.worker.close()
        self.app.removeNativeEventFilter(self.hotkeys)
        self.hotkeys.close()
        self.tray.hide()
