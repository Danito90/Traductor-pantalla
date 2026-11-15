import sys
import winreg
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "TraductorPantalla"


def startup_command() -> str:
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        command = f'"{executable}"'
    else:
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.is_file():
            executable = pythonw
        command = f'"{executable}" -m traductor_pantalla'
    if len(command.encode("utf-16-le")) // 2 > 260:
        raise ValueError("La ruta del traductor es demasiado larga para el inicio automático de Windows.")
    return command


def read_startup_entry() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return None
    return command if isinstance(command, str) and command else None


def write_startup_entry(command: str | None) -> None:
    if command is not None:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, access=winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, access=winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
