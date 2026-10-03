"""Build a self-contained Windows capture ZIP from local_tool."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "local_tool"
DESTINATION = ROOT / "releases" / "china_mobile_10086-local-capture.zip"
FILES = [
    "run_capture.py",
    "local_capture.py",
    "vault.py",
    "clipboard.py",
    "export_capture.py",
    "获取10086请求.cmd",
    "复制10086请求.cmd",
    "本地抓取说明.md",
]
DESTINATION.parent.mkdir(exist_ok=True)
with ZipFile(DESTINATION, "w", ZIP_DEFLATED) as archive:
    for name in FILES:
        source = SOURCE / name
        data = source.read_bytes()
        if name.lower().endswith(".cmd"):
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        archive.writestr(f"china_mobile_10086-local-capture/{name}", data)
    archive.write(
        SOURCE / "bin" / "mitmdump.exe",
        "china_mobile_10086-local-capture/bin/mitmdump.exe",
    )
    archive.write(
        SOURCE / "MITMPROXY-LICENSE.txt",
        "china_mobile_10086-local-capture/MITMPROXY-LICENSE.txt",
    )
    for source in sorted((SOURCE / "python").iterdir()):
        archive.write(source, f"china_mobile_10086-local-capture/python/{source.name}")
print(f"Built {DESTINATION} with {len(FILES)} tool files and bundled runtimes")
