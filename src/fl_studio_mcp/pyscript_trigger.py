"""Trigger FL's "Run last script again" (Ctrl+Alt+Y) from the daemon.

A background process can't normally steal focus on Windows (foreground-lock),
so we use the AttachThreadInput + synthetic-Alt trick to force FL's window to
the foreground, then send the hotkey. FL re-reads the .pyscript on this hotkey
(confirmed), so paired with pyscript_gen this applies fresh notes with no
manual click.

Caveat: the Piano Roll must be FL's active panel for the shortcut to fire
(it's a piano-roll command). Bringing the FL window forward normally keeps the
last-active panel active.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

_FL_WINDOW_CLASS = "TFruityLoopsMainForm"   # FL Studio main window (Delphi VCL)

_u = ctypes.windll.user32
_k = ctypes.windll.kernel32

_u.FindWindowW.restype = wintypes.HWND
_u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_u.GetForegroundWindow.restype = wintypes.HWND
_u.GetWindowThreadProcessId.restype = wintypes.DWORD
_u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_u.SetForegroundWindow.argtypes = [wintypes.HWND]
_u.SetForegroundWindow.restype = wintypes.BOOL
_u.BringWindowToTop.argtypes = [wintypes.HWND]
_u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
_u.IsIconic.argtypes = [wintypes.HWND]

_SW_RESTORE = 9
_VK_MENU = 0x12          # Alt
_KEYEVENTF_KEYUP = 0x02


def find_fl_hwnd():
    return _u.FindWindowW(_FL_WINDOW_CLASS, None)


def force_focus(hwnd):
    """Force a window to the foreground, defeating Windows foreground-lock."""
    if not hwnd:
        return False
    if _u.IsIconic(hwnd):
        _u.ShowWindow(hwnd, _SW_RESTORE)
    fg = _u.GetForegroundWindow()
    cur_tid = _k.GetCurrentThreadId()
    fg_tid = _u.GetWindowThreadProcessId(fg, None)
    tgt_tid = _u.GetWindowThreadProcessId(hwnd, None)
    _u.AttachThreadInput(cur_tid, fg_tid, True)
    _u.AttachThreadInput(cur_tid, tgt_tid, True)
    # A synthetic Alt tap lets SetForegroundWindow succeed under foreground-lock.
    _u.keybd_event(_VK_MENU, 0, 0, 0)
    _u.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
    _u.BringWindowToTop(hwnd)
    _u.SetForegroundWindow(hwnd)
    _u.AttachThreadInput(cur_tid, fg_tid, False)
    _u.AttachThreadInput(cur_tid, tgt_tid, False)
    return _u.GetForegroundWindow() == hwnd


def trigger_run_last_script(settle=0.35):
    """Focus FL and send Ctrl+Alt+Y. Returns what it did."""
    import pyautogui
    pyautogui.FAILSAFE = False
    hwnd = find_fl_hwnd()
    focused = force_focus(hwnd) if hwnd else False
    time.sleep(settle)
    pyautogui.hotkey("ctrl", "alt", "y")
    return {"fl_found": bool(hwnd), "focused": bool(focused)}
