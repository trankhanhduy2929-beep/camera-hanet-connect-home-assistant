// Generated from panel.css by scripts/sync_panel_css.py.
export const PANEL_CSS = String.raw`:host {
  display: block;
  min-height: 100vh;
  color: var(--primary-text-color);
  background:
    radial-gradient(ellipse at 96% 0%, color-mix(in srgb, var(--primary-color, #007e86) 14%, transparent), transparent 38%),
    var(--primary-background-color, var(--ha-card-background));
  font-family: var(--paper-font-body1_-_font-family, Roboto, "Segoe UI", sans-serif);
  --hc-page: var(--primary-background-color, #f1f6f9);
  --hc-surface: var(--card-background-color, var(--ha-card-background, #fff));
  --hc-soft: var(--secondary-background-color, rgba(0, 0, 0, 0.04));
  --hc-hover: color-mix(in srgb, var(--primary-color, #007e86) 10%, var(--hc-surface));
  --hc-line: var(--divider-color, rgba(21, 50, 77, 0.14));
  --hc-line-strong: color-mix(in srgb, var(--primary-text-color) 28%, transparent);
  --hc-muted: var(--secondary-text-color, #4e6377);
  --hc-ink: var(--primary-text-color, #15324d);
  --hc-accent: var(--primary-color, #007e86);
  --hc-accent-dark: color-mix(in srgb, var(--hc-accent) 78%, #001f24);
  --hc-accent-ink: color-mix(in srgb, var(--hc-accent) 52%, var(--hc-ink));
  --hc-accent-soft: color-mix(in srgb, var(--hc-accent) 14%, var(--hc-surface));
  --hc-success: var(--success-color, #17663f);
  --hc-success-soft: color-mix(in srgb, var(--hc-success) 12%, var(--hc-surface));
  --hc-warning: var(--warning-color, #805008);
  --hc-warning-soft: color-mix(in srgb, var(--hc-warning) 14%, var(--hc-surface));
  --hc-danger: var(--error-color, #ad2945);
  --hc-danger-soft: color-mix(in srgb, var(--hc-danger) 12%, var(--hc-surface));
  --hc-radius: var(--ha-card-border-radius, 16px);
  --hc-gap: 20px;
}

* { box-sizing: border-box; }
button, input, select, textarea { font: inherit; letter-spacing: normal; }
button, select { cursor: pointer; }
button { -webkit-tap-highlight-color: transparent; }
button:disabled, input:disabled, select:disabled { opacity: 0.55; cursor: not-allowed; }
:focus-visible { outline: 2px solid var(--hc-accent-ink); outline-offset: 3px; }
[hidden] { display: none !important; }
h1, h2, h3, p { margin: 0; }
h1, h2, h3, strong { font-weight: 650; }
.hc-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }

.hc-app { min-height: 100vh; }
.hc-topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 76px;
  padding: 12px clamp(16px, 3vw, 32px);
  border-bottom: 1px solid var(--hc-line);
  background: color-mix(in srgb, var(--hc-surface) 92%, transparent);
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
}
.hc-brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
.hc-brand-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  border: 1px solid color-mix(in srgb, var(--hc-accent) 35%, var(--hc-surface));
  border-radius: 14px;
  color: var(--hc-accent-ink);
  background: linear-gradient(145deg, var(--hc-accent-soft), var(--hc-surface));
  font-size: 1.375rem;
  font-weight: 750;
}
.hc-brand-copy { min-width: 0; }
.hc-brand-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.hc-brand-title h1 { font-size: 1.125rem; line-height: 1.35; }
.hc-brand-title > span { color: var(--hc-muted); font-size: 0.75rem; }
.hc-brand-copy p { max-width: 460px; margin-top: 2px; color: var(--hc-muted); font-size: 0.75rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hc-topbar-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
.hc-connection { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 6px 12px; border-radius: 999px; color: var(--hc-warning); background: var(--hc-warning-soft); font-size: 0.75rem; font-weight: 650; }
.hc-connection.is-online { color: var(--hc-success); background: var(--hc-success-soft); }
.hc-connection.is-error { color: var(--hc-danger); background: var(--hc-danger-soft); }
.hc-status-dot { width: 7px; height: 7px; flex: 0 0 7px; border-radius: 50%; background: currentColor; }

.hc-primary-nav {
  position: sticky;
  top: 76px;
  z-index: 25;
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding: 10px clamp(16px, 3vw, 32px);
  border-bottom: 1px solid var(--hc-line);
  background: color-mix(in srgb, var(--hc-page) 88%, transparent);
  -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px);
  scrollbar-width: thin;
}
.hc-nav-item {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  flex: 0 0 auto;
  min-height: 44px;
  padding: 8px 16px;
  border: 1px solid transparent;
  border-radius: 12px;
  color: var(--hc-muted);
  background: transparent;
  font-weight: 650;
  white-space: nowrap;
  transition: background-color 160ms ease, color 160ms ease, border-color 160ms ease;
}
.hc-nav-item:hover { color: var(--hc-ink); background: var(--hc-surface); }
.hc-nav-item[aria-selected="true"] { color: var(--hc-accent-ink); background: var(--hc-accent-soft); border-color: color-mix(in srgb, var(--hc-accent) 38%, transparent); }
.hc-nav-item ha-icon { --mdc-icon-size: 20px; }

.hc-workspace { width: 100%; max-width: 1660px; margin-inline: auto; padding: 32px clamp(16px, 3vw, 44px) 64px; }
.hc-page { min-width: 0; }
.hc-page-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-width: 0; margin-bottom: 24px; }
.hc-page-heading > div { min-width: 0; }
.hc-page-heading h2 { font-size: clamp(1.35rem, 2vw, 1.6rem); line-height: 1.3; text-wrap: balance; }
.hc-page-heading p { margin-top: 6px; color: var(--hc-muted); font-size: 0.875rem; }
.hc-eyebrow { display: block; margin-bottom: 6px; color: var(--hc-accent-ink); font-size: 0.75rem; font-weight: 650; }
.hc-hero-heading .hc-search-box { width: min(320px, 100%); }
.hc-page-heading.is-identity { align-items: flex-end; }
.hc-toolbar { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px; min-width: 0; }
.hc-toolbar .hc-search-box { width: min(250px, 100%); }

.hc-search-box, .hc-control-icon {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  min-height: 44px;
  padding-left: 12px;
  border: 1px solid var(--hc-line-strong);
  border-radius: 12px;
  background: var(--hc-surface);
}
.hc-search-box ha-icon, .hc-control-icon ha-icon { color: var(--hc-muted); --mdc-icon-size: 19px; }
.hc-search-box input, .hc-control-icon input { width: 100%; min-width: 0; min-height: 42px; padding: 0 12px 0 0; border: 0; background: transparent; color: var(--hc-ink); box-shadow: none; outline: none; }
.hc-control-icon { width: 190px; }
.hc-search-box:focus-within, .hc-control-icon:focus-within { border-color: var(--hc-accent-ink); box-shadow: 0 0 0 3px color-mix(in srgb, var(--hc-accent-ink) 18%, transparent); }

.hc-primary-button, .hc-secondary-button, .hc-icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 44px;
  padding: 10px 16px;
  border: 1px solid var(--hc-line-strong);
  border-radius: 12px;
  font-weight: 650;
  line-height: 1.4;
  text-decoration: none;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease;
}
.hc-primary-button { color: var(--text-primary-color, #fff); border-color: var(--hc-accent); background: var(--hc-accent); }
.hc-primary-button:hover:not(:disabled) { border-color: var(--hc-accent-dark); background: var(--hc-accent-dark); }
.hc-secondary-button, .hc-icon-button { color: var(--hc-ink); background: var(--hc-surface); }
.hc-secondary-button:hover:not(:disabled), .hc-icon-button:hover:not(:disabled) { background: var(--hc-hover); }
.hc-secondary-button.is-danger { color: var(--hc-danger); border-color: transparent; background: var(--hc-danger-soft); }
.hc-icon-button { width: 44px; height: 44px; flex: 0 0 44px; padding: 0; }
.hc-icon-button.is-small { width: 36px; height: 36px; min-height: 36px; flex-basis: 36px; border-radius: 10px; }
.hc-primary-button ha-icon, .hc-secondary-button ha-icon, .hc-icon-button ha-icon { --mdc-icon-size: 19px; }
.hc-load-more { display: flex; margin: 24px auto 0; }

.hc-metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 28px; border: 1px solid var(--hc-line); border-radius: var(--hc-radius); background: var(--hc-surface); overflow: hidden; }
.hc-metric-card { display: flex; align-items: center; gap: 12px; min-width: 0; min-height: 108px; padding: 20px; border-right: 1px solid var(--hc-line); }
.hc-metric-card:last-child { border-right: 0; }
.hc-metric-card > div { display: grid; gap: 4px; min-width: 0; }
.hc-metric-card strong { font-size: 1.625rem; line-height: 1.2; font-variant-numeric: tabular-nums; }
.hc-metric-card > div span { color: var(--hc-muted); font-size: 0.8125rem; overflow-wrap: anywhere; }
.hc-metric-icon { display: grid; place-items: center; width: 40px; height: 40px; flex: 0 0 40px; border-radius: 12px; color: var(--hc-accent-ink); background: var(--hc-accent-soft); }
.hc-metric-icon ha-icon { --mdc-icon-size: 21px; }
.hc-metric-card.is-online .hc-metric-icon { color: var(--hc-success); background: var(--hc-success-soft); }
.hc-metric-card.is-offline .hc-metric-icon, .hc-metric-card.is-events .hc-metric-icon { color: var(--hc-warning); background: var(--hc-warning-soft); }
.hc-metric-card.is-faces .hc-metric-icon { color: var(--hc-accent-ink); background: var(--hc-accent-soft); }

.hc-section-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 0 0 16px; }
.hc-section-heading h3 { font-size: 1.05rem; }
.hc-section-heading p { margin-top: 3px; color: var(--hc-muted); font-size: 0.8rem; }

.hc-camera-grid, .hc-recording-grid, .hc-person-grid { display: grid; gap: 20px; min-width: 0; }
.hc-camera-grid { grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr)); }
.hc-recording-grid { grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr)); }
.hc-person-grid { grid-template-columns: repeat(auto-fill, minmax(min(100%, 250px), 1fr)); }
.hc-camera-card, .hc-event-card, .hc-recording-card, .hc-person-card { min-width: 0; overflow: hidden; border: 1px solid var(--hc-line); border-radius: var(--hc-radius); background: var(--hc-surface); transition: border-color 160ms ease, box-shadow 160ms ease; }
.hc-camera-card:hover, .hc-recording-card:hover, .hc-person-card:hover { border-color: var(--hc-line-strong); box-shadow: 0 10px 30px rgba(21, 50, 77, 0.08); }

.hc-camera-preview, .hc-recording-preview {
  position: relative;
  display: grid;
  place-items: center;
  width: 100%;
  aspect-ratio: 16 / 9;
  padding: 0;
  overflow: hidden;
  border: 0;
  color: var(--hc-ink);
  background: var(--hc-soft);
}
.hc-camera-preview .hc-img, .hc-recording-preview .hc-img, .hc-person-image .hc-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.hc-camera-preview:hover .hc-img { transform: scale(1.025); }
.hc-camera-preview .hc-img { transition: transform 240ms ease; }
.hc-media-placeholder { display: grid; place-items: center; align-content: center; gap: 6px; width: 100%; height: 100%; min-height: 110px; color: var(--hc-muted); background: var(--hc-soft); font-size: 0.75rem; }
.hc-media-placeholder ha-icon { --mdc-icon-size: 30px; }
.hc-state-badge { display: inline-flex; align-items: center; gap: 6px; padding: 5px 9px; border-radius: 999px; color: var(--hc-danger); background: color-mix(in srgb, var(--hc-surface) 88%, transparent); font-size: 0.75rem; font-weight: 650; white-space: nowrap; }
.hc-camera-preview > .hc-state-badge, .hc-recording-preview > .hc-state-badge { position: absolute; top: 10px; left: 10px; }
.hc-state-badge > span { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.hc-state-badge.is-online { color: var(--hc-success); }
.hc-preview-note { position: absolute; right: 10px; bottom: 10px; display: inline-flex; align-items: center; gap: 5px; padding: 5px 8px; border-radius: 999px; color: #fff; background: rgba(21, 50, 77, 0.7); font-size: 0.7rem; }
.hc-preview-note ha-icon { --mdc-icon-size: 14px; }
.hc-camera-body { display: grid; gap: 14px; padding: 16px; }
.hc-camera-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.hc-camera-title { min-width: 0; }
.hc-camera-title strong { display: block; font-size: 1rem; overflow-wrap: anywhere; }
.hc-camera-title span { display: block; margin-top: 4px; color: var(--hc-muted); font-size: 0.8125rem; overflow-wrap: anywhere; }
.hc-camera-model { flex: 0 0 auto; padding: 3px 8px; border-radius: 8px; color: var(--hc-muted); background: var(--hc-soft); font-size: 0.7rem; }
.hc-camera-meta { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding-top: 12px; border-top: 1px solid var(--hc-line); color: var(--hc-muted); font-size: 0.75rem; }
.hc-camera-meta span { display: inline-flex; align-items: center; gap: 5px; min-width: 0; overflow-wrap: anywhere; }
.hc-camera-meta ha-icon { --mdc-icon-size: 15px; }
.hc-camera-quick { display: flex; align-items: center; gap: 6px; }
.hc-camera-quick .hc-icon-button { color: var(--hc-muted); }
.hc-camera-quick .hc-icon-button:hover:not(:disabled) { color: var(--hc-accent-ink); }
.hc-camera-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.hc-camera-actions .hc-secondary-button { min-height: 38px; padding: 7px 10px; font-size: 0.82rem; }

.hc-filter-bar { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: center; gap: 12px; margin-bottom: 16px; padding: 16px; border: 1px solid var(--hc-line); border-radius: var(--hc-radius); background: var(--hc-surface); }
.hc-filter-bar .hc-search-box { grid-column: 2 / -1; }
.hc-filter-bar select, .hc-toolbar select { width: 100%; min-width: 0; min-height: 44px; padding: 9px 30px 9px 12px; border: 1px solid var(--hc-line-strong); border-radius: 12px; color: var(--hc-ink); background: var(--hc-surface); }
.hc-filter-bar.is-recordings { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.hc-filter-bar.is-recordings .hc-search-box { grid-column: auto; }
.hc-quick-filters { display: flex; gap: 4px; min-width: 0; }
.hc-filter-chip { flex: 1 1 0; min-height: 44px; padding: 8px 12px; border: 1px solid transparent; border-radius: 12px; color: var(--hc-ink); background: var(--hc-soft); font-weight: 650; white-space: nowrap; }
.hc-filter-chip:hover { background: var(--hc-hover); }
.hc-filter-chip.is-active { color: var(--hc-accent-ink); background: var(--hc-accent-soft); border-color: var(--hc-accent); }

.hc-inline-status { display: flex; align-items: center; gap: 8px; min-height: 40px; margin-bottom: 12px; color: var(--hc-muted); font-size: 0.8125rem; }
.hc-inline-status.is-error { color: var(--hc-danger); }
.hc-inline-status.is-loading::before { content: ""; width: 14px; height: 14px; border: 2px solid var(--hc-line); border-top-color: var(--hc-accent); border-radius: 50%; animation: hc-spin 800ms linear infinite; }

.hc-event-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 420px), 1fr)); gap: 16px; }
.hc-event-card { display: grid; grid-template-columns: 120px minmax(0, 1fr); align-items: stretch; cursor: pointer; text-align: left; }
.hc-event-card:hover { background: var(--hc-hover); border-color: var(--hc-line-strong); }
.hc-event-image { min-height: 140px; width: 120px; overflow: hidden; background: var(--hc-soft); }
.hc-event-image .hc-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.hc-event-body { min-width: 0; padding: 16px; }
.hc-event-body strong { display: block; font-size: 1rem; overflow-wrap: anywhere; }
.hc-event-body p { margin-top: 6px; color: var(--hc-muted); font-size: 0.8125rem; overflow-wrap: anywhere; }
.hc-event-meta { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-top: 12px; color: var(--hc-muted); font-size: 0.75rem; }
.hc-event-badges { display: inline-flex; flex-wrap: wrap; gap: 6px; }
.hc-kind-tag, .hc-source-tag, .hc-type-tag, .hc-duration-tag { display: inline-flex; align-items: center; padding: 3px 8px; border-radius: 8px; color: var(--hc-success); background: var(--hc-success-soft); font-size: 0.72rem; font-weight: 650; }
.hc-kind-tag.is-alarm, .hc-kind-tag.is-stranger { color: var(--hc-danger); background: var(--hc-danger-soft); }
.hc-kind-tag.is-human, .hc-kind-tag.is-plate { color: var(--hc-warning); background: var(--hc-warning-soft); }
.hc-source-tag { color: var(--hc-muted); background: var(--hc-soft); }
.hc-type-tag.is-visitor { color: var(--hc-muted); background: var(--hc-soft); }

.hc-segmented { display: inline-flex; gap: 4px; margin-bottom: 12px; padding: 4px; border-radius: 12px; background: var(--hc-soft); }
.hc-segment { min-height: 38px; padding: 7px 18px; border: 0; border-radius: 9px; color: var(--hc-muted); background: transparent; font-weight: 650; }
.hc-segment.is-active { color: var(--hc-accent-ink); background: var(--hc-surface); box-shadow: 0 1px 3px rgba(0, 0, 0, 0.14); }
.hc-source-help { margin-bottom: 12px; color: var(--hc-muted); font-size: 0.8rem; }
.hc-recording-preview .hc-img.is-cover { object-fit: cover; }
.hc-play-circle { position: absolute; display: grid; place-items: center; width: 46px; height: 46px; border-radius: 50%; color: #fff; background: rgba(21, 50, 77, 0.78); box-shadow: 0 4px 18px rgba(0, 0, 0, 0.24); }
.hc-play-circle ha-icon { --mdc-icon-size: 26px; margin-left: 2px; }
.hc-recording-preview:hover .hc-play-circle { background: var(--hc-accent); }
.hc-duration-tag { position: absolute; right: 9px; bottom: 9px; color: #fff; background: rgba(21, 50, 77, 0.72); }
.hc-recording-body { display: grid; gap: 5px; padding: 14px 16px; }
.hc-recording-body strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hc-recording-body > span { color: var(--hc-muted); font-size: 0.8125rem; }
.hc-recording-actions { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 6px; }

.hc-person-card { display: grid; grid-template-columns: 92px minmax(0, 1fr); }
.hc-person-image { min-height: 128px; background: var(--hc-soft); }
.hc-person-body { display: grid; align-content: start; gap: 10px; padding: 14px; min-width: 0; }
.hc-person-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; min-width: 0; }
.hc-person-heading > div { min-width: 0; }
.hc-person-heading strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hc-person-heading span { display: block; margin-top: 3px; color: var(--hc-muted); font-size: 0.78rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hc-type-tag { flex: 0 0 auto; font-size: 0.68rem; }
.hc-person-meta { display: grid; gap: 4px; color: var(--hc-muted); font-size: 0.75rem; }
.hc-person-meta span { display: flex; align-items: center; gap: 5px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hc-person-meta ha-icon { --mdc-icon-size: 14px; flex: 0 0 auto; }
.hc-person-actions { display: flex; gap: 6px; }
.hc-person-actions .hc-secondary-button { min-height: 34px; padding: 5px 9px; font-size: 0.78rem; }

.hc-settings-grid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 0.9fr); align-items: start; gap: var(--hc-gap); }
.hc-settings-card { padding: 22px; border: 1px solid var(--hc-line); border-radius: var(--hc-radius); background: var(--hc-surface); }
.hc-settings-heading { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 18px; }
.hc-settings-heading h3 { font-size: 1rem; }
.hc-settings-heading p { margin-top: 4px; color: var(--hc-muted); font-size: 0.8rem; }
.hc-settings-icon { display: grid; place-items: center; width: 38px; height: 38px; flex: 0 0 38px; border-radius: 11px; color: var(--hc-accent-ink); background: var(--hc-accent-soft); }
.hc-settings-icon.is-bell { color: var(--hc-warning); background: var(--hc-warning-soft); }
.hc-settings-icon.is-cloud { color: var(--hc-success); background: var(--hc-success-soft); }
.hc-field-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
.hc-field { display: grid; gap: 6px; margin-bottom: 14px; }
.hc-field > span, .hc-field > label { color: var(--hc-muted); font-size: 0.78rem; font-weight: 650; }
.hc-field input, .hc-field select, .hc-field textarea { width: 100%; min-height: 42px; padding: 8px 11px; border: 1px solid var(--hc-line-strong); border-radius: 10px; color: var(--hc-ink); background: var(--hc-surface); }
.hc-field input[type="file"] { padding: 7px; }
.hc-check-field { display: flex; align-items: center; gap: 9px; color: var(--hc-ink); font-size: 0.85rem; }
.hc-check-field input { width: 18px; height: 18px; accent-color: var(--hc-accent); }
.hc-divider { height: 1px; margin: 22px 0; background: var(--hc-line); }
.hc-form-actions { display: flex; justify-content: flex-end; margin-top: 20px; }
.hc-status-list { display: grid; gap: 0; }
.hc-status-list > div { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 11px 0; border-bottom: 1px solid var(--hc-line); font-size: 0.84rem; }
.hc-status-list > div:last-child { border-bottom: 0; }
.hc-status-list span { color: var(--hc-muted); }
.hc-status-list strong { text-align: right; overflow-wrap: anywhere; }
.hc-code { font-family: var(--code-font-family, monospace); font-size: 0.76rem; }
.hc-notice { display: flex; align-items: flex-start; gap: 10px; margin-top: 18px; padding: 12px; border-radius: 12px; color: var(--hc-muted); background: var(--hc-soft); font-size: 0.78rem; line-height: 1.5; }
.hc-notice ha-icon { --mdc-icon-size: 18px; flex: 0 0 auto; color: var(--hc-accent); }

.hc-device-settings { display: grid; gap: 10px; margin-bottom: 22px; }
.hc-device-settings-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 14px 16px; border: 1px solid var(--hc-line); border-radius: var(--hc-radius); background: var(--hc-surface); }
.hc-device-settings-info { min-width: 0; }
.hc-device-settings-info strong { display: block; font-size: 0.92rem; overflow-wrap: anywhere; }
.hc-device-settings-info span { display: block; margin-top: 3px; color: var(--hc-muted); font-size: 0.78rem; overflow-wrap: anywhere; }
.hc-device-settings-actions { display: flex; flex: 0 0 auto; gap: 8px; }
.hc-device-settings-actions .hc-secondary-button { min-height: 38px; padding: 7px 10px; font-size: 0.82rem; }

.hc-control-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
.hc-control-section { padding: 16px; border: 1px solid var(--hc-line); border-radius: 14px; background: var(--hc-soft); }
.hc-control-section h3 { margin-bottom: 14px; font-size: 0.95rem; }
.hc-control-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.hc-control-buttons.is-stack { grid-template-columns: 1fr; }
.hc-control-buttons .hc-secondary-button { min-height: 42px; justify-content: flex-start; }
.hc-ptz-layout { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: 14px; }
.hc-ptz-pad { display: grid; grid-template-columns: repeat(3, 44px); grid-template-rows: repeat(3, 44px); gap: 6px; }
.hc-ptz-button { display: grid; place-items: center; width: 44px; height: 44px; padding: 0; border: 1px solid var(--hc-line-strong); border-radius: 12px; color: var(--hc-ink); background: var(--hc-surface); touch-action: none; user-select: none; }
.hc-ptz-button:hover:not(:disabled) { background: var(--hc-hover); }
.hc-ptz-button:active:not(:disabled) { transform: scale(0.96); }
.hc-ptz-button.is-stop { color: var(--hc-danger); background: var(--hc-danger-soft); border-color: transparent; }
.hc-ptz-button ha-icon { --mdc-icon-size: 20px; }
.hc-control-note { margin-top: 12px; color: var(--hc-muted); font-size: 0.76rem; }

.hc-setting-groups { display: grid; gap: 18px; }
.hc-setting-group h4 { margin-bottom: 8px; color: var(--hc-muted); font-size: 0.76rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
.hc-setting-list { border: 1px solid var(--hc-line); border-radius: 14px; background: var(--hc-surface); overflow: hidden; }
.hc-setting-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 52px; padding: 10px 14px; border-bottom: 1px solid var(--hc-line); font-size: 0.86rem; }
.hc-setting-row:last-child { border-bottom: 0; }
.hc-setting-row > span { min-width: 0; overflow-wrap: anywhere; }
.hc-setting-row input[type="text"], .hc-setting-row input[type="number"], .hc-setting-row select { width: min(220px, 46%); min-height: 38px; padding: 7px 10px; border: 1px solid var(--hc-line-strong); border-radius: 9px; color: var(--hc-ink); background: var(--hc-surface); }
.hc-setting-row input[type="checkbox"] { width: 20px; height: 20px; flex: 0 0 auto; accent-color: var(--hc-accent); }

.hc-empty-state { display: grid; place-items: center; justify-items: center; gap: 8px; padding: 46px 20px; border: 1px dashed var(--hc-line-strong); border-radius: var(--hc-radius); color: var(--hc-muted); text-align: center; }
.hc-empty-state ha-icon { --mdc-icon-size: 34px; }
.hc-empty-state strong { color: var(--hc-ink); }
.hc-empty-state span { max-width: 46ch; font-size: 0.83rem; }
.hc-empty-state.is-compact { padding: 28px 18px; }
.hc-skeleton-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--hc-gap); }
.hc-skeleton-card { display: grid; gap: 14px; padding: 20px; border: 1px solid var(--hc-line); border-radius: var(--hc-radius); background: var(--hc-surface); }
.hc-skeleton { height: 13px; border-radius: 999px; background: var(--hc-soft); animation: hc-pulse 1.2s ease-in-out infinite; }

dialog { width: min(820px, calc(100vw - 32px)); max-height: calc(100vh - 48px); padding: 0; border: 1px solid var(--hc-line); border-radius: 18px; background: var(--hc-surface); color: var(--hc-ink); overflow: auto; }
dialog::backdrop { background: rgba(8, 24, 38, 0.62); }
.hc-dialog-head { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 16px 18px; border-bottom: 1px solid var(--hc-line); background: var(--hc-surface); }
.hc-dialog-head h2 { font-size: 1.1rem; }
.hc-dialog-head .hc-eyebrow { margin-bottom: 3px; }
.hc-dialog-body { padding: 18px; }
.hc-dialog-image, .hc-dialog-video { display: block; width: 100%; max-height: 62vh; border-radius: 12px; object-fit: contain; background: #0b1b29; }
.hc-camera-dialog-media { overflow: hidden; border-radius: 12px; background: var(--hc-soft); }
.hc-camera-dialog-media .hc-img { display: block; width: 100%; max-height: 62vh; object-fit: contain; }
.hc-detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 16px; }
.hc-detail-grid > div { min-width: 0; padding: 10px 12px; border: 1px solid var(--hc-line); border-radius: 10px; }
.hc-detail-grid span { display: block; color: var(--hc-muted); font-size: 0.72rem; }
.hc-detail-grid strong { display: block; margin-top: 3px; font-size: 0.84rem; overflow-wrap: anywhere; }
.hc-dialog-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
.hc-face-preview { display: block; width: 100%; max-height: 220px; margin-bottom: 14px; border-radius: 12px; object-fit: contain; background: var(--hc-soft); }
.hc-dialog-note { margin-top: 12px; color: var(--hc-muted); font-size: 0.8rem; }

.hc-toast { position: fixed; left: 50%; bottom: 24px; z-index: 80; transform: translateX(-50%); max-width: min(560px, calc(100vw - 32px)); padding: 12px 16px; border: 1px solid var(--hc-line); border-radius: 12px; color: var(--hc-ink); background: var(--hc-surface); box-shadow: 0 8px 30px rgba(0, 0, 0, 0.24); font-size: 0.9rem; }
.hc-toast.is-error { border-color: var(--hc-danger); color: var(--hc-danger); }

@keyframes hc-spin { to { transform: rotate(360deg); } }
@keyframes hc-pulse { 50% { opacity: 0.45; } }
@media (prefers-reduced-motion: reduce) {
  .hc-skeleton, .hc-inline-status.is-loading::before { animation: none; }
  .hc-camera-preview .hc-img { transition: none; }
}

@media (max-width: 980px) {
  .hc-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hc-metric-card:nth-child(2) { border-right: 0; }
  .hc-metric-card:nth-child(-n+2) { border-bottom: 1px solid var(--hc-line); }
  .hc-settings-grid { grid-template-columns: 1fr; }
}

@media (max-width: 760px) {
  .hc-topbar { align-items: flex-start; }
  .hc-connection span:last-child { display: none; }
  .hc-connection { padding: 8px; }
  .hc-primary-nav { top: 76px; }
  .hc-workspace { padding-top: 22px; }
  .hc-page-heading, .hc-page-heading.is-identity { align-items: stretch; flex-direction: column; }
  .hc-page-heading .hc-toolbar { justify-content: flex-start; }
  .hc-filter-bar, .hc-filter-bar.is-recordings { grid-template-columns: 1fr; }
  .hc-filter-bar .hc-search-box { grid-column: auto; }
  .hc-event-list { grid-template-columns: 1fr; }
  .hc-person-grid { grid-template-columns: 1fr; }
  .hc-person-card { grid-template-columns: 104px minmax(0, 1fr); }
  .hc-device-settings-row { align-items: stretch; flex-direction: column; }
  .hc-device-settings-actions { flex-wrap: wrap; }
  .hc-ptz-layout { grid-template-columns: 1fr; justify-items: center; }
  .hc-control-buttons.is-stack { width: 100%; }
}

@media (max-width: 520px) {
  .hc-brand-title > span, .hc-brand-copy p { display: none; }
  .hc-metric-grid { grid-template-columns: 1fr; }
  .hc-metric-card { min-height: 90px; border-right: 0; border-bottom: 1px solid var(--hc-line); }
  .hc-metric-card:last-child { border-bottom: 0; }
  .hc-event-card { grid-template-columns: 104px minmax(0, 1fr); }
  .hc-event-image { width: 104px; min-height: 128px; }
  .hc-camera-actions { grid-template-columns: 1fr; }
  .hc-setting-row { align-items: flex-start; flex-direction: column; gap: 8px; }
  .hc-setting-row input[type="text"], .hc-setting-row input[type="number"], .hc-setting-row select { width: 100%; }
  .hc-toolbar .hc-control-icon { width: 100%; }
  .hc-dialog-actions .hc-primary-button, .hc-dialog-actions .hc-secondary-button { flex: 1 1 100%; }
}

/* Studio Console layout */
.hc-app {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  min-height: 100vh;
  background: var(--hc-page);
}
.hc-sidebar {
  position: sticky;
  top: 0;
  z-index: 35;
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100vh;
  padding: 18px 14px;
  overflow: auto;
  border-right: 1px solid var(--hc-line);
  background: var(--hc-surface);
}
.hc-sidebar .hc-brand { padding: 2px 4px 16px; border-bottom: 1px solid var(--hc-line); }
.hc-sidebar .hc-brand-mark { width: 40px; height: 40px; flex-basis: 40px; border-radius: 12px; font-size: 1.15rem; }
.hc-sidebar .hc-brand-title h1 { font-size: 0.92rem; }
.hc-sidebar .hc-brand-title > span { font-size: 0.62rem; }
.hc-sidebar .hc-brand-copy p { margin-top: 2px; font-size: 0.65rem; }
.hc-sidebar-label { padding: 0 8px; color: var(--hc-muted); font-size: 0.58rem; font-weight: 750; letter-spacing: 0.09em; text-transform: uppercase; }
.hc-sidebar-foot {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-top: auto;
  padding: 11px;
  border: 1px solid var(--hc-line);
  border-radius: 12px;
  color: var(--hc-muted);
  background: var(--hc-soft);
  font-size: 0.65rem;
  line-height: 1.5;
}
.hc-sidebar-foot ha-icon { --mdc-icon-size: 18px; flex: 0 0 auto; color: var(--hc-accent); }
.hc-main { display: flex; flex-direction: column; min-width: 0; }
.hc-main .hc-topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  min-height: 64px;
  padding: 10px clamp(16px, 2.4vw, 28px);
  border-bottom: 1px solid var(--hc-line);
  background: var(--hc-surface);
  -webkit-backdrop-filter: none;
  backdrop-filter: none;
}
.hc-topbar-copy { display: grid; gap: 2px; min-width: 0; }
.hc-crumb { color: var(--hc-muted); font-size: 0.72rem; font-weight: 650; letter-spacing: 0.01em; }
.hc-crumb b { color: var(--hc-ink); }
.hc-topbar-copy p { max-width: min(62vw, 720px); margin: 0; color: var(--hc-muted); font-size: 0.68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hc-main .hc-workspace { width: 100%; max-width: 1520px; padding: 24px clamp(16px, 2.5vw, 34px) 54px; }
.hc-sidebar .hc-primary-nav {
  position: static;
  z-index: auto;
  display: grid;
  gap: 3px;
  padding: 0;
  overflow: visible;
  border: 0;
  background: transparent;
  -webkit-backdrop-filter: none;
  backdrop-filter: none;
}
.hc-sidebar .hc-nav-item {
  justify-content: flex-start;
  width: 100%;
  min-height: 42px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  font-size: 0.76rem;
  text-align: left;
}
.hc-sidebar .hc-nav-item ha-icon { --mdc-icon-size: 19px; }
.hc-sidebar .hc-nav-item[aria-selected="true"] {
  color: var(--hc-accent-ink);
  border-color: color-mix(in srgb, var(--hc-accent) 24%, transparent);
  background: var(--hc-accent-soft);
}
.hc-sidebar .hc-nav-item:hover { color: var(--hc-ink); background: var(--hc-soft); }

.hc-page.is-entering { animation: hc-page-in 200ms ease both; }
.hc-page-heading { margin-bottom: 20px; }
.hc-page-heading h2 { font-size: clamp(1.3rem, 2vw, 1.55rem); letter-spacing: -0.015em; }
.hc-page-heading p { margin-top: 4px; font-size: 0.8rem; }
.hc-eyebrow { margin-bottom: 4px; font-size: 0.65rem; letter-spacing: 0.06em; text-transform: uppercase; }
.hc-section-heading { margin-bottom: 12px; }
.hc-section-heading h3 { font-size: 1rem; }
.hc-section-heading p { font-size: 0.72rem; }
.hc-metric-grid { margin-bottom: 18px; }
.hc-metric-card { min-height: 86px; padding: 14px 16px; }
.hc-metric-card strong { font-size: 1.35rem; }
.hc-metric-card > div span { font-size: 0.72rem; }
.hc-metric-icon { width: 34px; height: 34px; flex-basis: 34px; border-radius: 10px; }
.hc-metric-icon ha-icon { --mdc-icon-size: 18px; }

.hc-command-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.85fr);
  gap: 14px;
  margin-bottom: 24px;
}
.hc-command-preview {
  position: relative;
  display: block;
  min-height: 318px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--hc-line);
  border-radius: 16px;
  color: #fff;
  background: linear-gradient(135deg, #0d2632, #174451);
  text-align: left;
}
.hc-command-preview .hc-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 240ms ease;
}
.hc-command-preview:hover .hc-img { transform: scale(1.018); }
.hc-command-preview:after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(5, 19, 27, 0.1) 32%, rgba(5, 19, 27, 0.86));
}
.hc-command-preview .hc-media-placeholder {
  position: absolute;
  inset: 0;
  color: rgba(255, 255, 255, 0.72);
  background: rgba(9, 30, 40, 0.62);
}
.hc-command-preview-top {
  position: absolute;
  z-index: 2;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.hc-command-preview-top .hc-preview-note { position: static; }
.hc-command-preview-copy {
  position: absolute;
  z-index: 2;
  left: 18px;
  right: 110px;
  bottom: 16px;
  display: grid;
  gap: 3px;
  min-width: 0;
}
.hc-command-preview-copy .hc-eyebrow { color: rgba(255, 255, 255, 0.68); }
.hc-command-preview-copy strong { font-size: 1.32rem; line-height: 1.2; overflow-wrap: anywhere; }
.hc-command-preview-copy > span:last-child { color: rgba(255, 255, 255, 0.72); font-size: 0.7rem; overflow-wrap: anywhere; }
.hc-command-expand {
  position: absolute;
  z-index: 2;
  right: 14px;
  bottom: 15px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 9px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 9px;
  color: #fff;
  background: rgba(255, 255, 255, 0.12);
  font-size: 0.66rem;
  font-weight: 650;
}
.hc-command-expand ha-icon { --mdc-icon-size: 15px; }
.hc-command-deck {
  display: grid;
  align-content: start;
  gap: 11px;
  padding: 14px;
  border: 1px solid var(--hc-line);
  border-radius: 16px;
  background: var(--hc-surface);
}
.hc-command-deck-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.hc-command-deck-head > div { display: grid; gap: 2px; min-width: 0; }
.hc-command-deck-head strong { font-size: 0.92rem; }
.hc-command-deck-head > div > span:last-child { color: var(--hc-muted); font-size: 0.66rem; }
.hc-deck-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.hc-deck-action {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  min-height: 45px;
  padding: 7px 8px;
  border: 1px solid var(--hc-line);
  border-radius: 9px;
  color: var(--hc-ink);
  background: var(--hc-surface);
  text-align: left;
  transition: background-color 160ms ease, border-color 160ms ease;
}
.hc-deck-action:hover:not(:disabled) { border-color: var(--hc-line-strong); background: var(--hc-hover); }
.hc-deck-action b { display: block; font-size: 0.7rem; line-height: 1.2; }
.hc-deck-action small { display: block; margin-top: 1px; color: var(--hc-muted); font-size: 0.58rem; }
.hc-deck-icon { display: grid; place-items: center; width: 28px; height: 28px; flex: 0 0 28px; border-radius: 8px; color: var(--hc-accent-ink); background: var(--hc-accent-soft); }
.hc-deck-icon.is-warn { color: var(--hc-warning); background: var(--hc-warning-soft); }
.hc-deck-icon ha-icon { --mdc-icon-size: 17px; }
.hc-deck-controls { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: 10px; }
.hc-deck-pad { display: grid; grid-template-columns: repeat(3, 34px); grid-template-rows: repeat(3, 34px); gap: 4px; }
.hc-deck-pad-button { display: grid; place-items: center; width: 34px; height: 34px; padding: 0; border: 1px solid var(--hc-line-strong); border-radius: 8px; color: var(--hc-ink); background: var(--hc-surface); touch-action: none; user-select: none; }
.hc-deck-pad-button:hover:not(:disabled) { background: var(--hc-hover); }
.hc-deck-pad-button:active:not(:disabled) { transform: scale(0.95); }
.hc-deck-pad-button.is-stop { color: var(--hc-danger); border-color: transparent; background: var(--hc-danger-soft); }
.hc-deck-pad-button ha-icon { --mdc-icon-size: 17px; }
.hc-deck-zoom { display: grid; gap: 5px; }
.hc-deck-zoom .hc-secondary-button { justify-content: flex-start; min-height: 32px; padding: 5px 8px; font-size: 0.65rem; }
.hc-deck-zoom .hc-secondary-button ha-icon { --mdc-icon-size: 15px; }

.hc-settings-summary, .hc-count-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border-radius: 999px;
  color: var(--hc-muted);
  background: var(--hc-soft);
  font-size: 0.68rem;
  font-weight: 650;
  white-space: nowrap;
}
.hc-settings-summary ha-icon { --mdc-icon-size: 15px; }
.hc-settings-layout { display: grid; grid-template-columns: 208px minmax(0, 1fr); align-items: start; gap: 16px; }
.hc-settings-nav { position: sticky; top: 82px; display: grid; gap: 3px; padding: 6px; border: 1px solid var(--hc-line); border-radius: 14px; background: var(--hc-surface); }
.hc-settings-nav button { display: flex; align-items: center; gap: 9px; min-height: 44px; padding: 7px 8px; border: 1px solid transparent; border-radius: 9px; color: var(--hc-muted); background: transparent; text-align: left; }
.hc-settings-nav button:hover { color: var(--hc-ink); background: var(--hc-soft); }
.hc-settings-nav button[aria-current="page"] { color: var(--hc-accent-ink); border-color: color-mix(in srgb, var(--hc-accent) 22%, transparent); background: var(--hc-accent-soft); }
.hc-settings-nav-icon { display: grid; place-items: center; width: 30px; height: 30px; flex: 0 0 30px; border-radius: 8px; background: var(--hc-soft); }
.hc-settings-nav button[aria-current="page"] .hc-settings-nav-icon { background: var(--hc-surface); }
.hc-settings-nav-icon ha-icon { --mdc-icon-size: 17px; }
.hc-settings-nav b { display: block; font-size: 0.72rem; }
.hc-settings-nav small { display: block; margin-top: 1px; color: var(--hc-muted); font-size: 0.58rem; }
.hc-settings-panels { display: grid; gap: 14px; min-width: 0; }
.hc-settings-panel { display: grid; gap: 12px; min-width: 0; animation: hc-page-in 180ms ease both; }
.hc-settings-panel[hidden] { display: none !important; }
.hc-settings-panel-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 10px; }
.hc-settings-panel-head h3 { font-size: 1rem; }
.hc-settings-panel-head p { margin-top: 3px; color: var(--hc-muted); font-size: 0.7rem; }
.hc-settings-form { display: grid; gap: 14px; }
.hc-settings-card { padding: 16px; }
.hc-settings-heading { margin-bottom: 13px; }
.hc-settings-heading h3 { font-size: 0.86rem; }
.hc-settings-heading p { font-size: 0.7rem; }
.hc-settings-icon { width: 32px; height: 32px; flex-basis: 32px; border-radius: 9px; }
.hc-settings-icon ha-icon { --mdc-icon-size: 18px; }
.hc-settings-save {
  position: sticky;
  bottom: 12px;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--hc-line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--hc-surface) 96%, transparent);
  box-shadow: 0 8px 24px rgba(21, 50, 77, 0.08);
}
.hc-settings-save > span { color: var(--hc-muted); font-size: 0.68rem; }
.hc-settings-save .hc-primary-button { min-height: 36px; padding: 6px 11px; font-size: 0.7rem; }
.hc-device-settings { display: grid; gap: 8px; }
.hc-device-settings-row {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 11px 13px;
  border: 1px solid var(--hc-line);
  border-radius: 13px;
  background: var(--hc-surface);
  transition: border-color 160ms ease, background-color 160ms ease;
}
.hc-device-settings-row:hover { border-color: var(--hc-line-strong); background: var(--hc-surface2, var(--hc-surface)); }
.hc-device-settings-row.is-offline { opacity: 0.72; }
.hc-device-icon { position: relative; display: grid; place-items: center; width: 38px; height: 38px; border-radius: 11px; color: var(--hc-accent-ink); background: var(--hc-accent-soft); }
.hc-device-icon ha-icon { --mdc-icon-size: 19px; }
.hc-device-icon i { position: absolute; right: -2px; bottom: -2px; width: 10px; height: 10px; border: 2px solid var(--hc-surface); border-radius: 50%; background: var(--hc-muted); }
.hc-device-settings-row.is-online .hc-device-icon i { background: var(--hc-success); }
.hc-device-settings-actions { display: flex; gap: 6px; }
.hc-device-settings-actions .hc-secondary-button, .hc-device-settings-actions .hc-primary-button { min-height: 34px; padding: 5px 9px; border-radius: 8px; font-size: 0.68rem; }
.hc-device-settings-actions ha-icon { --mdc-icon-size: 15px; }

.hc-switch { position: relative; display: inline-flex; align-items: center; width: 46px; height: 44px; flex: 0 0 auto; }
.hc-switch input { position: absolute; inset: 0; z-index: 2; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; }
.hc-switch-track { position: relative; display: block; width: 42px; height: 25px; border-radius: 999px; background: var(--hc-line-strong); transition: background-color 180ms ease; }
.hc-switch-track:after { content: ""; position: absolute; left: 3px; top: 3px; width: 19px; height: 19px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.22); transition: transform 180ms ease; }
.hc-switch input:checked + .hc-switch-track { background: var(--hc-accent); }
.hc-switch input:checked + .hc-switch-track:after { transform: translateX(17px); }
.hc-switch input:focus-visible + .hc-switch-track { outline: 2px solid var(--hc-accent-ink); outline-offset: 3px; }
.hc-select-wrap { position: relative; display: inline-flex; align-items: center; width: min(240px, 52%); }
.hc-select-wrap select { width: 100%; padding-right: 30px; appearance: none; -webkit-appearance: none; }
.hc-select-wrap ha-icon { position: absolute; right: 9px; color: var(--hc-muted); --mdc-icon-size: 17px; pointer-events: none; }
.hc-setting-row { min-height: 54px; padding: 8px 13px; border-left: 2px solid transparent; transition: background-color 160ms ease, border-color 160ms ease; }
.hc-setting-row.is-saving { border-left-color: var(--hc-accent); background: var(--hc-accent-soft); }
.hc-setting-row.is-saved { border-left-color: var(--hc-success); background: var(--hc-success-soft); }
.hc-setting-row.is-error { border-left-color: var(--hc-danger); background: var(--hc-danger-soft); }
.hc-setting-row.is-saving .hc-switch-track, .hc-setting-row.is-saving select, .hc-setting-row.is-saving input { opacity: 0.7; }
.hc-setting-row .hc-setting-input { width: min(240px, 52%); }
.hc-setting-row .hc-switch { margin-right: 2px; }

.hc-control-dialog-body { padding: 16px; }
.hc-dialog-head-actions { display: flex; align-items: center; gap: 8px; }
.hc-control-layout { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr); align-items: start; gap: 14px; }
.hc-control-media { position: relative; min-height: 430px; overflow: hidden; border-radius: 14px; color: #fff; background: linear-gradient(135deg, #0d2632, #1a4855); }
.hc-control-media .hc-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.hc-control-media .hc-media-placeholder { position: absolute; inset: 0; color: rgba(255, 255, 255, 0.7); background: rgba(9, 30, 40, 0.58); }
.hc-control-media:after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(5, 19, 27, 0.1) 40%, rgba(5, 19, 27, 0.8)); }
.hc-control-media-top { position: absolute; z-index: 2; top: 11px; left: 11px; right: 11px; display: flex; justify-content: space-between; gap: 8px; }
.hc-live-tag { display: inline-flex; align-items: center; gap: 5px; padding: 4px 7px; border-radius: 999px; color: #fff; background: rgba(8, 24, 32, 0.62); font-size: 0.58rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
.hc-live-tag > span { width: 6px; height: 6px; border-radius: 50%; background: #4ade80; }
.hc-control-media-copy { position: absolute; z-index: 2; left: 14px; right: 14px; bottom: 13px; display: grid; gap: 2px; }
.hc-control-media-copy strong { font-size: 1rem; }
.hc-control-media-copy span { color: rgba(255, 255, 255, 0.72); font-size: 0.66rem; }
.hc-control-panel { display: grid; gap: 10px; align-content: start; }
.hc-control-section { padding: 12px; background: var(--hc-surface); }
.hc-control-section-head { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 10px; }
.hc-control-section-icon { display: grid; place-items: center; width: 28px; height: 28px; flex: 0 0 28px; border-radius: 8px; color: var(--hc-accent-ink); background: var(--hc-accent-soft); }
.hc-control-section-icon ha-icon { --mdc-icon-size: 16px; }
.hc-control-section-head h3 { font-size: 0.78rem; }
.hc-control-section-head p { margin-top: 2px; color: var(--hc-muted); font-size: 0.62rem; }
.hc-command-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.hc-command-tile { display: flex; align-items: center; gap: 7px; min-width: 0; min-height: 44px; padding: 7px 8px; border: 1px solid var(--hc-line); border-radius: 9px; color: var(--hc-ink); background: var(--hc-surface); text-align: left; }
.hc-command-tile:hover:not(:disabled) { border-color: var(--hc-line-strong); background: var(--hc-hover); }
.hc-command-tile.is-warn { color: var(--hc-warning); }
.hc-command-tile ha-icon { --mdc-icon-size: 18px; flex: 0 0 auto; }
.hc-command-tile b { display: block; font-size: 0.68rem; line-height: 1.2; }
.hc-command-tile small { display: block; margin-top: 1px; color: var(--hc-muted); font-size: 0.56rem; }
.hc-control-pad-layout { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: 10px; }
.hc-control-pad { display: grid; grid-template-columns: repeat(3, 40px); grid-template-rows: repeat(3, 40px); gap: 4px; }
.hc-control-pad-button { display: grid; place-items: center; width: 40px; height: 40px; padding: 0; border: 1px solid var(--hc-line-strong); border-radius: 9px; color: var(--hc-ink); background: var(--hc-surface); touch-action: none; user-select: none; }
.hc-control-pad-button:hover:not(:disabled) { background: var(--hc-hover); }
.hc-control-pad-button:active:not(:disabled) { transform: scale(0.95); }
.hc-control-pad-button.is-stop { color: var(--hc-danger); border-color: transparent; background: var(--hc-danger-soft); }
.hc-control-pad-button ha-icon { --mdc-icon-size: 18px; }
.hc-control-zoom { display: grid; gap: 5px; }
.hc-control-zoom .hc-secondary-button { justify-content: flex-start; min-height: 32px; padding: 5px 8px; font-size: 0.64rem; }
.hc-control-zoom ha-icon { --mdc-icon-size: 15px; }
.hc-control-note { display: flex; align-items: flex-start; gap: 7px; padding: 9px 10px; border-radius: 9px; color: var(--hc-muted); background: var(--hc-soft); font-size: 0.62rem; line-height: 1.45; }
.hc-control-note ha-icon { --mdc-icon-size: 16px; flex: 0 0 auto; color: var(--hc-accent); }

.hc-primary-button:active:not(:disabled), .hc-secondary-button:active:not(:disabled), .hc-icon-button:active:not(:disabled) { transform: scale(0.98); }
.hc-camera-card:hover, .hc-recording-card:hover, .hc-person-card:hover { box-shadow: 0 8px 24px rgba(21, 50, 77, 0.07); }
dialog[open] { animation: hc-dialog-in 200ms ease both; }
dialog::backdrop { animation: hc-fade-in 180ms ease both; }

@media (max-width: 1120px) {
  .hc-command-hero { grid-template-columns: 1fr; }
  .hc-command-preview { min-height: 280px; }
  .hc-command-deck { grid-template-columns: 1fr 1fr; align-items: start; }
  .hc-command-deck-head, .hc-deck-controls { grid-column: 1 / -1; }
}

@media (max-width: 980px) {
  .hc-app { grid-template-columns: 218px minmax(0, 1fr); }
  .hc-settings-layout { grid-template-columns: 1fr; }
  .hc-settings-nav { position: static; display: flex; overflow-x: auto; padding: 5px; }
  .hc-settings-nav button { flex: 0 0 auto; min-height: 36px; white-space: nowrap; }
  .hc-settings-nav small { display: none; }
  .hc-control-layout { grid-template-columns: 1fr; }
  .hc-control-media { min-height: 240px; }
}

@media (max-width: 760px) {
  .hc-app { display: block; padding-bottom: calc(82px + env(safe-area-inset-bottom)); }
  .hc-sidebar {
    position: fixed;
    inset: auto 0 0;
    z-index: 45;
    display: block;
    width: auto;
    height: auto;
    padding: 5px 6px calc(5px + env(safe-area-inset-bottom));
    overflow: visible;
    border-top: 1px solid var(--hc-line);
    border-right: 0;
    background: var(--hc-surface);
  }
  .hc-sidebar .hc-brand, .hc-sidebar-label, .hc-sidebar-foot { display: none; }
  .hc-sidebar .hc-primary-nav { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 2px; overflow: visible; }
  .hc-sidebar .hc-nav-item { flex-direction: column; justify-content: center; gap: 2px; min-height: 50px; padding: 4px 2px; border: 0; border-radius: 8px; font-size: 0.65rem; text-align: center; }
  .hc-sidebar .hc-nav-item ha-icon { --mdc-icon-size: 20px; }
  .hc-main .hc-topbar { min-height: 56px; padding: 8px 12px; }
  .hc-topbar-copy p { max-width: 58vw; font-size: 0.62rem; }
  .hc-crumb { font-size: 0.64rem; }
  .hc-main .hc-workspace { padding: 14px 12px 26px; }
  .hc-page-heading { margin-bottom: 14px; }
  .hc-page-heading h2 { font-size: 1.2rem; }
  .hc-command-preview { min-height: 220px; }
  .hc-command-preview-copy { right: 14px; bottom: 48px; }
  .hc-command-preview-copy strong { font-size: 1.08rem; }
  .hc-command-expand { right: 12px; bottom: 12px; }
  .hc-command-deck { grid-template-columns: 1fr; padding: 12px; }
  .hc-command-deck-head, .hc-deck-controls { grid-column: auto; }
  .hc-settings-panel-head { align-items: flex-start; flex-direction: column; }
  .hc-settings-save { position: static; align-items: stretch; flex-direction: column; }
  .hc-settings-save .hc-primary-button { width: 100%; }
  .hc-device-settings-row { grid-template-columns: 36px minmax(0, 1fr) auto; gap: 9px; }
  .hc-device-settings-actions { grid-column: 1 / -1; display: grid; grid-template-columns: 1fr 1fr; }
  .hc-device-settings-actions .hc-secondary-button, .hc-device-settings-actions .hc-primary-button { width: 100%; }
  .hc-select-wrap { width: 100%; }
  .hc-control-dialog-body { padding: 12px; }
  .hc-control-media { min-height: 210px; }
  .hc-control-panel { gap: 8px; }
  .hc-toast { bottom: calc(78px + env(safe-area-inset-bottom)); }
}

@media (max-width: 520px) {
  .hc-deck-pad { grid-template-columns: repeat(3, 33px); grid-template-rows: repeat(3, 33px); }
  .hc-deck-pad-button { width: 33px; height: 33px; }
  .hc-command-grid { grid-template-columns: 1fr 1fr; }
  .hc-control-pad-layout { grid-template-columns: auto minmax(0, 1fr); }
  .hc-control-pad { grid-template-columns: repeat(3, 37px); grid-template-rows: repeat(3, 37px); }
  .hc-control-pad-button { width: 37px; height: 37px; }
  .hc-setting-row { align-items: stretch; }
  .hc-setting-row .hc-setting-input { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .hc-page, .hc-page.is-entering, .hc-settings-panel, dialog[open], dialog::backdrop { animation: none; }
  .hc-command-preview .hc-img, .hc-switch-track, .hc-switch-track:after, .hc-setting-row, .hc-deck-action, .hc-device-settings-row { transition: none; }
  .hc-deck-pad-button:active, .hc-control-pad-button:active, .hc-primary-button:active, .hc-secondary-button:active, .hc-icon-button:active { transform: none; }
}

@keyframes hc-page-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes hc-dialog-in {
  from { opacity: 0; transform: translateY(8px) scale(0.985); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes hc-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
`;
