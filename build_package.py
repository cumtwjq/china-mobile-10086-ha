"""Build the HA integration package without local captures."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "releases" / "china_mobile_10086-experimental.zip"
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
