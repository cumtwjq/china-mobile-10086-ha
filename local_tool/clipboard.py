"""Copy Unicode text to the current Windows clipboard."""

from __future__ import annotations

import ctypes
import time


def copy_to_clipboard(value: str) -> None:
    """Place Unicode text on the current interactive Windows clipboard."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalAlloc.argtypes = (ctypes.c_uint, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = (ctypes.c_void_p,)
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
    kernel32.GlobalFree.argtypes = (ctypes.c_void_p,)
    user32.OpenClipboard.argtypes = (ctypes.c_void_p,)
    user32.SetClipboardData.argtypes = (ctypes.c_uint, ctypes.c_void_p)
    user32.SetClipboardData.restype = ctypes.c_void_p
    raw = value.encode("utf-16-le") + b"\x00\x00"
    handle = kernel32.GlobalAlloc(0x0002, len(raw))  # GMEM_MOVEABLE
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    address = kernel32.GlobalLock(handle)
    if not address:
        kernel32.GlobalFree(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    ctypes.memmove(address, raw, len(raw))
    kernel32.GlobalUnlock(handle)
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.1)
    else:
        kernel32.GlobalFree(handle)
        raise RuntimeError("Windows clipboard is busy")
    try:
        if not user32.EmptyClipboard() or not user32.SetClipboardData(13, handle):
            kernel32.GlobalFree(handle)
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        user32.CloseClipboard()

