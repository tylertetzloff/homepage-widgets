(() => {
  // Rewrites Homepage docker-status pills for cards in this group.
  // Change GROUP if your services.yaml group title is different.
  const GROUP = "Infra";
  const rules = [
    { id: "ugreen", title: "uGreen", service: "uGreen", fallback: "Healthy",
      pick: (j) => (j.health || j.data?.health || "Healthy").toString(),
      good: ["healthy"], warn: ["warning"] },
    { id: "mounts", title: "Mounts", service: "Mounts", fallback: "Connected",
      pick: (j) => {
        const s = (j.status || j.data?.status || "Connected").toString();
        if (/^(up|ok|connected|mounted)$/i.test(s)) return "Connected";
        if (/^(down|error|critical)$/i.test(s)) return "Down";
        return s;
      },
      good: ["connected", "mounted", "up"], warn: [] },
  ];
  const cache = {};
  let busy = false;

  async function load(service) {
    const q = new URLSearchParams({ group: GROUP, service, index: "0" });
    const r = await fetch("/api/services/proxy?" + q);
    if (!r.ok) throw new Error(String(r.status));
    return r.json();
  }

  function findCard(rule) {
    const byId = document.getElementById(rule.id);
    if (byId) return byId;
    const byData = document.querySelector('li.service[data-name="' + rule.title + '"]');
    if (byData) return byData;
    for (const el of document.querySelectorAll(".service-name")) {
      const name = (el.childNodes[0] && el.childNodes[0].textContent || "").trim();
      if (name === rule.title) return el.closest("li.service") || el.closest(".service");
    }
    return null;
  }

  function colorFor(text, rule) {
    const low = text.toLowerCase();
    if (rule.good.includes(low)) return "text-emerald-500/80";
    if (rule.warn.includes(low)) return "text-orange-400/80";
    return "text-rose-500/80";
  }

  function apply() {
    if (busy) return;
    busy = true;
    try {
      for (const rule of rules) {
        const card = findCard(rule);
        if (!card) continue;
        const text = cache[rule.service] || rule.fallback;
        const inner = card.querySelector(".docker-status div");
        if (!inner || inner.textContent === text) continue;
        inner.textContent = text;
        inner.className = "text-[8px] font-bold uppercase " + colorFor(text, rule);
        if (inner.parentElement) inner.parentElement.title = text;
      }
    } finally {
      busy = false;
    }
  }

  async function refresh() {
    for (const rule of rules) {
      try {
        cache[rule.service] = rule.pick(await load(rule.service));
      } catch (e) {
        console.debug("[infra-badge]", rule.service, e.message);
      }
    }
    apply();
  }

  refresh();
  setInterval(refresh, 20000);
  setInterval(apply, 2000);
})();
