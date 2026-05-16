# 项目状态

> 最后更新: 2026-05-16
> 当前版本: **client-v3**（V1 绘制 + V2 BLE 合并版）

---

## 版本状态

| 版本 | 状态 | 说明 |
|------|------|------|
| client-v1 | ✅ 已归档 | 完整原型，经验写入 `docs/postmortem-v1.md` |
| client-v2 | 🗑️ 废弃 | AimEngine 激光准星方案，后转为 Gyro Z 积分 + 替换为 V3 |
| **client-v3** | ✅ **当前** | V1 双显绘制 + V2 BLE 协议 + 激光准星 |
| firmware | ✅ 当前 | Madgwick + 陀螺仪 Z 积分 + 0xAA/0xBB + 250Hz |

## V3 已知问题

- [ ] 配置编辑器参数框宽度相互影响
- [ ] 准星平滑 +60fps 轮询后仍有卡顿，可继续调平滑参数

## 下次启动流程

```
1. 读取 docs/KNOWN_ISSUES.md      ← 关键问题知识库（必读！）
2. 读取 docs/postmortem-v1.md     ← V1 经验总结
3. 读取 DEVELOPMENT_FRAMEWORK.md
4. 读取 DECISION_LOG.md
5. 读取 SESSION_STATE.md
6. 读取 .devlog/ 最新日志
7. 输出"上下文就绪"确认
```
