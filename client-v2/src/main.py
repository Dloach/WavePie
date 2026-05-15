#!/usr/bin/env python3
"""WavePie V2 — BLE 体感控制器（桌面客户端）

输入：仅 ESP32 BLE
交互：激光准星（速率控制）
菜单：径向 12 项
"""

import sys
import os
import asyncio
import threading
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config
from src.aim.engine import AimEngine
from src.executor.actions import ActionExecutor
from src.ui.overlay import OverlayUI
from src.tray import TrayApp


class WavePieV2:
    def __init__(self, config_path: str = None):
        self._config_path = config_path or self._find_config()
        self.config = load_config(self._config_path)
        self.executor = ActionExecutor()
        self.aim = AimEngine(self.config)

        # ── UI ──
        self.ui = OverlayUI(
            config=self.config,
            on_execute=self._do_action,
        )

        # ── 托盘 ──
        self.tray = TrayApp(
            on_settings=self._open_settings,
            on_exit=self._exit_app,
        )

        # ── BLE ──
        self._ble = None
        self._ble_thread = None

        self._print_banner()

    @staticmethod
    def _find_config() -> str:
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "config.yaml")
        if os.path.exists(path):
            return path
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml",
        )

    def _print_banner(self):
        print("=" * 50)
        print("  WavePie V2 — BLE 体感控制器")
        print("=" * 50)
        print("  🎮  ESP32 手柄     唯一输入")
        print("  🎯  激光准星        自由瞄准")
        print("  🔽  托盘图标        设置 / 退出")
        print("=" * 50)

    # ── 动作执行 ──

    def _do_action(self, action_type: str, payload: str):
        try:
            result = asyncio.run(self.executor.execute(action_type, payload))
            status = "✅" if result["ok"] else "❌"
            print(f"[Exec] {status}: {result['detail']}")
        except Exception as e:
            print(f"[Exec] ❌ {e}")

    # ── BLE ──

    def _start_ble(self):
        from src.input.ble import BLEInputProvider

        ble = BLEInputProvider(device_name=self.config.ble.device_name)
        self._ble = ble

        # 按键回调
        def on_button(btn_id: int, pressed: bool):
            if btn_id == 0:
                if pressed:
                    self.ui.root.after(0, self._on_trigger, self._ble)
                else:
                    self.ui.root.after(0, self._on_release)

        ble.set_on_button(on_button)

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(ble.start())
                # 主线程轮询 IMU
                self.ui.root.after(33, self._poll_aim, ble)
                loop.run_forever()
            except Exception as e:
                print(f"[BLE] ❌ {e}")

        self._ble_thread = threading.Thread(target=run, daemon=True)
        self._ble_thread.start()

    def _poll_aim(self, ble):
        """主线程轮询 BLE latest_* → AimEngine → UI。"""
        if hasattr(self, '_ble') and self._ble and self._ble.is_connected:
            self.aim.on_motion(ble.latest_roll, ble.latest_pitch)
            if self.aim.is_active:
                cx, cy = self.aim.get_cursor()
                self.ui.set_sight(cx, cy)
        self.ui.root.after(33, self._poll_aim, ble)

    # ── 扳机 ──

    def _on_trigger(self, ble: object):
        """扳机按下：校准 + 打开菜单。"""
        self.aim.set_ring(self.ui._center_r, self.ui._visible_r)
        self.aim.on_trigger(ble.latest_roll, ble.latest_pitch)

        items = self._build_menu_items()
        self.ui.activate(items)

    def _on_release(self):
        """扳机松开：执行选中的命令。"""
        if self.ui.state != "menu_open":
            return
        idx = self.aim.on_release()
        if idx >= 0 and idx < len(self.ui._menu_items):
            item = self.ui._menu_items[idx]
            print(f"[Exec] 🎯 选中: {item.label}")
            self.ui.deactivate()
            self._do_action(item.action_type, item.action_payload)
        else:
            self.ui.deactivate()

    def _build_menu_items(self):
        """从配置构建菜单项对象列表。"""
        raw_items = self.config.menu_items
        class MenuItem:
            def __init__(self, d):
                self.label = d.get("label", "")
                self.action_type = d.get("action_type", "log")
                self.action_payload = d.get("action_payload", "")
        return [MenuItem(d) for d in raw_items]

    # ── 设置 / 退出 ──

    def _open_settings(self):
        self.ui.root.after(0, self._open_settings_impl)

    def _open_settings_impl(self):
        from src.config_editor import ConfigEditor
        editor = ConfigEditor(
            self._config_path,
            master=self.ui.root,
            on_close=lambda: None,
            on_save=self._on_config_saved,
        )

    def _on_config_saved(self, fresh_config):
        self.config = fresh_config
        print("[App] 🔄 配置已更新")

    def _exit_app(self):
        if self._ble:
            self._ble._running = False
        self.tray.stop()
        try:
            self.ui.root.quit()
        except Exception:
            pass
        os._exit(0)

    # ── 启动 ──

    def start(self):
        self._start_ble()
        self.tray.start_background()
        self.ui.root.mainloop()


def main():
    app = WavePieV2()
    app.start()


if __name__ == "__main__":
    main()
