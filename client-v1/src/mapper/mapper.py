"""ActionMapper — 按键到行为的映射与路由。

根据 config.yaml 中的 buttons / scroll 配置，
将 button_id 映射为对应的行为（Overlay 或 直接执行）。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RouteAction(Enum):
    """路由目标。"""
    OVERLAY = "overlay"       # 进入 Overlay 选择模式
    DIRECT = "direct"         # 直接执行动作
    SCROLL_MAP = "scroll"     # 滚轮映射（在 mapper 内部处理）


@dataclass
class ButtonRoute:
    """按键的路由信息。"""
    button_id: int
    route: RouteAction
    label: str = ""
    # route=DIRECT 时的执行参数
    action_type: str = ""
    action_payload: str = ""
    # route=OVERLAY 时的菜单项
    menu_items: list = None  # list[MenuItem]
    # 长按
    long_press_action_type: str = ""
    long_press_payload: str = ""


@dataclass
class MenuItem:
    """Overlay 菜单项。"""
    id: str
    label: str
    icon: str = ""
    action_type: str = ""
    action_payload: str = ""


@dataclass
class ScrollRoute:
    """滚轮的路由信息。"""
    up_action_type: str
    up_payload: str
    down_action_type: str
    down_payload: str


class ActionMapper:
    """动作路由器：button_id / scroll_delta → 行为。"""

    def __init__(self, button_configs: list, scroll_config):
        self._buttons: dict[int, ButtonRoute] = {}
        self._triggers: dict[str, ButtonRoute] = {}  # "gamepad:3" → ButtonRoute
        self._scroll: Optional[ScrollRoute] = None
        self._build(button_configs, scroll_config)

    def _build(self, button_configs: list, scroll_config) -> None:
        """从 config 数据构建内部索引。

        button_configs: list[ButtonMapDef] (来自 config.py 的 dataclass)
        scroll_config: ScrollDef (来自 config.py 的 dataclass)
        """
        for b in button_configs:
            route = RouteAction(b.route)
            br = ButtonRoute(
                button_id=b.button_id,
                route=route,
                label=b.label,
                action_type=b.action_type,
                action_payload=b.action_payload,
                long_press_action_type=b.long_press_action_type,
                long_press_payload=b.long_press_payload,
            )
            if route == RouteAction.OVERLAY and b.menu_items:
                br.menu_items = [
                    MenuItem(
                        id=item.id,
                        label=item.label,
                        icon=getattr(item, 'icon', ''),
                        action_type=item.action_type,
                        action_payload=item.action_payload,
                    )
                    for item in b.menu_items
                ]
            self._buttons[br.button_id] = br
            if b.trigger:
                self._triggers[b.trigger] = br

        self._scroll = ScrollRoute(
            up_action_type=scroll_config.up_action_type,
            up_payload=scroll_config.up_payload,
            down_action_type=scroll_config.down_action_type,
            down_payload=scroll_config.down_payload,
        )

    def route_button(self, button_id: int) -> Optional[ButtonRoute]:
        """查询按钮的路由配置。返回 None 表示未配置。"""
        return self._buttons.get(button_id)

    def route_trigger(self, trigger: str) -> Optional[ButtonRoute]:
        """按触发键标识查询路由。例如 'gamepad:3' → ButtonRoute。"""
        return self._triggers.get(trigger)

    def route_scroll(self, delta: int) -> Optional[tuple[str, str]]:
        """查询滚轮方向对应的动作 (type, payload)。"""
        if self._scroll is None:
            return None
        if delta >= 0:
            return (self._scroll.up_action_type, self._scroll.up_payload)
        else:
            return (self._scroll.down_action_type, self._scroll.down_payload)

    def get_overlay_menu(self, button_id: int) -> list:
        """获取某个按钮的 Overlay 菜单项列表。"""
        br = self._buttons.get(button_id)
        if br and br.route == RouteAction.OVERLAY:
            return br.menu_items or []
        return []
