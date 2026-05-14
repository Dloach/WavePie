"""GamepadProvider — XInput 手柄输入驱动。

左摇杆 → 控制径向菜单选择方向
L2 扳机 → 按住激活菜单 / 松开执行
"""

import math
import threading
import time
from typing import Optional


STICK_DEAD_ZONE = 0.25
L2_THRESHOLD = 0.5       # 扳机值 0(松开) ~ 1(按下)


class GamepadProvider:
    """XInput 手柄输入源。"""

    def __init__(self, overlay, on_action: callable = None):
        """
        on_action: 直接动作回调，接收 (action_type, action_payload)
        """
        self._overlay = overlay
        self._on_action = on_action
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._joystick = None
        self._connected = False
        self._last_sent_idx = -1
        self._l2_was_down = False
        self._prev_buttons: list[bool] = []  # 上一帧的按键状态（边缘检测用）

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """扫描并连接第一个可用的手柄。"""
        import pygame
        pygame.init()
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        if count == 0:
            print("[Gamepad] ❌ 未检测到手柄")
            return False

        # 找第一个手柄
        for i in range(count):
            j = pygame.joystick.Joystick(i)
            j.init()
            name = j.get_name()
            # 跳过蓝牙 DualSense（无法读取信号）
            if 'DualSense' in name or 'Dual Shock' in name:
                print(f"[Gamepad] ⏭️  跳过 [{i}] {name}（PS 手柄）")
                continue
            self._joystick = j
            axes = j.get_numaxes()
            btns = j.get_numbuttons()
            print(f"[Gamepad] ✅ 已连接 [{i}] {name}")
            print(f"[Gamepad]    轴={axes} 按键={btns}")
            self._connected = True
            return True

        print("[Gamepad] ❌ 未找到可用的 XInput 手柄")
        return False

    def start(self):
        if not self._joystick and not self.connect():
            return
        if not self._connected:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        print("[Gamepad] 🔄 轮询已启动")

    def stop(self):
        self._running = False

    def _poll_loop(self):
        import pygame
        j = self._joystick

        while self._running:
            try:
                pygame.event.pump()

                # 左摇杆
                stick_x = j.get_axis(0)
                stick_y = -j.get_axis(1)   # 上推为正

                # L2 扳机
                try:
                    l2_val = j.get_axis(4)
                    if l2_val < 0:
                        l2_val = (l2_val + 1) / 2
                except Exception:
                    l2_val = 0

                # L2 触发检测
                l2_pressed = l2_val > L2_THRESHOLD
                if l2_pressed and not self._l2_was_down:
                    self._l2_was_down = True
                    print("[Gamepad] 🟢 L2 按下 → 激活菜单")
                    self._overlay.root.after(0, self._overlay.on_trigger_press)
                elif not l2_pressed and self._l2_was_down:
                    self._l2_was_down = False
                    print("[Gamepad] 🔴 L2 松开 → 执行")
                    self._overlay.root.after(0, self._overlay.on_trigger_release)

                # 摇杆方向 → 扇区
                mag = math.hypot(stick_x, stick_y)
                if mag < STICK_DEAD_ZONE:
                    self._update_selection(-1)
                else:
                    nx = stick_x / mag
                    ny = stick_y / mag
                    angle = (-math.atan2(ny, nx) + math.pi / 2) % (2 * math.pi)
                    self._update_selection_by_angle(angle)

                # ── 全局按键检测（直接动作触发）──
                num_btns = j.get_numbuttons()
                for k in range(num_btns):
                    pressed = j.get_button(k)
                    prev = (self._prev_buttons[k]
                            if k < len(self._prev_buttons) else False)
                    if pressed and not prev:
                        # 按钮刚被按下
                        trigger = f"gamepad:{k}"
                        if self._on_action:
                            self._overlay.root.after(
                                0, lambda t=trigger: self._on_action(t))
                # 更新上一帧状态
                self._prev_buttons = [j.get_button(k) for k in range(num_btns)]

                time.sleep(0.016)
            except Exception:
                pass  # 关闭时守护线程静默退出

    def _update_selection_by_angle(self, angle_rad: float):
        items = getattr(self._overlay, '_menu_items', [])
        n = len(items)
        if n == 0:
            return
        sector = 2 * math.pi / n
        # 偏移半格对齐 UI（12点=扇区中心）
        idx = int((angle_rad + sector / 2) / sector) % n
        self._update_selection(idx)

    def _update_selection(self, idx: int):
        if idx == self._last_sent_idx:
            return
        self._last_sent_idx = idx
        self._overlay.root.after(0, lambda: self._overlay.select_sector(idx))
