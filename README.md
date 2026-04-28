# CrossPoint Reader

适用于 **Xteink X4** 电子墨水屏阅读器的开源固件（本项目与 Xteink 官方无关）。  
使用 **PlatformIO** 构建，目标平台为 **ESP32-C3** 微控制器。

CrossPoint Reader 是 Xteink 官方固件的完全开源替代品，致力于在原有硬件上提供更优质的 EPUB 阅读体验。

![](./docs/images/cover.jpg)

---

## 中文版说明

本仓库在上游 [crosspoint-reader/crosspoint-reader](https://github.com/crosspoint-reader/crosspoint-reader) 的基础上，完整加入了 **简体中文 UI 支持**。

### 本次汉化工作内容（2025-04）

| 工作项 | 说明 |
|--------|------|
| 翻译文件 | 新增 `lib/I18n/translations/chinese.yaml`，全量翻译 300 条界面字符串，覆盖率 100%，无英文回退 |
| 语言代码 | `Language::ZH`（枚举索引 22），遵循 ISO 639 语言代码规范 |
| 字体生成脚本 | 新增 `scripts/gen_cjk_fonts.py`，提取 UI 实际用字（337 个汉字），使用 Ubuntu + Noto Sans SC 字体栈生成最小化 CJK 子集字体 |
| 字体目录 | 新增 `lib/EpdFont/builtinFonts/source/NotoSansSC/`，存放 Noto Sans SC 字体源文件 |
| 版本标识 | 固件版本号追加 `-中文版` 后缀，便于与原版区分 |
| C++ 代码 | 自动生成文件 `I18nKeys.h` / `I18nStrings.h` / `I18nStrings.cpp` 已重新生成并包含中文 |

### 启用中文界面

1. 使用此仓库固件刷写设备（见下方安装说明）
2. 开机后进入 **设置 → 语言**，选择「中文」
3. 设置将自动保存，重启后生效

### 本地编译

本仓库已包含预生成的 CJK UI 字体（337 个汉字子集，基于 Noto Sans SC v2.004），
克隆后直接编译即可，无需额外步骤：

```bash
git clone --recursive https://github.com/dilidaladi/crosspoint-reader
cd crosspoint-reader
pio run --target upload
```

如需重新生成字体（例如修改了翻译文件后），运行：

```bash
pip install freetype-py fonttools
python scripts/gen_cjk_fonts.py
```

---

## 项目简介

市面上大多数电子墨水阅读器是封闭系统，定制空间有限。**Xteink X4** 是一款价格实惠的电子墨水设备，但官方固件未开放源码。CrossPoint 项目旨在：

- 提供**完全开源**的固件替代方案
- 在资源受限的硬件上实现完整的 **EPUB 文档阅读**体验
- 支持**字体、排版与显示**的个性化配置
- 专为 **Xteink X4 硬件**设计运行

本项目**与 Xteink 官方及 X4 硬件制造商无任何关联**，是纯社区项目。

---

## 功能特性

- [x] EPUB 解析与渲染（支持 EPUB 2 和 EPUB 3）
- [x] EPUB 内嵌图片显示
- [x] 阅读进度保存
- [x] 文件浏览器
  - [x] 从根目录选择 EPUB 文件
  - [x] 支持多级文件夹
  - [ ] 带封面预览的 EPUB 选择器（计划中）
- [x] 自定义休眠屏幕
  - [x] 封面休眠屏幕
- [x] WiFi 书籍上传
- [x] WiFi OTA 在线升级
- [x] KOReader Sync 跨设备阅读进度同步
- [x] 字体、排版与显示选项配置
  - [ ] 用户自定义字体（计划中）
  - [ ] 完整 UTF 支持（计划中）
- [x] 屏幕旋转
- [x] **简体中文界面**（本版本新增）

多语言支持：可阅读英语、西班牙语、法语、德语、意大利语、葡萄牙语、俄语、乌克兰语、波兰语、瑞典语、中文等多种语言的 EPUB 书籍。

---

## 安装方法

### 方式一：网页刷写（最新固件）

1. 用 USB-C 将 Xteink X4 连接到电脑，并唤醒/解锁设备
2. 访问 https://xteink.dve.al/，点击「Flash CrossPoint firmware」

如需恢复官方固件，可在同一页面刷写官方固件，或通过 https://xteink.dve.al/debug 使用「Swap boot partition」切换回另一分区。

### 方式二：命令行刷写（指定版本）

1. 安装 [`esptool`](https://github.com/espressif/esptool)：
```bash
pip install esptool
```
2. 从 [Releases 页面](https://github.com/crosspoint-reader/crosspoint-reader/releases)下载目标版本的 `firmware.bin`
3. 用 USB-C 连接设备，确认设备端口号（Linux 用 `dmesg`，macOS 查看 `/dev/cu.*`）
4. 执行刷写：
```bash
esptool.py --chip esp32c3 --port /dev/ttyACM0 --baud 921600 write_flash 0x10000 firmware.bin
```
将 `/dev/ttyACM0` 替换为实际端口。

---

## 开发环境

### 前置要求

- **PlatformIO Core**（`pio`）或 **VS Code + PlatformIO IDE**
- Python 3.8+
- USB-C 数据线
- Xteink X4 设备

### 获取代码

```bash
git clone --recursive https://github.com/dilidaladi/crosspoint-reader
cd crosspoint-reader
```

若已克隆但未拉取子模块：
```bash
git submodule update --init --recursive
```

### 编译与刷写

```bash
pio run --target upload
```

### 调试日志

```bash
pip install pyserial colorama matplotlib
python scripts/debugging_monitor.py          # Linux
python scripts/debugging_monitor.py /dev/cu.usbmodem2101  # macOS
```

---

## 内部实现

CrossPoint Reader 采用激进的 SD 卡缓存策略以最小化 RAM 占用——ESP32-C3 仅有约 380 KB 可用 RAM。

### 数据缓存结构

首次加载章节时，内容会缓存到 SD 卡：

```
.crosspoint/
├── epub_12471232/
│   ├── progress.bin     # 阅读进度（章节、页码等）
│   ├── cover.bmp        # 书籍封面图
│   ├── book.bin         # 书籍元数据（标题、作者、目录等）
│   └── sections/
│       ├── 0.bin        # 章节数据（按脊骨索引命名）
│       └── ...
└── epub_189013891/
```

删除 `.crosspoint` 目录可清除全部缓存。  
注意：删除书籍文件不会自动清除对应缓存；移动书籍文件会重置阅读进度。

---

## 参与贡献

欢迎各种形式的贡献！

- 提交 Bug：请在 [Issues](https://github.com/dilidaladi/crosspoint-reader/issues) 中报告
- 功能建议：查看[想法讨论区](https://github.com/crosspoint-reader/crosspoint-reader/discussions/categories/ideas)
- 翻译改进：直接修改 `lib/I18n/translations/chinese.yaml` 并提 PR

提交贡献流程：
1. Fork 本仓库
2. 创建分支（例：`feature/cjk-font-improvement`）
3. 提交修改
4. 发起 Pull Request

---

## 致谢

- 上游项目：[crosspoint-reader/crosspoint-reader](https://github.com/crosspoint-reader/crosspoint-reader)
- 灵感来源：[diy-esp32-epub-reader](https://github.com/atomic14/diy-esp32-epub-reader) by atomic14
- 中文汉化：[dilidaladi](https://github.com/dilidaladi)（2025-04）
