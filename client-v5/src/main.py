#!/usr/bin/env python3
"""WavePie V5 — 双击 GPIO4 切换鼠标模式。"""

import sys, os, asyncio, subprocess, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config
from src.executor.actions import ActionExecutor
from src.ui.overlay import OverlayUI
from src.tray import TrayApp
from src.input.mouse_ctrl import MouseCtrl


class WavePieV5:
    def __init__(self, config_path: str = None):
        self._config_path = config_path or self._find_config()
        self.config = load_config(self._config_path)
        self.executor = ActionExecutor()

        # ── 模式 ──
        self._mouse_mode = False          # True=鼠标模式, False=菜单模式
        self._last_confirm_t = 0.0        # 上次 0xBB 时间
        self._confirm_count = 0           # 连续无选择释放次数

        self.mouse = MouseCtrl(sensitivity=5.0)
        self.ui = OverlayUI(config=self.config, on_execute=self._do_action)
        self.tray = TrayApp(
            on_settings=self._open_settings,
            on_restart=self._restart,
            on_exit=self._exit_app,
        )
        self._ble = None
        self._smooth_rx = 0.0
        self._smooth_ry = 0.0
        print("=" * 40 + "\n  WavePie V5\n" + "=" * 40)

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

        def _poll_sight():
            if self.ui.state == "menu_open":
                rx = -ble.latest_roll / 127.0 * 2.25
                ry = -ble.latest_pitch / 127.0 * 2.25
                smooth = 0.65
                self._smooth_rx = self._smooth_rx * smooth + rx * (1 - smooth)
                self._smooth_ry = self._smooth_ry * smooth + ry * (1 - smooth)
                self.ui.set_sight(self._smooth_rx, self._smooth_ry)
            elif self._mouse_mode:
                self.mouse.on_motion(ble.latest_roll, ble.latest_pitch)
            self.ui.root.after(16, _poll_sight)

        def on_aim(roll_byte: int, pitch_byte: int):
            if self._mouse_mode:
                return
            if self.ui.state != "menu_open":
                items = self._build_menu_items()
                self.ui.root.after(0, self.ui.activate, len(items), [it.label for it in items])

        def on_confirm(idx: int):
            now = time.monotonic()
            # 双击检测：800ms 内两次释放且无选中
            is_double = (now - self._last_confirm_t < 0.8)
            self._last_confirm_t = now

            if self.ui.state == "idle" and self._mouse_mode:
                # 鼠标模式中按 GPIO4 → 切回菜单模式
                self._toggle_mode()
                return

            if self.ui.state == "menu_open":
                items = self._build_menu_items()
                idx2 = self.ui.selected_idx
                if 0 <= idx2 < len(items):
                    # 正常执行命令
                    self._confirm_count = 0
                    item = items[idx2]
                    print(f"[Exec] 🎯 确认扇区{idx2}: {item.label}")
                    self._do_action(item.action_type, item.action_payload)
                    self.ui.confirm_and_exit()
                elif is_double:
                    self.ui.deactivate()
                    self._toggle_mode()
                else:
                    self.ui.deactivate()
            elif self._mouse_mode:
                # 鼠标模式中单击 = 左键
                self.mouse.click("left")

        ble.on_aim = on_aim
        ble.on_confirm = on_confirm
        self.ui.root.after(8, _poll_sight)

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(ble.start())
                loop.run_forever()
            except Exception as e:
                print(f"[BLE] ❌ {e}")
        threading.Thread(target=run, daemon=True).start()

    def _toggle_mode(self):
        self._mouse_mode = not self._mouse_mode
        if self._mouse_mode:
            self.mouse.activate()
            self.ui.root.title("WavePie V5 — 🖱️ 鼠标模式")
            print("[Mode] 🖱️ 鼠标模式")
        else:
            self.mouse.deactivate()
            self.ui.root.title("WavePie V5")
            print("[Mode] 📋 菜单模式")

    def _on_confirm(self):
        pass  # 不再使用

    def _build_menu_items(self):
        class Item:
            def __init__(self, d):
                self.label = d.get("label","")
                self.action_type = d.get("action_type","log")
                self.action_payload = d.get("action_payload","")
        return [Item(d) for d in self.config.menu_items]

    # ── 设置 / 退出 / 重启 ──
    def _open_settings(self):
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
    WavePieV5().start()

if __name__ == "__main__":
    main()
