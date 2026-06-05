const startButton = document.querySelector("#startButton");
const clearButton = document.querySelector("#clearButton");
const mediaInput = document.querySelector("#mediaInput");
const mediaName = document.querySelector("#mediaName");
const mediaPlayer = document.querySelector("#mediaPlayer");
const liveCaption = document.querySelector("#liveCaption");
const liveSource = document.querySelector(".live-source");
const liveTranslation = document.querySelector(".live-translation");
const list = document.querySelector("#subtitleList");
const emptyState = document.querySelector("#emptyState");
const connectionDot = document.querySelector("#connectionDot");
const connectionText = document.querySelector("#connectionText");

let socket = null;
let selectedMedia = null;
const renderedSegments = new Map();

loadLatestMedia();

mediaInput.addEventListener("change", async () => {
  const file = mediaInput.files?.[0];
  if (!file) {
    return;
  }
  await uploadMedia(file);
});

startButton.addEventListener("click", async () => {
  if (!selectedMedia) {
    setStatus("error", "请先选择媒体");
    return;
  }
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
  }
  await clearSubtitles();
  try {
    await mediaPlayer.play();
  } catch {
    setStatus("connecting", "字幕处理中");
  }
  connectMediaStream(selectedMedia.media_id);
});

clearButton.addEventListener("click", async () => {
  await clearSubtitles();
});

async function uploadMedia(file) {
  setStatus("connecting", "上传中");
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/media", {
    method: "POST",
    body,
  });

  if (!response.ok) {
    const message = await response.text();
    setStatus("error", "上传失败");
    throw new Error(message);
  }

  selectMediaAsset(await response.json(), file.name);
  setStatus("idle", "媒体已就绪");
}

async function loadLatestMedia() {
  const response = await fetch("/api/media");
  if (!response.ok) {
    return;
  }
  const assets = await response.json();
  const latest = assets.at(-1);
  if (latest) {
    selectMediaAsset(latest, latest.filename);
    setStatus("idle", "媒体已就绪");
  }
}

function selectMediaAsset(asset, displayName) {
  selectedMedia = asset;
  mediaName.textContent = displayName;
  mediaPlayer.src = asset.url;
  mediaPlayer.hidden = false;
  startButton.disabled = false;
}

async function clearSubtitles() {
  await fetch("/api/subtitles/clear", { method: "POST" });
  renderedSegments.clear();
  list.replaceChildren();
  emptyState.hidden = false;
  liveCaption.hidden = true;
}

function connectMediaStream(mediaId) {
  setStatus("connecting", "连接中");
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const params = new URLSearchParams({ media_id: mediaId });
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/interpret?${params}`);

  socket.addEventListener("open", () => {
    setStatus("live", "正在识别翻译");
  });

  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.event === "subtitle.upsert") {
      renderSegment(payload.segment);
    }
    if (payload.event === "status") {
      setStatus(payload.state || "idle", payload.message || "字幕处理完成");
    }
  });

  socket.addEventListener("close", () => {
    setStatus("idle", "字幕处理结束");
  });

  socket.addEventListener("error", () => {
    setStatus("error", "连接异常");
  });
}

function renderSegment(segment) {
  emptyState.hidden = true;
  let item = renderedSegments.get(segment.segment_id);

  if (!item) {
    item = document.createElement("li");
    item.className = "subtitle-item";
    item.innerHTML = `
      <p class="source-line"></p>
      <p class="translation-line"></p>
      <div class="meta-line">
        <span class="status-text"></span>
        <span class="time-text"></span>
      </div>
    `;
    renderedSegments.set(segment.segment_id, item);
    list.appendChild(item);
  }

  item.dataset.status = segment.status;
  item.querySelector(".source-line").textContent = segment.source_text;
  item.querySelector(".translation-line").textContent = segment.translated_text;
  item.querySelector(".status-text").textContent = statusLabel(segment);
  item.querySelector(".time-text").textContent = formatRange(segment.start_ms, segment.end_ms);
  liveCaption.hidden = false;
  liveCaption.dataset.status = segment.status;
  liveSource.textContent = segment.source_text;
  liveTranslation.textContent = segment.translated_text;
  item.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function statusLabel(segment) {
  const labels = {
    partial: "临时识别",
    final: "最终字幕",
    corrected: `已自动修正 · 第 ${segment.revision} 版`,
  };
  return labels[segment.status] || segment.status;
}

function formatRange(startMs, endMs) {
  const start = formatSeconds(startMs);
  const end = formatSeconds(endMs ?? startMs + 3000);
  return `${start} - ${end}`;
}

function formatSeconds(ms) {
  return `${(ms / 1000).toFixed(1)}s`;
}

function setStatus(state, label) {
  connectionDot.className = "dot";
  if (state === "live") {
    connectionDot.classList.add("is-live");
  }
  if (state === "error") {
    connectionDot.classList.add("is-error");
  }
  connectionText.textContent = label;
}
