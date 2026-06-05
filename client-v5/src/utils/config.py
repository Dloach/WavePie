"""配置加载 — 简化版，仅支持 V2 所需字段。"""

import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class MenuConfig:
    num_sectors: int = 6
    items: list = field(default_factory=list)


@dataclass
class MenuItemDef:
    label: str = ""
    action_type: str = "log"
    action_payload: str = ""


@dataclass
class AimConfig:
    sensitivity: float = 3.0
    dead_zone: float = 1.0
    smoothing: float = 0.7


@dataclass
class BleConfig:
    device_name: str = "BLE Gesture Ctrl"


@dataclass
class AppConfig:
    ble: BleConfig = field(default_factory=BleConfig)
    aim: AimConfig = field(default_factory=AimConfig)
    menu: dict = field(default_factory=lambda: {"items": [], "num_sectors": 6})

    @property
    def menu_items(self):
        return self.menu.get("items", [])

    @menu_items.setter
    def menu_items(self, items):
        self.menu["items"] = items


def _find_config() -> str:
    """从 exe 同目录或源码目录找 config.yaml。"""
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


def load_config(path: str = None) -> AppConfig:
    if not path:
        path = _find_config()
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = AppConfig()

    # BLE
    b = raw.get("ble", {})
    cfg.ble = BleConfig(
        device_name=b.get("device_name", "BLE Gesture Ctrl"),
    )

    # Aim
    a = raw.get("aim", {})
    cfg.aim = AimConfig(
        sensitivity=float(a.get("sensitivity", 3.0)),
        dead_zone=float(a.get("dead_zone", 1.0)),
        smoothing=float(a.get("smoothing", 0.7)),
    )

    # Menu
    raw_menu = raw.get("menu", {})
    if isinstance(raw_menu, dict):
        if "num_sectors" not in raw_menu:
            raw_menu["num_sectors"] = 6
        cfg.menu = raw_menu
    else:
        cfg.menu = {"items": [], "num_sectors": 6}

    return cfg
