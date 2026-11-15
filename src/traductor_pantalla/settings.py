import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


MODIFIERS = {"Ctrl": 0x0002, "Alt": 0x0001, "Shift": 0x0004}
KEYS = {f"F{number}": 0x6F + number for number in range(1, 13)}
KEYS.update({key: ord(key) for key in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})


def parse_hotkey(text: str) -> tuple[int, int]:
    parts = text.split("+")
    modifiers, key = parts[:-1], parts[-1]
    if not modifiers or len(set(modifiers)) != len(modifiers):
        raise ValueError("Usá modificadores distintos y una tecla, por ejemplo Ctrl+Alt+F8.")
    if key not in KEYS or any(part not in MODIFIERS for part in modifiers):
        raise ValueError("Usá Ctrl, Alt o Shift y una letra, número o tecla F1 a F12.")
    return sum(MODIFIERS[part] for part in modifiers), KEYS[key]


@dataclass(frozen=True)
class Settings:
    monitor_device_path: str | None = None
    toggle_translation_hotkey: str = "Ctrl+Alt+F8"
    toggle_original_hotkey: str = "Ctrl+Alt+F9"

    def hotkeys(self) -> tuple[tuple[int, int], tuple[int, int]]:
        first = parse_hotkey(self.toggle_translation_hotkey)
        second = parse_hotkey(self.toggle_original_hotkey)
        if first == second:
            raise ValueError("Los dos atajos deben ser distintos.")
        return first, second


def settings_path() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "TraductorPantalla" / "settings.json"


def load_settings(path: Path) -> tuple[Settings, str | None]:
    try:
        values = Settings(**json.loads(path.read_text(encoding="utf-8")))
        if values.monitor_device_path is not None and not isinstance(values.monitor_device_path, str):
            raise ValueError("Monitor inválido")
        values.hotkeys()
        return values, None
    except FileNotFoundError:
        return Settings(), None
    except (OSError, TypeError, ValueError, AttributeError):
        return Settings(), "No se pudo leer la configuración. Se cargaron los valores iniciales."


def save_settings(path: Path, settings: Settings) -> None:
    settings.hotkeys()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(asdict(settings), handle, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
