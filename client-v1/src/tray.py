"""WavePie 系统托盘图标。

启动后缩到 Windows 右下角通知栏，右键菜单：
  - 设置 → 打开配置编辑器
  - 退出 → 完全退出程序

纯内存图标（Pillow 内联生成），不依赖外部 .ico 文件。
"""

import threading
from typing import Callable, Optional

try:
    import pystray
    from pystray import MenuItem as TrayItem
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    pystray = None


def _make_icon() -> Image.Image:
    """内联生成托盘图标（64x64，蓝底白字 "W"）。"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景圆
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill="#4A90D9",
    )

    # 文字 "W"
    try:
        font = ImageFont.truetype("segoeui.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "W", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) / 2 - bbox[0]
    ty = (size - th) / 2 - bbox[1]
    draw.text((tx, ty), "W", fill="white", font=font)

    return img


class TrayApp:
    """系统托盘图标控制器。

    用法：
        tray = TrayApp(on_settings=open_config, on_exit=clean_exit)
        tray.run()   # 阻塞，在独立线程中运行
    """

    def __init__(
        self,
        on_settings: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
    ):
        self._on_settings = on_settings
        self._on_exit = on_exit
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def _build_menu(self):
        items = []
        if self._on_settings:
            items.append(TrayItem("设置", self._settings_clicked))
        if self._on_exit:
            items.append(TrayItem("退出", self._exit_clicked))
        return items

    def _settings_clicked(self):
        if self._on_settings:
            self._on_settings()

    def _exit_clicked(self):
        if self._icon:
            self._icon.stop()
        if self._on_exit:
            self._on_exit()

    def run(self):
        """启动托盘（在当前线程阻塞，通常放在独立线程）。"""
        if pystray is None:
            print("[Tray] ❌ pystray 未安装，跳过托盘图标")
            return
        icon = pystray.Icon(
            "WavePie",
            _make_icon(),
            "WavePie — 蓝牙体感控制器",
            menu=self._build_menu(),
        )
        self._icon = icon
        icon.run()

    def start_background(self):
        """在后台线程启动托盘。"""
        if pystray is None:
            print("[Tray] ❌ pystray 未安装，跳过托盘图标")
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        print("[Tray] ✅ 托盘图标已启动")

    def stop(self):
        """停止托盘图标。"""
        if self._icon:
            self._icon.stop()
            self._icon = None
