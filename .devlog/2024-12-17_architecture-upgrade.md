# 2024-12-17: 架构升级 — 多按键分路由 + 双向反馈

## 操作人
AI

## 涉及版本
v0（框架层）

## 做了什么
- 升级 `DEVELOPMENT_FRAMEWORK.md`：
  - Section 1：架构图加入多按键(B0/B1/B2)、滚轮、DeviceFeedback、ActionMapper 路由层、3 条交互路径
  - Section 4：Phase 1 新增 ActionMapper（1.3）和滚轮动作（1.6）；Phase 2 新增 Feedback 通道；后续版本增加反馈规则引擎
  - Section 5（HAL 大改写，~50行→~250行）：
    - InputEvent 升级：button_id, is_long_press, scroll_delta, EventType.SCROLL
    - 新增 ButtonRole 枚举定义主/副键角色
    - 新增 DeviceFeedback / FeedbackCommand / NoopFeedback 接口
    - 新增 ActionMapper / ButtonActionMap / ScrollMap 路由层
    - 升级 BLE 协议预留：4 个 characteristic（Buttons/IMU/Scroll/Feedback），支持双向
  - Section 6：技术栈新增反馈通道、技术储备新增 BLE Write 和 ESP32 GATT Read
  - Section 7：文件结构新增 mapper/ 目录和 feedback.py 文件
- 追加 `DECISION_LOG.md` D-004 记录本次升级的完整决策链

## 关键决策
见 DECISION_LOG.md D-004

## 遗留问题 / 待办
- [ ] 等待开发者确认架构升级是否满足需求
- [ ] 确认后进入 v1 Phase 1.0

## 备注
本次升级将所有"未来扩展点"转化成了"已定义接口"。Phase 1 模拟阶段只实现鼠标签约端，device feedback 用 NoopFeedback 空操作，不会增加 v1 开发复杂度。
