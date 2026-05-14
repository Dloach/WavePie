# 架构决策记录

> 每次做出架构、技术、设计的重大决策时在此追加一条。
> 每条格式：`D-NNN | YYYY-MM-DD | 标题`

---

## D-001 | 2024-12-17 | 确定开发框架文档体系

**背景：** 项目处于启动阶段，需要为长期（数月的）AI 协作开发建立规范性框架。

**方案对比：**
- 无文档 / 少量零散记录：AI 上下文过期后容易走偏
- 单一大文档包罗万象：定位为"宪法"，其他决策单独跟踪
- 分散到多个松散文件：容易丢失

**决策：** 建立三级文档体系
1. `DEVELOPMENT_FRAMEWORK.md` — 宪法级（架构、规范、流程），长期稳定
2. `DECISION_LOG.md` — 决策日志（增量追加），记录每次架构决策及理由
3. `SESSION_STATE.md` — 状态文件（每次操作后更新），记录当前进展
4. `.devlog/` — 操作日志目录（按日期命名的细粒度操作记录）

**理由：** 结构清晰、职责单一。AI 每次启动通过"启动检查清单"快速恢复上下文，避免依赖历史对话。

**后续影响：**
- 每次关键操作后需更新 SESSION_STATE.md 和 .devlog
- 涉及架构选择时追加到 DECISION_LOG.md
- 框架文档本身的修改需特别谨慎

---

## D-002 | 2024-12-17 | 采用 HAL 模式抽象输入源

**背景：** 项目需要先以鼠标模拟体感（Phase 1），后续再接入真实 BLE 设备（Phase 3），两套输入源必须无缝切换，不能影响上层业务代码。

**方案对比：**
- 条件分支（if/else 判断输入源）：散落在各处，难以维护
- 策略模式 / 接口抽象：统一 InputProvider 接口，运行时切换
- 事件驱动架构：通过消息队列解耦输入和消费

**决策：** 定义 `InputProvider` 抽象基类 + `InputEvent` 数据类，两个实现（`MouseInputProvider`, `BLEInputProvider`），通过配置文件切换。

**理由：** 接口简单清晰，Phase 1 先实现鼠标版，Phase 3 只需新增一个实现类，零修改业务代码。事件驱动架构对当前规模过度设计。

**后续影响：**
- 所有输入消费代码只依赖 `InputProvider`，不依赖具体实现
- 配置格式统一（YAML），`input.provider` 字段切换
- 固件 BLE 协议设计时需保证能映射为 `InputEvent`

---

## D-003 | 2024-12-17 | 每个版本独立子目录，而非 Git 分支管理

**背景：** 项目以"版本快照"方式推进（v1 → v2 → 硬件接入），每个版本是独立原型，不是持续演进的主干。

**方案对比：**
- Git 分支：版本间共享历史，但分支切换需要 stash/commit，认知负担大
- 独立子目录：每个版本完全独立，互不干扰，对比方便

**决策：** 使用 `client-v1/` `client-v2/` `firmware/` 独立子目录，每个版本自包含（依赖除外）。

**理由：** 更适合原型迭代风格。版本间可以完全重写某层而不影响其他版本。对比 v1 和 v2 的同模块设计只需 diff 目录。

**后续影响：**
- 公共工具函数如果跨版本复用，成熟后提取到 `shared/`
- 早期不强求复用，允许各版本有不同实现风格

---

## D-004 | 2024-12-17 | 架构升级：多按键分路由 + 双向反馈通道

**背景：** 原架构只考虑了一个主按钮（触发 Overlay 体感选择），用户提出扩展需求：
1. 硬件上有多个副键和滚轮，可直接触发快捷键/宏，不经过 Overlay UI
2. 软件需要向硬件发送状态信号（LED/蜂鸣/震动）

**方案设计：**

**(A) 输入事件模型升级**
- `InputEvent` 新增 `button_id`（区分多键）、`is_long_press`（长按预留）、`scroll_delta`（滚轮）
- `EventType` 新增 `SCROLL` 类型
- 应用代码通过 `button_id` 区分来源，不依赖硬编码的"一个按钮"

**(B) 新增 ActionMapper 路由层**
- 位于输入层和处理层之间
- 根据 `button_id` + 配置，将事件分流到 Overlay 路径或直接执行路径
- `ButtonActionMap` 和 `ScrollMap` 数据类承载映射配置
- config.yaml 驱动，用户可自定义

**(C) 新增 DeviceFeedback 接口**
- `InputProvider` 新增 `feedback` 属性，返回 `DeviceFeedback` 实例
- `FeedbackCommand` 支持 LED 颜色/模式、蜂鸣、震动、状态码
- 模拟阶段使用 `NoopFeedback`（空实现），真实阶段写 BLE Write 特征值
- 实现软件 → 硬件的双向通信，不破坏单向输入流的设计

**(D) BLE 协议预留**
- 固件侧新增 Feedback characteristic（Write），4 字节格式（LED+蜂鸣+状态码+预留）
- 按钮 characteristic 从单字节升级为位掩码 + 事件标记，支持多键和多击
- 新增 Scroll characteristic 承载滚轮增量

**理由：**
1. ActionMapper 引入了一个薄路由层，但避免了在手势引擎或 UI 中散落 if/else 判断
2. DeviceFeedback 是独立接口（不是 InputProvider 的内部方法），未来可以支持非 BLE 设备（串口、hidraw）
3. 所有扩展都通过接口新增，不修改已有接口签名，v1 代码在硬件接入阶段不需要重构

**后续影响：**
- Phase 1 开发步骤更新（v1.3 新增 ActionMapper，v1.6 强调多键全链路）
- Phase 2 步骤更新（新增 DeviceFeedbackOverBLE 实现）
- 固件开发时需实现 4 个 characteristic（Buttons / IMU / Scroll / Feedback）
- DEVLOPMENT_FRAMEWORK.md 的 Section 5 从 ~50 行扩展至 ~250 行，但核心设计一致
