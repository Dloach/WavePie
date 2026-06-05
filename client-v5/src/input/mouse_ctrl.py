"""MouseCtrl — 体感→鼠标控制（速率模式）。"""
import ctypes
import math
import time

user32 = ctypes.windll.user32


class MouseCtrl:
    def __init__(self, sensitivity=3.0, dead_zone=2.0):
        self._sens = sensitivity
        self._dz = dead_zone
        self._last_x = 0.0
        self._last_y = 0.0
        self._active = False

    def activate(self):
        """激活鼠标模式：记录当前鼠标位置。"""
        self._last_x = ctypes.c_int()
        self._last_y = ctypes.c_int()
        user32.GetCursorPos(ctypes.byref(self._last_x), ctypes.byref(self._last_y))
        self._active = True

    def deactivate(self):
        self._active = False

    @property
    def is_active(self):
        return self._active

    def on_motion(self, roll_byte: int, pitch_byte: int):
        """BLE 瞄准数据 → 鼠标移动。"""
        if not self._active:
            return
        # 归一化到 -1..1
        rx = roll_byte / 127.0
        ry = pitch_byte / 127.0
        # 死区
        if abs(rx) < self._dz / 30.0:
            rx = 0
        if abs(ry) < self._dz / 30.0:
            ry = 0
        # 像素位移
        dx = int(rx * self._sens)
        dy = int(ry * self._sens)
        if dx == 0 and dy == 0:
            return
        # 获取当前鼠标位置并增量移动
        x = ctypes.c_int()
        y = ctypes.c_int()
        user32.GetCursorPos(ctypes.byref(x), ctypes.byref(y))
        user32.SetCursorPos(x.value + dx, y.value + dy)

    def click(self, button: str = "left"):
        """发送鼠标点击。"""
        if button == "left":
            user32.mouse_event(2, 0, 0, 0, 0)  # down
            time.sleep(0.02)
            user32.mouse_event(4, 0, 0, 0, 0)  # up
        elif button == "right":
            user32.mouse_event(8, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(16, 0, 0, 0, 0)
