import sys


def main() -> int:
    if sys.platform != "win32":
        print("Traductor de pantalla requiere Windows 11 x64.", file=sys.stderr)
        return 1

    from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

    from traductor_pantalla.tray import TrayController

    if sys.argv[1:] == ["--verificar"]:
        from traductor_pantalla.models import model_root, verify_local_inference

        verify_local_inference(model_root())
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("Traductor de pantalla")
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Traductor de pantalla", "Windows no tiene una bandeja disponible.")
        return 1
    try:
        controller = TrayController(app)
    except OSError as exc:
        QMessageBox.critical(None, "Traductor de pantalla", str(exc))
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
