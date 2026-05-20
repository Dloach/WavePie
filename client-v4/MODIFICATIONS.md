# WavePie V3 — UI 改造记录

> 最后更新: 2026-05-17  
> 改造范围: `src/config_editor.py` · `src/ui/overlay.py`  
> 最新改动: 准星加速 + 扇区磁吸吸附

---

## 1. 配置编辑器 (`src/config_editor.py`)

**改造前**: 340 行，单行拥挤布局，无法排序，无预览，宏编辑为原始文本框。  
**改造后**: ~680 行，卡片式垂直布局，上下排序，实时预览，表格化宏编辑器。

### 改动的组件

| 组件 | 改动 |
|------|------|
| `ConfigEditor` | 完全重写。工具栏 + 滚动卡片 + 状态栏布局，Ctrl+S/Z/Esc 快捷键，撤销删除 |
| `ActionParamPanel` | 改为全宽布局，每个 action_type 独立子面板，不再挤一行 |
| `MacroEditorDialog` | **全新**。表格化逐行编辑宏步骤，替代原纯文本框 |
| `KeyRecorderDialog` | 保留核心逻辑，UI 微调（居中、尺寸） |
| `_render_card` | 每张卡片含：序号、标签输入、类型彩色徽章、▲▼排序、✕删除、参数面板、预览行 |
| `_rebuild` | 销毁全部 + 重建卡片 + 重建添加按钮 |

### 关键设计决策
- 类型颜色徽章: `log=灰 key=青 key_combo=紫 macro=黄 script=绿`
- 预览文字实时更新，如 `预览: 将按下组合键: Ctrl + Shift + S`
- 鼠标滚轮通过 `bind_all("<MouseWheel>")` + Enter/Leave 切换实现
- 添加按钮通过 `before` pack 参数确保始终在卡片列表底部

---

## 2. 圆形菜单 Overlay (`src/ui/overlay.py`)

**改造前**: 260 行，静态边框弧线，无动画，基础准星。  
**改造后**: ~520 行，60fps 动画循环，扇区填充高亮，呼吸中心，确认闪光，淡入淡出。

### 核心架构

```
set_sight(60fps) → 更新位置/扇区 → _tick(60fps) → itemconfig/coords 原地更新
```

**关键原则: Canvas 元素仅在 `activate()` 时创建一次，之后零创建/零删除，仅通过 `itemconfig()` 改色 + `coords()` 移位。**

### 画布元素层次 (创建顺序)

| 层 | ID 键 | 说明 |
|----|-------|------|
| 1 | `veil` | 全屏暗色遮罩 `#0A0A18` |
| 2 | `ring_bg` | 菜单圆形底色 `#12122A` |
| 3 | `fills[]` | **扇区填充块** (pieslice)，初始同背景色，高亮时过渡到 `#3355BB` |
| 4 | `dead` | 死区圆形 `#0C0C20`，**覆盖在 fills 之上**形成环形色块 |
| 5 | `ring_out` | 外装饰线 |
| 6 | `arcs[]` + `seps[]` | 扇区边框弧线 + 径向分隔线 |
| 7 | `labels[]` | 标签文字 (前8字，高亮时字号+3pt变白) |
| 8 | `center_dot` + `center_halo` | 中心呼吸点 + 光晕环 |
| 9 | `sight_*` | 准星: 外环 + 内环 + 中心点 + 4条十字线 |
| 10 | `flash_*` | 确认闪光: 扩散环 + 扇区白闪 (平时隐藏于0,0) |

### 动画参数

| 动画 | 时长 | 实现 |
|------|------|------|
| 入场 | 280ms | `root.attributes("-alpha")` 从 0.01 → 0.87, cubic ease-out |
| 退场 | 200ms | alpha 从 0.87 → 0.01 |
| 确认闪光 | 350ms | 扩散环 + 扇区白闪 → 然后退场 |
| 扇区发光过渡 | 100ms | `_lerp_hex(RING_FILL, SECTOR_GLOW, glow)` |
| 中心呼吸 | 2.2s 周期 | `sin()` 驱动中心点大小 + 颜色脉冲 |
| 准星平滑 | 系数 **0.20** | 指数平滑 `sx = sx*0.2 + target*0.8` (比旧版快一倍) |
| 扇区磁吸 | 强度 **0.68** | 角度拉向扇区中心 + 径向拉向环形中段 |

