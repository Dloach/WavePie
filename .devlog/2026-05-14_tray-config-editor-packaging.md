# 2026-05-14: client-v1 桌面应用增强 — 托盘 + 配置编辑器 + EXE 打包

## 操作人
AI + 开发者

## 涉及版本
client-v1

## 做了什么

### 1. 系统托盘 (src/tray.py)
- pystray 实现 Windows 右下角通知栏常驻
- Pillow 内联绘制图标（蓝色圆底白字 "W"），无外部 .ico 依赖
- 右键菜单：设置 → 打开配置编辑器，退出 → 完全退出

### 2. 配置编辑器 (src/config_editor.py)
- tkinter 图形界面，左侧导航 + 右侧编辑区
- 可编辑：菜单项（图标/标签/动作类型/参数）、副键直接动作、滚轮映射、手势参数
- 修改后点「💾 保存配置」写回 config.yaml

### 3. 统一入口 (src/app.py)
- 同时支持 F12（键盘）+ L2（手柄）+ 鼠标滚轮 + 托盘图标
- 配置编辑保存后自动重载

### 4. PyInstaller 打包
- `--onefile --noconsole` 模式，单文件 38MB
- 零安装：双击 WavePie.exe 即运行，缩到托盘
- 零卸载：删除 WavePie.exe + config.yaml 即可
- 不改注册表 / 不开机启动 / 不写 AppData

### 5. 文件清单
```
client-v1/src/
├── app.py           (新建)  统一入口
├── tray.py          (新建)  系统托盘
├── config_editor.py (新建)  配置编辑器
└── utils/config.py  (修改)  新增 save_config()
```

## 已知问题
- 暂未做开机自启（未来可加，可选）
- 首次打包体积较大（38MB），主要来自 pygame + tkinter 捆绑