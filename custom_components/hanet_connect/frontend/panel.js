const TABS = [
  ["overview", "Tổng quan", "mdi:view-dashboard-outline"],
  ["cameras", "Camera", "mdi:cctv"],
  ["events", "Sự kiện", "mdi:motion-sensor"],
  ["people", "FaceID", "mdi:face-recognition"],
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

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));

const groupOf = (event) => {
  if (event.person_id && !["employee", "visitor", "stranger", "alarm"].includes(event.kind)) {
    return "known";
  }
  return GROUP_FOR_KIND[event.kind] || "motion";
};

const kindLabel = (event) => event.kind_name || KIND_LABELS[event.kind] || event.kind || "Sự kiện";

const fmtTime = (value) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
};

const relative = (value) => {
  if (!value) return "chưa có";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return `${seconds} giây trước`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  return fmtTime(value);
};

const art = (src, alt, cls = "") =>
  src
    ? `<img class="hc-img ${cls}" src="${esc(src)}" alt="${esc(alt)}" loading="lazy">`
    : `<div class="hc-placeholder"><ha-icon icon="mdi:image-off-outline"></ha-icon></div>`;

const fileToDataUrl = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("Không đọc được ảnh"));
    reader.readAsDataURL(file);
  });

class HanetConnectPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._data = null;
    this._tab = "overview";
    this._eventGroup = "all";
    this._faceSearch = "";
    this._loading = false;
    this._error = "";
    this._timer = null;
    this._dialog = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._data && !this._loading) this.load();
  }

  connectedCallback() {
    this.shadowRoot.innerHTML = `
      <link rel="stylesheet" href="/hanet_connect_static/panel.css">
      <div class="hc-shell">
        <header class="hc-header">
          <div class="hc-brand">
            <span class="hc-logo"><ha-icon icon="mdi:cctv"></ha-icon></span>
            <div><h1>HANET Connect</h1><p id="subtitle">Đang tải dữ liệu…</p></div>
          </div>
          <div class="hc-actions">
            <button class="hc-btn" type="button" data-action="refresh">
              <ha-icon icon="mdi:refresh"></ha-icon><span>Làm mới</span>
            </button>
          </div>
        </header>
        <nav class="hc-tabs" role="tablist" aria-label="Khu vực HANET Connect" id="tabs"></nav>
        <main class="hc-panel" id="content"></main>
      </div>
      <dialog id="dialog"></dialog>
      <div id="toast" class="hc-toast" hidden></div>
    `;
    this._tabs = this.shadowRoot.getElementById("tabs");
    this._content = this.shadowRoot.getElementById("content");
    this._subtitle = this.shadowRoot.getElementById("subtitle");
    this._dialog = this.shadowRoot.getElementById("dialog");
    this._toast = this.shadowRoot.getElementById("toast");
    this.shadowRoot.addEventListener("click", (event) => this.onClick(event));
    this.shadowRoot.addEventListener("input", (event) => this.onInput(event));
    this._tabs.addEventListener("keydown", (event) => this.onTabKeydown(event));
    this._dialog.addEventListener("click", (event) => {
      if (event.target === this._dialog) this._dialog.close();
    });
    this._timer = window.setInterval(() => this.autoLoad(), 30000);
    if (this._hass) this.load();
  }

  disconnectedCallback() {
    if (this._timer) window.clearInterval(this._timer);
    this._timer = null;
  }

  async autoLoad() {
    if (document.visibilityState !== "visible") return;
    if (this._dialog?.open) return;
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
      this.render();
    } catch (error) {
      this._error = this.wsError(error);
      if (!this._data || !silent) this.render();
    } finally {
      this._loading = false;
    }
  }

  wsError(error) {
    if (!error) return "Không tải được dữ liệu";
    if (typeof error === "string") return error;
    return error.message || error.code || "Không tải được dữ liệu";
  }

  toast(message, isError = false) {
    this._toast.textContent = message;
    this._toast.classList.toggle("error", isError);
    this._toast.hidden = false;
    window.clearTimeout(this._toastTimer);
    this._toastTimer = window.setTimeout(() => {
      this._toast.hidden = true;
    }, 4200);
  }

  render(skeleton = false) {
    this._tabs.innerHTML = TABS.map(([id, label, icon]) => `
      <button class="hc-tab" type="button" role="tab" data-action="tab" data-tab="${id}"
        aria-selected="${this._tab === id}" aria-controls="content" tabindex="${this._tab === id ? "0" : "-1"}">
        <ha-icon icon="${icon}"></ha-icon><span>${label}</span>
      </button>
    `).join("");

    if (skeleton) {
      this._subtitle.textContent = "Đang tải dữ liệu…";
      this._content.innerHTML = `
        <div class="hc-card"><div class="hc-card-body">
          <div class="hc-skeleton" style="width:42%;margin-bottom:14px"></div>
          <div class="hc-skeleton" style="width:72%;margin-bottom:10px"></div>
          <div class="hc-skeleton" style="width:56%"></div>
        </div></div>`;
      return;
    }

    if (!this._data) {
      this._subtitle.textContent = "Chưa kết nối";
      this._content.innerHTML = `
        <div class="hc-empty">
          <ha-icon icon="mdi:cloud-alert-outline"></ha-icon>
          <strong>${esc(this._error || "Chưa có cấu hình HANET Connect")}</strong>
          <button class="hc-btn" type="button" data-action="refresh">Thử lại</button>
        </div>`;
      return;
    }

    const data = this._data;
    const status = data.status || {};
    this._renderStamp = Date.now();
    this._subtitle.textContent = `${status.online || 0}/${status.devices || 0} camera online · ${data.entry_title || "HANET"}`;
    this._content.innerHTML = this[`render${this._tab[0].toUpperCase()}${this._tab.slice(1)}`]?.() || this.renderOverview();
    const settingsForm = this._content.querySelector('[data-form="settings"]');
    if (settingsForm) {
      settingsForm.addEventListener("submit", (event) => this.submitSettings(event));
    }
    this.attachImageFallbacks();
  }

  attachImageFallbacks() {
    this.shadowRoot.querySelectorAll("img.hc-img").forEach((image) => {
      image.addEventListener("error", () => {
        const placeholder = document.createElement("div");
        placeholder.className = "hc-placeholder";
        placeholder.innerHTML = '<ha-icon icon="mdi:image-off-outline"></ha-icon>';
        image.replaceWith(placeholder);
      }, { once: true });
    });
  }

  latestEventFor(deviceId) {
    return (this._data?.events || []).find((event) => event.device_id === deviceId) || null;
  }

  renderOverview() {
    const data = this._data;
    const status = data.status || {};
    const devices = data.devices || [];
    const events = data.events || [];
    const transport = status.transport === "sse"
      ? `SSE trực tiếp${status.latency_seconds != null ? ` · ${status.latency_seconds}s` : ""}`
      : status.transport === "polling" ? "Polling dự phòng" : status.transport || "Đang kết nối";
    const latest = events.slice(0, 8);
    return `
      <div class="hc-stats">
        <div class="hc-stat"><span>Camera online</span><strong>${status.online || 0}<small class="hc-muted"> / ${status.devices || 0}</small></strong></div>
        <div class="hc-stat"><span>Sự kiện gần đây</span><strong>${events.length}</strong></div>
        <div class="hc-stat"><span>FaceID</span><strong>${data.people?.length || 0}</strong></div>
        <div class="hc-stat"><span>Realtime</span><strong style="font-size:1rem">${esc(transport)}</strong><span>${esc(relative(status.last_event_at))}</span></div>
      </div>
      <div class="hc-section-head" style="margin-top:22px"><h2>Sự kiện mới nhất</h2>
        <button class="hc-btn ghost" type="button" data-action="tab" data-tab="events">Xem tất cả <ha-icon icon="mdi:chevron-right"></ha-icon></button>
      </div>
      ${latest.length ? `<div class="hc-events">${latest.map((event) => this.eventCard(event)).join("")}</div>` : this.empty("mdi:shield-check-outline", "Chưa có sự kiện", "Sự kiện nhận diện sẽ xuất hiện tại đây.")}
      <div class="hc-section-head" style="margin-top:22px"><h2>Camera</h2>
        <button class="hc-btn ghost" type="button" data-action="tab" data-tab="cameras">Quản lý <ha-icon icon="mdi:chevron-right"></ha-icon></button>
      </div>
      <div class="hc-grid">${devices.map((device) => this.deviceCard(device, true)).join("") || this.empty("mdi:cctv-off", "Chưa có camera")}</div>
    `;
  }

  renderCameras() {
    const devices = this._data.devices || [];
    if (!devices.length) return this.empty("mdi:cctv-off", "Chưa có camera", "Kiểm tra tài khoản HANET và làm mới dữ liệu.");
    return `
      <div class="hc-section-head"><h2>Camera và thiết bị</h2><span class="hc-muted">${devices.length} thiết bị</span></div>
      <div class="hc-grid">${devices.map((device) => this.deviceCard(device)).join("")}</div>
    `;
  }

  deviceCard(device, compact = false) {
    const event = this.latestEventFor(device.id);
    const state = device.camera_entity ? this._hass?.states?.[device.camera_entity] : null;
    const token = state?.attributes?.access_token;
    const snapshot = device.camera_entity && token
      ? `/api/camera_proxy/${encodeURIComponent(device.camera_entity)}?token=${encodeURIComponent(token)}&t=${this._renderStamp || Date.now()}`
      : event?.image || "";
    return `
      <article class="hc-card">
        <div class="hc-device-media">
          ${art(snapshot, device.name || "Camera")}
          <span class="hc-badge"><span class="hc-dot ${device.online ? "on" : ""}"></span>${device.online ? "Online" : "Offline"}</span>
        </div>
        <div class="hc-card-body hc-device">
          <div class="hc-between"><h3>${esc(device.name || "HANET")}</h3>
            <button class="hc-btn ghost icon" type="button" data-action="device-events" data-device="${esc(device.id)}" aria-label="Xem sự kiện của ${esc(device.name || "camera")}">
              <ha-icon icon="mdi:history"></ha-icon>
            </button>
          </div>
          <div class="hc-meta"><span>${esc(device.place_name || "Chưa rõ địa điểm")}</span>${device.model ? `<span>${esc(device.model)}</span>` : ""}${device.firmware ? `<span>FW ${esc(device.firmware)}</span>` : ""}</div>
          ${compact ? "" : `<div class="hc-meta"><span>Sự kiện cuối: <b>${esc(event ? kindLabel(event) : "chưa có")}</b></span><span>${esc(event ? relative(event.occurred_at) : "")}</span></div>`}
        </div>
      </article>`;
  }

  renderEvents() {
    const all = this._data.events || [];
    const events = this._eventGroup === "all"
      ? all
      : all.filter((event) => groupOf(event) === this._eventGroup);
    const groups = this._data.groups || [];
    return `
      <div class="hc-section-head"><h2>Sự kiện</h2><span class="hc-muted">${events.length} sự kiện</span></div>
      <div class="hc-row" style="margin-bottom:14px" role="group" aria-label="Lọc theo nhóm">
        <button class="hc-chip" type="button" data-action="filter-events" data-group="all" aria-pressed="${this._eventGroup === "all"}">Tất cả</button>
        ${groups.map((group) => `<button class="hc-chip" type="button" data-action="filter-events" data-group="${esc(group.group)}" aria-pressed="${this._eventGroup === group.group}">${esc(group.label)}</button>`).join("")}
      </div>
      ${events.length ? `<div class="hc-events">${events.map((event) => this.eventCard(event)).join("")}</div>` : this.empty("mdi:motion-sensor-off", "Không có sự kiện", "Thử chọn nhóm khác hoặc làm mới dữ liệu.")}
    `;
  }

  eventCard(event) {
    return `
      <button class="hc-event" type="button" data-action="event" data-id="${esc(event.id)}" title="${esc(kindLabel(event))}">
        <span class="hc-event-media">${art(event.image, kindLabel(event))}</span>
        <span class="hc-event-body">
          <strong>${esc(event.person_name || kindLabel(event))}</strong>
          <small>${esc(kindLabel(event))}${event.device_name ? ` · ${esc(event.device_name)}` : ""}</small>
          <small>${esc(fmtTime(event.occurred_at))}</small>
        </span>
      </button>`;
  }

  renderPeople() {
    const people = this._data.people || [];
    const places = this.places();
    const filtered = people.filter((person) =>
      !this._faceSearch
      || String(person.name || "").toLocaleLowerCase().includes(this._faceSearch)
      || String(person.department || "").toLocaleLowerCase().includes(this._faceSearch)
    );
    return `
      <div class="hc-section-head"><h2>FaceID</h2>
        <div class="hc-row">
          <input class="hc-search" type="search" placeholder="Tìm tên hoặc phòng ban" aria-label="Tìm FaceID" value="${esc(this._faceSearch)}" data-search="people">
          <button class="hc-btn primary" type="button" data-action="add-face" ${places.length ? "" : "disabled"}>
            <ha-icon icon="mdi:account-plus-outline"></ha-icon><span>Thêm FaceID</span>
          </button>
        </div>
      </div>
      ${!places.length ? this.empty("mdi:map-marker-off-outline", "Chưa có địa điểm", "Cần tải được place từ HANET trước khi thêm FaceID.") : ""}
      ${filtered.length ? `<div class="hc-people">${filtered.map((person) => this.personCard(person)).join("")}</div>` : this.empty("mdi:face-recognition", "Chưa có FaceID", "Thêm ảnh và tên để nhận diện người quen.")}
    `;
  }

  personCard(person) {
    return `
      <article class="hc-person" data-person-name="${esc(String(person.name || "").toLocaleLowerCase())}" data-person-department="${esc(String(person.department || "").toLocaleLowerCase())}">
        ${art(person.image, person.name || "FaceID")}
        <div class="hc-person-body">
          <strong>${esc(person.name || "FaceID")}</strong>
          <span class="hc-muted">${esc(person.type_name || (person.type === 0 ? "Nhân viên" : person.type === 1 ? "Khách" : "FaceID"))}</span>
          ${person.department ? `<span class="hc-muted">${esc(person.department)}</span>` : ""}
        </div>
        <div class="hc-person-actions">
          <button class="hc-btn" type="button" data-action="edit-face" data-id="${esc(person.id)}">Sửa</button>
          <button class="hc-btn danger" type="button" data-action="delete-face" data-id="${esc(person.id)}">Xoá</button>
        </div>
      </article>`;
  }

  renderSettings() {
    const data = this._data;
    const settings = data.settings || {};
    const status = data.status || {};
    return `
      <div class="hc-settings-grid">
        <form class="hc-card" data-form="settings">
          <div class="hc-card-body">
            <h2>Thời gian giữ trạng thái</h2>
            <p class="hc-hint">Số giây sensor giữ ON sau lần nhận diện gần nhất. Đổi xong integration tự tải lại.</p>
            <div class="hc-fields">
              ${(data.groups || []).map((group) => `
                <div class="hc-field">
                  <label for="recency-${esc(group.group)}">${esc(group.label)} (giây)</label>
                  <input id="recency-${esc(group.group)}" type="number" min="1" max="3600" step="1" required
                    name="recency_${esc(group.group)}" value="${Number(settings[`recency_${group.group}`] || 10)}">
                </div>`).join("")}
            </div>
            <h2 style="margin-top:20px">Thông báo</h2>
            <div class="hc-field">
              <label for="notify-service">Dịch vụ notify</label>
              <input id="notify-service" type="text" name="notify_service" placeholder="notify.mobile_app_abc" value="${esc(settings.notify_service || "")}">
            </div>
            <label class="hc-row" style="gap:8px">
              <input type="checkbox" name="notify_persistent" ${settings.notify_persistent ? "checked" : ""}>
              <span>Hiện thông báo trong Home Assistant</span>
            </label>
            <div class="hc-form-footer">
              <button class="hc-btn primary" type="submit"><ha-icon icon="mdi:content-save-outline"></ha-icon><span>Lưu cài đặt</span></button>
            </div>
          </div>
        </form>
        <section class="hc-card"><div class="hc-card-body">
          <h2>Trạng thái kết nối</h2>
          <div class="hc-meta" style="display:grid;gap:10px;margin-top:12px">
            <span>Kênh realtime: <b>${esc(status.transport || "—")}</b></span>
            <span>Độ trễ gần nhất: <b>${status.latency_seconds != null ? `${esc(status.latency_seconds)} giây` : "—"}</b></span>
            <span>Sự kiện gần nhất: <b>${esc(relative(status.last_event_at))}</b></span>
            <span>Config entry: <b>${esc(data.entry_id)}</b></span>
          </div>
          <p class="hc-hint" style="margin-top:16px">Cần chỉnh quyền license hoặc thông báo nâng cao? Mở Options của integration trong Settings → Devices &amp; services.</p>
        </div></section>
      </div>
    `;
  }

  empty(icon, title, copy = "") {
    return `<div class="hc-empty"><ha-icon icon="${icon}"></ha-icon><strong>${esc(title)}</strong>${copy ? `<span>${esc(copy)}</span>` : ""}</div>`;
  }

  places() {
    const seen = new Map();
    for (const device of this._data?.devices || []) {
      if (device.place_id) seen.set(String(device.place_id), device.place_name || `Địa điểm ${device.place_id}`);
    }
    for (const person of this._data?.people || []) {
      if (person.place_id) seen.set(String(person.place_id), seen.get(String(person.place_id)) || `Địa điểm ${person.place_id}`);
    }
    return Array.from(seen, ([id, name]) => ({ id, name }));
  }

  onClick(event) {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    const action = target.dataset.action;
    if (action === "tab") {
      this._tab = target.dataset.tab || "overview";
      this.render();
    } else if (action === "refresh") {
      this.load();
    } else if (action === "filter-events") {
      this._eventGroup = target.dataset.group || "all";
      this.render();
    } else if (action === "event") {
      this.openEvent(target.dataset.id);
    } else if (action === "device-events") {
      this._eventGroup = "all";
      this._tab = "events";
      this.render();
      const deviceId = target.dataset.device;
      this._content.querySelectorAll(".hc-event").forEach((card) => {
        const item = (this._data.events || []).find((row) => row.id === card.dataset.id);
        card.hidden = Boolean(deviceId && item && item.device_id !== deviceId);
      });
      this.toast("Đang lọc sự kiện theo camera");
    } else if (action === "add-face") {
      this.openFaceDialog();
    } else if (action === "edit-face") {
      this.openFaceDialog(target.dataset.id);
    } else if (action === "delete-face") {
      this.openDeleteDialog(target.dataset.id);
    } else if (action === "close-dialog") {
      this._dialog.close();
    }
  }

  onTabKeydown(event) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const tabs = [...this._tabs.querySelectorAll(".hc-tab")];
    const current = tabs.indexOf(this.shadowRoot.activeElement);
    const next = event.key === "Home" ? 0
      : event.key === "End" ? tabs.length - 1
        : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    this._tab = tabs[next].dataset.tab;
    this.render();
    this._tabs.querySelector(`[data-tab="${this._tab}"]`)?.focus();
  }

  onInput(event) {
    const input = event.target.closest('[data-search="people"]');
    if (!input) return;
    this._faceSearch = input.value.trim().toLocaleLowerCase();
    this.shadowRoot.querySelectorAll("[data-person-name]").forEach((card) => {
      const haystack = `${card.dataset.personName} ${card.dataset.personDepartment}`;
      card.hidden = Boolean(this._faceSearch) && !haystack.includes(this._faceSearch);
    });
  }

  openEvent(eventId) {
    const item = (this._data?.events || []).find((event) => event.id === eventId);
    if (!item) return;
    this._dialog.innerHTML = `
      <div class="hc-dialog-head"><h2>${esc(item.person_name || kindLabel(item))}</h2>
        <button class="hc-btn ghost icon" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        ${item.image ? `<img class="hc-dialog-image hc-img" src="${esc(item.image)}" alt="${esc(kindLabel(item))}">` : this.empty("mdi:image-off-outline", "Không có ảnh")}
        <div class="hc-meta" style="margin-top:14px">
          <span><b>${esc(kindLabel(item))}</b></span>
          <span>${esc(item.device_name || item.device_id || "")}</span>
          <span>${esc(item.place_name || "")}</span>
          <span>${esc(fmtTime(item.occurred_at))}</span>
        </div>
      </div>`;
    this.attachImageFallbacks();
    this._dialog.showModal();
  }

  openFaceDialog(personId = "") {
    const person = (this._data?.people || []).find((item) => item.id === personId);
    const places = this.places();
    const editing = Boolean(person);
    const placeValue = person?.place_id || places[0]?.id || "";
    this._dialog.innerHTML = `
      <div class="hc-dialog-head"><h2>${editing ? "Sửa FaceID" : "Thêm FaceID"}</h2>
        <button class="hc-btn ghost icon" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        <form data-form="face" data-person-id="${esc(personId)}">
          <div class="hc-field"><label for="face-name">Tên</label>
            <input id="face-name" name="name" required maxlength="120" value="${esc(person?.name || "")}">
          </div>
          <div class="hc-fields">
            <div class="hc-field"><label for="face-place">Địa điểm</label>
              <select id="face-place" name="place_id" required>
                ${places.map((place) => `<option value="${esc(place.id)}" ${place.id === placeValue ? "selected" : ""}>${esc(place.name)}</option>`).join("")}
              </select>
            </div>
            <div class="hc-field"><label for="face-type">Loại</label>
              <select id="face-type" name="person_type">
                <option value="0" ${Number(person?.type) === 0 || !editing ? "selected" : ""}>Nhân viên / người nhà</option>
                <option value="1" ${Number(person?.type) === 1 ? "selected" : ""}>Khách</option>
              </select>
            </div>
            <div class="hc-field"><label for="face-department">Phòng ban</label>
              <select id="face-department" name="department_id">
                <option value="">Không chọn</option>
                ${(this._data.departments || []).map((department) => `<option value="${esc(department.id)}" ${String(department.id) === String(person?.department_id || "") ? "selected" : ""}>${esc(department.name || department.id)}</option>`).join("")}
              </select>
            </div>
            <div class="hc-field"><label for="face-alias">Mã định danh</label>
              <input id="face-alias" name="alias_id" value="${esc(person?.alias_id || "")}">
            </div>
          </div>
          <div class="hc-field"><label for="face-image">${editing ? "Ảnh mới (không bắt buộc)" : "Ảnh khuôn mặt"}</label>
            <input id="face-image" name="image" type="file" accept="image/jpeg,image/png" ${editing ? "" : "required"}>
            <p class="hc-hint">JPEG hoặc PNG, tối đa 6 MB. Nên dùng ảnh chân dung rõ mặt.</p>
          </div>
          <div class="hc-form-footer">
            <button class="hc-btn" type="button" data-action="close-dialog">Huỷ</button>
            <button class="hc-btn primary" type="submit"><ha-icon icon="mdi:content-save-outline"></ha-icon><span>${editing ? "Lưu thay đổi" : "Thêm FaceID"}</span></button>
          </div>
        </form>
      </div>`;
    const form = this._dialog.querySelector("form");
    form.addEventListener("submit", (event) => this.submitFace(event, editing));
    this._dialog.showModal();
  }

  async submitFace(event, editing) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const payload = Object.fromEntries(new FormData(form).entries());
    const file = form.querySelector('input[type="file"]')?.files?.[0];
    if (!editing && !file) {
      this.toast("Chọn ảnh khuôn mặt trước khi thêm", true);
      return;
    }
    button.disabled = true;
    try {
      if (file) {
        payload.image = await fileToDataUrl(file);
        payload.filename = file.name;
      } else {
        delete payload.image;
      }
      const message = {
        type: editing ? "hanet_connect/panel/face_update" : "hanet_connect/panel/face_create",
        name: payload.name,
        place_id: payload.place_id,
        person_type: Number(payload.person_type || 0),
        department_id: payload.department_id || "",
        alias_id: payload.alias_id || "",
      };
      if (editing) {
        message.person_id = form.dataset.personId;
        if (payload.image) {
          message.image = payload.image;
          message.filename = payload.filename;
        }
      } else {
        message.image = payload.image;
        message.filename = payload.filename;
      }
      const response = await this._hass.callWS(message);
      this._data = response.snapshot || this._data;
      this._dialog.close();
      this.render();
      this.toast(editing ? "Đã lưu FaceID" : "Đã thêm FaceID");
    } catch (error) {
      this.toast(this.wsError(error), true);
    } finally {
      button.disabled = false;
    }
  }

  openDeleteDialog(personId) {
    const person = (this._data?.people || []).find((item) => item.id === personId);
    if (!person) return;
    this._dialog.innerHTML = `
      <div class="hc-dialog-head"><h2>Xoá FaceID</h2>
        <button class="hc-btn ghost icon" type="button" data-action="close-dialog" aria-label="Đóng"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="hc-dialog-body">
        <p>Xoá <b>${esc(person.name || person.id)}</b> khỏi HANET? Thao tác này không thể hoàn tác.</p>
        <div class="hc-form-footer">
          <button class="hc-btn" type="button" data-action="close-dialog">Huỷ</button>
          <button class="hc-btn danger" type="button" data-action="confirm-delete" data-id="${esc(person.id)}">Xoá FaceID</button>
        </div>
      </div>`;
    this._dialog.querySelector('[data-action="confirm-delete"]').addEventListener("click", (event) => this.submitDelete(event.currentTarget.dataset.id, event.currentTarget));
    this._dialog.showModal();
  }

  async submitDelete(personId, button) {
    button.disabled = true;
    try {
      const person = (this._data?.people || []).find((item) => item.id === personId);
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

  async submitSettings(event) {
    event.preventDefault();
    const form = event.currentTarget;
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
}

if (!customElements.get("hanet-connect-panel")) {
  customElements.define("hanet-connect-panel", HanetConnectPanel);
}
