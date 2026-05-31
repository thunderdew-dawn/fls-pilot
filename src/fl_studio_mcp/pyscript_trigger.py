"""Trigger FL's "Run last script again" hotkey from the daemon.

Platform-aware:
  * Windows: AttachThreadInput + SetForegroundWindow (ctypes.windll) + Ctrl+Alt+Y
  * macOS:   osascript "activate" + Cmd+Opt+Y via pyautogui

The Piano Roll must be FL's active panel for the shortcut to fire (it's a
piano-roll command). Bringing the FL window forward normally keeps the
last-active panel active.
"""

from __future__ import annotations

import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# macOS implementation
# ---------------------------------------------------------------------------

def _find_fl_macos() -> bool:
    """Check whether FL Studio is running (macOS)."""
    try:
        out = subprocess.check_output(
            ["pgrep", "-x", "FL Studio"],
            stderr=subprocess.DEVNULL,
        )
        return bool(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _force_focus_macos() -> bool:
    """Bring FL Studio to the foreground via AppleScript."""
    try:
        subprocess.check_call(
            ["osascript", "-e", 'tell application "FL Studio" to activate'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _trigger_macos(settle: float = 0.35) -> dict:
    """Focus FL Studio and send Cmd+Opt+Y on macOS."""
    import pyautogui
    pyautogui.FAILSAFE = False
    found = _find_fl_macos()
    focused = _force_focus_macos() if found else False
    time.sleep(settle)
    pyautogui.hotkey("command", "option", "y")
    return {"fl_found": found, "focused": focused}


# ---------------------------------------------------------------------------
# Windows implementation (original logic, deferred import)
# ---------------------------------------------------------------------------

def _trigger_windows(settle: float = 0.35) -> dict:
    """Focus FL Studio via Win32 API and send Ctrl+Alt+Y."""
    import ctypes
    from ctypes import wintypes

    _FL_WINDOW_CLASS = "TFruityLoopsMainForm"

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
    _VK_MENU = 0x12
    _KEYEVENTF_KEYUP = 0x02

    hwnd = _u.FindWindowW(_FL_WINDOW_CLASS, None)
    focused = False

    if hwnd:
        if _u.IsIconic(hwnd):
            _u.ShowWindow(hwnd, _SW_RESTORE)
        fg = _u.GetForegroundWindow()
        cur_tid = _k.GetCurrentThreadId()
        fg_tid = _u.GetWindowThreadProcessId(fg, None)
        tgt_tid = _u.GetWindowThreadProcessId(hwnd, None)
        _u.AttachThreadInput(cur_tid, fg_tid, True)
        _u.AttachThreadInput(cur_tid, tgt_tid, True)
        _u.keybd_event(_VK_MENU, 0, 0, 0)
        _u.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
        _u.BringWindowToTop(hwnd)
        _u.SetForegroundWindow(hwnd)
        _u.AttachThreadInput(cur_tid, fg_tid, False)
        _u.AttachThreadInput(cur_tid, tgt_tid, False)
        focused = _u.GetForegroundWindow() == hwnd

    import pyautogui
    pyautogui.FAILSAFE = False
    time.sleep(settle)
    pyautogui.hotkey("ctrl", "alt", "y")
    return {"fl_found": bool(hwnd), "focused": bool(focused)}


# ---------------------------------------------------------------------------
# Public API -- dispatch by platform
# ---------------------------------------------------------------------------

def trigger_run_last_script(settle: float = 0.35) -> dict:
    """Focus FL Studio and send the 'run last script' hotkey.

    Returns ``{"fl_found": bool, "focused": bool}``.
    """
    if sys.platform == "darwin":
        return _trigger_macos(settle)
    else:
        return _trigger_windows(settle)
