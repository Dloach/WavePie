#!/usr/bin/env python3
"""WavePie — 蓝牙体感控制器（桌面应用版）

启动后缩到系统托盘中，常驻后台。
  F12 或 L2 → 弹出径向菜单
  托盘点/双击 → 设置
"""

import sys
import os
import asyncio
import tkinter as tk
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config
from src.mapper.mapper import ActionMapper, RouteAction
from src.gesture.engine import GestureEngine
from src.input.protocol import EventType
from src.executor.actions import ActionExecutor
from src.ui.overlay import OverlayUI
from src.tray import TrayApp
from src.config_editor import ConfigEditor


def _find_config() -> str:
    """从 exe 同目录或源码目录找 config.yaml。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "config.yaml")
    if os.path.exists(path):
        return path
    src_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config.yaml",
    )
    return src_path


class WavePieApp:
    """全局应用控制器。"""

    def __init__(self, config_path: str = None):
        self._config_path = config_path or _find_config()
        self.config = load_config(self._config_path)
        cfg = self.config

        self.mapper = ActionMapper(cfg.buttons, cfg.scroll)
        self.gesture = GestureEngine(cfg.gesture)
        self.executor = ActionExecutor(cfg)
        self._button_map = {b.button_id: b for b in cfg.buttons}

        # ── UI ──
        self.ui = OverlayUI(
            config=self.config,
            on_execute=self._do_action,
        )
        self.ui.set_activate_callback(self._on_trigger_activate)

        # ── 托盘 ──
        self._config_editor = None
        self.tray = TrayApp(
            on_settings=self._open_settings,
            on_exit=self._exit_app,
        )

        # ── 输入源 ──
        self._gamepad = None
        self._kb_listener = None

        self._print_banner()

    def _print_banner(self):
        print("=" * 50)
        print("  WavePie — 蓝牙体感控制器")
        print("=" * 50)
        print("  ⌨️  F12 按住      → 弹出圆形菜单")
        print("  🕹️  L2 扳机       → 弹出圆形菜单（有手柄时）")
        print("  🖱️  鼠标移动方向  → 选择扇区")
        print("  🎮  直接动作按键  → 一键触发绑定命令")
        print("  🔽  托盘图标      → 设置 / 退出")
        print("=" * 50)

    # ── 统一执行入口 ──
    # 所有触发源（圆形菜单、手柄按键）都走这里

    def _do_action(self, action_type: str, payload: str):
        """执行一个动作。圆形菜单和手柄直接动作都调用此方法。"""
        try:
            result = asyncio.run(
                self.executor.execute(action_type, payload))
            status = "✅" if result["ok"] else "❌"
            print(f"[Exec] {status}: {result['detail']}")
        except Exception as e:
            print(f"[Exec] ❌ {e}")

    def _do_trigger(self, trigger: str):
        """根据 trigger 查找命令并执行（手柄直接动作入口）。"""
        br = self.mapper.route_trigger(trigger)
        if br and br.route == RouteAction.DIRECT:
            self._do_action(br.action_type, br.action_payload)

    def _on_trigger_activate(self):
        bm = self._button_map.get(0)
        if bm and bm.route == "overlay":
            import pynput.mouse
            try:
                x, y = pynput.mouse.Controller().position
            except Exception:
                x, y = (0, 0)
            self.ui.activate(0, bm.menu_items, x, y)

    # ── 设置窗口 ──

    def _open_settings(self):
        self.ui.root.after(0, self._open_settings_impl)

    def _open_settings_impl(self):
        if self._config_editor is not None:
            try:
                self._config_editor.root.lift()
                return
            except Exception:
                self._config_editor = None
        editor = ConfigEditor(
            self._config_path,
            master=self.ui.root,
            on_close=self._on_settings_closed,
            on_save=self._on_config_saved,
        )
        self._config_editor = editor

    def _on_config_saved(self, fresh_config):
        self.config = fresh_config
        self.mapper = ActionMapper(self.config.buttons, self.config.scroll)
        self.gesture = GestureEngine(self.config.gesture)
        self._button_map = {b.button_id: b for b in self.config.buttons}
        print("[App] 🔄 配置已热更新（内存）")

    def _on_settings_closed(self):
        self._config_editor = None
        self._reload_config()

    def _reload_config(self):
        try:
            self.config = load_config(self._config_path)
            self.mapper = ActionMapper(self.config.buttons, self.config.scroll)
            self.gesture = GestureEngine(self.config.gesture)
            self._button_map = {b.button_id: b for b in self.config.buttons}
            print("[App] 🔄 配置已重载")
        except Exception as e:
            print(f"[App] ❌ 配置重载失败: {e}")

    # ── 退出 ──

    def _exit_app(self):
        print("[App] 👋 退出")
        if self._kb_listener:
            self._kb_listener.stop()
        if self._gamepad:
            self._gamepad.stop()
        self.tray.stop()
        self.ui.root.quit()
        os._exit(0)

    # ── BLE 体感输入 ──

    def _start_ble(self):
        """在后台线程启动 BLE 输入源。"""
        try:
            from src.input.ble import BLEMotionInputProvider
            ble = BLEMotionInputProvider(self.config)

            def run_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._ble_event_loop(ble))
                except Exception as e:
                    print(f"[BLE] ❌ {e}")

            t = threading.Thread(target=run_loop, daemon=True)
            t.start()
            print("[App] 📡 BLE 体感已启动")
        except Exception as e:
            print(f"[App] 📡 BLE 初始化失败: {e}")

    async def _ble_event_loop(self, ble):
        """BLE 事件循环：读事件 → 路由到 UI 或直接动作。"""
        await ble.start()
        async for evt in ble.read_events():
            if evt.type == EventType.MOTION:
                self.ui.root.after(0, self._ble_on_motion, evt)
            elif evt.type == EventType.BUTTON_DOWN:
                if evt.button_id == 0:
                    self.ui.root.after(0, self.ui.on_trigger_press)
                else:
                    self._do_trigger(f"gamepad:{evt.button_id}")
            elif evt.type == EventType.BUTTON_UP:
                if evt.button_id == 0:
                    self.ui.root.after(0, self.ui.on_trigger_release)

    def _ble_on_motion(self, evt):
        """BLE IMU 数据 → 二维角度 → 径向菜单扇区高亮。"""
        if not hasattr(self.ui, '_menu_items'):
            return
        num = len(self.ui._menu_items)
        if num == 0:
            return

        import math
        # roll（左右摆）→ X, pitch（前后倾）→ Y
        dx = evt.roll
        dy = evt.pitch

        # 死区
        dz = self.config.gesture.dead_zone * 30
        if abs(dx) < dz: dx = 0.0
        if abs(dy) < dz: dy = 0.0

        # 如果两个轴都死区，不切换
        if dx == 0.0 and dy == 0.0:
            return

        # 计算方向角（度），12点钟方向=0°，顺时针递增
        angle = math.degrees(math.atan2(dx, -dy)) % 360
        sector = 360.0 / num
        idx = int((angle + sector / 2) / sector) % num
        self.ui.select_sector(idx)

    # ── 输入源 ──

    def _start_keyboard(self):
        from pynput import keyboard

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

        self._kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._kb_listener.daemon = True
        self._kb_listener.start()
        print("[App] ⌨️  F12 监听已启动")

    def _start_gamepad(self):
        try:
            from src.input.gamepad import GamepadProvider
            gp = GamepadProvider(self.ui, on_action=self._do_trigger)
            if gp.connect():
                self._gamepad = gp
                t = threading.Thread(target=gp._poll_loop, daemon=True)
                gp._running = True
                t.start()
                print("[App] 🎮  手柄已连接")
            else:
                print("[App] 🎮  未检测到手柄，仅键盘模式")
        except Exception as e:
            print(f"[App] 🎮  手柄初始化跳过: {e}")

    # ── 启动 ──

    def start(self):
        self._start_keyboard()
        # 根据配置选择输入源
        if self.config.input_provider == "ble":
            self.ui.set_gamepad_mode(True)
            self._start_ble()
        else:
            self._start_gamepad()
        self.tray.start_background()
        self.ui.run()


def main():
    app = WavePieApp()
    app.start()


if __name__ == "__main__":
    main()
