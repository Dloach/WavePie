#!/usr/bin/env python3
"""蓝牙体感控制器 v1 — PS5 手柄模拟入口。

用 PS5 手柄左摇杆控制径向菜单选择：
  Cross 键按住 → 弹出菜单
  左摇杆推方向 → 选中对应的扇区
  Cross 键松开 → 执行选中项
  Esc 键       → 取消 / 退出

启动方式:
    cd v1; python -m src.main_gamepad
"""

import sys
import os
import asyncio
from pynput import keyboard

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config
from src.mapper.mapper import ActionMapper
from src.gesture.engine import GestureEngine
from src.executor.actions import ActionExecutor
from src.ui.overlay import OverlayUI
from src.input.gamepad import GamepadProvider


class AppController:
    """全局控制器（手柄版）。"""

    def __init__(self, config_path: str = None):
        self.config = load_config(config_path)
        cfg = self.config

        self.mapper = ActionMapper(cfg.buttons, cfg.scroll)
        self.gesture = GestureEngine(cfg.gesture)
        self.executor = ActionExecutor(cfg)
        self._button_map = {b.button_id: b for b in cfg.buttons}

        # 创建 UI
        self.ui = OverlayUI(
            config=self.config,
            on_execute=self._on_execute_sync,
        )
        self.ui.set_activate_callback(self._on_trigger_activate)
        self.ui.set_gamepad_mode(True)   # 隐藏鼠标指针连线

        # 启动手柄
        self.gamepad = GamepadProvider(self.ui)

        # F12 备用 + Esc 退出
        self._start_key_listeners()

        self._print_banner()

    def _print_banner(self):
        print("=" * 50)
        print("  蓝牙体感控制器 v1 — PS5 手柄模式")
        print("=" * 50)
        print("  🎮  L2 扳机按住  → 弹出圆形菜单")
        print("  🕹️  左摇杆方向   → 选择扇区")
        print("  🎮  L2 扳机松开  → 执行选中项")
        print("  ⌨️  Esc         → 取消 / 退出")
        print("  🔄 滚轮         → 音量控制")
        print("  ℹ️  F12 键        → 备用触发")
        print("=" * 50)

    def _on_execute_sync(self, action_type: str, payload: str):
        result = asyncio.run(self.executor.execute(action_type, payload))
        status = "✅" if result["ok"] else "❌"
        print(f"[Exec] {status}: {result['detail']}")

    def _on_trigger_activate(self):
        """激活菜单。"""
        bm = self._button_map.get(0)
        if bm and bm.route == "overlay":
            # 圆心固定在屏幕中心，坐标从 _get_monitor_center 自动计算
            self.ui.activate(0, bm.menu_items, 0, 0)

    def _start_key_listeners(self):
        """键盘：F12 备用触发 + Esc 退出。"""
        def on_press(key):
            try:
                if key == keyboard.Key.f12:
                    self.ui.on_trigger_press()
                elif key == keyboard.Key.esc:
                    self.ui.on_global_esc()
            except Exception:
                pass
        def on_release(key):
            try:
                if key == keyboard.Key.f12:
                    self.ui.on_trigger_release()
            except Exception:
                pass
        kb = keyboard.Listener(on_press=on_press, on_release=on_release)
        kb.daemon = True
        kb.start()

    def start(self):
        self.gamepad.start()
        self.ui.run()


def main():
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config.yaml",
    )
    app = AppController(config_path)
    app.start()


if __name__ == "__main__":
    main()
