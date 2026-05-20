#!/usr/bin/env python3
"""WavePie V3 — V1 双显绘制 + V2 BLE 交互 + 激光准星。"""

import sys, os, asyncio, subprocess, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config
from src.executor.actions import ActionExecutor
from src.ui.overlay import OverlayUI
from src.tray import TrayApp


class WavePieV3:
    def __init__(self, config_path: str = None):
        self._config_path = config_path or self._find_config()
        self.config = load_config(self._config_path)
        self.executor = ActionExecutor()

        self.ui = OverlayUI(config=self.config, on_execute=self._do_action)
        self.tray = TrayApp(
            on_settings=self._open_settings,
            on_restart=self._restart,
            on_exit=self._exit_app,
        )
        self._ble = None
        print("=" * 40 + "\n  WavePie V3\n" + "=" * 40)

    @staticmethod
    def _find_config() -> str:
        if getattr(sys, "frozen", False):
            return os.path.join(os.path.dirname(sys.executable), "config.yaml")
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")

    # ── 动作 ──
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

        # 平滑 + 磁吸状态
        self._smooth_rx = 0.0
        self._smooth_ry = 0.0

        def _poll_sight():
            if self.ui.state == "menu_open":
                rx = -ble.latest_roll / 127.0 * 2.25
                ry = -ble.latest_pitch / 127.0 * 2.25
                # 指数平滑（去抖）
                smooth = 0.65
                self._smooth_rx = self._smooth_rx * smooth + rx * (1 - smooth)
                self._smooth_ry = self._smooth_ry * smooth + ry * (1 - smooth)
                self.ui.set_sight(self._smooth_rx, self._smooth_ry)
            self.ui.root.after(8, _poll_sight)  # ~60fps

        # 启动准星轮询（60fps）
        self.ui.root.after(16, _poll_sight)

        def on_aim(roll_byte: int, pitch_byte: int):
            if self.ui.state != "menu_open":
                items = self._build_menu_items()
                self.ui.root.after(0, self.ui.activate, len(items), [it.label for it in items])

        def on_confirm(idx: int):
            self.ui.root.after(0, self._on_confirm)

        ble.on_aim = on_aim
        ble.on_confirm = on_confirm

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(ble.start())
                loop.run_forever()
            except Exception as e:
                print(f"[BLE] ❌ {e}")
        threading.Thread(target=run, daemon=True).start()

    def _on_confirm(self):
        if self.ui.state == "menu_open":
            items = self._build_menu_items()
            idx = self.ui.selected_idx
            if 0 <= idx < len(items):
                item = items[idx]
                print(f"[Exec] 🎯 确认扇区{idx}: {item.label}")
                self._do_action(item.action_type, item.action_payload)
                self.ui.confirm_and_exit()
            else:
                self.ui.deactivate()  # 无效选择，直接关闭
        else:
            items = self._build_menu_items()
            self.ui.root.after(0, self.ui.activate, len(items), [it.label for it in items])

    def _build_menu_items(self):
        class Item:
            def __init__(self, d):
                self.label = d.get("label","")
                self.action_type = d.get("action_type","log")
                self.action_payload = d.get("action_payload","")
        return [Item(d) for d in self.config.menu_items]

    # ── 设置 / 退出 / 重启 ──
    _last_settings_open = 0.0

    def _open_settings(self):
        import time
        now = time.monotonic()
        if now - self._last_settings_open < 0.5:
            return  # 防抖：500ms 内不重复打开
        self._last_settings_open = now
        self.ui.root.after(0, self._open_settings_impl)
    def _open_settings_impl(self):
        from src.config_editor import ConfigEditor
        ConfigEditor(self._config_path, master=self.ui.root,
                     on_close=lambda: None, on_save=self._on_config_saved)
    def _on_config_saved(self, _data):
        self.config = load_config(self._config_path)
    def _exit_app(self):
        if self._ble: self._ble._running = False
        self.tray.stop()
        try: self.ui.root.quit()
        except: pass
        os._exit(0)
    def _restart(self):
        if self._ble: self._ble._running = False
        self.tray.stop()
        self.ui.root.destroy()
        cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.Popen([sys.executable, "-m", "src.main"], cwd=cwd)
        os._exit(0)

    def start(self):
        self._start_ble()
        self.tray.start_background()
        self.ui.root.mainloop()


def main():
    WavePieV3().start()

if __name__ == "__main__":
    main()
