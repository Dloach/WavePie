# 项目状态

> 最后更新: 2026-05-14
> **client-v1 已完成历史任务，正式归档。**
> 下一阶段开发 client-v2 前请阅读 `docs/postmortem-v1.md` 和 `.devlog/` 最新日志。

---

## 版本状态

| 版本 | 状态 | 说明 |
|------|------|------|
| **client-v1** | ✅ **已归档** | PC 端完整原型 + ESP32 固件 + BLE 联调验证 |
| **firmware** | ⏸️ 暂停 | 已通过硬件验证，待 V2 启动时同步更新 |
| **client-v2** | ⏳ 待启动 | 基于 V1 经验的重构版本 |

## client-v1 完成项

### 已验证通过的
- [x] OverlayUI 径向菜单 — 全屏透明 + 12扇区 + 鼠标/体感控制
- [x] ActionExecutor — key / key_combo / macro / script 四种动作执行
- [x] ActionMapper — button_id + trigger 双索引路由
- [x] 配置编辑器 — 动态参数面板 + 键盘录制 + 宏/脚本编辑
- [x] 系统托盘 — pystray 常驻，双击设置，右键退出
- [x] PyInstaller 单文件 exe — 零安装零卸载
- [x] GPIO 4 一键触发菜单 + 体感扇区选择（BLE 模式）
- [x] ESP32 BLE IMU 数据流（66Hz）→ PC 端轮询渲染（30fps）
- [x] 零点基准校准（按下按钮时记录当前姿态）

### 已解决的 Bug
- [x] Enum vs 字符串比较（RouteAction.DIRECT == "direct" 永远 False）
- [x] Python 闭包循环变量捕获
- [x] tkinter 线程安全（Toplevel 替代独立 Tk）
- [x] GPIO 3(RXD0) 冲突、GPIO 6/7(Flash) 冲突
- [x] bleak 3.x 无 get_services()
- [x] 高频 IMU 数据 per-event 调度堵死 tkinter 队列

### 经验文档
- [x] `docs/postmortem-v1.md` — 完整经验总结（必读）
- [x] `DECISION_LOG.md` D-005 — 归档决策记录

## V2 待办（参考 `docs/postmortem-v1.md`）

- [ ] 重新评估 UI 框架（tkinter / PyQt / WinUI）
- [ ] 改进 GestureEngine 对圆形菜单的适配
- [ ] BLE 断线重连
- [ ] 配置热重载健壮性
- [ ] 日常使用体验打磨

## 下次启动流程

```
1. 读取 docs/postmortem-v1.md    ← V1 经验总结
2. 读取 DEVELOPMENT_FRAMEWORK.md
3. 读取 DECISION_LOG.md（特别是 D-005）
4. 读取 SESSION_STATE.md
5. 读取 .devlog/ 最新日志
6. 输出"上下文就绪"确认
```
