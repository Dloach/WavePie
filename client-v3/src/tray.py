"""WavePie V2 系统托盘图标。"""

import os
import sys
import threading
from PIL import Image, ImageDraw
import pystray


def _gen_icon(size: int):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    margin = size // 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill="#4A90D9", outline="white", width=2,
    )
    # W 字母
    tw = size * 0.4
    draw.text(
        ((size - tw) / 2, size * 0.22),
        "W", fill="white",
        font=None,
    )
    return im


class TrayApp:
    def __init__(self, on_settings=None, on_restart=None, on_exit=None):
        self._on_settings = on_settings
        self._on_restart = on_restart
        self._on_exit = on_exit
        self._icon = None

    def start_background(self):
        icon = pystray.Icon(
            "WavePie",
            _gen_icon(64),
            "WavePie V2",
            menu=pystray.Menu(
                pystray.MenuItem("设置", self._settings, default=True),
                pystray.MenuItem("重启", self._restart_item),
                pystray.MenuItem("退出", self._exit),
            ),
        )
        self._icon = icon
        t = threading.Thread(target=icon.run, daemon=True)
        t.start()
        print("[Tray] ✅ 托盘图标已启动")

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _settings(self):
        if self._on_settings:
            self._on_settings()

    def _restart_item(self):
        if self._on_restart:
            self._on_restart()

    def _exit(self):
        if self._on_exit:
            self._on_exit()
