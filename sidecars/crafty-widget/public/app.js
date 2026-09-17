(() => {
  const stats = document.getElementById("stats");
  const list = document.getElementById("list");
  const sub = document.getElementById("sub");
  if (new URLSearchParams(location.search).has("embed")) {
    document.documentElement.classList.add("embed");
  }

  const well = (n, l, tone) => {
    const d = document.createElement("div");
    d.className = "well";
    d.innerHTML = `<div class="n ${tone || ""}"></div><div class="l"></div>`;
    d.querySelector(".n").textContent = n;
    d.querySelector(".l").textContent = l;
    return d;
  };

  const pct = (v) => (v == null ? "—" : Math.round(v) + "%");

  function render(data) {
    const servers = data.servers || [];
    const running = data.running || 0;
    stats.replaceChildren(
      well(running + "/" + (data.count || servers.length), "servers", running ? "tone-ok" : "tone-warn"),
      well(String(data.players || 0), "players", data.players ? "tone-ok" : ""),
      well(data.health || "—", "status", running ? "tone-ok" : "tone-warn"),
      well(servers.filter((s) => s.running).length ? "live" : "idle", "query", running ? "tone-ok" : ""),
    );
    sub.textContent = running ? running + " running" : "no servers running";

    if (!servers.length) {
      list.innerHTML = '<div class="empty">No Minecraft servers in Crafty</div>';
      return;
    }
    list.replaceChildren();
    for (const s of servers) {
      const row = document.createElement("div");
      row.className = "row";
      const cap = s.max ? s.online + "/" + s.max : String(s.online);
      const bits = [
        cap + " online",
        s.world && s.world,
        s.version && s.version,
        s.cpu != null && "cpu " + pct(s.cpu),
        s.mem_percent != null && "ram " + pct(s.mem_percent),
      ].filter(Boolean);
      const who = (s.players || []).join(", ");
      row.innerHTML =
        '<div class="row-title"><p></p><span class="st"></span></div>' +
        '<div class="nums"></div>' +
        (who ? '<div class="who">players <b></b></div>' : "");
      row.querySelector("p").textContent = s.name || "Minecraft";
      const st = row.querySelector(".st");
      st.textContent = s.running ? "running" : "stopped";
      st.classList.add(s.running ? "tone-ok" : "tone-bad");
      row.querySelector(".nums").textContent = bits.join(" · ");
      if (who) row.querySelector(".who b").textContent = who;
      list.appendChild(row);
    }
  }

  async function tick() {
    try {
      const r = await fetch("/api/summary", { cache: "no-store" });
      if (!r.ok) throw new Error(String(r.status));
      render(await r.json());
    } catch (e) {
      stats.replaceChildren();
      list.innerHTML = '<div class="err">Crafty unreachable (' + e.message + ")</div>";
      sub.textContent = "error";
    }
  }

  tick();
  setInterval(tick, 15000);
})();
