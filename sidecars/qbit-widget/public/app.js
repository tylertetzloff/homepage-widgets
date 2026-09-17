// Same-origin only. Nginx proxies /api/v2 to qBittorrent on the Docker network.
const API = "/api/v2";
const QBIT_USER = "";
const QBIT_PASS = "";
const TABS = [
  { id: "active", short: "Active", states: ["downloading", "metaDL", "checking", "forcedDL", "checkingDL", "allocating", "moving", "stalledDL"] },
  { id: "inactive", short: "Inactive", states: ["pausedDL", "stoppedDL", "queuedDL"] },
  { id: "failed", short: "Errored", states: ["error", "missingFiles"] },
  { id: "seeding", short: "Seeding", states: ["uploading", "pausedUP", "stoppedUP", "stalledUP", "queuedUP", "forcedUP", "checkingUP"] },
];
const state = { torrents: [], tab: "active", toast: "", pending: null, confirm: "", connected: false, err: "" };
const embed = new URLSearchParams(location.search).get("embed") === "1" || window.self !== window.top;
if (embed) {
  document.documentElement.classList.add("embed");
  document.body.classList.add("embed");
  document.getElementById("page").classList.add("embed");
  const title = document.getElementById("pageTitle");
  if (title) title.hidden = true;
}
const I = {
  play: '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 14 8 5 13"/></svg>',
  pause: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>',
  stop: '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="10" height="10"/></svg>',
  announce: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/></svg>',
  recheck: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
  remove: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
};
function bytes(n) {
  const u = ["B", "KB", "MB", "GB", "TB"];
  let v = n, i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
}
function rate(n) { return n <= 0 ? "0" : `${bytes(n)}/s`; }
function eta(s) {
  if (!isFinite(s) || s < 0 || s >= 8640000) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${Math.floor(s / 3600)}h`;
}
function normState(s) {
  if (s === "stoppedDL") return "pausedDL";
  if (s === "stoppedUP") return "pausedUP";
  if (s === "forcedDL") return "downloading";
  if (s === "forcedUP") return "uploading";
  if (String(s).startsWith("checking")) return "checking";
  return s;
}
function tabOf(st) { return TABS.find((t) => t.states.includes(st))?.id || "inactive"; }
function label(t) {
  if (t.state === "metaDL") return "metadata";
  if (t.state === "missingFiles") return "missing";
  if (t.state.includes("paused")) return "paused";
  if (t.state.includes("stalled")) return "stalled";
  if (t.state.includes("queued")) return "queued";
  return t.state;
}
function tone(t) {
  if (t.state === "error" || t.state === "missingFiles") return "tone-bad";
  if (t.state.includes("stalled")) return "tone-warn";
  if (["downloading", "uploading", "checking"].includes(t.state)) return "tone-ok";
  return "";
}
function closeModal() {
  state.pending = null;
  state.confirm = "";
  const m = document.getElementById("modal");
  if (m) {
    m.classList.remove("open");
    if (typeof m.close === "function") { try { m.close(); } catch (e) {}
    }
    m.removeAttribute("open");
  }
  render();
}
function toast(msg) {
  state.toast = msg;
  render();
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { state.toast = ""; render(); }, 2200);
}
async function qpost(path, params) {
  return fetch(API + path, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(params),
  });
}
async function login() {
  if (!QBIT_USER) return false;
  const r = await qpost("/auth/login", { username: QBIT_USER, password: QBIT_PASS });
  const t = await r.text();
  return r.ok && t.trim() === "Ok.";
}
async function act(hash, kind) {
  const t = state.torrents.find((x) => x.hash === hash);
  if (t && kind === "pause") {
    t.state = t.progress >= 1 ? "pausedUP" : "pausedDL";
    t.dlspeed = 0; t.upspeed = 0;
  }
  if (t && kind === "resume") {
    t.state = t.progress >= 1 ? "uploading" : "downloading";
  }
  render();
  try {
    let r;
    if (kind === "resume") {
      r = await qpost("/torrents/start", { hashes: hash });
      if (!r.ok) r = await qpost("/torrents/resume", { hashes: hash });
      await qpost("/torrents/setForceStart", { hashes: hash, value: "true" });
    } else if (kind === "pause") {
      r = await qpost("/torrents/stop", { hashes: hash });
      if (!r.ok) r = await qpost("/torrents/pause", { hashes: hash });
    } else if (kind === "announce") {
      r = await qpost("/torrents/reannounce", { hashes: hash });
    } else if (kind === "recheck") {
      r = await qpost("/torrents/recheck", { hashes: hash });
    }
    if (r && !r.ok) toast("Action failed");
  } catch (e) {
    toast("qBit unreachable");
  }
  state.pending = null;
  await refresh();
}
async function remove(hash, files) {
  try {
    const r = await qpost("/torrents/delete", { hashes: hash, deleteFiles: files ? "true" : "false" });
    state.pending = null; state.confirm = "";
    toast(r.ok ? (files ? "Removed torrent and files" : "Removed from list") : "Remove failed");
    await refresh();
  } catch (e) { toast("qBit unreachable"); }
}
async function refresh() {
  try {
    let r = await fetch(API + "/sync/maindata", { credentials: "include" });
    if (r.status === 403 || r.status === 401) {
      await login();
      r = await fetch(API + "/sync/maindata", { credentials: "include" });
    }
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const raw = data.torrents || {};
    state.torrents = Object.entries(raw).map(([hash, t]) => ({
      hash,
      name: t.name,
      size: t.size,
      progress: t.progress,
      dlspeed: t.dlspeed,
      upspeed: t.upspeed,
      eta: t.eta,
      state: normState(t.state),
      ratio: t.ratio,
      error: t.state === "error" || t.state === "missingFiles" ? (t.msg || t.state) : undefined,
    }));
    state.dl = data.server_state?.dl_info_speed ?? state.torrents.reduce((a, t) => a + t.dlspeed, 0);
    state.up = data.server_state?.up_info_speed ?? state.torrents.reduce((a, t) => a + t.upspeed, 0);
    state.connected = true;
    state.err = "";
  } catch (e) {
    state.connected = false;
    state.err = String(e.message || e);
  }
  render();
}
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&" + "amp;")
    .replace(/</g, "&" + "lt;")
    .replace(/>/g, "&" + "gt;")
    .replace(/"/g, "&" + "quot;")
    .replace(/'/g, "&#39;");
}
function render() {
  const counts = { active: 0, inactive: 0, failed: 0, seeding: 0 };
  for (const t of state.torrents) counts[tabOf(t.state)]++;
  const speeds = document.getElementById("speeds");
  speeds.textContent = state.connected
    ? `↓ ${rate(state.dl || 0)}   ↑ ${rate(state.up || 0)}`
    : (state.err ? `qBit unreachable (${state.err})` : "connecting…");
  document.getElementById("stats").innerHTML = TABS.map((tab) => {
    const n = counts[tab.id];
    const tn = tab.id === "failed" && n ? "tone-bad" : tab.id === "active" && n ? "tone-ok" : "";
    return `<button type="button" class="well${state.tab === tab.id ? " active" : ""}" data-tab="${tab.id}"><span class="n ${tn}">${n}</span><span class="l">${tab.short}</span></button>`;
  }).join("");
  const xfer = document.getElementById("xfer");
  if (xfer) xfer.innerHTML = `<span class="down">↓ ${rate(state.dl || 0)}</span><span class="up">↑ ${rate(state.up || 0)}</span>`;
  const rows = state.torrents.filter((t) => TABS.find((x) => x.id === state.tab).states.includes(t.state));
  const list = document.getElementById("list");
  if (!state.connected && !state.torrents.length) {
    list.innerHTML = `<div class="empty">Waiting for qBittorrent API…</div>`;
  } else if (!rows.length) {
    list.innerHTML = `<div class="empty">Nothing in ${state.tab}.</div>`;
  } else {
    list.innerHTML = rows.map((t) => {
      const start = /paused|stopped/i.test(t.state);
      const stopLbl = state.tab === "seeding" ? "Stop seed" : "Stop";
      return `<div class="row">
            <div class="meta">
              <div class="row-title"><p>${escapeHtml(t.name)}</p><span class="st ${tone(t)}">${label(t)}</span></div>
              ${t.error ? `<p class="err">${escapeHtml(t.error)}</p>` : ""}
              <div class="bar${t.state === "error" || t.state === "missingFiles" ? " bad" : ""}"><span style="width:${Math.round(t.progress * 1000) / 10}%"></span></div>
              <div class="nums">
                <span>${Math.round(t.progress * 100)}%</span>
                <span>${bytes(t.size * t.progress)} / ${bytes(t.size)}</span>
                <span>↓ ${rate(t.dlspeed)}</span>
                <span>↑ ${rate(t.upspeed)}</span>
                <span>${t.progress < 1 ? "eta " + eta(t.eta) : "ratio " + Number(t.ratio || 0).toFixed(2)}</span>
              </div>
            </div>
            <div class="acts">
              <button class="icon" data-act="${start ? "resume" : "pause"}" data-hash="${t.hash}" title="${start ? "Start" : stopLbl}" aria-label="${start ? "Start" : stopLbl}">${start ? I.play : (state.tab === "seeding" ? I.stop : I.pause)}</button>
              <button class="icon" data-act="announce" data-hash="${t.hash}" title="Announce" aria-label="Announce">${I.announce}</button>
              <button class="icon" data-act="recheck" data-hash="${t.hash}" title="Recheck" aria-label="Recheck">${I.recheck}</button>
              <button class="icon" data-act="remove" data-hash="${t.hash}" title="Remove" aria-label="Remove">${I.remove}</button>
            </div>
          </div>`;
    }).join("");
  }
  const toastEl = document.getElementById("toast");
  toastEl.hidden = !state.toast;
  toastEl.textContent = state.toast;
  const modal = document.getElementById("modal");
  if (!state.pending) { modal.hidden = true; modal.className = ""; modal.innerHTML = ""; }
  else {
    const t = state.torrents.find((x) => x.hash === state.pending.hash);
    modal.hidden = false;
    modal.className = "modal-bg";
    if (document.activeElement && document.activeElement.id === "confirm") {
      const ok = modal.querySelector("[data-ok]");
      if (ok) {
        const ready = !state.pending.files || state.confirm.trim() === "DELETE";
        ok.disabled = !ready;
        ok.className = "btn " + (state.pending.files ? (ready ? "danger fill" : "danger") : "primary");
      }
    } else {
      modal.innerHTML = t ? `<div class="modal" role="dialog" aria-modal="true">
          <h2>Remove torrent</h2>
          <p>${escapeHtml(t.name)}</p>
          <div class="stack">
            <button class="btn${state.pending.files ? "" : " primary"}" data-files="0">Remove from list only</button>
            <button class="btn${state.pending.files ? " danger fill" : ""}" data-files="1">Delete files from disk</button>
          </div>
          ${state.pending.files ? `<label>Type DELETE to confirm<input id="confirm" value="${escapeHtml(state.confirm)}" autocomplete="off"></label>` : ""}
          <div class="foot">
            <button type="button" class="btn" data-cancel>Cancel</button>
            <button class="btn ${state.pending.files ? (state.confirm.trim() === "DELETE" ? "danger fill" : "danger") : "primary"}" data-ok ${state.pending.files && state.confirm.trim() !== "DELETE" ? "disabled" : ""}>Confirm</button>
          </div>
        </div>` : "";
    }
  }
}
document.getElementById("stats").addEventListener("click", (e) => {
  const b = e.target.closest("[data-tab]");
  if (b) { state.tab = b.dataset.tab; render(); }
});
document.getElementById("list").addEventListener("click", (e) => {
  const b = e.target.closest("[data-act]");
  if (!b) return;
  if (b.dataset.act === "remove") { state.pending = { hash: b.dataset.hash, files: false }; state.confirm = ""; render(); }
  else act(b.dataset.hash, b.dataset.act);
});
document.getElementById("modal").addEventListener("input", (e) => {
  if (e.target.id !== "confirm" || !state.pending) return;
  state.confirm = e.target.value;
  const ok = document.querySelector("[data-ok]");
  if (!ok) return;
  const ready = !state.pending.files || state.confirm.trim() === "DELETE";
  ok.disabled = !ready;
  ok.className = "btn " + (state.pending.files ? (ready ? "danger fill" : "danger") : "primary");
});
document.getElementById("modal").addEventListener("click", (e) => {
  if (e.target.dataset.cancel !== undefined || e.target.id === "modal" || e.target.hasAttribute("data-cancel")) { closeModal(); return; }
  if (e.target.dataset.files !== undefined) { state.pending.files = e.target.dataset.files === "1"; render(); return; }
  if (e.target.dataset.ok !== undefined && state.pending) remove(state.pending.hash, state.pending.files);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && state.pending) closeModal();
});
refresh();
setInterval(refresh, 2000);
