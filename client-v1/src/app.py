#!/usr/bin/env python3
"""WavePie — 蓝牙体感控制器（桌面应用版）

启动后缩到系统托盘中，常驻后台。
  F12 或 L2 → 弹出径向菜单
  托盘右键  → 设置 / 退出

用法:
    python -m src.app                  # 开发调试
    ./dist/WavePie.exe                 # 打包后
"""

import sys
import os
import asyncio
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config
from src.mapper.mapper import ActionMapper
from src.gesture.engine import GestureEngine
from src.executor.actions import ActionExecutor
from src.ui.overlay import OverlayUI
from src.tray import TrayApp
from src.config_editor import ConfigEditor


def _find_config() -> str:
    """从 exe 同目录或源码目录找 config.yaml。"""
    # PyInstaller 打包后 _MEIPASS 是临时目录，config 应该在 exe 旁边
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "config.yaml")
    if os.path.exists(path):
        return path
    # 回退到源码目录
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
            on_execute=self._on_execute_sync,
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
        print("  ⌨️  F12/L2 松开   → 执行选中项")
        print("  ❌  Esc           → 取消 / 退出")
        print("  🔄  滚轮          → 音量控制")
        print("  🔽  托盘图标      → 设置 / 退出")
        print("=" * 50)

    # ── 回调 ──

    def _on_execute_sync(self, action_type: str, payload: str):
        try:
            result = asyncio.run(self.executor.execute(action_type, payload))
            status = "✅" if result["ok"] else "❌"
            print(f"[Exec] {status}: {result['detail']}")
        except Exception as e:
            print(f"[Exec] ❌ 异常: {e}")

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
        """从托盘线程安全地打开设置窗口（调度到主线程）。"""
        self.ui.root.after(0, self._open_settings_impl)

    def _open_settings_impl(self):
        """在主线程上创建配置编辑器（Toplevel 而非 Tk）。"""
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
        """配置编辑器保存时直接更新内存中的配置，无需等关闭。"""
        self.config = fresh_config
        self.mapper = ActionMapper(self.config.buttons, self.config.scroll)
        self.gesture = GestureEngine(self.config.gesture)
        self._button_map = {b.button_id: b for b in self.config.buttons}
        print("[App] 🔄 配置已热更新（内存）")

    def _on_settings_closed(self):
        """配置编辑器关闭后从文件重载（兜底）。"""
        self._config_editor = None
        self._reload_config()

    def _reload_config(self):
        """编辑保存后重新加载配置。"""
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

    # ── 启动输入监听 ──

    def _start_keyboard(self):
        """全局 F12 / Esc 监听。"""
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

    def _on_gamepad_action(self, trigger: str):
        """手柄直接动作：根据 trigger 查找命令并执行。"""
        br = self.mapper.route_trigger(trigger)
        if br and br.route == "direct":
            try:
                import asyncio
                result = asyncio.run(
                    self.executor.execute(br.action_type, br.action_payload))
                status = "✅" if result["ok"] else "❌"
                print(f"[🎮 {trigger}] {status}: {result['detail']}")
            except Exception as e:
                print(f"[🎮 {trigger}] ❌ {e}")

    def _start_gamepad(self):
        """尝试启动手柄（若无手柄则静默跳过）。"""
        try:
            from src.input.gamepad import GamepadProvider
            gp = GamepadProvider(self.ui, on_action=self._on_gamepad_action)
            if gp.connect():
                self._gamepad = gp
                gp._poll_loop = gp._poll_loop  # keep reference
                import threading
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
        # 先启动键盘
        self._start_keyboard()

        # 尝试启动手柄（非阻塞）
        self._start_gamepad()

        # 后台启动托盘
        self.tray.start_background()

        # 鼠标滚轮（独立监听）
        self._start_scroll_listener()

        # 启动 UI 主循环（阻塞）
        self.ui.run()

    def _start_scroll_listener(self):
        """全局滚轮监听。"""
        from pynput import mouse

        def on_scroll(x, y, dx, dy):
            route = self.mapper.route_scroll(dy)
            if route:
                try:
                    result = asyncio.run(
                        self.executor.execute(route[0], route[1])
                    )
                    status = "✅" if result["ok"] else "❌"
                    print(f"[Scroll] dy={dy} {status}: {result['detail']}")
                except Exception as e:
                    print(f"[Scroll] ❌ {e}")

        ms = mouse.Listener(on_scroll=on_scroll)
        ms.daemon = True
        ms.start()


def main():
    app = WavePieApp()
    app.start()


if __name__ == "__main__":
    main()
