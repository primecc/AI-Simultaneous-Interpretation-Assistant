# AI 同声传译助手

面向英语演讲、技术分享、国际会议和网课场景的桌面同传工具。启动后显示一个可拖动的“译”悬浮图标，点击后直接听取电脑正在播放的网页或软件声音，识别英文语音并显示中文字幕。

## 当前能力

- Windows 桌面悬浮“译”图标，一键开启/关闭字幕
- 通过 WASAPI loopback 读取系统播放音频，不需要浏览器扩展
- 本地 Whisper 语音识别，不需要填写 API key
- 免 key 中文翻译
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

1. 屏幕上出现可拖动的“译”悬浮图标。
2. 打开哔哩哔哩、网课、会议网页或任意播放英文声音的软件。
3. 点击“译”图标开启字幕。
4. 字幕显示在屏幕底部。
5. 再点击一次“译”图标关闭字幕。

首次运行会自动准备本地识别模型。无需填写 OpenAI API key，也不需要手动配置浏览器扩展。翻译使用免 key 的在线翻译通道，因此需要保持网络可用。

源码仓库不直接提交大体积模型权重文件。开发运行时默认使用 `tiny.en` 自动下载；发布 EXE 时，如果本地存在完整的 `models/faster-whisper-tiny.en/model.bin`，打包脚本会自动将模型内置到发布包。

## 软件内导入视频/音频

右键“译”图标，选择“打开软件界面”，或打开：

```text
http://127.0.0.1:8000
```

在网页工作台里选择本地视频或音频文件，然后点击“播放并生成字幕”。系统会对该媒体文件做本地语音识别，并生成中文字幕，字幕可导出为 TXT 或 SRT。

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

## Windows EXE 打包

```powershell
python -m pip install pyinstaller
python -m PyInstaller packaging\AI-Simultaneous-Interpreter.spec --noconfirm --clean
```

构建结果：

```text
dist\AI-Simultaneous-Interpreter\AI-Simultaneous-Interpreter.exe
```

跨机器发布请看 [跨机器发布方案](docs/跨机器发布方案.md)。未签名 EXE 在开启 Smart App Control 的 Windows 11 机器上可能会被阻止；要稳定分发，需要使用可信代码签名证书签名。

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
- pytest / ruff：测试与代码检查

## 原创功能说明

项目核心实现包含桌面悬浮字幕控制、本地系统音频采集、本地语音识别、字幕片段存储、字幕导出，以及对同一字幕片段的修正版管理。每条字幕保留稳定的 `segment_id` 与 `revision`，后续识别结果可更新已有字幕并标记为 corrected。

## Demo 视频

待录制并上传。提交前需要将可播放链接补充到这里。
