# PR 提交记录与补交方案

## 当前审计结论

审计时间：2026-06-05，时区 Asia/Shanghai。

当前本地仓库状态：

- 当前分支：`codex/init-mvp`
- 本地提交历史：无 commit
- 本地 PR 记录：无
- 远端地址：`https://github.com/primecc/AI-Simultaneous-Interpretation-Assistant.git`
- `gh` 命令：当前机器未安装，无法通过 GitHub CLI 查询 PR
- `git ls-remote`：当前环境连接 GitHub 超时，无法验证远端分支
- GitHub 网页访问：当前环境无法打开该仓库页面，疑似仓库未公开或网络不可达

结论：当前环境下没有可验证的 PR 记录，也没有本地 commit 记录。后续不能伪造历史 PR、不能回填虚假的 commit 时间，只能如实记录已有开发内容，并从现在开始按功能拆分 commit 与 PR。

## 上传结果

上传时间：2026-06-05，时区 Asia/Shanghai。

- 分支：`codex/init-mvp`
- 基准分支：`main`
- 首次功能提交：`5627676 feat: implement AI simultaneous interpretation assistant MVP`
- 发布产物提交：`a079907 build: upload packaged application artifacts`
- Pull Request：[#1 Implement AI simultaneous interpretation assistant MVP](https://github.com/primecc/AI-Simultaneous-Interpretation-Assistant/pull/1)
- PR 状态：Draft

说明：该 PR 是本地项目首次上传到 GitHub 后形成的真实 PR 记录。上方“当前审计结论”保留上传前的审计事实，用于说明此前没有可验证 PR 记录；本节记录上传后的结果。用户要求“所有文件全都上传”后，已通过 Git LFS 补充上传模型权重、根目录 EXE、`_internal/` 运行目录、`dist/` 打包目录和 `release/` 发布压缩包。

## 已完成变更记录

### 1. 项目规则与需求文档

涉及文件：

- `作品评审规则.md`
- `参赛提交与开发规范.md`
- `docs/需求清单与执行方案.md`
- `docs/开发路线图.md`

功能描述：

- 整理作品评分标准、参赛提交规则、PR 规范和 README/demo 要求。
- 针对“AI 同声传译助手”题目形成需求清单和可执行开发方案。
- 约束后续开发按照完整度、创新性、开发质量、PR 质量和演示表达推进。

实现思路：

- 将比赛规则沉淀为项目内文档。
- 将产品需求拆成音频采集、ASR、翻译、字幕修正、桌面悬浮控制、媒体导入、打包发布等模块。

验证方式：

- 检查文档可读性和规则覆盖度。
- 确认 README 中包含依赖、原创功能说明和 demo 视频占位。

### 2. FastAPI 本地服务与字幕数据模型

涉及文件：

- `src/simultaneous_interpreter/main.py`
- `src/simultaneous_interpreter/models.py`
- `src/simultaneous_interpreter/config.py`
- `src/simultaneous_interpreter/services/subtitle_store.py`
- `tests/test_api.py`
- `tests/test_subtitle_store.py`

功能描述：

- 提供本地 API、WebSocket 字幕流、启动/停止翻译接口。
- 定义字幕片段、翻译状态、修正版本等核心数据结构。
- 支持同一字幕片段后续修正，保留 `segment_id`、`revision` 和 corrected 标记。

实现思路：

- 使用 FastAPI 承载本地服务。
- 使用 Pydantic 定义请求、响应和字幕片段模型。
- 使用内存字幕存储管理实时字幕、历史字幕和修正版本。

验证方式：

- `python -m pytest tests/test_api.py tests/test_subtitle_store.py`

### 3. 视频/音频导入与字幕导出

涉及文件：

- `src/simultaneous_interpreter/services/media_library.py`
- `src/simultaneous_interpreter/services/media_interpreter.py`
- `src/simultaneous_interpreter/services/exporter.py`
- `src/simultaneous_interpreter/static/index.html`
- `src/simultaneous_interpreter/static/app.js`
- `src/simultaneous_interpreter/static/styles.css`
- `tests/test_exporter.py`

功能描述：

- 支持上传本地视频或音频文件。
- 在网页工作台播放媒体并生成中文字幕。
- 支持导出 TXT 和 SRT 字幕。

实现思路：

- 后端保存上传媒体并调用本地识别、翻译管线。
- 前端提供媒体导入、播放器字幕覆盖、字幕历史和导出入口。
- 导出服务按字幕时间轴生成 TXT/SRT。

验证方式：

- `python -m pytest tests/test_exporter.py`
- 手动打开 `http://127.0.0.1:8000` 上传媒体文件验证字幕生成流程。

### 4. 系统音频实时同传管线

涉及文件：

- `src/simultaneous_interpreter/services/system_audio_translator.py`
- `src/simultaneous_interpreter/services/local_runtime.py`
- `tests/test_system_audio_translator.py`
- `tests/test_local_runtime.py`

功能描述：

- 读取 Windows 系统正在播放的声音，例如网页、网课、会议软件或本地播放器。
- 使用本地 Whisper 识别英文语音。
- 使用 Google/MyMemory 免 key 在线翻译通道生成中文字幕。
- 翻译网络异常时显示短提示并继续监听系统音频。
- 使用智能语义断句缓冲合并 ASR 碎片，减少固定音频块导致的不必要断句。
- 缺失 VAD 资源时自动降级，避免程序直接崩溃。

实现思路：

- 使用 PyAudioWPatch 的 WASAPI loopback 捕获系统输出音频。
- 使用 faster-whisper 进行本地 ASR。
- 默认使用 beam=3 / best_of=3 提升识别稳定性。
- 使用 deep-translator 提供 Google/MyMemory 免 key 翻译容错。
- 打包环境下优先加载内置 `models/faster-whisper-tiny.en` 模型。

验证方式：

- `python -m pytest tests/test_system_audio_translator.py tests/test_local_runtime.py`
- 手动播放英文视频，点击桌面悬浮按钮验证字幕流。

### 5. 桌面悬浮图标与字幕浮层

涉及文件：

- `src/simultaneous_interpreter/desktop_launcher.py`
- `src/simultaneous_interpreter/desktop_overlay.py`
- `src/simultaneous_interpreter/assets/app-icon.png`
- `src/simultaneous_interpreter/assets/app-icon.ico`
- `src/simultaneous_interpreter/assets/app-icon-64.png`
- `src/simultaneous_interpreter/assets/app-icon-launcher-96.png`
- `assets/app-icon.png`
- `assets/app-icon.ico`
- `assets/app-icon-64.png`
- `assets/ai-interpreter-creative-icon-2048.png`
- `tests/test_desktop_overlay.py`

功能描述：

- 启动 EXE 后显示可拖动悬浮图标。
- 点击图标开启/关闭后台同传。
- 悬浮按钮使用 2048 原图生成的高清图标，并带拖影效果。
- 字幕条恢复为最初版深色半透明样式，可拖动并记住位置。

实现思路：

- 使用 Tkinter 创建置顶无边框桌面窗体。
- 使用 Windows 鼠标状态轮询增强悬浮按钮和字幕条拖动稳定性。
- 使用 96px 专用悬浮窗图标直显，避免小图拉伸和边缘彩边。
- 使用独立 Tk Label 字幕窗体显示实时中文字幕。
- 将位置保存到本地 JSON 文件，避免下次启动回到默认位置。

验证方式：

- `python -m pytest tests/test_desktop_overlay.py`
- 手动运行 EXE，拖动按钮和字幕条，重启后检查位置保持。

### 6. 浏览器浮层原型

涉及文件：

- `browser-extension/manifest.json`
- `browser-extension/content.js`
- `browser-extension/overlay.css`
- `docs/浏览器浮层使用说明.md`
- `tests/test_browser_extension.py`

功能描述：

- 保留浏览器内容脚本浮层原型。
- 当前主方案已改为桌面级系统音频监听，不依赖浏览器扩展。

实现思路：

- 浏览器扩展用于早期验证网页字幕浮层交互。
- 后续主路径通过桌面 EXE 监听系统音频，覆盖网页和软件播放场景。

验证方式：

- `python -m pytest tests/test_browser_extension.py`

### 7. EXE 打包与跨机器发布

涉及文件：

- `packaging/AI-Simultaneous-Interpreter.spec`
- `packaging/version_info.txt`
- `packaging/build-windows-release.ps1`
- `packaging/sign-release.ps1`
- `packaging/verify-release-signature.ps1`
- `packaging/Windows-EXE-使用说明.md`
- `docs/跨机器发布方案.md`
- `models/faster-whisper-tiny.en/`
- `AI同声传译助手.exe`
- `EXE使用说明.md`

功能描述：

- 生成 Windows 桌面 EXE。
- 将模型、VAD 资源、图标、静态页面、文档和 VC++ 运行库纳入打包。
- 提供强制签名发布脚本、代码签名脚本、验签脚本和跨机器发布说明。

实现思路：

- 使用 PyInstaller one-dir 模式打包。
- 在 spec 中收集 `faster_whisper` assets、内置模型、应用静态资源和运行时 DLL。
- 对 Smart App Control 场景给出可信代码签名方案，并把未签名包拦截为发布门禁。

验证方式：

- `python -m PyInstaller packaging\AI-Simultaneous-Interpreter.spec --noconfirm --clean`
- `.\packaging\verify-release-signature.ps1`
- 检查 `_internal\models\faster-whisper-tiny.en\model.bin`
- 检查 `_internal\faster_whisper\assets\silero_vad_v6.onnx`
- 检查 `_internal\vcruntime140.dll` 和 `_internal\msvcp140.dll`

### 8. 测试与代码质量

涉及文件：

- `pyproject.toml`
- `tests/`

功能描述：

- 添加单元测试覆盖 API、字幕存储、导出、浏览器扩展结构、桌面浮层和本地运行时。
- 配置 Ruff 保持代码风格一致。

实现思路：

- 使用 pytest 做核心逻辑回归测试。
- 使用 Ruff 检查导入、语法、现代 Python 写法和常见 bug。

验证方式：

- `python -m pytest`
- `python -m ruff check .`

最近一次验证结果：

- `pytest`：17 passed
- `ruff`：All checks passed

## 建议补交 PR 拆分

如果当前仓库还没有 PR 记录，建议从现在开始按以下顺序拆分补交。每个 PR 都必须真实 commit、真实推送、真实创建，不能改写时间或伪造历史。

### PR 1：初始化项目规则、需求文档与开发规范

标题：

```text
docs: add project rules, requirements, and delivery plan
```

功能描述：

- 新增作品评审规则、参赛提交规范、需求清单和开发路线图。

实现思路：

- 将比赛要求拆解成项目内可执行文档。

测试方式：

- 检查文档内容完整、无乱码、规则覆盖 README/demo/PR/commit 要求。

### PR 2：搭建 FastAPI 服务和字幕核心模型

标题：

```text
feat(api): add local subtitle service and data models
```

功能描述：

- 新增本地服务、字幕模型、字幕存储和 WebSocket 字幕流。

实现思路：

- 使用 FastAPI + Pydantic 建立后端基础架构。

测试方式：

- `python -m pytest tests/test_api.py tests/test_subtitle_store.py`

### PR 3：支持媒体文件导入、播放字幕和导出

标题：

```text
feat(media): add media import, subtitle playback, and export
```

功能描述：

- 支持导入视频/音频文件、生成字幕、覆盖显示字幕并导出 TXT/SRT。

实现思路：

- 后端保存上传文件并处理字幕，前端提供播放器和导出操作。

测试方式：

- `python -m pytest tests/test_exporter.py`
- 手动上传媒体文件验证字幕展示。

### PR 4：接入系统音频监听、本地 ASR 和翻译

标题：

```text
feat(audio): add system audio translation pipeline
```

功能描述：

- 监听电脑正在播放的声音，自动识别英文并翻译成中文字幕。

实现思路：

- 使用 PyAudioWPatch WASAPI loopback 采集系统音频。
- 使用 faster-whisper 本地识别。
- 使用 deep-translator 免 key 翻译。

测试方式：

- `python -m pytest tests/test_system_audio_translator.py tests/test_local_runtime.py`
- 手动播放英文网页视频验证实时字幕。

### PR 5：新增桌面悬浮按钮、拖动和字幕浮层

标题：

```text
feat(desktop): add draggable floating control and caption overlay
```

功能描述：

- 启动后显示桌面悬浮图标，点击控制同传开关。
- 支持按钮拖动、拖影效果和字幕条拖动。

实现思路：

- 使用 Tkinter 创建置顶桌面窗体和字幕窗体。
- 保存位置配置，提升重复使用体验。

测试方式：

- `python -m pytest tests/test_desktop_overlay.py`
- 手动拖动悬浮按钮和字幕条验证交互。

### PR 6：补充浏览器浮层原型和测试

标题：

```text
feat(extension): add browser subtitle overlay prototype
```

功能描述：

- 保留浏览器端字幕浮层原型，用作展示和扩展方向。

实现思路：

- 使用 Manifest V3 内容脚本注入字幕浮层。

测试方式：

- `python -m pytest tests/test_browser_extension.py`

### PR 7：完善 EXE 打包和跨机器发布方案

标题：

```text
build(windows): package desktop app with bundled runtime assets
```

功能描述：

- 新增 PyInstaller 打包配置、版本信息、强制签名发布脚本、签名脚本、验签脚本和跨机器发布说明。
- 内置模型、VAD 资源、图标和 VC++ 运行库。

实现思路：

- 使用 PyInstaller one-dir 模式打包。
- 明确未签名 EXE 在 Smart App Control 下的风险和代码签名方案；正式发布脚本默认要求签名并验签。

测试方式：

- `python -m PyInstaller packaging\AI-Simultaneous-Interpreter.spec --noconfirm --clean`
- `.\packaging\verify-release-signature.ps1`
- 检查生成 EXE 和 `_internal` 关键资源。

### PR 8：补充 README、依赖说明和最终测试

标题：

```text
docs: update README with usage, dependencies, and demo notes
```

功能描述：

- 完善 README 的功能说明、安装启动、依赖、原创功能、demo 视频入口和发布说明。

实现思路：

- 按参赛提交要求整理 README。

测试方式：

- `python -m pytest`
- `python -m ruff check .`
- 手动运行 EXE 和网页工作台。

## 后续提交纪律

- 每个 PR 只做一件事。
- 每个 PR 描述必须包含标题、功能描述、实现思路、测试方式、依赖与原创说明。
- 不提交 `_internal/`、`dist/`、`build/`、`release/`、运行日志和本地位置文件。
- 大体积发布包应放 GitHub Release 或外部网盘，不应直接作为源码 PR 内容。
- 如提交内置模型，必须在 README 和 PR 描述中说明来源、用途和原创边界。
- 不能改写 commit 时间戳，也不能把已有开发说成过去已经有 PR。
