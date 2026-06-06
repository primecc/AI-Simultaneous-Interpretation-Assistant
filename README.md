# AI 同声传译助手

面向英语演讲、技术分享、国际会议和网课场景的桌面同传工具。启动后显示一个可拖动的高清圆角悬浮图标，点击后直接听取电脑正在播放的网页或软件声音，识别英文语音并以最初版深色半透明字幕条显示中文翻译。

## 当前能力

- Windows 桌面高清圆角悬浮图标，一键开启/关闭字幕
- 通过 WASAPI loopback 读取系统播放音频，不需要浏览器扩展
- 本地 Whisper 语音识别，不需要填写 API key
- 低延迟免 key 中文翻译，默认 2.2 秒音频块
- 翻译网络容错：Google 免费通道失败后自动尝试 MyMemory，单次网络失败不会停止后台监听
- 口语化中文润色，减少直译感
- 实时字幕修正：相似片段会复用同一字幕 ID，并以 corrected/revision 标记自动修正
- 可拖动深色半透明桌面字幕条，沿用最初版清爽字幕样式
- 视频/音频文件导入、播放器字幕覆盖、字幕历史记录
- TXT 与 SRT 字幕导出
- FastAPI 本地服务与网页工作台
- 单元测试覆盖核心接口、字幕存储、导出和本地识别管线

## 直接使用 EXE

双击运行：

```text
AI-Simultaneous-Interpreter.exe
```

默认流程：

1. 屏幕上出现可拖动的高清 AI 同传悬浮图标。
2. 打开哔哩哔哩、网课、会议网页或任意播放英文声音的软件。
3. 点击悬浮图标开启后台同传。
4. 中文字幕显示在屏幕底部的深色半透明字幕条中，可拖动位置。
5. 再点击一次悬浮图标关闭字幕；右键可打开完整界面或退出。

首次运行会自动准备本地识别模型。无需填写 OpenAI API key，也不需要手动配置浏览器扩展。翻译使用免 key 的在线翻译通道，因此需要保持网络可用。

当前分支通过 Git LFS 提交了模型权重、Windows EXE、`_internal/` 运行目录、`dist/` 打包目录和 `release/` 发布压缩包，便于评审直接检查完整发布产物。开发运行时仍可使用 `tiny.en` 自动下载；发布 EXE 时，如果本地存在完整的 `models/faster-whisper-tiny.en/model.bin`，打包脚本会自动将模型内置到发布包。Smart App Control 拦截未知发布者是固定发布风险，正式发布必须使用可信代码签名证书签名。

## 最近改进

- 字幕浮层恢复为最初版深色半透明 Label 字幕条，并使用鼠标状态轮询修复不能拖动的问题。
- 翻译服务增加免 key 备用通道和失败降级提示，避免 Google 免费接口 SSL 断开时直接停止后台同传。
- 实时翻译从 4 秒块降到默认 2.2 秒块，并增加翻译缓存，降低重复翻译等待。
- 增加口语化中文润色，将生硬直译改成更自然的中文表达。
- 增加实时修正记忆：相似识别结果会更新上一条字幕，并显示“已自动修正第 N 版”。
- 悬浮图标替换为 2048 原图生成的高清圆角视觉，提供 16-2048 多尺寸 PNG、Windows ICO 和 96px 悬浮窗专用无彩边资源。
- 退出流程改为先停止翻译、收起字幕和拖影窗口，再销毁主窗口，修复退出残留白框问题。

## 软件内导入视频/音频

右键“译”图标，选择“打开软件界面”，或打开：

```text
http://127.0.0.1:8000
```

在网页工作台里选择本地视频或音频文件，然后点击“播放并生成字幕”。系统会对该媒体文件做本地语音识别，并生成中文字幕，字幕可导出为 TXT 或 SRT。

网页播放器中的字幕也恢复为最初版深色半透明背景；如果字幕被后续结果修正，会以蓝色描边提示修正状态。

## 开发启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn simultaneous_interpreter.main:app --reload
```

启动后打开：

```text
http://127.0.0.1:8000
```

可选配置写入 `.env`：

```text
LOCAL_ASR_MODEL=tiny.en
SOURCE_LANGUAGE=en
TARGET_LANGUAGE=zh
AUDIO_CHUNK_SECONDS=2.2
```

## Windows EXE 打包

```powershell
python -m pip install pyinstaller
python -m PyInstaller packaging\AI-Simultaneous-Interpreter.spec --noconfirm --clean
```

上面的命令只适合本机开发自测。正式发布必须使用可信代码签名证书：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\packaging\build-windows-release.ps1 `
  -CertificatePath "C:\path\to\certificate.pfx" `
  -CertificatePassword "证书密码" `
  -SignAllBinaries
```

如果证书在 Windows 证书库中，也可以使用：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\packaging\build-windows-release.ps1 `
  -CertificateThumbprint "证书指纹" `
  -SignAllBinaries
```

发布脚本会重新打包、同步根目录 EXE、执行 Authenticode 签名、验签，并生成 release zip。没有可信证书时脚本会失败，这是为了防止再次产出会被 Smart App Control 拦截的包。仅本机调试时才允许显式加 `-SkipSignature`。

构建结果：

```text
dist\AI-Simultaneous-Interpreter\AI-Simultaneous-Interpreter.exe
```

发布给评委或其他机器时，优先使用：

```text
release\AI-Simultaneous-Interpreter-windows.zip
```

也可以使用项目根目录的 `AI同声传译助手.exe`，但必须保留旁边的 `_internal/` 目录。

跨机器发布请看 [跨机器发布方案](docs/跨机器发布方案.md)。未签名 EXE 不能作为评审或对外发布包。

## 开发过程与 PR 记录

当前开发过程审计、已完成变更清单和后续 PR 拆分方案见 [PR 提交记录与补交方案](docs/PR提交记录与补交方案.md)。

## 测试

```powershell
python -m pytest
python -m ruff check .
```

## 第三方依赖

- FastAPI / Uvicorn：本地 API 与 WebSocket 服务
- PyAudioWPatch：Windows WASAPI loopback 系统音频读取
- faster-whisper：本地语音识别
- deep-translator：免 key 中文翻译
- numpy：音频切片与重采样
- Pydantic / Pydantic Settings：数据模型与配置
- python-multipart：视频/音频上传
- Git LFS：托管模型权重、EXE、DLL 和发布压缩包等大文件
- pytest / ruff：测试与代码检查

## 原创功能说明

项目核心实现包含桌面悬浮字幕控制、本地系统音频采集、本地语音识别、实时翻译缓存、口语化翻译润色、字幕片段存储、字幕导出，以及对同一字幕片段的修正版管理。每条可修正字幕保留稳定的 `segment_id` 与 `revision`，后续识别或翻译结果可更新已有字幕并标记为 corrected。

## Demo 视频

待录制并上传。提交前需要将可播放链接补充到这里。
