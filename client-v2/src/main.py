#!/usr/bin/env python3
"""WavePie V2 — BLE 扇区接收 + 径向菜单显示。

ESP32 端完成姿态→扇区计算，PC 端只负责：
  1. BLE 接收扇区索引 (0xAA) → 高亮菜单
  2. BLE 接收确认包 (0xBB) → 执行命令
"""

import sys
import os
import asyncio
import subprocess
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config
from src.executor.actions import ActionExecutor
from src.ui.overlay import OverlayUI
from src.tray import TrayApp


class WavePieV2:
    def __init__(self, config_path: str = None):
        self._config_path = config_path or self._find_config()
        self.config = load_config(self._config_path)
        self.executor = ActionExecutor()

        self.ui = OverlayUI(config=self.config, on_execute=self._do_action)
        self.tray = TrayApp(on_settings=self._open_settings, on_exit=self._exit_app)
        self._ble = None
        self._ble_thread = None
        self._menu_items_cache = []
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
        print("  WavePie V2")
        print("=" * 50)
        print("  🎮  ESP32 → 扇区索引 → 菜单高亮")
        print("  🔽  托盘图标 → 设置 / 退出")
        print("=" * 50)

    def _build_menu_items(self):
        raw = self.config.menu_items
        class Item:
            def __init__(self, d):
                self.label = d.get("label", "")
                self.action_type = d.get("action_type", "log")
                self.action_payload = d.get("action_payload", "")
        return [Item(d) for d in raw]

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

        def on_aim(roll_byte: int, pitch_byte: int):
            # 第一个 0xAA 打开菜单
            if self.ui.state != "menu_open":
                items = self._build_menu_items()
                self._menu_items_cache = items
                self.ui.root.after(0, self.ui.activate, items)
            # 更新准星位置和扇区
            # 芯片平放，文字顺时针90°，小圆点在左前：
            #   X→右手方向  Y→正前方  Z→天花板
            #   gz(水平旋转)→rx, gy(前后俯仰)→ry
            # 取反：实际安装方向与参考方向差180°
            # 芯片平放，文字顺时针90°，小圆点在左前：
            #   水平(gz) → rx, 垂直(gy) → ry
            rx = -roll_byte / 127.0
            ry = -pitch_byte / 127.0
            self.ui.root.after(0, self.ui.set_sight, rx, ry)

        def on_confirm(idx: int):
            self.ui.root.after(0, self._on_confirm, idx)

        ble.on_aim = on_aim

        # ble.on_sector = on_sector  # removed, using on_aim instead
        ble.on_confirm = on_confirm

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(ble.start())
                loop.run_forever()
            except Exception as e:
                print(f"[BLE] ❌ {e}")

        self._ble_thread = threading.Thread(target=run, daemon=True)
        self._ble_thread.start()

    def _on_confirm(self, idx: int):
        """用户确认（松开扳机）→ 执行当前高亮命令。"""
        if self.ui.state == "menu_open":
            items = self._build_menu_items()
            sel = self.ui.selected_idx
            if sel >= 0 and sel < len(items):
                item = items[sel]
                print(f"[Exec] 🎯 确认扇区{sel}: {item.label}")
                self.ui.deactivate()
                self._do_action(item.action_type, item.action_payload)
            else:
                self.ui.deactivate()
        else:
            items = self._build_menu_items()
            self._menu_items_cache = items
            self.ui.root.after(0, self.ui.activate, items)

    # ── 设置 / 退出 ──

    def _open_settings(self):
        self.ui.root.after(0, self._open_settings_impl)

    def _open_settings_impl(self):
        from src.config_editor import ConfigEditor
        ConfigEditor(
            self._config_path,
            master=self.ui.root,
            on_close=lambda: None,
            on_save=self._on_config_saved,
        )

    def _on_config_saved(self, _data):
        self.config = load_config(self._config_path)
        self._menu_items_cache = self._build_menu_items()
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

    def _restart(self):
        """重启应用。"""
        print("[App] 🔄 重启中...")
        if self._ble:
            self._ble._running = False
        self.tray.stop()
        self.ui.root.destroy()
        subprocess.Popen([sys.executable, "-m", "src.main"])
        os._exit(0)

    def start(self):
        self._start_ble()
        self.tray.start_background()
        # Ctrl+R 重启
        self.ui.root.bind("<Control-r>", lambda e: self._restart())
        self.ui.root.mainloop()


def main():
    app = WavePieV2()
    app.start()


if __name__ == "__main__":
    main()
