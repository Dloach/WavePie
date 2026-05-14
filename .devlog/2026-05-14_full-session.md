# 2026-05-14: 完整 session — 从框架搭建到桌面应用增强

## 操作人
AI + 开发者

## 涉及版本
client-v1, firmware

## 本次完成

### 项目初始化
- 全面分析迁移过来的项目（v1 软件原型 + firmware）
- 删除混淆的 v3 目录，固件归入 firmware/
- 命名项目为 **WavePie**，创建 GitHub 仓库 https://github.com/Dloach/WavePie
- GPLv3 许可证
- 分 5 批 commit 推送为 v0.0.1（脚手架→文档→v1→固件→日志）

### 桌面应用增强
- `v1/` → `client-v1/`（可读性优化，后续可 client-v2/v3）
- 系统托盘 (tray.py) — pystray，右下角通知栏常驻，双击打开设置
- 配置编辑器 (config_editor.py) — tkinter GUI，可视化编辑菜单项
- 统一入口 app.py — F12 + 手柄 + 托盘 + Overlay 合一
- PyInstaller 打包 — `--onefile --noconsole`，40MB，零安装零残留

### 编辑器迭代
- 布局修复：combo 和参数区顺序导致控件挤压
- 线程修复：Toplevel（挂主窗口）替代独立 Tk()，修复所有 tkinter 事件异常
- 动态参数面板：key_combo / key / macro / script / log 按类型切换
- 键盘录制：pynput 监听，支持 Ctrl+Shift+Z 等多组合键（VK 码识别）
- VK 码表提升为模块级常量，避免控制字符 \x1a→方框 bug
- 宏编辑器弹窗 + 脚本文件选择器
- 保存 toast + 自动关闭编辑器
- ESC 不再关闭编辑器 / 退出程序

### 执行链路修复
- **Enum vs 字符串 bug**：`br.route == "direct"` 比较 `RouteAction.DIRECT` 枚举与字符串始终为 False，导致直接动作查到了但不执行。修为 `RouteAction.DIRECT` 枚举比较
- 统一执行入口 `_do_action()` — 圆形菜单和手柄按键都走同一条路
- 移除滚轮触发（用户不需要）
- 移除 overlay 的 `_quit` / `sys.exit(0)`

### 手柄功能
- 编辑器中可下拉选择手柄按键绑定（gamepad:0 ~ N）
- 运行时轮询所有手柄按钮，边缘检测按下事件
- Mapper 新增 `_triggers` 索引 + `route_trigger()` 方法
- 信号检测面板 (GamepadMonitor) 诊断用

### 配置编辑器的菜单项编辑
- 标签和类型切换修复（闭包捕获 bug：用默认参数固定循环变量）
- 所有类型下拉菜单统一添加 key/log/key_combo/macro/script
- 移除滚轮映射导航项

## 文件统计
```
client-v1/src/
├── app.py              (120行)  统一入口（重写）
├── tray.py             (115行)  系统托盘
├── config_editor.py    (1126行) 配置编辑器（大幅扩展）
├── ui/overlay.py       (428行)  径向菜单（焦点执行顺序修复）
├── input/gamepad.py    (155行)  增加全按钮轮询+直接动作触发
├── mapper/mapper.py    (117行)  增加 route_trigger + _triggers 索引
├── executor/actions.py (250行)  VK 表提升模块级 + key 类型 + _keybd_send
└── utils/config.py     (✓)     trigger 字段 + save_config
```
总计约 17 个源文件，~2300 行代码

## 待办
- [ ] ESP32 到货 → 烧录固件接线
- [ ] PC 端 BLEInputProvider 实现
- [ ] 硬件↔PC 联调
- [ ] 日常使用体验打磨