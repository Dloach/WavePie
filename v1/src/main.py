#!/usr/bin/env python3
"""蓝牙体感控制器 v1 — 软件模拟原型主入口。

交互方式:
   按住 F12     → 弹出圆形菜单
   移动鼠标     → 连线选择扇区
   松开 F12     → 执行选中项
   Esc         → 取消 / 退出
   滚轮         → 音量控制
"""

import sys
import os
import asyncio
from pynput import keyboard, mouse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config
from src.mapper.mapper import ActionMapper
from src.gesture.engine import GestureEngine
from src.executor.actions import ActionExecutor
from src.ui.overlay import OverlayUI


class AppController:
    """全局控制器。"""

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

        self._start_hotkeys()
        self._print_banner()

    def _print_banner(self):
        print("=" * 50)
        print("  蓝牙体感控制器 v1 — 软件模拟原型")
        print("=" * 50)
        print("  ⌨️  按住 F12   → 弹出圆形菜单")
        print("  🖱️  移动鼠标    → 连线选择扇区")
        print("  ⌨️  松开 F12   → 执行选中项")
        print("  ❌  Esc       → 取消 / 退出")
        print("  🔄  滚轮       → 音量控制")
        print("=" * 50)

    def _on_execute_sync(self, action_type: str, payload: str):
        result = asyncio.run(self.executor.execute(action_type, payload))
        status = "✅" if result["ok"] else "❌"
        print(f"[Exec] {status}: {result['detail']}")

    def _on_trigger_activate(self):
        """激活菜单（F12 按下时调用）。"""
        bm = self._button_map.get(0)
        if bm and bm.route == "overlay":
            try:
                x, y = mouse.Controller().position
            except Exception:
                x, y = (0, 0)
            self.ui.activate(0, bm.menu_items, x, y)

    # ── 全局监听 ──

    def _start_hotkeys(self):
        """启动 pynput 全局监听。"""

        # ── 键盘：F12 按下/松开 + Esc ──
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

        # ── 鼠标：滚轮 ──
        def on_scroll(x, y, dx, dy):
            route = self.mapper.route_scroll(dy)
            if route:
                result = asyncio.run(
                    self.executor.execute(route[0], route[1])
                )
                status = "✅" if result["ok"] else "❌"
                print(f"[Scroll] dy={dy} {status}: {result['detail']}")

        ms = mouse.Listener(on_scroll=on_scroll)
        ms.daemon = True
        ms.start()

    # ── 启动 ──

    def start(self):
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
