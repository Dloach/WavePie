"""配置加载器 — 从 config.yaml 加载并校验配置。"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 配置数据结构
# ============================================================

@dataclass
class MouseButtonMap:
    main_button: str = "<Button-1>"
    aux_buttons: dict = field(default_factory=lambda: {"<Button-3>": 1})


@dataclass
class MouseConfig:
    sensitivity: float = 1.0
    button_map: MouseButtonMap = field(default_factory=MouseButtonMap)


@dataclass
class GestureConfig:
    dead_zone: float = 0.05
    sensitivity: float = 1.2
    acceleration: bool = True


@dataclass
class ActionDef:
    """一个动作的定义。"""
    action_type: str = "key_combo"     # "key_combo" | "macro" | "script"
    action_payload: str = ""


@dataclass
class MenuItem(ActionDef):
    id: str = ""
    label: str = ""
    icon: str = ""


@dataclass
class ButtonMapDef:
    """按键映射配置条目。"""
    button_id: int = 0
    trigger: str = ""                  # "gamepad:3" 等触发键标识
    route: str = "overlay"             # "overlay" | "direct"
    label: str = ""
    # route=overlay 时的菜单项
    menu_items: list = field(default_factory=list)
    # route=direct 时的直接动作
    action_type: str = ""
    action_payload: str = ""
    # 长按（预留）
    long_press_action_type: str = ""
    long_press_payload: str = ""


@dataclass
class ScrollDef:
    up_action_type: str = "key_combo"
    up_payload: str = ""
    down_action_type: str = "key_combo"
    down_payload: str = ""


@dataclass
class FeedbackRule:
    led_color: str = "green"
    led_pattern: str = "slow_blink"
    buzzer: bool = False


@dataclass
class UIConfig:
    overlay_opacity: float = 0.85
    font_size: int = 14
    item_height: int = 40
    item_padding: int = 10
    highlight_color: str = "#4A90D9"


@dataclass
class AppConfig:
    """顶层配置。"""
    input_provider: str = "mouse"        # "mouse" | "ble"
    mouse: MouseConfig = field(default_factory=MouseConfig)
    gesture: GestureConfig = field(default_factory=GestureConfig)
    buttons: list = field(default_factory=list)
    scroll: ScrollDef = field(default_factory=ScrollDef)
    feedback_rules: dict = field(default_factory=dict)
    ui: UIConfig = field(default_factory=UIConfig)


# ============================================================
# 加载器
# ============================================================

def load_config(path: str = None) -> AppConfig:
    """加载 YAML 配置文件并转换为 AppConfig。"""
    if path is None:
        # 默认在当前文件所在目录的父目录找 config.yaml
        path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")

    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"配置文件未找到: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    cfg = AppConfig()

    # input
    inp = raw.get("input", {})
    cfg.input_provider = inp.get("provider", "mouse")
    mouse_raw = inp.get("mouse", {})
    bm = mouse_raw.get("button_map", {})
    cfg.mouse = MouseConfig(
        sensitivity=mouse_raw.get("sensitivity", 1.0),
        button_map=MouseButtonMap(
            main_button=bm.get("main_button", "<Button-1>"),
            aux_buttons=bm.get("aux_buttons", {}),
        ),
    )

    # gesture
    g = raw.get("gesture", {})
    cfg.gesture = GestureConfig(
        dead_zone=g.get("dead_zone", 0.05),
        sensitivity=g.get("sensitivity", 1.2),
        acceleration=g.get("acceleration", True),
    )

    # buttons
    cfg.buttons = []
    for b in raw.get("buttons", []):
        bm = ButtonMapDef(
            button_id=b.get("button_id", 0),
            trigger=b.get("trigger", ""),
            route=b.get("route", "direct"),
            label=b.get("label", ""),
            action_type=b.get("action_type", ""),
            action_payload=b.get("action_payload", ""),
            long_press_action_type=b.get("long_press_action_type", ""),
            long_press_payload=b.get("long_press_payload", ""),
        )
        if b.get("route") == "overlay":
            bm.menu_items = [
                MenuItem(
                    id=item.get("id", ""),
                    label=item.get("label", ""),
                    icon=item.get("icon", ""),
                    action_type=item.get("action_type", ""),
                    action_payload=item.get("action_payload", ""),
                )
                for item in b.get("menu_items", [])
            ]
        cfg.buttons.append(bm)

    # scroll
    s = raw.get("scroll", {})
    cfg.scroll = ScrollDef(
        up_action_type=s.get("up", {}).get("action_type", "key_combo"),
        up_payload=s.get("up", {}).get("action_payload", ""),
        down_action_type=s.get("down", {}).get("action_type", "key_combo"),
        down_payload=s.get("down", {}).get("action_payload", ""),
    )

    # feedback_rules
    cfg.feedback_rules = raw.get("feedback_rules", {})

    # ui
    ui = raw.get("ui", {})
    cfg.ui = UIConfig(
        overlay_opacity=ui.get("overlay_opacity", 0.85),
        font_size=ui.get("font_size", 14),
        item_height=ui.get("item_height", 40),
        item_padding=ui.get("item_padding", 10),
        highlight_color=ui.get("highlight_color", "#4A90D9"),
    )

    return cfg


# ============================================================
# 保存器
# ============================================================

def save_config(cfg: AppConfig, path: str) -> None:
    """将 AppConfig 保存回 YAML 文件。"""

    # 构建 buttons list
    buttons_raw = []
    for b in cfg.buttons:
        bd = {
            "button_id": b.button_id,
            "route": b.route,
            "label": b.label,
        }
        if b.trigger:
            bd["trigger"] = b.trigger
        if b.route == "overlay" and b.menu_items:
            bd["menu_items"] = [
                {
                    "id": item.id,
                    "label": item.label,
                    "icon": item.icon,
                    "action_type": item.action_type,
                    "action_payload": item.action_payload,
                }
                for item in b.menu_items
            ]
        else:
            bd["action_type"] = b.action_type
            bd["action_payload"] = b.action_payload
        if b.long_press_action_type:
            bd["long_press_action_type"] = b.long_press_action_type
            bd["long_press_payload"] = b.long_press_payload
        buttons_raw.append(bd)

    raw = {
        "input": {
            "provider": cfg.input_provider,
            "mouse": {
                "sensitivity": cfg.mouse.sensitivity,
                "button_map": {
                    "main_button": cfg.mouse.button_map.main_button,
                    "aux_buttons": cfg.mouse.button_map.aux_buttons,
                },
            },
        },
        "gesture": {
            "dead_zone": cfg.gesture.dead_zone,
            "sensitivity": cfg.gesture.sensitivity,
            "acceleration": cfg.gesture.acceleration,
        },
        "buttons": buttons_raw,
        "scroll": {
            "up": {
                "action_type": cfg.scroll.up_action_type,
                "action_payload": cfg.scroll.up_payload,
            },
            "down": {
                "action_type": cfg.scroll.down_action_type,
                "action_payload": cfg.scroll.down_payload,
            },
        },
        "feedback_rules": cfg.feedback_rules,
        "ui": {
            "overlay_opacity": cfg.ui.overlay_opacity,
            "font_size": cfg.ui.font_size,
            "item_height": cfg.ui.item_height,
            "item_padding": cfg.ui.item_padding,
            "highlight_color": cfg.ui.highlight_color,
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"[Config] ✅ 已保存: {path}")
