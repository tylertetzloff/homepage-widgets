const embed = new URLSearchParams(location.search).get("embed") === "1" || window.self !== window.top;
if (embed) {
  document.documentElement.classList.add("embed");
  document.body.classList.add("embed");
  document.getElementById("page").classList.add("embed");
  document.getElementById("pageTitle").hidden = true;
}

const state = { albums: [], i: 0, job: { state: "idle", log: [], progress: 0, wrote: 0 }, keep: true };

function bytes(n) {
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

function album() { return state.albums[state.i] || null; }

function well(n, l, tone) {
  return `<div class="well"><span class="n ${tone || ""}">${n}</span><span class="l">${l}</span></div>`;
}

function render() {
  const a = album();
  const j = state.job;
  const running = j.state === "running";
  const status = running ? `${j.progress || 0}%` : j.state === "done" ? "done" : j.state === "error" ? "fail" : "idle";
  const tone = j.state === "done" ? "tone-ok" : j.state === "error" ? "tone-bad" : running ? "tone-warn" : "";
  document.getElementById("stats").innerHTML = [
    well(a ? a.ntracks : "0", "Tracks"),
    well(a ? bytes(a.size) : "—", "Image"),
    well(status, "Status", tone),
    well(String(j.wrote || 0), "Wrote", j.wrote ? "tone-ok" : ""),
  ].join("");
  const files = document.getElementById("files");
  if (!a) {
    files.innerHTML = `<p class="empty">No CUE + FLAC pairs under inbox.</p>`;
  } else {
    files.innerHTML = `
      <button class="file" type="button" data-cycle="1"><div><div class="v">${a.cue_name}</div><div class="k">CUE · ${a.artist} — ${a.album}</div></div><span class="chg">Change</span></button>
      <button class="file" type="button" data-cycle="1"><div><div class="v">${a.audio_name}</div><div class="k">FLAC · ${bytes(a.size)}</div></div><span class="chg">Change</span></button>
      <div class="file"><div><div class="v">${a.folder}/</div><div class="k">Out</div></div></div>`;
  }
  const tracks = document.getElementById("tracks");
  if (a && a.tracks.length) {
    tracks.innerHTML = a.tracks.map((t) =>
      `<div class="row"><span class="nums">${String(t.n).padStart(2, "0")}</span><span class="meta">${t.title}</span></div>`
    ).join("");
  } else tracks.innerHTML = "";
  const bar = document.getElementById("bar");
  bar.hidden = !(running || j.state === "done");
  bar.firstElementChild.style.width = `${j.progress || 0}%`;
  document.getElementById("log").textContent = (j.log || []).at(-1) || "";
  const err = document.getElementById("err");
  err.hidden = !j.error;
  err.textContent = j.error || "";
  document.getElementById("split").disabled = !a || running;
  document.getElementById("split").textContent = a ? `Split ${a.ntracks} tracks` : "Split";
  document.getElementById("keep").textContent = state.keep ? "Keep image" : "Delete image after";
}

document.getElementById("files").addEventListener("click", (e) => {
  if (!e.target.closest("[data-cycle]")) return;
  if (!state.albums.length) return;
  state.i = (state.i + 1) % state.albums.length;
  render();
});
document.getElementById("keep").onclick = () => { state.keep = !state.keep; render(); };
document.getElementById("split").onclick = async () => {
  const a = album();
  if (!a) return;
  try {
    await api("/api/split", { cue: a.cue, audio: a.audio, out: a.folder, keep_image: state.keep });
  } catch (e) {
    state.job.error = e.message;
    render();
  }
};

async function tick() {
  try {
    const [alb, job] = await Promise.all([api("/api/albums"), api("/api/job")]);
    state.albums = alb.albums || [];
    if (state.i >= state.albums.length) state.i = 0;
    state.job = job;
  } catch (e) {
    state.job.error = e.message;
  }
  render();
}
tick();
setInterval(tick, 1500);
