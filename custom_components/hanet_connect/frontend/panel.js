import { PANEL_CSS } from "./panel.css.js";

const TABS = [
  ["cameras", "Camera", "mdi:cctv"],
  ["events", "Sự kiện", "mdi:bell-ring-outline"],
  ["recordings", "Ghi hình", "mdi:filmstrip-box-multiple"],
  ["identity", "Danh tính", "mdi:face-recognition"],
  ["settings", "Cài đặt", "mdi:cog-outline"],
];

const KIND_LABELS = {
  employee: "Người nhà",
  visitor: "Người quen",
  stranger: "Người lạ",
  alarm: "Báo động",
  human: "Chuyển động",
  plate: "Biển số",
  checkin: "Chấm công",
  face: "Khuôn mặt",
  other: "Khác",
};

const GROUP_FOR_KIND = {
  alarm: "alarm",
  stranger: "stranger",
  employee: "employee",
  visitor: "known",
};

const SOURCE_LABELS = {
  cloud: "Cloud",
  cloud_poll: "Cloud",
  sse: "Trực tiếp",
  webhook: "Webhook",
  polling: "Polling",
};

const COMMAND_LABELS = {
  open_door: "Mở cửa",
  close_door: "Đóng cửa",
  alarm: "Bật còi",
  stop_alarm: "Tắt còi",
  up: "Lên",
  down: "Xuống",
  left: "Trái",
  right: "Phải",
  leftUp: "Lên trái",
  rightUp: "Lên phải",
  leftDown: "Xuống trái",
  rightDown: "Xuống phải",
  zoomIn: "Phóng to",
  zoomOut: "Thu nhỏ",
  autoScan: "Quét tự động",
  stop: "Dừng",
  presetSet: "Lưu vị trí",
  presetGo: "Đến vị trí",
};

const HOLD_COMMANDS = new Set([
  "up", "down", "left", "right",
  "leftUp", "rightUp", "leftDown", "rightDown",
  "zoomIn", "zoomOut",
]);

const PTZ_PAD = [
  ["leftUp", "mdi:arrow-top-left"], ["up", "mdi:arrow-up"], ["rightUp", "mdi:arrow-top-right"],
  ["left", "mdi:arrow-left"], ["stop", "mdi:stop"], ["right", "mdi:arrow-right"],
  ["leftDown", "mdi:arrow-bottom-left"], ["down", "mdi:arrow-down"], ["rightDown", "mdi:arrow-bottom-right"],
];

const SETTING_GROUP_ORDER = [
  "Hình ảnh & âm thanh",
  "Nhận diện",
  "Ghi hình & cảnh báo",
  "Thông báo",
  "PTZ",
  "Khác",
];

const commandLabel = (command) => COMMAND_LABELS[command] || command;

const truthy = (value) => (
  value === true
  || value === 1
  || ["1", "true", "yes", "on", "enabled", "active"].includes(String(value ?? "").toLocaleLowerCase())
);

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));

const localDay = (offset = 0) => {
  const date = new Date();
  date.setDate(date.getDate() - offset);
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
};

const timestampMs = (value) => {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number" || /^\d+$/.test(String(value))) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return null;
    return numeric < 100000000000 ? numeric * 1000 : numeric;
  }
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? null : parsed;
};

const dayFromValue = (value) => {
  const date = new Date(timestampMs(value) ?? NaN);
  if (Number.isNaN(date.getTime())) return localDay();
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
};

const dayTitle = (value) => {
  const [year, month, day] = String(value || "").split("-").map(Number);
  if (!year || !month || !day) return value || "";
  return new Intl.DateTimeFormat("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(year, month - 1, day, 12));
};

const fmtTime = (value) => {
  const timestamp = timestampMs(value);
  if (timestamp === null) return String(value || "");
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(timestamp));
};

const fmtClock = (value) => {
  const timestamp = timestampMs(value);
  if (timestamp === null) return String(value || "");
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp));
};

const relative = (value) => {
  const timestamp = timestampMs(value);
  if (timestamp === null) return "chưa có";
  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (seconds < 60) return `${seconds} giây trước`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  return fmtTime(timestamp);
};

const recordingDurationMs = (value) => {
  const duration = Number(value || 0);
  if (!Number.isFinite(duration) || duration <= 0) return 0;
  return duration > 86400 ? duration : duration * 1000;
};