### 修复的 Bug

| Bug | 原因 | 修复 |
|-----|------|------|
| `unknown color name "12.0"` | `SIGHT_CROSS` 被定义为颜色后又定义为长度 `12.0`，后者覆盖前者 | 改名 `SIGHT_LINE`(颜色) + `SIGHT_CROSS_L`(长度) |
| 打开菜单卡死 | 初版每帧删除重建全部 Canvas 元素 (~80 个 × 60fps) | 改为一次性创建 + 原地更新 |
| 偶尔不执行命令 | 长按 GPIO4 手漂移到死区，`selected_idx` 变 -1 | **粘性选择**: 进入死区不重置已选扇区 |
| 退场后立即重新激活 | BLE 残留 0xAA 包触发 `on_aim` → `activate()` | `activate()` 加 600ms 冷却期 |
| 退场期间重复确认 | BLE 多发 0xBB 多次调度 `_on_confirm` | `deactivate()` 加 `_exiting` 守卫 |

### 新增特性: 扇区磁吸

准星进入扇区后，视觉位置被磁力拉向该扇区的中心角度 + 环形中段半径。

```
原始位置 (raw_sx, raw_sy) → 扇区判定 → 选中扇区 i
                                    ↓
视觉位置 (sx, sy) = 原始位置 + (扇区中心 - 原始位置) × 0.68
```

- `SNAP = 0.68` — 角度吸附强度，越大越"粘"
- `SNAP_RADIAL = 0.35` — 径向吸附强度，拉到环形中间
- 当准星跨越扇区边界进入新扇区范围时，吸附目标立即切换
- `_raw_sx/y` 用于扇区判定（保证边界响应及时），`_sx/y` 用于绘制（视觉丝滑）

### 调色板

```python
VEIL        = "#0A0A18"   # 背景遮罩
RING_FILL   = "#12122A"   # 环形底色
SECTOR_LINE = "#2A2A52"   # 扇区边框(空闲)
SECTOR_HL   = "#4466DD"   # 扇区边框(高亮)
SECTOR_GLOW = "#3355BB"   # 扇区填充(高亮)
DEAD_FILL   = "#0C0C20"   # 死区填充
CENTER_DOT  = "#5577FF"   # 中心点
TEXT_IDLE   = "#7777AA"   # 文字(空闲)
TEXT_HL     = "#FFFFFF"   # 文字(高亮)
```

---

## 3. 未改动的文件

- `src/main.py` — API 兼容，无需修改
- `src/input/ble.py` — 未改动
- `src/executor/actions.py` — 未改动
- `src/tray.py` — 未改动
- `src/utils/config.py` — 未改动

---

## 4. 继续开发指南

### 如果要修改圆形菜单视觉效果
1. 调色板在 `overlay.py` 顶部 ~20 行
2. 尺寸常量紧随其后 (~38 行)
3. 元素创建在 `_build()` 方法
4. 逐帧更新在 `_update_*()` 系列方法
5. 添加新元素: 在 `_build()` 创建并存 ID → 在对应 `_update_*()` 用 `itemconfig/coords` 更新

### 如果要修改配置编辑器
1. 卡片布局在 `_render_card()` 方法
2. 参数面板在 `ActionParamPanel` 类
3. 宏编辑器在 `MacroEditorDialog` 类
4. 添加新 action_type: 
   - `executor/actions.py` 添加 `_exec_*()` 方法
   - `config_editor.py` 的 `TYPE_NAMES`/`TYPE_COLORS` 添加条目
   - `ActionParamPanel._build()` 添加分支
   - `ActionParamPanel.get_preview()` 添加预览逻辑

### 调试技巧
- BLE 数据流: `ble.py → main.py → overlay.py`
- `0xAA` = 瞄准数据 (roll + pitch) → `on_aim` → `activate` 或 `set_sight`
- `0xBB` = 确认 → `on_confirm` → `_on_confirm` → `deactivate` + `_do_action`
- 所有 UI 操作在主线程 (`root.after(0, ...)`)
- 准星轮询在 `_poll_sight` (60fps)
- 动画循环在 `overlay._tick` (60fps)

### 已知限制
- Canvas 不支持真正 alpha 透明度 (用颜色插值模拟)
- Windows Tkinter 不支持 4 字节 emoji
- `-transparentcolor="black"` 意味着 `#000000` 完全透明
