import sys
from importlib import metadata
from pathlib import Path
from shutil import copyfile


root = Path(__file__).resolve().parents[1] / "build" / "third-party-licenses"
root.mkdir(parents=True, exist_ok=True)
for package in sorted(metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
    for file in package.files or ():
        name = file.name.lower()
        if name.startswith(("license", "licence", "copying", "notice")) and ".dist-info" in file.parts[0]:
            source = package.locate_file(file)
            if source.is_file():
                target = root / file
                target.parent.mkdir(parents=True, exist_ok=True)
                copyfile(source, target)

python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    copyfile(python_license, root / "Python-LICENSE.txt")