const durationText = (value) => {
  const seconds = Math.round(recordingDurationMs(value) / 1000);
  if (!seconds) return "Video";
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes} phút ${seconds % 60} giây` : `${seconds} giây`;
};

const canonicalKind = (event) => {
  const kind = String(event?.kind || "").toLocaleLowerCase();
  return kind === "cloud_poll" ? "cloud" : kind || "other";
};

const canonicalSource = (event) => {
  const source = String(event?.source || "").toLocaleLowerCase();
  return source === "cloud_poll" ? "cloud" : source || "cloud";
};

const kindLabel = (event) =>
  event?.kind_name || KIND_LABELS[canonicalKind(event)] || event?.kind || "Sự kiện";

const eventTitle = (event) =>
  event?.person_name || event?.title || event?.person_title || kindLabel(event);

const sourceLabel = (event) => SOURCE_LABELS[canonicalSource(event)] || "Cloud";

const groupOf = (event) => {
  if (event.person_id && !["employee", "visitor", "stranger", "alarm"].includes(event.kind)) {
    return "known";
  }
  return GROUP_FOR_KIND[event.kind] || "motion";
};

const eventSearchText = (event) =>
  [eventTitle(event), event.person_title, kindLabel(event), event.device_name, event.place_name, event.source]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase("vi");

const art = (src, alt, fallback = "", cls = "") =>
  src
    ? `<img class="hc-img ${cls}" src="${esc(src)}" ${fallback ? `data-fallback="${esc(fallback)}"` : ""} alt="${esc(alt)}" loading="lazy">`
    : `<div class="hc-media-placeholder"><ha-icon icon="mdi:image-off-outline"></ha-icon><span>Không có ảnh</span></div>`;

const fileToDataUrl = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("Không đọc được ảnh"));
    reader.readAsDataURL(file);
  });

const mergeRows = (first, second) => {
  const seen = new Set();
  const rows = [];
  for (const row of [...first, ...second]) {
    const key = String(row.id || [
      row.device_id, row.person_id, row.occurred_at, row.received_at, row.image_url,
    ].join("|"));
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    rows.push(row);
  }
  rows.sort((a, b) =>
    String(b.occurred_at || b.received_at || "").localeCompare(
      String(a.occurred_at || a.received_at || ""),
    ));
  return rows;
};

class HanetConnectPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._data = null;
    this._tab = "cameras";
    this._loading = false;
    this._error = "";
    this._timer = null;
    this._dialog = null;
    this._renderStamp = Date.now();
    this._cameraSearch = "";
    this._identitySearch = "";
    this._identityType = "";
    this._events = {
      day: localDay(), rows: [], loaded: false, loading: false, error: "",
      limit: 60, search: "", device: "", kind: "", source: "",
    };
    this._recordings = {
      day: localDay(), clips: [], loaded: false, loading: false, error: "",
      limit: 48, search: "", device: "", period: "",
    };
    this._eventsRequest = 0;
    this._recordingsRequest = 0;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._data && !this._loading) this.load();
  }

  applyPanelStyles() {
    let applied = false;
    try {
      if (
        "adoptedStyleSheets" in this.shadowRoot
        && typeof CSSStyleSheet !== "undefined"
        && "replaceSync" in CSSStyleSheet.prototype
      ) {
        const sheet = new CSSStyleSheet();
        sheet.replaceSync(PANEL_CSS);
        this.shadowRoot.adoptedStyleSheets = [sheet];
        applied = true;
      }
    } catch (error) {
      applied = false;
    }
    if (applied) return;
    if (this.shadowRoot.querySelector("style[data-panel-css]")) return;
    const style = document.createElement("style");
    style.dataset.panelCss = "";
    style.textContent = PANEL_CSS;
    this.shadowRoot.prepend(style);
  }

  connectedCallback() {
    this.shadowRoot.innerHTML = `
      <div class="hc-app">
        <header class="hc-topbar">
          <div class="hc-brand">
            <span class="hc-brand-mark" aria-hidden="true">H</span>
            <div class="hc-brand-copy">
              <div class="hc-brand-title"><h1>HANET Connect</h1><span>Home Assistant</span></div>
              <p id="subtitle">Đang tải dữ liệu…</p>
            </div>
          </div>
          <div class="hc-topbar-actions">
            <span id="connection" class="hc-connection is-waiting">
              <span class="hc-status-dot" aria-hidden="true"></span><span>Đang kết nối</span>
            </span>
            <button class="hc-icon-button" type="button" data-action="refresh" title="Đồng bộ" aria-label="Đồng bộ">
              <ha-icon icon="mdi:refresh"></ha-icon>
            </button>
          </div>
        </header>
        <nav class="hc-primary-nav" role="tablist" aria-label="Chức năng HANET Connect" id="tabs"></nav>
        <main class="hc-workspace" id="content"></main>
      </div>
      <dialog id="dialog" aria-modal="true"></dialog>
      <div id="toast" class="hc-toast" role="status" aria-live="polite" hidden></div>
    `;
    this.applyPanelStyles();
    this._tabs = this.shadowRoot.getElementById("tabs");
    this._content = this.shadowRoot.getElementById("content");
    this._subtitle = this.shadowRoot.getElementById("subtitle");
    this._connection = this.shadowRoot.getElementById("connection");
    this._dialog = this.shadowRoot.getElementById("dialog");
    this._toast = this.shadowRoot.getElementById("toast");
    this.shadowRoot.addEventListener("click", (event) => this.onClick(event));
    this.shadowRoot.addEventListener("input", (event) => this.onInput(event));
    this.shadowRoot.addEventListener("change", (event) => this.onChange(event));
    this.shadowRoot.addEventListener("submit", (event) => this.onSubmit(event));
    this.shadowRoot.addEventListener("keydown", (event) => this.onCardKeydown(event));
    this.shadowRoot.addEventListener("pointerdown", (event) => this.onPointerDown(event));
    this.shadowRoot.addEventListener("pointerup", (event) => this.onPointerUp(event));
    this.shadowRoot.addEventListener("pointercancel", (event) => this.onPointerUp(event));
    this.shadowRoot.addEventListener("pointerleave", (event) => this.onPointerUp(event));
    this._onDocumentPointerUp = () => this.onPointerUp();
    document.addEventListener("pointerup", this._onDocumentPointerUp);
    document.addEventListener("pointercancel", this._onDocumentPointerUp);
    this._tabs.addEventListener("keydown", (event) => this.onTabKeydown(event));
    this._dialog.addEventListener("click", (event) => {
      if (event.target === this._dialog) this._dialog.close();
    });
    this._dialog.addEventListener("close", () => {
      if (!this._dialog.open) this._dialog.innerHTML = "";
    });
    this._timer = window.setInterval(() => this.autoLoad(), 30000);
    if (this._hass) this.load();
  }

  disconnectedCallback() {
    if (this._timer) window.clearInterval(this._timer);
    this._timer = null;
    window.clearTimeout(this._toastTimer);
    if (this._onDocumentPointerUp) {
      document.removeEventListener("pointerup", this._onDocumentPointerUp);
      document.removeEventListener("pointercancel", this._onDocumentPointerUp);
      this._onDocumentPointerUp = null;
    }
  }

  async autoLoad() {
    if (document.visibilityState !== "visible" || this._dialog?.open) return;
    if (this.shadowRoot.activeElement?.matches("input, select, textarea")) return;
    await this.load(true);
  }

  async load(silent = false) {
    if (!this._hass || this._loading || !this._content) return;
    this._loading = true;
    if (!silent && !this._data) this.render(true);
    try {
      const data = await this._hass.callWS({ type: "hanet_connect/panel/state" });
      this._data = data;
      this._error = "";
      this._renderStamp = Date.now();
      if (this._events.day === localDay()) {
        this._events.rows = mergeRows(data.events || [], this._events.rows || []);
      }
      this.render();
    } catch (error) {
      this._error = this.wsError(error);
      if (!this._data || !silent) this.render();
    } finally {
      this._loading = false;
    }
  }

  async loadEvents({ resetLimit = false } = {}) {
    if (!this._hass || this._events.loading) return;
    const day = this._events.day;
    const request = ++this._eventsRequest;
    this._events.loading = true;
    this._events.error = "";
    if (resetLimit) this._events.limit = 60;
    if (this._tab === "events") this.render();
    try {
      const response = await this._hass.callWS({
        type: "hanet_connect/panel/events", day, limit: 2000,
      });
      if (request !== this._eventsRequest || day !== this._events.day) return;
      this._events.rows = response.events || [];
      this._events.loaded = true;
    } catch (error) {
      if (request !== this._eventsRequest || day !== this._events.day) return;
      this._events.error = this.wsError(error);
    } finally {
      if (request === this._eventsRequest) {
        this._events.loading = false;
        if (this._tab === "events") this.render();
      }
    }
  }

  async loadRecordings({ resetLimit = false } = {}) {
    if (!this._hass || this._recordings.loading) return;
    const day = this._recordings.day;
    const request = ++this._recordingsRequest;
    this._recordings.loading = true;
    this._recordings.error = "";
    if (resetLimit) this._recordings.limit = 48;
    if (this._tab === "recordings") this.render();
    try {
      const response = await this._hass.callWS({
        type: "hanet_connect/panel/recordings", day, source: "cloud",
      });
      if (request !== this._recordingsRequest || day !== this._recordings.day) return;
      this._recordings.clips = response.clips || [];
      this._recordings.loaded = true;
    } catch (error) {
      if (request !== this._recordingsRequest || day !== this._recordings.day) return;
      this._recordings.error = this.wsError(error);
    } finally {
      if (request === this._recordingsRequest) {
        this._recordings.loading = false;
        if (this._tab === "recordings") this.render();
      }
    }
  }

  wsError(error) {
    if (!error) return "Không tải được dữ liệu";
    if (typeof error === "string") return error;
    return error.message || error.code || "Không tải được dữ liệu";
  }

  toast(message, isError = false) {
    this._toast.textContent = message;
    this._toast.classList.toggle("is-error", isError);
    this._toast.hidden = false;
    window.clearTimeout(this._toastTimer);
    this._toastTimer = window.setTimeout(() => {
      this._toast.hidden = true;
    }, 4400);
  }

  render(skeleton = false) {
    this._tabs.innerHTML = TABS.map(([id, label, icon]) => `
      <button class="hc-nav-item" type="button" role="tab" data-action="tab" data-tab="${id}"
        aria-selected="${this._tab === id}" aria-controls="content" tabindex="${this._tab === id ? "0" : "-1"}">
        <ha-icon icon="${icon}"></ha-icon><span>${label}</span>
      </button>
    `).join("");

    if (skeleton) {
      this._subtitle.textContent = "Đang tải dữ liệu…";
      this._content.innerHTML = `
        <div class="hc-skeleton-grid">
          <div class="hc-skeleton-card"><div class="hc-skeleton" style="width:44%"></div><div class="hc-skeleton" style="width:76%"></div><div class="hc-skeleton" style="width:62%"></div></div>
          <div class="hc-skeleton-card"><div class="hc-skeleton" style="width:52%"></div><div class="hc-skeleton" style="width:84%"></div><div class="hc-skeleton" style="width:48%"></div></div>
        </div>`;
      return;
    }

    if (!this._data) {
      this._subtitle.textContent = "Chưa kết nối";
      this._content.innerHTML = `
        <div class="hc-empty-state">
          <ha-icon icon="mdi:cloud-alert-outline"></ha-icon>
          <strong>${esc(this._error || "Chưa có cấu hình HANET Connect")}</strong>
          <span>Kiểm tra integration HANET Connect trong Settings → Devices &amp; services.</span>
          <button class="hc-secondary-button" type="button" data-action="refresh">Thử lại</button>
        </div>`;
      return;
    }

    const status = this._data.status || {};
    this._subtitle.textContent = `${status.online || 0}/${status.devices || 0} camera online · ${this._data.entry_title || "HANET"}`;
    this._connection.className = `hc-connection ${status.online ? "is-online" : "is-error"}`;
    this._connection.innerHTML = `<span class="hc-status-dot" aria-hidden="true"></span><span>${status.online ? "Cloud online" : "Mất kết nối"}</span>`;
    const renderer = {
      cameras: () => this.renderCameras(),
      events: () => this.renderEvents(),
      recordings: () => this.renderRecordings(),
      identity: () => this.renderIdentity(),
      settings: () => this.renderSettings(),
    }[this._tab] || (() => this.renderCameras());
    this._content.innerHTML = renderer();
    this.attachImageFallbacks();
    this.applyEventFilter();
    this.applyRecordingFilter();
    this.applyCameraFilter();
    this.applyIdentityFilter();
  }

  attachImageFallbacks() {
    this.shadowRoot.querySelectorAll("img.hc-img").forEach((image) => {
      image.addEventListener("error", () => {
        const fallback = image.dataset.fallback || "";
        if (fallback && fallback !== image.getAttribute("src")) {
          image.dataset.fallback = "";
          image.src = fallback;
          return;
        }
        const placeholder = document.createElement("div");
        placeholder.className = "hc-media-placeholder";
        placeholder.innerHTML = '<ha-icon icon="mdi:image-off-outline"></ha-icon><span>Không có ảnh</span>';
        image.replaceWith(placeholder);
      }, { once: true });
    });
  }

  latestEventFor(deviceId) {
    return (this._data?.events || []).find((event) => event.device_id === deviceId) || null;
  }

  onlineSummary() {
    const devices = this._data?.devices || [];
    return {
      online: devices.filter((device) => device.online).length,
      offline: devices.filter((device) => !device.online).length,
    };
  }

  renderCameras() {
    const devices = this._data.devices || [];
    const events = this._data.events || [];
    const summary = this.onlineSummary();
    const transport = this._data.status?.transport;
    const transportLabel = transport === "sse"
      ? "Realtime"
      : transport === "polling" ? "Polling" : transport || "Cloud";
    return `
      <section class="hc-page">
        <div class="hc-page-heading hc-hero-heading">
          <div>
            <span class="hc-eyebrow">Tổng quan</span>
            <h2>Trung tâm camera</h2>
            <p>${devices.length} thiết bị · ${events.length} sự kiện gần đây · ${esc(transportLabel)}</p>
          </div>
          <label class="hc-search-box" for="camera-search">
            <ha-icon icon="mdi:magnify"></ha-icon>
            <span class="hc-sr-only">Tìm camera</span>
            <input id="camera-search" type="search" placeholder="Tìm camera" autocomplete="off" value="${esc(this._cameraSearch)}" data-search="cameras">
          </label>
        </div>
        <div class="hc-metric-grid" role="group" aria-label="Tổng quan camera">
          <article class="hc-metric-card is-online">
            <span class="hc-metric-icon"><ha-icon icon="mdi:wifi"></ha-icon></span>
            <div><strong>${summary.online}</strong><span>Đang trực tuyến</span></div>
          </article>
          <article class="hc-metric-card is-offline">
            <span class="hc-metric-icon"><ha-icon icon="mdi:wifi-off"></ha-icon></span>
            <div><strong>${summary.offline}</strong><span>Mất kết nối</span></div>
          </article>
          <article class="hc-metric-card is-events">
            <span class="hc-metric-icon"><ha-icon icon="mdi:bell-ring-outline"></ha-icon></span>
            <div><strong>${events.length}</strong><span>Sự kiện hôm nay</span></div>
          </article>
          <article class="hc-metric-card is-faces">
            <span class="hc-metric-icon"><ha-icon icon="mdi:account-group-outline"></ha-icon></span>
            <div><strong>${this._data.people?.length || 0}</strong><span>Danh tính FaceID</span></div>
          </article>
        </div>
        <div class="hc-section-heading">
          <div><h3>Danh sách camera</h3><p id="camera-count">${devices.length} thiết bị</p></div>
        </div>
        <div class="hc-camera-grid" id="camera-grid">
          ${devices.map((device) => this.cameraCard(device)).join("") || this.empty("mdi:cctv-off", "Chưa có camera", "Kiểm tra tài khoản HANET và làm mới dữ liệu.")}
        </div>
        <div class="hc-empty-state" id="camera-empty" hidden>
          <ha-icon icon="mdi:magnify-close"></ha-icon><strong>Không tìm thấy camera</strong><span>Thử từ khoá khác.</span>
        </div>
      </section>`;
  }

  cameraCard(device) {
    const event = this.latestEventFor(device.id);
    const state = device.camera_entity ? this._hass?.states?.[device.camera_entity] : null;
    const token = state?.attributes?.access_token;
    const snapshot = device.camera_entity && token
      ? `/api/camera_proxy/${encodeURIComponent(device.camera_entity)}?token=${encodeURIComponent(token)}&t=${this._renderStamp || Date.now()}`
      : event?.image || "";
    const fallback = event?.image && event.image !== snapshot ? event.image : "";
    const haystack = `${device.name || ""} ${device.place_name || ""} ${device.model || ""}`.toLocaleLowerCase("vi");
    return `
      <article class="hc-camera-card" data-camera-search="${esc(haystack)}">
        <button class="hc-camera-preview" type="button" data-action="camera-preview" data-device="${esc(device.id)}" aria-label="Xem ${esc(device.name || "camera")}">
          ${art(snapshot, device.name || "Camera", fallback)}
          <span class="hc-state-badge ${device.online ? "is-online" : ""}"><span></span>${device.online ? "Online" : "Offline"}</span>
          ${event ? `<span class="hc-preview-note"><ha-icon icon="mdi:clock-outline"></ha-icon>${esc(relative(event.occurred_at))}</span>` : ""}
        </button>
        <div class="hc-camera-body">
          <div class="hc-camera-heading">
            <div class="hc-camera-title">
              <strong>${esc(device.name || "HANET")}</strong>
              <span>${esc(device.place_name || "Chưa rõ địa điểm")}</span>
            </div>
            <span class="hc-camera-model">${esc(device.model || "Camera")}</span>
          </div>
          <div class="hc-camera-meta">
            <span><ha-icon icon="mdi:information-outline"></ha-icon>${event ? esc(kindLabel(event)) : "Chưa có sự kiện"}</span>
            <span><ha-icon icon="mdi:chip"></ha-icon>${esc(device.firmware || "N/A")}</span>
          </div>
          <div class="hc-camera-quick" role="group" aria-label="Điều khiển nhanh ${esc(device.name || "camera")}">
            <button class="hc-icon-button is-small" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="open_door" title="Mở cửa" aria-label="Mở cửa"><ha-icon icon="mdi:door-open"></ha-icon></button>
            <button class="hc-icon-button is-small" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="close_door" title="Đóng cửa" aria-label="Đóng cửa"><ha-icon icon="mdi:door-closed"></ha-icon></button>
            <button class="hc-icon-button is-small" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="alarm" title="Bật còi" aria-label="Bật còi"><ha-icon icon="mdi:alarm-light"></ha-icon></button>
            <button class="hc-icon-button is-small" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="stop_alarm" title="Tắt còi" aria-label="Tắt còi"><ha-icon icon="mdi:alarm-light-off"></ha-icon></button>
          </div>
          <div class="hc-camera-actions">
            <button class="hc-secondary-button" type="button" data-action="camera-events" data-device="${esc(device.id)}">
              <ha-icon icon="mdi:history"></ha-icon><span>Sự kiện</span>
            </button>
            <button class="hc-secondary-button" type="button" data-action="camera-recordings" data-device="${esc(device.id)}">
              <ha-icon icon="mdi:filmstrip"></ha-icon><span>Ghi hình</span>
            </button>
            <button class="hc-secondary-button" type="button" data-action="camera-controls" data-device="${esc(device.id)}">
              <ha-icon icon="mdi:gamepad-variant-outline"></ha-icon><span>Điều khiển</span>
            </button>
            <button class="hc-secondary-button" type="button" data-action="camera-settings" data-device="${esc(device.id)}">
              <ha-icon icon="mdi:cog-outline"></ha-icon><span>Cài đặt</span>
            </button>
          </div>
        </div>
      </article>`;
  }

  renderEvents() {
    const usingSnapshot = !this._events.loaded && this._events.day === localDay();
    const rows = usingSnapshot ? mergeRows(this._data.events || [], this._events.rows) : this._events.rows;
    const devices = this._data.devices || [];
    const loading = this._events.loading;
    const error = this._events.error;
    const visible = rows.slice(0, this._events.limit);
    const status = loading ? "Đang tải sự kiện…" : error || `${rows.length} sự kiện trong ngày`;
    return `
      <section class="hc-page">
        <div class="hc-page-heading">
          <div>
            <span class="hc-eyebrow">Nhật ký hoạt động</span>
            <h2>Sự kiện</h2>
            <p id="events-summary">${esc(dayTitle(this._events.day))}</p>
          </div>
          <div class="hc-toolbar">
            <label class="hc-control-icon" for="event-day">
              <ha-icon icon="mdi:calendar-month-outline"></ha-icon>
              <input id="event-day" type="date" value="${esc(this._events.day)}" data-day="events" aria-label="Ngày sự kiện">
            </label>
            <button class="hc-icon-button" type="button" data-action="events-reload" title="Tải lại" aria-label="Tải lại sự kiện">
              <ha-icon icon="mdi:refresh"></ha-icon>
            </button>
          </div>
        </div>
        <div class="hc-filter-bar" role="group" aria-label="Lọc sự kiện">
          <div class="hc-quick-filters">
            <button class="hc-filter-chip ${this._events.day === localDay() ? "is-active" : ""}" type="button" data-action="events-day" data-offset="0">Hôm nay</button>
            <button class="hc-filter-chip ${this._events.day === localDay(1) ? "is-active" : ""}" type="button" data-action="events-day" data-offset="1">Hôm qua</button>
          </div>
          <label class="hc-search-box" for="event-search">
            <ha-icon icon="mdi:magnify"></ha-icon>
            <span class="hc-sr-only">Tìm sự kiện</span>
            <input id="event-search" type="search" placeholder="Tên người, camera" autocomplete="off" value="${esc(this._events.search)}" data-search="events">
          </label>
          <select data-filter="events-device" aria-label="Camera sự kiện">
            <option value="">Tất cả camera</option>
            ${devices.map((device) => `<option value="${esc(device.id)}" ${this._events.device === String(device.id) ? "selected" : ""}>${esc(device.name || device.id)}</option>`).join("")}
          </select>
          <select data-filter="events-kind" aria-label="Loại sự kiện">
            <option value="">Tất cả loại</option>
            <option value="employee" ${this._events.kind === "employee" ? "selected" : ""}>Người nhà</option>
            <option value="visitor" ${this._events.kind === "visitor" ? "selected" : ""}>Người quen</option>
            <option value="stranger" ${this._events.kind === "stranger" ? "selected" : ""}>Người lạ</option>
            <option value="human" ${this._events.kind === "human" ? "selected" : ""}>Chuyển động</option>
            <option value="alarm" ${this._events.kind === "alarm" ? "selected" : ""}>Báo động</option>
          </select>
          <select data-filter="events-source" aria-label="Nguồn sự kiện">
            <option value="">Tất cả nguồn</option>
            <option value="cloud" ${this._events.source === "cloud" ? "selected" : ""}>Cloud</option>
            <option value="sse" ${this._events.source === "sse" ? "selected" : ""}>Trực tiếp</option>
            <option value="webhook" ${this._events.source === "webhook" ? "selected" : ""}>Webhook</option>
          </select>
        </div>
        <div class="hc-inline-status ${error ? "is-error" : loading ? "is-loading" : ""}" role="status" aria-live="polite">${esc(status)}</div>
        <div class="hc-event-list" id="event-list">
          ${visible.map((event) => this.eventCard(event)).join("")}
        </div>
        ${!rows.length && !loading ? this.empty(error ? "mdi:cloud-alert-outline" : "mdi:bell-off-outline", "Không có sự kiện", error || "Thử chọn ngày khác hoặc làm mới dữ liệu.") : ""}
        <div class="hc-empty-state" id="events-empty" hidden>
          <ha-icon icon="mdi:filter-off-outline"></ha-icon><strong>Không có sự kiện phù hợp</strong><span>Thử bỏ bớt bộ lọc.</span>
        </div>
        ${rows.length > this._events.limit ? `<button class="hc-secondary-button hc-load-more" type="button" data-action="events-more">Xem thêm</button>` : ""}
      </section>`;
  }

  eventCard(event) {
    const kind = canonicalKind(event);
    const source = canonicalSource(event);
    const title = eventTitle(event);
    return `
      <article class="hc-event-card" role="button" tabindex="0"
        data-action="event" data-id="${esc(event.id)}"
        data-event-search="${esc(eventSearchText(event))}"
        data-event-device="${esc(event.device_id || "")}"
        data-event-kind="${esc(kind)}"
        data-event-group="${esc(groupOf(event))}"
        data-event-source="${esc(source)}"
        aria-label="Xem sự kiện ${esc(title)}">
        <div class="hc-event-image">${art(event.image, title)}</div>
        <div class="hc-event-body">
          <strong>${esc(title)}</strong>
          <p>${esc([event.person_title, event.device_name, event.place_name].filter(Boolean).join(" · ") || kindLabel(event))}</p>
          <div class="hc-event-meta">
            <time>${esc(fmtTime(event.occurred_at || event.received_at))}</time>
            <span class="hc-event-badges">
              <span class="hc-kind-tag is-${esc(kind)}">${esc(kindLabel(event))}</span>
              <span class="hc-source-tag">${esc(sourceLabel(event))}</span>
            </span>
          </div>
        </div>
      </article>`;
  }

  renderRecordings() {
    const clips = this._recordings.clips;
    const devices = this._data.devices || [];
    const loading = this._recordings.loading;
    const error = this._recordings.error;
    const visible = clips.slice(0, this._recordings.limit);
    const status = loading ? "Đang tải ghi hình Cloud…" : error || `${clips.length} đoạn ghi hình`;
    return `
      <section class="hc-page">
        <div class="hc-page-heading">
          <div>
            <span class="hc-eyebrow">Cloud recording</span>
            <h2>Ghi hình</h2>
            <p id="recordings-summary">${esc(dayTitle(this._recordings.day))}</p>
          </div>
          <div class="hc-toolbar">
            <label class="hc-control-icon" for="recording-day">
              <ha-icon icon="mdi:calendar-month-outline"></ha-icon>
              <input id="recording-day" type="date" value="${esc(this._recordings.day)}" data-day="recordings" aria-label="Ngày ghi hình">
            </label>
            <button class="hc-icon-button" type="button" data-action="recordings-reload" title="Tải lại" aria-label="Tải lại ghi hình">
              <ha-icon icon="mdi:refresh"></ha-icon>
            </button>
          </div>
        </div>
        <div class="hc-segmented" role="tablist" aria-label="Nguồn ghi hình">
          <button class="hc-segment is-active" type="button" role="tab" aria-selected="true">Cloud</button>
          <button class="hc-segment" type="button" role="tab" aria-selected="false" disabled title="Thẻ SD chưa được hỗ trợ trong bản Home Assistant">Thẻ SD</button>
        </div>
        <p class="hc-source-help">Clip Cloud được phát qua proxy Home Assistant, không lộ URL HANET. Thẻ SD chưa được hỗ trợ trong custom component.</p>
        <div class="hc-filter-bar is-recordings" role="group" aria-label="Lọc ghi hình">
          <div class="hc-quick-filters">
            <button class="hc-filter-chip ${this._recordings.day === localDay() ? "is-active" : ""}" type="button" data-action="recordings-day" data-offset="0">Hôm nay</button>
            <button class="hc-filter-chip ${this._recordings.day === localDay(1) ? "is-active" : ""}" type="button" data-action="recordings-day" data-offset="1">Hôm qua</button>
          </div>
          <label class="hc-search-box" for="recording-search">
            <ha-icon icon="mdi:magnify"></ha-icon>
            <span class="hc-sr-only">Tìm ghi hình</span>
            <input id="recording-search" type="search" placeholder="Tên camera, địa điểm" autocomplete="off" value="${esc(this._recordings.search)}" data-search="recordings">
          </label>
          <select data-filter="recordings-device" aria-label="Camera ghi hình">
            <option value="">Tất cả camera</option>
            ${devices.map((device) => `<option value="${esc(device.id)}" ${this._recordings.device === String(device.id) ? "selected" : ""}>${esc(device.name || device.id)}</option>`).join("")}
          </select>
          <select data-filter="recordings-period" aria-label="Khung giờ">
            <option value="">Cả ngày</option>
            <option value="morning" ${this._recordings.period === "morning" ? "selected" : ""}>Buổi sáng</option>
            <option value="afternoon" ${this._recordings.period === "afternoon" ? "selected" : ""}>Buổi chiều</option>
            <option value="evening" ${this._recordings.period === "evening" ? "selected" : ""}>Buổi tối</option>
          </select>
        </div>
        <div class="hc-inline-status ${error ? "is-error" : loading ? "is-loading" : ""}" role="status" aria-live="polite">${esc(status)}</div>
        <div class="hc-recording-grid" id="recording-list">
          ${visible.map((clip) => this.recordingCard(clip)).join("")}
        </div>
        ${!clips.length && !loading ? this.empty(error ? "mdi:cloud-alert-outline" : "mdi:filmstrip-off", "Không có ghi hình", error || "Chọn ngày khác hoặc kiểm tra gói lưu trữ Cloud.") : ""}
        <div class="hc-empty-state" id="recordings-empty" hidden>
          <ha-icon icon="mdi:filter-off-outline"></ha-icon><strong>Không có clip phù hợp</strong><span>Thử bỏ bớt bộ lọc.</span>
        </div>
        ${clips.length > this._recordings.limit ? `<button class="hc-secondary-button hc-load-more" type="button" data-action="recordings-more">Xem thêm</button>` : ""}
      </section>`;
  }

  recordingCard(clip) {
    const timestamp = timestampMs(clip.timestamp);
    const date = timestamp === null ? null : new Date(timestamp);
    const period = !date ? "" : date.getHours() < 12 ? "morning" : date.getHours() < 18 ? "afternoon" : "evening";
    const search = `${clip.device_name || ""} ${clip.place_name || ""} ${clip.event_id || ""}`.toLocaleLowerCase("vi");
    return `
      <article class="hc-recording-card" data-recording-search="${esc(search)}"
        data-recording-device="${esc(clip.device_id || "")}" data-recording-period="${esc(period)}">
        <button class="hc-recording-preview" type="button" data-action="clip" data-id="${esc(clip.id)}" aria-label="Phát clip ${esc(clip.device_name || "")}">
          ${art(clip.thumbnail, clip.device_name || "Clip", "", "is-cover")}
          <span class="hc-play-circle"><ha-icon icon="mdi:play"></ha-icon></span>
          <span class="hc-duration-tag">${esc(durationText(clip.duration))}</span>
        </button>
        <div class="hc-recording-body">
          <strong>${esc(clip.device_name || "Camera HANET")}</strong>
          <span>${esc(fmtClock(clip.timestamp))} · ${esc(clip.place_name || "Cloud")}</span>
          <div class="hc-recording-actions">
            <span class="hc-source-tag">Cloud</span>
            <button class="hc-icon-button is-small" type="button" data-action="clip" data-id="${esc(clip.id)}" title="Phát clip" aria-label="Phát clip">
              <ha-icon icon="mdi:play-circle-outline"></ha-icon>
            </button>
          </div>
        </div>
      </article>`;
  }

  renderIdentity() {
    const people = this._data.people || [];
    const places = this.places();
    const departments = this._data.departments || [];
    return `
      <section class="hc-page">
        <div class="hc-page-heading is-identity">
          <div>
            <span class="hc-eyebrow">FaceID</span>
            <h2>Danh tính</h2>
            <p id="identity-summary">${people.length} hồ sơ · ${departments.length} phòng ban</p>
          </div>
          <div class="hc-toolbar">
            <label class="hc-search-box" for="identity-search">
              <ha-icon icon="mdi:magnify"></ha-icon>
              <span class="hc-sr-only">Tìm danh tính</span>
              <input id="identity-search" type="search" placeholder="Tìm tên, phòng ban" autocomplete="off" value="${esc(this._identitySearch)}" data-search="identity">
            </label>
            <select data-filter="identity-type" aria-label="Loại danh tính">
              <option value="">Tất cả loại</option>
              <option value="0" ${this._identityType === "0" ? "selected" : ""}>Người nhà</option>
              <option value="1" ${this._identityType === "1" ? "selected" : ""}>Khách</option>
            </select>
            <button class="hc-primary-button" type="button" data-action="add-face" ${places.length ? "" : "disabled"}>
              <ha-icon icon="mdi:account-plus-outline"></ha-icon><span>Thêm FaceID</span>
            </button>
          </div>
        </div>
        ${!places.length ? this.empty("mdi:map-marker-off-outline", "Chưa có địa điểm", "Cần tải được place từ HANET trước khi thêm FaceID.") : ""}
        <div class="hc-person-grid" id="person-grid">
          ${people.map((person) => this.personCard(person)).join("")}
        </div>
        ${!people.length ? this.empty("mdi:face-recognition", "Chưa có FaceID", "Thêm ảnh và tên để nhận diện người quen.") : ""}
        <div class="hc-empty-state" id="people-empty" hidden>
          <ha-icon icon="mdi:account-search-outline"></ha-icon><strong>Không tìm thấy danh tính</strong><span>Thử từ khoá hoặc loại khác.</span>
        </div>
      </section>`;
  }

  personCard(person) {
    const search = [person.name, person.department, person.title, person.phone, person.alias_id]
      .filter(Boolean).join(" ").toLocaleLowerCase("vi");
    return `
      <article class="hc-person-card" data-person-search="${esc(search)}" data-person-type="${esc(person.type ?? "")}">
        <div class="hc-person-image">${art(person.image, person.name || "FaceID")}</div>
        <div class="hc-person-body">
          <div class="hc-person-heading">
            <div>
              <strong>${esc(person.name || "FaceID")}</strong>
              <span>${esc(person.title || person.department || person.type_name || "Danh tính HANET")}</span>
            </div>
            <span class="hc-type-tag ${Number(person.type) === 1 ? "is-visitor" : ""}">${esc(person.type_name || (Number(person.type) === 1 ? "Khách" : "Người nhà"))}</span>
          </div>
          <div class="hc-person-meta">
            ${person.department ? `<span><ha-icon icon="mdi:office-building-outline"></ha-icon>${esc(person.department)}</span>` : ""}
            ${person.phone ? `<span><ha-icon icon="mdi:phone-outline"></ha-icon>${esc(person.phone)}</span>` : ""}
            ${person.email ? `<span><ha-icon icon="mdi:email-outline"></ha-icon>${esc(person.email)}</span>` : ""}
          </div>
          <div class="hc-person-actions">
            <button class="hc-secondary-button" type="button" data-action="edit-face" data-id="${esc(person.id)}"><ha-icon icon="mdi:pencil-outline"></ha-icon><span>Sửa</span></button>
            <button class="hc-secondary-button is-danger" type="button" data-action="delete-face" data-id="${esc(person.id)}"><ha-icon icon="mdi:trash-can-outline"></ha-icon><span>Xoá</span></button>
          </div>
        </div>
      </article>`;
  }

  renderSettings() {
    const data = this._data;
    const settings = data.settings || {};
    const status = data.status || {};
    const transport = status.transport === "sse" ? "SSE trực tiếp" : status.transport || "Cloud polling";
    return `
      <section class="hc-page">
        <div class="hc-page-heading">
          <div>
            <span class="hc-eyebrow">Cấu hình</span>
            <h2>Cài đặt</h2>
            <p>Thời gian giữ trạng thái, thông báo và thông tin kết nối HANET.</p>
          </div>
        </div>
        ${this.deviceSettingsMarkup()}
        <div class="hc-settings-grid">
          <form class="hc-settings-card" data-form="settings">
            <div class="hc-settings-heading">
              <span class="hc-settings-icon"><ha-icon icon="mdi:timer-sand"></ha-icon></span>
              <div><h3>Thời gian giữ trạng thái</h3><p>Số giây sensor giữ ON sau lần nhận diện gần nhất.</p></div>
            </div>
            <div class="hc-field-grid">
              ${(data.groups || []).map((group) => `
                <label class="hc-field">
                  <span>${esc(group.label)} (giây)</span>
                  <input type="number" min="1" max="3600" step="1" required name="recency_${esc(group.group)}" value="${Number(settings[`recency_${group.group}`] || 10)}">
                </label>`).join("")}
            </div>
            <div class="hc-divider"></div>
            <div class="hc-settings-heading">
              <span class="hc-settings-icon is-bell"><ha-icon icon="mdi:bell-outline"></ha-icon></span>
              <div><h3>Thông báo</h3><p>Gửi thông báo khi HANET nhận diện sự kiện mới.</p></div>
            </div>
            <label class="hc-field">
              <span>Dịch vụ notify</span>
              <input type="text" name="notify_service" placeholder="notify.mobile_app_abc" value="${esc(settings.notify_service || "")}">
            </label>
            <label class="hc-check-field">
              <input type="checkbox" name="notify_persistent" ${settings.notify_persistent ? "checked" : ""}>
              <span>Hiện thông báo trong Home Assistant</span>
            </label>
            <div class="hc-form-actions">
              <button class="hc-primary-button" type="submit"><ha-icon icon="mdi:content-save-outline"></ha-icon><span>Lưu cài đặt</span></button>
            </div>
          </form>
          <aside class="hc-settings-card">
            <div class="hc-settings-heading">
              <span class="hc-settings-icon is-cloud"><ha-icon icon="mdi:cloud-check-outline"></ha-icon></span>
              <div><h3>Trạng thái kết nối</h3><p>Kênh dữ liệu và thông tin integration.</p></div>
            </div>
            <div class="hc-status-list">
              <div><span>Realtime</span><strong>${esc(transport)}</strong></div>
              <div><span>Độ trễ gần nhất</span><strong>${status.latency_seconds != null ? `${esc(status.latency_seconds)} giây` : "—"}</strong></div>
              <div><span>Sự kiện gần nhất</span><strong>${esc(relative(status.last_event_at))}</strong></div>
              <div><span>Camera online</span><strong>${status.online || 0}/${status.devices || 0}</strong></div>
              <div><span>FaceID</span><strong>${data.people?.length || 0}</strong></div>
              <div><span>Config entry</span><strong class="hc-code">${esc(data.entry_id)}</strong></div>
            </div>
            <div class="hc-notice">
              <ha-icon icon="mdi:information-outline"></ha-icon>
              <p>Ghi hình hiện hỗ trợ Cloud. Thẻ SD cần daemon/P2P riêng nên chưa có trong custom component.</p>
            </div>
          </aside>
        </div>
      </section>`;
  }

  empty(icon, title, copy = "") {
    return `<div class="hc-empty-state"><ha-icon icon="${icon}"></ha-icon><strong>${esc(title)}</strong>${copy ? `<span>${esc(copy)}</span>` : ""}</div>`;
  }

  places() {
    if (this._data?.places?.length) return this._data.places;
    const seen = new Map();
    for (const device of this._data?.devices || []) {
      if (device.place_id) seen.set(String(device.place_id), device.place_name || `Địa điểm ${device.place_id}`);
    }
    for (const person of this._data?.people || []) {
      if (person.place_id) seen.set(String(person.place_id), seen.get(String(person.place_id)) || `Địa điểm ${person.place_id}`);
    }
    return Array.from(seen, ([id, name]) => ({ id, name }));
  }

  findEvent(eventId) {
    return (this._events.rows || []).find((event) => String(event.id) === String(eventId))
      || (this._data?.events || []).find((event) => String(event.id) === String(eventId))
      || null;
  }

  findClip(clipId) {
    return (this._recordings.clips || []).find((clip) => String(clip.id) === String(clipId)) || null;
  }

  onClick(event) {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    const action = target.dataset.action;
    if (action === "tab") {
      this.openTab(target.dataset.tab || "cameras");
    } else if (action === "refresh") {
      this.load();
    } else if (action === "events-reload") {
      this.loadEvents({ resetLimit: true });
    } else if (action === "recordings-reload") {
      this.loadRecordings({ resetLimit: true });
    } else if (action === "events-day") {
      this.setDay("events", localDay(Number(target.dataset.offset || 0)));
    } else if (action === "recordings-day") {
      this.setDay("recordings", localDay(Number(target.dataset.offset || 0)));
    } else if (action === "events-more") {
      this._events.limit += 60;
      this.render();
    } else if (action === "recordings-more") {
      this._recordings.limit += 48;
      this.render();
    } else if (action === "event") {
      this.openEvent(target.dataset.id);
    } else if (action === "camera-preview") {
      this.openCameraDialog(target.dataset.device);
    } else if (action === "camera-events") {
      this._events.device = String(target.dataset.device || "");
      this._events.search = "";
      this._events.kind = "";
      this._events.source = "";
      this._events.day = localDay();
      this._events.rows = [];
      this._events.loaded = false;
      this.openTab("events", true);
    } else if (action === "camera-recordings") {
      this._recordings.device = String(target.dataset.device || "");
      this._recordings.search = "";
      this._recordings.period = "";
      this._recordings.day = localDay();
      this._recordings.clips = [];
      this._recordings.loaded = false;
      this.openTab("recordings", true);
    } else if (action === "camera-controls") {
      this.openCameraControls(target.dataset.device);
    } else if (action === "camera-settings") {
      this.openCameraSettings(target.dataset.device);
    } else if (action === "camera-command") {
      if (target.hasAttribute("data-hold")) return;
      const device = this.deviceById(target.dataset.device);
      if (device) this.runCameraCommand(device, target.dataset.command, target);
    } else if (action === "clip") {
      this.openClipDialog(target.dataset.id);
    } else if (action === "event-recordings") {
      this.openRecordingsForEvent(target.dataset.id);
    } else if (action === "add-face") {
      this.openFaceDialog();
    } else if (action === "edit-face") {
      this.openFaceDialog(target.dataset.id);
    } else if (action === "delete-face") {
      this.openDeleteDialog(target.dataset.id);
    } else if (action === "close-dialog") {
      this._dialog.close();
    } else if (action === "confirm-delete") {
      this.submitDelete(target.dataset.id, target);
    }
  }

  openTab(tab, force = false) {
    this._tab = TABS.some(([id]) => id === tab) ? tab : "cameras";
    this.render();
    if (this._tab === "events" && (force || !this._events.loaded)) this.loadEvents();
    if (this._tab === "recordings" && (force || !this._recordings.loaded)) this.loadRecordings();
  }

  setDay(kind, day) {
    if (!day) return;
    if (kind === "events") {
      if (this._events.day === day) return;
      this._events.day = day;
      this._events.rows = [];
      this._events.loaded = false;
      this._events.error = "";
      this._eventsRequest += 1;
      this._events.loading = false;
      this.render();
      this.loadEvents({ resetLimit: true });
    } else {
      if (this._recordings.day === day) return;
      this._recordings.day = day;
      this._recordings.clips = [];
      this._recordings.loaded = false;
      this._recordings.error = "";
      this._recordingsRequest += 1;
      this._recordings.loading = false;
      this.render();
      this.loadRecordings({ resetLimit: true });
    }
  }

  onTabKeydown(event) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const tabs = [...this._tabs.querySelectorAll(".hc-nav-item")];
    const current = tabs.indexOf(this.shadowRoot.activeElement);
    const next = event.key === "Home" ? 0
      : event.key === "End" ? tabs.length - 1
        : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    this.openTab(tabs[next].dataset.tab);
    this._tabs.querySelector(`[data-tab="${this._tab}"]`)?.focus();
  }

  onCardKeydown(event) {
    if (!["Enter", " "].includes(event.key)) return;
    const card = event.target.closest(".hc-event-card");
    if (!card) return;
    event.preventDefault();
    this.openEvent(card.dataset.id);
  }

  onInput(event) {
    const search = event.target.closest("[data-search]");
    if (search) {
      const value = search.value.trim().toLocaleLowerCase("vi");
      const kind = search.dataset.search;
      if (kind === "cameras") {
        this._cameraSearch = value;
        this.applyCameraFilter();
      } else if (kind === "events") {
        this._events.search = value;
        this.applyEventFilter();
      } else if (kind === "recordings") {
        this._recordings.search = value;
        this.applyRecordingFilter();
      } else if (kind === "identity") {
        this._identitySearch = value;
        this.applyIdentityFilter();
      }
      return;
    }
    const file = event.target.closest('[data-preview="face"]');
    if (file?.files?.[0]) {
      const preview = this._dialog.querySelector("[data-face-preview]");
      if (preview) {
        preview.src = URL.createObjectURL(file.files[0]);
        preview.hidden = false;
      }
    }
  }

  onChange(event) {
    const setting = event.target.closest("[data-setting-key]");
    if (setting) {
      this.applySetting(setting);
      return;
    }
    const dayInput = event.target.closest("[data-day]");
    if (dayInput) {
      this.setDay(dayInput.dataset.day, dayInput.value);
      return;
    }
    const filter = event.target.closest("[data-filter]");
    if (!filter) return;
    const name = filter.dataset.filter;
    if (name === "events-device") this._events.device = filter.value;
    else if (name === "events-kind") this._events.kind = filter.value;
    else if (name === "events-source") this._events.source = filter.value;
    else if (name === "recordings-device") this._recordings.device = filter.value;
    else if (name === "recordings-period") this._recordings.period = filter.value;
    else if (name === "identity-type") {
      this._identityType = filter.value;
      this.applyIdentityFilter();
      return;
    }
    this.applyEventFilter();
    this.applyRecordingFilter();
  }

  applyCameraFilter() {
    const cards = [...this.shadowRoot.querySelectorAll("[data-camera-search]")];
    let visible = 0;
    cards.forEach((card) => {
      const show = !this._cameraSearch || card.dataset.cameraSearch.includes(this._cameraSearch);
      card.hidden = !show;
      if (show) visible += 1;
    });
    const count = this.shadowRoot.getElementById("camera-count");
    if (count && cards.length) count.textContent = `${visible} thiết bị`;
    const empty = this.shadowRoot.getElementById("camera-empty");
    if (empty) empty.hidden = !cards.length || visible > 0;
  }

  applyEventFilter() {
    const cards = [...this.shadowRoot.querySelectorAll(".hc-event-card")];
    let visible = 0;
    for (const card of cards) {
      const show = (!this._events.search || card.dataset.eventSearch.includes(this._events.search))
        && (!this._events.device || card.dataset.eventDevice === this._events.device)
        && (!this._events.kind || card.dataset.eventKind === this._events.kind || card.dataset.eventGroup === this._events.kind)
        && (!this._events.source || card.dataset.eventSource === this._events.source);
      card.hidden = !show;
      if (show) visible += 1;
    }
    const empty = this.shadowRoot.getElementById("events-empty");
    if (empty) empty.hidden = !cards.length || visible > 0;
    const summary = this.shadowRoot.getElementById("events-summary");
    if (summary && cards.length) summary.textContent = `${visible}/${cards.length} sự kiện · ${dayTitle(this._events.day)}`;
  }

  applyRecordingFilter() {
    const cards = [...this.shadowRoot.querySelectorAll(".hc-recording-card")];
    let visible = 0;
    for (const card of cards) {
      const show = (!this._recordings.search || card.dataset.recordingSearch.includes(this._recordings.search))
        && (!this._recordings.device || card.dataset.recordingDevice === this._recordings.device)
        && (!this._recordings.period || card.dataset.recordingPeriod === this._recordings.period);
      card.hidden = !show;
      if (show) visible += 1;
    }
    const empty = this.shadowRoot.getElementById("recordings-empty");
    if (empty) empty.hidden = !cards.length || visible > 0;
    const summary = this.shadowRoot.getElementById("recordings-summary");
    if (summary && cards.length) summary.textContent = `${visible}/${cards.length} clip · ${dayTitle(this._recordings.day)}`;
  }

  applyIdentityFilter() {
    const cards = [...this.shadowRoot.querySelectorAll("[data-person-search]")];
    let visible = 0;
    for (const card of cards) {
      const show = (!this._identitySearch || card.dataset.personSearch.includes(this._identitySearch))
        && (!this._identityType || card.dataset.personType === this._identityType);
      card.hidden = !show;
      if (show) visible += 1;
    }
    const empty = this.shadowRoot.getElementById("people-empty");
    if (empty) empty.hidden = !cards.length || visible > 0;
    const summary = this.shadowRoot.getElementById("identity-summary");
    if (summary && cards.length) summary.textContent = `${visible}/${cards.length} hồ sơ · ${this._data.departments?.length || 0} phòng ban`;
  }

  openEvent(eventId) {
    const item = this.findEvent(eventId);
    if (!item) return;
    this._dialog.innerHTML = `
      <div class="hc-dialog-head">
        <div><span class="hc-eyebrow">${esc(kindLabel(item))}</span><h2>${esc(eventTitle(item))}</h2></div>
        <button class="hc-icon-button" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        ${item.image ? `<img class="hc-dialog-image hc-img" src="${esc(item.image)}" alt="${esc(eventTitle(item))}">` : this.empty("mdi:image-off-outline", "Không có ảnh")}
        <div class="hc-detail-grid">
          <div><span>Thời gian</span><strong>${esc(fmtTime(item.occurred_at || item.received_at))}</strong></div>
          <div><span>Camera</span><strong>${esc(item.device_name || item.device_id || "—")}</strong></div>
          <div><span>Địa điểm</span><strong>${esc(item.place_name || "—")}</strong></div>
          <div><span>Nguồn</span><strong>${esc(sourceLabel(item))}</strong></div>
          ${item.person_title ? `<div><span>Thông tin</span><strong>${esc(item.person_title)}</strong></div>` : ""}
          <div><span>Loại</span><strong>${esc(kindLabel(item))}</strong></div>
        </div>
        <div class="hc-dialog-actions">
          <button class="hc-secondary-button" type="button" data-action="close-dialog">Đóng</button>
          <button class="hc-primary-button" type="button" data-action="event-recordings" data-id="${esc(item.id)}">
            <ha-icon icon="mdi:filmstrip"></ha-icon><span>Xem ghi hình sự kiện</span>
          </button>
        </div>
      </div>`;
    this.attachImageFallbacks();
    this._dialog.showModal();
  }

  openCameraDialog(deviceId) {
    const device = (this._data?.devices || []).find((item) => String(item.id) === String(deviceId));
    if (!device) return;
    const event = this.latestEventFor(device.id);
    const state = device.camera_entity ? this._hass?.states?.[device.camera_entity] : null;
    const token = state?.attributes?.access_token;
    const src = device.camera_entity && token
      ? `/api/camera_proxy/${encodeURIComponent(device.camera_entity)}?token=${encodeURIComponent(token)}&t=${Date.now()}`
      : event?.image || "";
    this._dialog.innerHTML = `
      <div class="hc-dialog-head">
        <div><span class="hc-eyebrow">${device.online ? "Online" : "Offline"}</span><h2>${esc(device.name || "Camera")}</h2></div>
        <button class="hc-icon-button" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        <div class="hc-camera-dialog-media">${art(src, device.name || "Camera", event?.image || "")}</div>
        <div class="hc-detail-grid">
          <div><span>Địa điểm</span><strong>${esc(device.place_name || "—")}</strong></div>
          <div><span>Model</span><strong>${esc(device.model || "—")}</strong></div>
          <div><span>Firmware</span><strong>${esc(device.firmware || "—")}</strong></div>
          <div><span>Serial</span><strong>${esc(device.serial || "—")}</strong></div>
          <div><span>Sự kiện cuối</span><strong>${event ? esc(`${kindLabel(event)} · ${relative(event.occurred_at)}`) : "Chưa có"}</strong></div>
        </div>
        <div class="hc-dialog-actions">
          <button class="hc-secondary-button" type="button" data-action="camera-controls" data-device="${esc(device.id)}"><ha-icon icon="mdi:gamepad-variant-outline"></ha-icon><span>Điều khiển</span></button>
          <button class="hc-secondary-button" type="button" data-action="camera-settings" data-device="${esc(device.id)}"><ha-icon icon="mdi:cog-outline"></ha-icon><span>Cài đặt</span></button>
          <button class="hc-secondary-button" type="button" data-action="camera-events" data-device="${esc(device.id)}">Sự kiện</button>
          <button class="hc-primary-button" type="button" data-action="camera-recordings" data-device="${esc(device.id)}">Ghi hình</button>
        </div>
      </div>`;
    this.attachImageFallbacks();
    this._dialog.showModal();
  }

  deviceById(deviceId) {
    return (this._data?.devices || []).find((item) => String(item.id) === String(deviceId)) || null;
  }

  openCameraControls(deviceId) {
    const device = this.deviceById(deviceId);
    if (!device) return;
    const pad = PTZ_PAD.map(([command, icon]) => `
      <button class="hc-ptz-button${command === "stop" ? " is-stop" : ""}" type="button"
        data-action="camera-command" data-device="${esc(device.id)}" data-command="${command}"
        ${HOLD_COMMANDS.has(command) ? "data-hold" : ""} aria-label="${esc(commandLabel(command))}" title="${esc(commandLabel(command))}">
        <ha-icon icon="${icon}"></ha-icon>
      </button>`).join("");
    this._dialog.innerHTML = `
      <div class="hc-dialog-head">
        <div><span class="hc-eyebrow">Điều khiển</span><h2>${esc(device.name || "Camera")}</h2></div>
        <button class="hc-icon-button" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        <div class="hc-control-grid">
          <section class="hc-control-section">
            <h3>Hướng &amp; thu phóng</h3>
            <div class="hc-ptz-layout">
              <div class="hc-ptz-pad">${pad}</div>
              <div class="hc-control-buttons is-stack">
                <button class="hc-secondary-button" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="zoomIn" data-hold><ha-icon icon="mdi:magnify-plus-outline"></ha-icon><span>Phóng to</span></button>
                <button class="hc-secondary-button" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="zoomOut" data-hold><ha-icon icon="mdi:magnify-minus-outline"></ha-icon><span>Thu nhỏ</span></button>
                <button class="hc-secondary-button" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="autoScan"><ha-icon icon="mdi:pan-horizontal"></ha-icon><span>Quét tự động</span></button>
              </div>
            </div>
            <p class="hc-control-note">Giữ nút hướng hoặc thu phóng để di chuyển liên tục, thả ra để dừng.</p>
          </section>
          <section class="hc-control-section">
            <h3>Cửa &amp; cảnh báo</h3>
            <div class="hc-control-buttons">
              <button class="hc-secondary-button" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="open_door"><ha-icon icon="mdi:door-open"></ha-icon><span>Mở cửa</span></button>
              <button class="hc-secondary-button" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="close_door"><ha-icon icon="mdi:door-closed"></ha-icon><span>Đóng cửa</span></button>
              <button class="hc-secondary-button" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="alarm"><ha-icon icon="mdi:alarm-light"></ha-icon><span>Bật còi</span></button>
              <button class="hc-secondary-button" type="button" data-action="camera-command" data-device="${esc(device.id)}" data-command="stop_alarm"><ha-icon icon="mdi:alarm-light-off"></ha-icon><span>Tắt còi</span></button>
            </div>
          </section>
        </div>
        <div class="hc-dialog-actions">
          <button class="hc-secondary-button" type="button" data-action="camera-settings" data-device="${esc(device.id)}"><ha-icon icon="mdi:cog-outline"></ha-icon><span>Cài đặt camera</span></button>
          <button class="hc-secondary-button" type="button" data-action="close-dialog">Đóng</button>
        </div>
      </div>`;
    this._dialog.showModal();
  }

  settingControl(deviceId, setting) {
    const common = `data-setting-key="${esc(setting.key)}" data-device="${esc(deviceId)}" data-setting-current="${esc(JSON.stringify(setting.value ?? ""))}"`;
    const value = setting.value;
    if (setting.kind === "boolean") {
      return `<input type="checkbox" role="switch" ${common} ${truthy(value) ? "checked" : ""} aria-label="${esc(setting.label)}">`;
    }
    if (setting.kind === "select") {
      const options = setting.options || [];
      const current = String(value ?? "");
      const rendered = options.map((option) => {
        const optionValue = String(option.value);
        return `<option value="${esc(optionValue)}" ${optionValue === current ? "selected" : ""}>${esc(option.label)}</option>`;
      }).join("");
      const missing = current && !options.some((option) => String(option.value) === current)
        ? `<option value="${esc(current)}" selected>${esc(current)}</option>`
        : "";
      return `<select ${common} aria-label="${esc(setting.label)}">${missing}${rendered}</select>`;
    }
    if (setting.kind === "number") {
      const step = Number.isInteger(Number(value)) ? "1" : "0.1";
      return `<input type="number" ${common} step="${step}" value="${esc(value ?? 0)}" aria-label="${esc(setting.label)}">`;
    }
    return `<input type="text" ${common} value="${esc(value ?? "")}" aria-label="${esc(setting.label)}">`;
  }

  settingsMarkup(device) {
    const settings = device.settings || [];
    if (!settings.length) {
      return `<div class="hc-empty-state is-compact"><ha-icon icon="mdi:tune-variant"></ha-icon><strong>Không có thông số có thể ghi</strong><span>Camera này không trả về cài đặt được hỗ trợ.</span></div>`;
    }
    return `<div class="hc-setting-groups">
      ${SETTING_GROUP_ORDER.map((group) => {
        const rows = settings.filter((setting) => setting.group === group);
        if (!rows.length) return "";
        return `<section class="hc-setting-group">
          <h4>${esc(group)}</h4>
          <div class="hc-setting-list">
            ${rows.map((setting) => `<label class="hc-setting-row">
              <span>${esc(setting.label)}</span>
              ${this.settingControl(device.id, setting)}
            </label>`).join("")}
          </div>
        </section>`;
      }).join("")}
    </div>`;
  }

  deviceSettingsMarkup() {
    const devices = (this._data?.devices || []).filter((device) => (device.settings || []).length);
    if (!devices.length) return "";
    return `<div class="hc-section-heading">
      <div><h3>Cài đặt thiết bị</h3><p>Chỉnh trực tiếp thông số camera qua HANET cloud.</p></div>
    </div>
    <div class="hc-device-settings">
      ${devices.map((device) => `<article class="hc-device-settings-row">
        <div class="hc-device-settings-info">
          <strong>${esc(device.name || device.id)}</strong>
          <span>${esc(device.place_name || "Chưa rõ địa điểm")} · ${(device.settings || []).length} thông số</span>
        </div>
        <div class="hc-device-settings-actions">
          <button class="hc-secondary-button" type="button" data-action="camera-controls" data-device="${esc(device.id)}"><ha-icon icon="mdi:gamepad-variant-outline"></ha-icon><span>Điều khiển</span></button>
          <button class="hc-secondary-button" type="button" data-action="camera-settings" data-device="${esc(device.id)}"><ha-icon icon="mdi:cog-outline"></ha-icon><span>Cài đặt</span></button>
        </div>
      </article>`).join("")}
    </div>`;
  }

  openCameraSettings(deviceId) {
    const device = this.deviceById(deviceId);
    if (!device) return;
    this._dialog.innerHTML = `
      <div class="hc-dialog-head">
        <div><span class="hc-eyebrow">Cài đặt camera</span><h2>${esc(device.name || "Camera")}</h2></div>
        <button class="hc-icon-button" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        ${this.settingsMarkup(device)}
        <div class="hc-dialog-actions">
          <button class="hc-secondary-button" type="button" data-action="camera-controls" data-device="${esc(device.id)}"><ha-icon icon="mdi:gamepad-variant-outline"></ha-icon><span>Điều khiển</span></button>
          <button class="hc-secondary-button" type="button" data-action="close-dialog">Đóng</button>
        </div>
      </div>`;
    this._dialog.showModal();
  }

  async runCameraCommand(device, command, button = null, hold = false) {
    if (button) button.disabled = true;
    try {
      await this._hass.callWS({
        type: "hanet_connect/panel/command",
        device_id: device.id,
        command,
      });
      if (!hold) this.toast(`${commandLabel(command)} · ${device.name || "Camera"}`);
    } catch (error) {
      this.toast(this.wsError(error), true);
    } finally {
      if (button && command !== "stop") button.disabled = false;
    }
  }

  onPointerDown(event) {
    const button = event.target.closest("[data-hold]");
    if (!button || button.disabled) return;
    event.preventDefault();
    const device = this.deviceById(button.dataset.device);
    if (!device) return;
    this._holdCommand = { device, command: button.dataset.command };
    this.runCameraCommand(device, button.dataset.command, button, true);
  }

  onPointerUp() {
    if (!this._holdCommand) return;
    const { device } = this._holdCommand;
    this._holdCommand = null;
    this.runCameraCommand(device, "stop");
  }

  async applySetting(input) {
    const deviceId = input.dataset.device;
    const setting = input.dataset.settingKey;
    const device = this.deviceById(deviceId);
    const row = (device?.settings || []).find((item) => item.key === setting);
    const value = input.type === "checkbox" ? input.checked
      : input.type === "number" ? Number(input.value) : input.value;
    const previous = input.dataset.settingCurrent;
    input.disabled = true;
    try {
      const response = await this._hass.callWS({
        type: "hanet_connect/panel/setting",
        device_id: deviceId,
        setting,
        value,
      });
      this._data = response.snapshot || this._data;
      input.dataset.settingCurrent = JSON.stringify(value);
      this.toast(`${row?.label || setting} đã cập nhật`);
    } catch (error) {
      this.restoreSettingInput(input, previous);
      this.toast(this.wsError(error), true);
    } finally {
      input.disabled = false;
    }
  }

  restoreSettingInput(input, previous) {
    let value = previous;
    try {
      value = JSON.parse(previous);
    } catch (error) {
      value = previous;
    }
    if (input.type === "checkbox") input.checked = truthy(value);
    else input.value = String(value ?? "");
  }

  async openRecordingsForEvent(eventId) {
    const event = this.findEvent(eventId);
    if (!event) return;
    const eventTime = event.occurred_at || event.received_at;
    this._dialog.close();
    this._recordings.day = dayFromValue(eventTime);
    this._recordings.device = String(event.device_id || "");
    this._recordings.search = "";
    this._recordings.period = "";
    this._recordings.clips = [];
    this._recordings.loaded = false;
    this._recordings.error = "";
    this._recordingsRequest += 1;
    this._recordings.loading = false;
    this._tab = "recordings";
    this.render();
    await this.loadRecordings({ resetLimit: true });
    const clip = this.recordingForEvent(event);
    if (clip) {
      this.openClipDialog(clip.id, eventTime);
    } else {
      this.toast("Không tìm thấy clip gần thời điểm sự kiện trên camera này", true);
    }
  }

  recordingForEvent(event) {
    const eventId = String(event.id || "");
    const deviceId = String(event.device_id || "");
    const candidates = (this._recordings.clips || []).filter((clip) => (
      !deviceId || String(clip.device_id || "") === deviceId
    ));
    if (eventId) {
      const exact = candidates.find((clip) => String(clip.event_id || clip.id || "") === eventId);
      if (exact) return exact;
    }
    const eventTime = timestampMs(event.occurred_at || event.received_at);
    if (eventTime === null) return null;
    let best = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (const clip of candidates) {
      const startedAt = timestampMs(clip.timestamp);
      if (startedAt === null) continue;
      const endedAt = startedAt + recordingDurationMs(clip.duration);
      const distance = eventTime < startedAt
        ? startedAt - eventTime
        : eventTime > endedAt ? eventTime - endedAt : 0;
      if (distance < bestDistance) {
        best = clip;
        bestDistance = distance;
      }
    }
    return bestDistance <= 10 * 60 * 1000 ? best : null;
  }

  openClipDialog(clipId, eventTime = null) {
    const clip = this.findClip(clipId);
    if (!clip) return;
    const offset = eventTime
      ? Math.max(0, ((timestampMs(eventTime) || 0) - (timestampMs(clip.timestamp) || 0)) / 1000)
      : 0;
    this._dialog.innerHTML = `
      <div class="hc-dialog-head">
        <div><span class="hc-eyebrow">Cloud recording</span><h2>${esc(clip.device_name || "Ghi hình HANET")}</h2></div>
        <button class="hc-icon-button" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        <video class="hc-dialog-video" controls autoplay playsinline ${clip.thumbnail ? `poster="${esc(clip.thumbnail)}"` : ""} src="${esc(clip.playback)}"></video>
        <div class="hc-detail-grid">
          <div><span>Thời gian</span><strong>${esc(fmtTime(clip.timestamp))}</strong></div>
          <div><span>Thời lượng</span><strong>${esc(durationText(clip.duration))}</strong></div>
          <div><span>Camera</span><strong>${esc(clip.device_name || clip.device_id || "—")}</strong></div>
          <div><span>Địa điểm</span><strong>${esc(clip.place_name || "—")}</strong></div>
          <div><span>Nguồn</span><strong>Cloud</strong></div>
        </div>
        <div class="hc-dialog-actions">
          <button class="hc-secondary-button" type="button" data-action="close-dialog">Đóng</button>
          ${clip.download ? `<a class="hc-primary-button" href="${esc(clip.download)}" download><ha-icon icon="mdi:download"></ha-icon><span>Tải clip</span></a>` : ""}
        </div>
      </div>`;
    const video = this._dialog.querySelector("video");
    if (video && offset > 0) {
      video.addEventListener("loadedmetadata", () => {
        const maximum = Number.isFinite(video.duration) ? Math.max(0, video.duration - 0.25) : offset;
        video.currentTime = Math.max(0, Math.min(offset, maximum));
      }, { once: true });
    }
    this._dialog.showModal();
  }

  openFaceDialog(personId = "") {
    const person = (this._data?.people || []).find((item) => String(item.id) === String(personId));
    const places = this.places();
    const departments = this._data?.departments || [];
    const editing = Boolean(person);
    const placeValue = person?.place_id || places[0]?.id || "";
    this._dialog.innerHTML = `
      <div class="hc-dialog-head">
        <div><span class="hc-eyebrow">FaceID</span><h2>${editing ? "Sửa danh tính" : "Thêm FaceID"}</h2></div>
        <button class="hc-icon-button" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        <form data-form="face" data-person-id="${esc(personId)}">
          <img class="hc-face-preview" data-face-preview src="${esc(person?.image || "")}" alt="Ảnh khuôn mặt" ${person?.image ? "" : "hidden"}>
          <div class="hc-field-grid">
            <label class="hc-field">
              <span>Tên</span>
              <input name="name" required maxlength="120" value="${esc(person?.name || "")}">
            </label>
            <label class="hc-field">
              <span>Địa điểm</span>
              <select name="place_id" required>
                ${places.map((place) => `<option value="${esc(place.id)}" ${place.id === placeValue ? "selected" : ""}>${esc(place.name)}</option>`).join("")}
              </select>
            </label>
            <label class="hc-field">
              <span>Loại</span>
              <select name="person_type">
                <option value="0" ${Number(person?.type) === 0 || !editing ? "selected" : ""}>Người nhà / nhân viên</option>
                <option value="1" ${Number(person?.type) === 1 ? "selected" : ""}>Khách</option>
              </select>
            </label>
            <label class="hc-field">
              <span>Phòng ban</span>
              <select name="department_id">
                <option value="">Không chọn</option>
                ${departments.map((department) => `<option value="${esc(department.id)}" ${String(department.id) === String(person?.department_id || "") ? "selected" : ""}>${esc(department.name || department.id)}</option>`).join("")}
              </select>
            </label>
            <label class="hc-field">
              <span>Giới tính</span>
              <select name="sex">
                <option value="0" ${Number(person?.sex) !== 1 ? "selected" : ""}>Nam</option>
                <option value="1" ${Number(person?.sex) === 1 ? "selected" : ""}>Nữ</option>
              </select>
            </label>
            <label class="hc-field">
              <span>Chức danh</span>
              <input name="title" maxlength="120" value="${esc(person?.title || "")}">
            </label>
            <label class="hc-field">
              <span>Điện thoại</span>
              <input name="phone" type="tel" maxlength="40" value="${esc(person?.phone || "")}">
            </label>
            <label class="hc-field">
              <span>Email</span>
              <input name="email" type="email" maxlength="120" value="${esc(person?.email || "")}">
            </label>
            <label class="hc-field">
              <span>Ngày sinh</span>
              <input name="dob" type="date" value="${esc(person?.dob || "")}">
            </label>
            <label class="hc-field">
              <span>Mã định danh</span>
              <input name="alias_id" maxlength="120" value="${esc(person?.alias_id || "")}">
            </label>
          </div>
          <label class="hc-field">
            <span>${editing ? "Ảnh mới (không bắt buộc)" : "Ảnh khuôn mặt"}</span>
            <input type="file" name="image" accept="image/jpeg,image/png" data-preview="face" ${editing ? "" : "required"}>
          </label>
          <p class="hc-dialog-note">JPEG hoặc PNG, tối đa 6 MB. Nên dùng ảnh chân dung rõ mặt.</p>
          <div class="hc-dialog-actions">
            <button class="hc-secondary-button" type="button" data-action="close-dialog">Huỷ</button>
            <button class="hc-primary-button" type="submit"><ha-icon icon="mdi:content-save-outline"></ha-icon><span>${editing ? "Lưu thay đổi" : "Thêm FaceID"}</span></button>
          </div>
        </form>
      </div>`;
    this.attachImageFallbacks();
    this._dialog.showModal();
  }

  async submitFace(form, editing) {
    const button = form.querySelector('button[type="submit"]');
    const payload = Object.fromEntries(new FormData(form).entries());
    const file = form.querySelector('input[type="file"]')?.files?.[0];
    if (!editing && !file) {
      this.toast("Chọn ảnh khuôn mặt trước khi thêm", true);
      return;
    }
    button.disabled = true;
    try {
      const message = {
        type: editing ? "hanet_connect/panel/face_update" : "hanet_connect/panel/face_create",
        name: payload.name,
        place_id: payload.place_id,
        person_type: Number(payload.person_type || 0),
        department_id: payload.department_id || "",
        alias_id: payload.alias_id || "",
        sex: Number(payload.sex || 0),
        title: payload.title || "",
        phone: payload.phone || "",
        email: payload.email || "",
        dob: payload.dob || "",
      };
      if (file) {
        message.image = await fileToDataUrl(file);
        message.filename = file.name;
      }
      if (editing) {
        const person = (this._data?.people || []).find((item) => String(item.id) === String(form.dataset.personId));
        message.person_id = form.dataset.personId;
        message.previous_department_id = String(person?.department_id || "");
      }
      const response = await this._hass.callWS(message);
      this._data = response.snapshot || this._data;
      this._dialog.close();
      this.render();
      this.toast(editing ? "Đã lưu danh tính" : "Đã thêm FaceID");
    } catch (error) {
      this.toast(this.wsError(error), true);
    } finally {
      button.disabled = false;
    }
  }

  openDeleteDialog(personId) {
    const person = (this._data?.people || []).find((item) => String(item.id) === String(personId));
    if (!person) return;
    this._dialog.innerHTML = `
      <div class="hc-dialog-head">
        <div><span class="hc-eyebrow">FaceID</span><h2>Xoá danh tính</h2></div>
        <button class="hc-icon-button" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        <p>Xoá <b>${esc(person.name || person.id)}</b> khỏi HANET? Thao tác này không thể hoàn tác.</p>
        <div class="hc-dialog-actions">
          <button class="hc-secondary-button" type="button" data-action="close-dialog">Huỷ</button>
          <button class="hc-secondary-button is-danger" type="button" data-action="confirm-delete" data-id="${esc(person.id)}">Xoá FaceID</button>
        </div>
      </div>`;
    this._dialog.showModal();
  }

  async submitDelete(personId, button) {
    button.disabled = true;
    try {
      const person = (this._data?.people || []).find((item) => String(item.id) === String(personId));
      const response = await this._hass.callWS({
        type: "hanet_connect/panel/face_delete",
        person_id: personId,
        ...(person?.place_id ? { place_id: person.place_id } : {}),
      });
      this._data = response.snapshot || this._data;
      this._dialog.close();
      this.render();
      this.toast("Đã xoá FaceID");
    } catch (error) {
      this.toast(this.wsError(error), true);
    } finally {
      button.disabled = false;
    }
  }

  async submitSettings(form) {
    const button = form.querySelector('button[type="submit"]');
    const data = Object.fromEntries(new FormData(form).entries());
    const payload = {
      type: "hanet_connect/panel/settings",
      notify_service: data.notify_service || "",
      notify_persistent: form.querySelector('[name="notify_persistent"]').checked,
    };
    for (const group of this._data.groups || []) {
      payload[`recency_${group.group}`] = Math.max(1, Math.min(3600, Number(data[`recency_${group.group}`] || 10)));
    }
    button.disabled = true;
    try {
      await this._hass.callWS(payload);
      this.toast("Đã lưu cài đặt, integration đang tải lại");
      window.setTimeout(() => this.load(true), 1800);
    } catch (error) {
      this.toast(this.wsError(error), true);
    } finally {
      button.disabled = false;
    }
  }

  onSubmit(event) {
    const form = event.target.closest("[data-form]");
    if (!form) return;
    event.preventDefault();
    if (form.dataset.form === "settings") {
      this.submitSettings(form);
    } else if (form.dataset.form === "face") {
      this.submitFace(form, Boolean(form.dataset.personId));
    }
  }
}

if (!customElements.get("hanet-connect-panel")) {
  customElements.define("hanet-connect-panel", HanetConnectPanel);
}
