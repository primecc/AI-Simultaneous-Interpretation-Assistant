# [codex] 实现 AI 同声传译助手 MVP

## 标题

实现 AI 同声传译助手 MVP。

## 功能描述

本 PR 上传项目当前完整源码：本地 FastAPI 服务、系统音频监听、本地 Whisper 识别、免 key 中文翻译、桌面悬浮图标、桌面字幕浮层、视频/音频导入、字幕历史、TXT/SRT 导出、浏览器浮层原型、Windows EXE 打包配置、跨机器发布说明和参赛提交规范文档。

## 实现思路

- 后端使用 FastAPI、Pydantic 和 WebSocket 提供本地服务与字幕流。
- Windows 后台同传使用 PyAudioWPatch WASAPI loopback 读取系统播放音频。
- ASR 使用 faster-whisper 本地模型，翻译使用 deep-translator 免 key 在线翻译。
- 桌面交互使用 Tkinter 实现置顶悬浮按钮、拖动和字幕浮层。
- 打包使用 PyInstaller one-dir 模式，并补充版本信息、运行库、签名脚本和发布说明。

## 测试方式

- `python -m pytest`
- `python -m ruff check .`
- 手动运行 EXE，点击悬浮图标开启/关闭字幕。
- 手动打开网页工作台上传视频/音频并验证字幕生成和导出。

## 依赖与原创说明

- 新增第三方依赖：FastAPI、Uvicorn、Pydantic、PyAudioWPatch、faster-whisper、deep-translator、numpy、python-multipart、pytest、ruff。
- 原创功能部分：桌面悬浮控制、系统音频同传管线、字幕片段修正模型、媒体导入字幕工作台、字幕导出、Windows 打包发布流程和参赛过程文档。
- 复用过往代码及来源：未复用个人过往代码；浏览器扩展为本项目内原型实现。

## 开发过程说明

当前仓库此前只有 `main` 的初始提交，本 PR 是本地项目首次上传到 GitHub。已在 `docs/PR提交记录与补交方案.md` 中如实记录当前 PR/commit 状态和后续建议拆分方案，不伪造历史 PR 或 commit 时间。
