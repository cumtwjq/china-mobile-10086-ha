"""Keep the owner's China Mobile requests encrypted with Windows DPAPI."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
from pathlib import Path


VAULT = Path.home() / "AppData" / "Local" / "ChinaMobileHA" / "capture.dpapi"


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _crypt(data: bytes, decrypt: bool) -> bytes:
    source, keep_alive = _blob(data)
    result = DataBlob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    name = "CryptUnprotectData" if decrypt else "CryptProtectData"
    function = getattr(crypt32, name)
    function.argtypes = [
        ctypes.POINTER(DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


def save_capture(capture: dict) -> None:
    """Save only the verified read-only request, encrypted for this Windows user."""
    VAULT.parent.mkdir(parents=True, exist_ok=True)
    plaintext = json.dumps(capture, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    VAULT.write_bytes(_crypt(plaintext, decrypt=False))


def load_capture() -> dict:
    """Load the capture locally for the owner's HA import."""
    return json.loads(_crypt(VAULT.read_bytes(), decrypt=True))
