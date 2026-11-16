"""Prepara los modelos durante la compilación, nunca durante el uso de la app."""

import hashlib
import json
import shutil
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from tarfile import open as open_tar
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.request import urlopen


PROJECT = Path(__file__).resolve().parents[1]
DESTINATION = PROJECT / "models" / "assets"


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def download(url, target, expected=None):
    if expected and target.is_file() and sha256(target) == expected:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    try:
        print(f"Descargando {target.name}", flush=True)
        with urlopen(url, timeout=45) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        if expected and sha256(temporary) != expected:
            raise RuntimeError(f"SHA-256 inesperado para {target.name}")
        temporary.replace(target)
    except URLError as exc:
        raise SystemExit(f"No se pudo descargar {target.name}: {exc}. Volvé a ejecutar el script para reintentar.") from exc
    finally:
        temporary.unlink(missing_ok=True)


def prepare_ocr(spec):
    from onnxruntime import InferenceSession

    destination = DESTINATION / "ocr"
    base = f'https://huggingface.co/{spec["project"]}/resolve/{spec["revision"]}'
    for filename, asset in spec["files"].items():
        download(f'{base}/{asset["path"]}', destination / filename, asset["sha256"])
    engine = InferenceSession(str(destination / "recognizer.onnx"), providers=["CPUExecutionProvider"])
    metadata = engine.get_modelmeta().custom_metadata_map
    characters = metadata.get("character")
    if not characters or "\n" not in characters:
        raise RuntimeError("El modelo de reconocimiento no contiene el diccionario esperado.")
    (destination / "character.txt").write_text(characters.rstrip("\r\n") + "\n", encoding="utf-8")


def unpack_translation(archive, destination):
    expected = {"source.spm", "target.spm", "model.bin", "config.json", "shared_vocabulary.json"}
    extracted = set()
    with open_tar(archive, mode="r|gz") as package:
        for item in package:
            name = PurePosixPath(item.name).name
            if name not in expected:
                continue
            if not item.isfile() or not item.size or name in extracted:
                raise RuntimeError(f"Entrada inválida en el paquete OPUS-MT: {name}")
            with package.extractfile(item) as source, (destination / name).open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted.add(name)
    missing = expected - extracted
    if missing:
        raise RuntimeError(f"Faltan archivos en el paquete OPUS-MT: {', '.join(sorted(missing))}")


def prepare_translation(spec):
    destination = DESTINATION / "translation"
    archive = PROJECT / "build" / "model-downloads" / spec["archive"]
    url = f'https://huggingface.co/{spec["distributor"]}/resolve/{spec["revision"]}/{spec["archive"]}'
    download(url, archive, spec["archive_sha256"])
    with TemporaryDirectory(dir=DESTINATION) as directory:
        unpack_translation(archive, Path(directory))
        destination.mkdir(exist_ok=True)
        for file in Path(directory).iterdir():
            file.replace(destination / file.name)


def verify_assets():
    manifest_path = DESTINATION / "manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in report["sha256"].items():
        path = DESTINATION / name
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"Modelo faltante o modificado: {name}")


def main():
    from traductor_pantalla.models import verify_local_inference

    lock = json.loads((PROJECT / "models" / "models.lock.json").read_text(encoding="utf-8"))
    manifest = DESTINATION / "manifest.json"
    if manifest.is_file():
        existing = json.loads(manifest.read_text(encoding="utf-8"))
        if existing["sources"] == lock and existing["ctranslate2"] == version("ctranslate2"):
            verify_assets()
            verify_local_inference(DESTINATION)
            print("Modelos locales verificados.")
            return
    DESTINATION.mkdir(parents=True, exist_ok=True)
    prepare_ocr(lock["ocr"])
    prepare_translation(lock["translation"])
    apache_license = DESTINATION / "Apache-2.0.txt"
    if not apache_license.is_file() or apache_license.stat().st_size == 0:
        download("https://www.apache.org/licenses/LICENSE-2.0.txt", apache_license)
    verify_local_inference(DESTINATION)
    report = {"sources": lock, "ctranslate2": version("ctranslate2"),
              "sha256": {path.relative_to(DESTINATION).as_posix(): sha256(path)
                         for directory in ("ocr", "translation")
                         for path in sorted((DESTINATION / directory).iterdir()) if path.is_file()}}
    manifest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    verify_assets()
    print("Modelos locales verificados.")


if __name__ == "__main__":
    main()
