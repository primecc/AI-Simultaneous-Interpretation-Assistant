(() => {
  const ROOT_ID = "ai-si-overlay-root";
  const WS_URL = "ws://127.0.0.1:8000/ws/interpret?source=browser-overlay";
  const POSITION_KEY = "ai-si-overlay-position";

  if (document.getElementById(ROOT_ID)) {
    return;
  }

  const host = document.createElement("div");
  host.id = ROOT_ID;
  document.documentElement.appendChild(host);

  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host {
        all: initial;
        color-scheme: light;
        font-family: Inter, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      }

      .launcher {
        position: fixed;
        z-index: 2147483647;
        right: 28px;
        bottom: 96px;
        display: grid;
        place-items: center;
        width: 54px;
        height: 54px;
        border: 1px solid rgba(12, 92, 160, 0.38);
        border-radius: 999px;
        background: #0f78c9;
        color: #fff;
        box-shadow: 0 18px 44px rgba(15, 42, 72, 0.24);
        cursor: grab;
        user-select: none;
      }

      .launcher:active {
        cursor: grabbing;
      }

      .launcher-text {
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 0;
      }

      .launcher-dot {
        position: absolute;
        right: 7px;
        top: 7px;
        width: 10px;
        height: 10px;
        border: 2px solid #fff;
        border-radius: 999px;
        background: #9ca3af;
      }

      .launcher-dot.is-live {
        background: #15a46f;
      }

      .launcher-dot.is-error {
        background: #dc3d32;
      }

      .panel {
        position: fixed;
        z-index: 2147483647;
        right: 28px;
        bottom: 164px;
        display: grid;
        gap: 10px;
        width: min(420px, calc(100vw - 28px));
        max-height: min(520px, calc(100vh - 120px));
        padding: 14px;
        border: 1px solid rgba(202, 213, 226, 0.94);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.96);
        box-shadow: 0 22px 72px rgba(20, 31, 48, 0.22);
        color: #172033;
      }

      .panel[hidden] {
        display: none;
      }

      .panel-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }

      .title {
        margin: 0;
        font-size: 15px;
        font-weight: 780;
      }

      .status {
        color: #607086;
        font-size: 12px;
        white-space: nowrap;
      }

      .controls {
        display: flex;
        gap: 8px;
      }

      button {
        min-height: 34px;
        padding: 0 12px;
        border-radius: 8px;
        font: inherit;
        font-size: 13px;
        cursor: pointer;
      }

      .primary {
        border: 1px solid #0f6fb7;
        background: #0f78c9;
        color: #fff;
      }

      .ghost {
        border: 1px solid #c6d1de;
        background: #fff;
        color: #25364d;
      }

      .caption-list {
        display: grid;
        gap: 8px;
        margin: 0;
        padding: 0;
        overflow: auto;
        max-height: 350px;
        list-style: none;
      }

      .empty {
        display: grid;
        min-height: 96px;
        place-items: center;
        border: 1px dashed #c7d1dc;
        border-radius: 8px;
        color: #607086;
        font-size: 13px;
        text-align: center;
      }

      .caption {
        display: grid;
        gap: 5px;
        padding: 10px 11px;
        border: 1px solid #dce3eb;
        border-left: 4px solid #8d99a8;
        border-radius: 8px;
        background: #fff;
      }

      .caption[data-status="partial"] {
        border-left-color: #c88719;
      }

      .caption[data-status="final"] {
        border-left-color: #168a58;
      }

      .caption[data-status="corrected"] {
        border-left-color: #0f78c9;
      }

      .source {
        margin: 0;
        color: #5b6879;
        font-size: 13px;
        line-height: 1.45;
      }

      .translation {
        margin: 0;
        color: #151f2e;
        font-size: 18px;
        font-weight: 720;
        line-height: 1.45;
      }

      .meta {
        color: #7a8798;
        font-size: 11px;
      }

      @media (max-width: 520px) {
        .panel {
          right: 14px;
          left: 14px;
          width: auto;
        }
      }
    </style>

    <button class="launcher" type="button" aria-label="AI 同声传译浮层">
      <span class="launcher-text">译</span>
      <span class="launcher-dot" aria-hidden="true"></span>
    </button>

    <section class="panel" hidden aria-label="AI 同声传译字幕">
      <div class="panel-header">
        <div>
          <p class="title">AI 同声传译</p>
          <span class="status">未连接</span>
        </div>
        <div class="controls">
          <button class="primary start" type="button">开启</button>
          <button class="ghost stop" type="button">关闭</button>
        </div>
      </div>
      <div class="empty">开启后将在当前网页上显示实时中文字幕。</div>
      <ol class="caption-list"></ol>
    </section>
  `;

  const launcher = root.querySelector(".launcher");
  const panel = root.querySelector(".panel");
  const dot = root.querySelector(".launcher-dot");
  const statusText = root.querySelector(".status");
  const startButton = root.querySelector(".start");
  const stopButton = root.querySelector(".stop");
  const empty = root.querySelector(".empty");
  const captionList = root.querySelector(".caption-list");

  let socket = null;
  let didDrag = false;
  let pointerOffset = { x: 0, y: 0 };
  const renderedSegments = new Map();

  restorePosition();

  launcher.addEventListener("pointerdown", (event) => {
    didDrag = false;
    launcher.setPointerCapture(event.pointerId);
    const rect = launcher.getBoundingClientRect();
    pointerOffset = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
  });

  launcher.addEventListener("pointermove", (event) => {
    if (!launcher.hasPointerCapture(event.pointerId)) {
      return;
    }
    didDrag = true;
    moveLauncher(event.clientX - pointerOffset.x, event.clientY - pointerOffset.y);
  });

  launcher.addEventListener("pointerup", (event) => {
    if (launcher.hasPointerCapture(event.pointerId)) {
      launcher.releasePointerCapture(event.pointerId);
    }
    persistPosition();
    if (!didDrag) {
      panel.hidden = !panel.hidden;
      syncPanelPosition();
    }
  });

  startButton.addEventListener("click", () => {
    renderedSegments.clear();
    captionList.replaceChildren();
    empty.hidden = false;
    connect();
  });

  stopButton.addEventListener("click", () => {
    disconnect();
    setStatus("idle", "已关闭");
  });

  function connect() {
    disconnect();
    setStatus("connecting", "连接本地服务中");
    socket = new WebSocket(WS_URL);

    socket.addEventListener("open", () => {
      setStatus("live", "同传字幕开启中");
    });

    socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data);
      if (payload.event === "subtitle.upsert") {
        renderSegment(payload.segment);
      }
    });

    socket.addEventListener("close", () => {
      setStatus("idle", "连接已关闭");
    });

    socket.addEventListener("error", () => {
      setStatus("error", "无法连接本地服务");
    });
  }

  function disconnect() {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close();
    }
    socket = null;
  }

  function renderSegment(segment) {
    empty.hidden = true;
    let item = renderedSegments.get(segment.segment_id);

    if (!item) {
      item = document.createElement("li");
      item.className = "caption";
      item.innerHTML = `
        <p class="source"></p>
        <p class="translation"></p>
        <span class="meta"></span>
      `;
      renderedSegments.set(segment.segment_id, item);
      captionList.appendChild(item);
    }

    item.dataset.status = segment.status;
    item.querySelector(".source").textContent = segment.source_text;
    item.querySelector(".translation").textContent = segment.translated_text;
    item.querySelector(".meta").textContent = statusLabel(segment);
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

  function setStatus(state, label) {
    dot.className = "launcher-dot";
    if (state === "live") {
      dot.classList.add("is-live");
    }
    if (state === "error") {
      dot.classList.add("is-error");
    }
    statusText.textContent = label;
  }

  function moveLauncher(left, top) {
    const clampedLeft = clamp(left, 8, window.innerWidth - launcher.offsetWidth - 8);
    const clampedTop = clamp(top, 8, window.innerHeight - launcher.offsetHeight - 8);
    launcher.style.left = `${clampedLeft}px`;
    launcher.style.top = `${clampedTop}px`;
    launcher.style.right = "auto";
    launcher.style.bottom = "auto";
    syncPanelPosition();
  }

  function syncPanelPosition() {
    const rect = launcher.getBoundingClientRect();
    const panelWidth = Math.min(420, window.innerWidth - 28);
    const left = clamp(rect.left + rect.width - panelWidth, 14, window.innerWidth - panelWidth - 14);
    const top = rect.top > 540 ? rect.top - 532 : rect.bottom + 10;
    panel.style.left = `${left}px`;
    panel.style.right = "auto";
    panel.style.top = `${clamp(top, 14, window.innerHeight - 120)}px`;
    panel.style.bottom = "auto";
  }

  function persistPosition() {
    const rect = launcher.getBoundingClientRect();
    try {
      window.localStorage.setItem(
        POSITION_KEY,
        JSON.stringify({ left: Math.round(rect.left), top: Math.round(rect.top) }),
      );
    } catch {
      // Some pages disable localStorage; the overlay still works without persistence.
    }
  }

  function restorePosition() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(POSITION_KEY) || "null");
      if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) {
        requestAnimationFrame(() => moveLauncher(saved.left, saved.top));
      }
    } catch {
      // Ignore invalid or unavailable persisted state.
    }
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }
})();
