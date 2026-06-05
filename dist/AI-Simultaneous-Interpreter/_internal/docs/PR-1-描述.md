# [codex] 实现 AI 同声传译助手 MVP

## 标题

实现 AI 同声传译助手 MVP。

## 功能描述

本 PR 上传项目当前完整源码和发布产物：本地 FastAPI 服务、系统音频监听、本地 Whisper 识别、免 key 中文翻译、桌面悬浮图标、桌面字幕浮层、视频/音频导入、字幕历史、TXT/SRT 导出、浏览器浮层原型、Windows EXE 打包配置、跨机器发布说明、参赛提交规范文档、模型权重、根目录 EXE、`_internal/` 运行目录、`dist/` 打包目录和 `release/` 发布压缩包。

## 本次改进

1. 字幕背景改为透明，并使用大字号白字加深色描边提升清晰度。
2. 实时音频块从 4 秒降到默认 2.2 秒，并增加翻译缓存，降低等待。
3. 增加口语化中文润色，减少生硬直译。
4. 增加实时修正记忆，相似识别结果会自动更新上一条字幕并提升 revision。
5. 悬浮球替换为高清圆形 3D 助手图标，提供多尺寸 PNG 和 ICO。
6. 退出流程先停止翻译并收起所有浮窗，修复退出残留白框。
7. README 从头到尾更新，补充最新功能、配置、发布方式和依赖说明。
8. 补充 Windows 可信签名发布门禁，避免未签名 EXE 被 Smart App Control 拦截后仍被当作正式包。

## 实现思路

- 后端使用 FastAPI、Pydantic 和 WebSocket 提供本地服务与字幕流。
- Windows 后台同传使用 PyAudioWPatch WASAPI loopback 读取系统播放音频。
- ASR 使用 faster-whisper 本地模型，翻译使用 deep-translator 免 key 在线翻译。
- 桌面交互使用 Tkinter 实现置顶悬浮按钮、拖动和字幕浮层。
- 打包使用 PyInstaller one-dir 模式，并补充版本信息、运行库、签名脚本和发布说明。
- 大体积模型、EXE、DLL 和发布 zip 通过 Git LFS 上传，避免触发 GitHub 普通 Git 单文件大小限制。
- 桌面字幕改用透明 Tk 窗口和 Canvas 描边文字，悬浮球使用透明 PNG 资源。
- 实时翻译增加 `RealtimeCorrectionMemory`，用相似度判断修正同一字幕片段。
- Windows 正式发布改为 `build-windows-release.ps1` 流程，默认要求 Authenticode 签名和验签；`-SkipSignature` 仅允许本机开发自测。

## 测试方式

- `python -m pytest`
- `python -m ruff check .`
- 重新打包 Windows EXE 并刷新根目录、`dist/`、`_internal/` 和 `release/` 产物。
- 检查 Git LFS 对象上传完成，并确认 PR 分支包含 `release/AI-Simultaneous-Interpreter-windows.zip`。
- 运行 `verify-release-signature.ps1`，确认当前未签名 EXE 会被发布门禁拦截。
- 手动运行 EXE，点击悬浮图标开启/关闭字幕。
- 手动打开网页工作台上传视频/音频并验证字幕生成和导出。

## 依赖与原创说明

- 新增第三方依赖：FastAPI、Uvicorn、Pydantic、PyAudioWPatch、faster-whisper、deep-translator、numpy、python-multipart、pytest、ruff。
- 原创功能部分：桌面悬浮控制、系统音频同传管线、字幕片段修正模型、媒体导入字幕工作台、字幕导出、Windows 打包发布流程和参赛过程文档。
- 复用过往代码及来源：未复用个人过往代码；浏览器扩展为本项目内原型实现。

## 开发过程说明

当前仓库此前只有 `main` 的初始提交，本 PR 是本地项目首次上传到 GitHub。已在 `docs/PR提交记录与补交方案.md` 中如实记录当前 PR/commit 状态和后续建议拆分方案，不伪造历史 PR 或 commit 时间。
