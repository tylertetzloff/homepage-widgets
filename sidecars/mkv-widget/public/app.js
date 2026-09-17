const embed = new URLSearchParams(location.search).get("embed") === "1" || window.self !== window.top;
if (embed) {
  document.documentElement.classList.add("embed");
  document.body.classList.add("embed");
  document.getElementById("page").classList.add("embed");
  document.getElementById("pageTitle").hidden = true;
}

const state = {
  sources: [], dests: [], si: 0, di: 0,
  titles: [], job: { state: "idle", log: [], progress: 0, line: "" },
};

function bytes(n) {
  if (!n) return "";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let v = n, i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
}

async function api(path, body) {
  const opt = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

function src() { return state.sources[state.si] || null; }
function dest() { return state.dests[state.di] || ""; }
function picked() { return state.titles.filter((t) => t.on); }

function well(n, l, tone) {
  return `<div class="well"><span class="n ${tone || ""}">${n}</span><span class="l">${l}</span></div>`;
}

function render() {
  const s = src();
  const j = state.job;
  const running = j.state === "running";
  const sel = picked();
  const status = running ? `${j.progress || 0}%` : j.state === "done" ? "done" : j.state === "error" ? "fail" : "idle";
  const tone = j.state === "done" ? "tone-ok" : j.state === "error" ? "tone-bad" : running ? "tone-warn" : "";
  document.getElementById("stats").innerHTML = [
    well(String(sel.length), "Titles"),
    well(s ? (s.kind || "").toUpperCase() : "—", "Source"),
    well(status, "Status", tone),
    well(s ? bytes(s.size) || "—" : "—", "Image"),
  ].join("");
  const files = document.getElementById("files");
  files.innerHTML = `
    <button class="file" type="button" data-src="1"><div><div class="v">${s ? s.name : "No sources"}</div><div class="k">${s ? s.kind.toUpperCase() + " · " + s.label : "Inbox empty"}</div></div><span class="chg">Change</span></button>
    <button class="file" type="button" data-dest="1"><div><div class="v">${dest() || "—"}</div><div class="k">Dest</div></div><span class="chg">Change</span></button>`;
  const box = document.getElementById("titles");
  if (!state.titles.length) {
    box.innerHTML = `<p class="empty">Scan titles on the selected source.</p>`;
  } else {
    box.innerHTML = state.titles.map((t, i) =>
      `<button class="row ${t.on ? "on" : ""}" type="button" data-t="${i}">
        <span class="check"></span>
        <span class="meta">${String(t.id).padStart(2, "0")} ${t.name}</span>
        <span class="nums">${t.duration || ""} ${t.size || ""}</span>
      </button>`
    ).join("");
  }
  const bar = document.getElementById("bar");
  bar.hidden = !(running || j.state === "done");
  bar.firstElementChild.style.width = `${j.progress || 0}%`;
  document.getElementById("log").textContent = j.line || (j.log || []).at(-1) || "";
  const err = document.getElementById("err");
  err.hidden = !j.error;
  err.textContent = j.error || "";
  document.getElementById("scan").disabled = !s || running;
  document.getElementById("rip").disabled = !s || !sel.length || running;
  document.getElementById("rip").textContent = `Rip ${sel.length || 0} title${sel.length === 1 ? "" : "s"}`;
}

document.getElementById("files").addEventListener("click", (e) => {
  if (e.target.closest("[data-src]") && state.sources.length) {
    state.si = (state.si + 1) % state.sources.length;
    state.titles = [];
  }
  if (e.target.closest("[data-dest]") && state.dests.length) {
    state.di = (state.di + 1) % state.dests.length;
  }
  render();
});
document.getElementById("titles").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-t]");
  if (!btn) return;
  const t = state.titles[+btn.dataset.t];
  if (t) t.on = !t.on;
  render();
});
document.getElementById("scan").onclick = async () => {
  const s = src();
  if (!s) return;
  try {
    const r = await api("/api/info", { kind: s.kind, path: s.path });
    state.titles = (r.titles || []).map((t, i) => ({ ...t, on: i === 0 }));
  } catch (e) {
    state.job.error = e.message;
  }
  render();
};
document.getElementById("rip").onclick = async () => {
  const s = src();
  if (!s) return;
  try {
    await api("/api/rip", {
      kind: s.kind,
      path: s.path,
      dest: dest(),
      titles: picked().map((t) => t.id),
    });
  } catch (e) {
    state.job.error = e.message;
  }
  render();
};

async function tick() {
  try {
    const [srcp, job] = await Promise.all([api("/api/sources"), api("/api/job")]);
    state.sources = srcp.sources || [];
    state.dests = srcp.dests || [];
    if (state.si >= state.sources.length) state.si = 0;
    if (state.di >= state.dests.length) state.di = 0;
    state.job = job;
  } catch (e) {
    state.job.error = e.message;
  }
  render();
}
tick();
setInterval(tick, 1500);
