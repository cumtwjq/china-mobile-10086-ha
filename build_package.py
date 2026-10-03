"""Build the HA integration and HAOS app packages without local captures."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "releases" / "china_mobile_10086-experimental.zip"
APP_DESTINATION = ROOT / "releases" / "china_mobile_10086-haos-app.zip"
SOURCES = [
    *sorted((ROOT / "custom_components" / "china_mobile_10086").rglob("*.py")),
    *sorted((ROOT / "custom_components" / "china_mobile_10086").rglob("*.json")),
    ROOT / "README.md",
    ROOT / "INSTALL.md",
]
DESTINATION.parent.mkdir(exist_ok=True)
with ZipFile(DESTINATION, "w", ZIP_DEFLATED) as archive:
    for source in SOURCES:
        archive.write(source, source.relative_to(ROOT))
print(f"Built {DESTINATION} with {len(SOURCES)} files")

APP_SOURCES = [
    source for source in sorted((ROOT / "china_mobile_browser").rglob("*"))
    if source.is_file() and source.suffix not in {".pyc", ".pyo"}
    and "__pycache__" not in source.parts
]
with ZipFile(APP_DESTINATION, "w", ZIP_DEFLATED) as archive:
    for source in APP_SOURCES:
        archive.write(source, source.relative_to(ROOT))
print(f"Built {APP_DESTINATION} with {len(APP_SOURCES)} files")
