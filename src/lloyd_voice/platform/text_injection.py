import sys
import subprocess
import logging

logger = logging.getLogger(__name__)


def inject_text(text: str) -> bool:
    system = sys.platform
    if system == "win32":
        return _inject_windows(text)
    elif system == "darwin":
        return _inject_macos(text)
    elif system == "linux":
        return _inject_linux(text)
    else:
        logger.warning(f"Unsupported platform: {system}")
        return False


def _inject_windows(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        import ctypes
        USER32 = ctypes.windll.user32
        USER32.keybd_event(0x11, 0, 0, 0)
        USER32.keybd_event(0x56, 0, 0, 0)
        USER32.keybd_event(0x56, 0, 2, 0)
        USER32.keybd_event(0x11, 0, 2, 0)
        return True
    except Exception as e:
        logger.error(f"Windows text injection failed: {e}")
        return False


def _inject_macos(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        subprocess.run(
            ["osascript", "-e", f'tell application "System Events" to keystroke "v" using command down'],
            capture_output=True, text=True, timeout=5,
        )
        return True
    except Exception as e:
        logger.error(f"macOS text injection failed: {e}")
        return False


def _inject_linux(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        subprocess.run(["xdotool", "key", "ctrl+v"], capture_output=True, text=True, timeout=5)
        return True
    except FileNotFoundError:
        try:
            subprocess.run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"], capture_output=True, text=True, timeout=5)
            return True
        except FileNotFoundError:
            try:
                subprocess.run(["ydotool", "key", "ctrl+v"], capture_output=True, text=True, timeout=5)
                return True
            except FileNotFoundError:
                logger.error("No Linux text injection tool found (try xdotool, wtype, or ydotool)")
                return False
    except Exception as e:
        logger.error(f"Linux text injection failed: {e}")
        return False
