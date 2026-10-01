import time
import ctypes
from ctypes import wintypes

# Win32 Constants
INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004

KEYEVENTF_KEYDOWN    = 0x0000
KEYEVENTF_KEYUP      = 0x0002
KEYEVENTF_SCANCODE   = 0x0008

SCAN_CODES = {
    't': 0x14,
    'e': 0x12,
    'space': 0x39,
    '1': 0x02,
    'f': 0x21,
    'q': 0x10,
}

VK_CODES = {
    't': 0x54,
    'e': 0x45,
    'space': 0x20,
    '1': 0x31,
    'f': 0x46,
    'q': 0x51,
}

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]

class InputManager:
    """
    High-performance Windows input simulator with state tracking.
    Uses official SendInput API with hardware scan codes.
    """
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.is_mouse_down = False
        self.held_keys = set()

    def _send_mouse_flag(self, flag):
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = 0
        inp.union.mi.dy = 0
        inp.union.mi.mouseData = 0
        inp.union.mi.dwFlags = flag
        inp.union.mi.time = 0
        inp.union.mi.dwExtraInfo = None
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        self.user32.mouse_event(flag, 0, 0, 0, 0)

    def mouse_down(self):
        """Transitions mouse to down state (Hold). Only sends event on state transition."""
        if not self.is_mouse_down:
            self._send_mouse_flag(MOUSEEVENTF_LEFTDOWN)
            self.is_mouse_down = True

    def mouse_up(self):
        """Transitions mouse to up state (Release). Only sends event on state transition."""
        if self.is_mouse_down:
            self._send_mouse_flag(MOUSEEVENTF_LEFTUP)
            self.is_mouse_down = False

    def force_mouse_up(self):
        """Unconditionally release mouse left button"""
        self._send_mouse_flag(MOUSEEVENTF_LEFTUP)
        self.is_mouse_down = False

    def click(self, duration=0.03):
        """Performs a single click (Hold -> Brief delay -> Release)"""
        self.mouse_down()
        if duration > 0:
            time.sleep(duration)
        self.mouse_up()

    def key_down(self, key_char):
        k = key_char.lower()
        self.held_keys.add(k)
        scan = SCAN_CODES.get(k, 0)
        vk = VK_CODES.get(k, ord(k.upper()) if len(k) == 1 else 0)

        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.wScan = scan
        inp.union.ki.dwFlags = KEYEVENTF_KEYDOWN | (KEYEVENTF_SCANCODE if scan != 0 else 0)
        inp.union.ki.time = 0
        inp.union.ki.dwExtraInfo = None
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        self.user32.keybd_event(vk, scan, KEYEVENTF_KEYDOWN, 0)

    def key_up(self, key_char):
        k = key_char.lower()
        if k in self.held_keys:
            self.held_keys.remove(k)
        scan = SCAN_CODES.get(k, 0)
        vk = VK_CODES.get(k, ord(k.upper()) if len(k) == 1 else 0)

        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.wScan = scan
        inp.union.ki.dwFlags = KEYEVENTF_KEYUP | (KEYEVENTF_SCANCODE if scan != 0 else 0)
        inp.union.ki.time = 0
        inp.union.ki.dwExtraInfo = None
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        self.user32.keybd_event(vk, scan, KEYEVENTF_KEYUP, 0)

    def hold_key(self, key_char, duration, is_running_check=None, repeat_interval=0.05):
        """
        Holds a key down for specified duration while periodically pulsing
        typematic keydown events every `repeat_interval` seconds.
        Ensures game interaction prompts (like Roblox Hold T to store) complete reliably.
        """
        k = key_char.lower()
        self.key_down(k)
        end_time = time.time() + duration
        last_repeat = time.time()

        while time.time() < end_time:
            if is_running_check and not is_running_check():
                break
            now = time.time()
            if now - last_repeat >= repeat_interval:
                self.key_down(k)
                last_repeat = now
            time.sleep(0.01)

        self.key_up(k)

    def release_all(self):
        """Safety release for any held keys or mouse buttons"""
        self.force_mouse_up()
        for k in list(self.held_keys):
            self.key_up(k)
        self.held_keys.clear()
