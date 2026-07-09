const TOKEN = window.HLOC_TOKEN || "";

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (TOKEN) headers["X-HLOC-Token"] = TOKEN;
  const res = await fetch(path, { ...opts, headers });
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("json")) return res.json();
  return res;
}

function toast(msg) {
  const el = document.createElement("div");
  el.style.cssText =
    "position:fixed;top:70px;right:16px;background:#141b26;border:1px solid #232b38;border-left:3px solid #2fd9d0;padding:10px 14px;border-radius:6px;font-size:12px;z-index:99";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function show(v) {
  document.querySelectorAll(".view").forEach((x) => x.classList.remove("active"));
  document.querySelectorAll(".nav").forEach((x) => x.classList.remove("active"));
  document.getElementById("v-" + v)?.classList.add("active");
  document.querySelector(`.nav[data-v="${v}"]`)?.classList.add("active");
  if (v === "dash") loadDash();
  if (v === "links") loadLinks();
  if (v === "events") loadEvents();
}

document.querySelectorAll(".nav").forEach((n) =>
  n.addEventListener("click", () => show(n.dataset.v))
);

async function loadDash() {
  const s = await api("/api/stats");
  document.getElementById("d-links").textContent = s.links || 0;
  document.getElementById("d-active").textContent = s.active_links || 0;
  document.getElementById("d-events").textContent = s.events || 0;
  document.getElementById("d-gps").textContent = s.gps_shares || 0;
  document.getElementById("st-links").textContent = `${s.links || 0} liens`;
  document.getElementById("st-events").textContent = `${s.events || 0} events`;
  document.getElementById("st-gps").textContent = `${s.gps_shares || 0} GPS`;

  const ev = await api("/api/events");
  renderEventsList(document.getElementById("dash-events"), (ev.events || []).slice(0, 8));
  loadMap();
}

let map, mapLayer;
async function loadMap() {
  const el = document.getElementById("map");
  if (!el || typeof L === "undefined") return;
  const geo = await api("/api/events/geojson");
  if (!map) {
    map = L.map("map").setView([13.5, 2.1], 3);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OSM",
      maxZoom: 18,
    }).addTo(map);
  }
  if (mapLayer) map.removeLayer(mapLayer);
  mapLayer = L.geoJSON(geo, {
    pointToLayer: (f, latlng) =>
      L.circleMarker(latlng, {
        radius: 7,
        color: f.properties.gps ? "#2fd9d0" : "#f77f00",
        fillOpacity: 0.8,
      }).bindPopup(
        `#${f.properties.id} ${f.properties.type}<br>${f.properties.ip}<br>${f.properties.created}`
      ),
  }).addTo(map);
  try {
    if (geo.features?.length) map.fitBounds(mapLayer.getBounds().pad(0.3));
  } catch (_) {}
}

function renderEventsList(box, events) {
  if (!events.length) {
    box.innerHTML = `<div class="empty">Aucun événement.</div>`;
    return;
  }
  box.innerHTML = events
    .map((e) => {
      const geo = e.geo_ip || {};
      const maps =
        e.lat != null
          ? `<a href="https://www.openstreetmap.org/?mlat=${e.lat}&mlon=${e.lon}#map=16/${e.lat}/${e.lon}" target="_blank" rel="noopener">Carte GPS</a>`
          : geo.maps_url
            ? `<a href="${esc(geo.maps_url)}" target="_blank" rel="noopener">Carte IP</a>`
            : "—";
      const badge =
        e.event_type === "share"
          ? "gps"
          : e.event_type === "view"
            ? "view"
            : e.event_type === "partial"
              ? "off"
              : "ok";
      return `<div class="ev-card">
        <h3><span class="badge ${badge}">${esc(e.event_type)}</span> #${e.id}
          <span class="mono">${esc(e.created)}</span></h3>
        <div class="mono">IP ${esc(e.ip || "—")} · ${esc(geo.city || "?")}, ${esc(geo.country || "?")}</div>
        <div class="mono">GPS: ${e.lat != null ? `${e.lat}, ${e.lon} (±${e.accuracy || "?"}m)` : "non"} · ${maps}</div>
        <div class="mono">${esc(((e.extra || {}).ua_info || {}).device || "")} / ${esc(((e.extra || {}).ua_info || {}).browser || "")} / ${esc(((e.extra || {}).ua_info || {}).os || "")}</div>
      </div>`;
    })
    .join("");
}

async function loadLinks() {
  const d = await api("/api/links");
  const box = document.getElementById("links-box");
  const links = d.links || [];
  if (!links.length) {
    box.innerHTML = `<div class="empty">Aucun lien — crée-en un.</div>`;
    return;
  }
  box.innerHTML = `<table><thead><tr>
    <th>Titre</th><th>URL / QR</th><th>État</th><th>Clics</th><th>Expire</th><th></th>
  </tr></thead><tbody>
  ${links
    .map(
      (L) => `<tr>
    <td><b>${esc(L.title)}</b><div class="mono">${esc(L.operator_name || "")}</div></td>
    <td class="mono"><a href="${esc(L.url)}" target="_blank" style="color:var(--cyan)">${esc(L.url)}</a>
      <button class="mini secondary" data-copy="${esc(L.url)}">copier</button>
      <br><img src="/api/links/${L.id}/qr?token=${encodeURIComponent(TOKEN)}" alt="QR" style="margin-top:6px;width:96px;height:96px;background:#fff;border-radius:4px" onerror="this.style.display='none'">
    </td>
    <td><span class="badge ${L.active ? "ok" : "off"}">${L.active ? "actif" : "off"}</span>
      ${L.has_password ? '<span class="badge view">mdp</span>' : ""}</td>
    <td>${L.click_count || 0}${L.max_clicks ? "/" + L.max_clicks : ""}</td>
    <td class="mono">${esc(L.expires_at || "—")}</td>
    <td>
      <button class="mini secondary" data-toggle="${L.id}">on/off</button>
      <button class="mini secondary" data-open="${L.id}">détail</button>
      <button class="mini danger" data-del="${L.id}">suppr</button>
    </td>
  </tr>`
    )
    .join("")}
  </tbody></table>`;

  box.querySelectorAll("[data-copy]").forEach((b) =>
    b.addEventListener("click", () => {
      navigator.clipboard?.writeText(b.dataset.copy);
      toast("Lien copié");
    })
  );
  box.querySelectorAll("[data-toggle]").forEach((b) =>
    b.addEventListener("click", async () => {
      await api(`/api/links/${b.dataset.toggle}/toggle`, { method: "POST" });
      loadLinks();
    })
  );
  box.querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("Supprimer ce lien et ses events ?")) return;
      await api(`/api/links/${b.dataset.del}`, { method: "DELETE" });
      loadLinks();
      loadDash();
    })
  );
  box.querySelectorAll("[data-open]").forEach((b) =>
    b.addEventListener("click", async () => {
      const d = await api(`/api/links/${b.dataset.open}`);
      const ev = d.events || [];
      alert(
        `${d.link.title}\n${d.link.url}\n\n${ev.length} événement(s)\n` +
          ev
            .slice(0, 5)
            .map((e) => `${e.created} ${e.event_type} ${e.ip}`)
            .join("\n")
      );
    })
  );
}

async function loadEvents() {
  const d = await api("/api/events");
  renderEventsList(document.getElementById("events-box"), d.events || []);
}

document.getElementById("btn-create").addEventListener("click", async () => {
  const body = {
    title: document.getElementById("c-title").value.trim(),
    operator_name: document.getElementById("c-op").value.trim(),
    message: document.getElementById("c-msg").value.trim(),
    require_gps: document.getElementById("c-gps").checked,
    max_clicks: parseInt(document.getElementById("c-max").value || "0", 10),
    expires_hours: parseInt(document.getElementById("c-exp").value || "0", 10),
    password: document.getElementById("c-pass").value,
    theme: document.getElementById("c-theme").value,
    redirect_url: document.getElementById("c-redir").value.trim(),
    notes: document.getElementById("c-notes").value.trim(),
  };
  if (!body.title) return toast("Titre requis");
  const r = await api("/api/links", { method: "POST", body: JSON.stringify(body) });
  const out = document.getElementById("create-out");
  if (!r.ok) {
    out.classList.remove("hidden");
    out.style.borderColor = "var(--red)";
    out.textContent = r.message || r.error || "Erreur";
    toast(r.message || "Erreur");
    return;
  }
  out.classList.remove("hidden");
  out.style.borderColor = "var(--green)";
  out.innerHTML = `<b>Lien créé</b><br><a href="${esc(r.data.url)}" target="_blank">${esc(r.data.url)}</a>
    <br><button class="mini secondary" id="copy-new">Copier</button>`;
  document.getElementById("copy-new")?.addEventListener("click", () => {
    navigator.clipboard?.writeText(r.data.url);
    toast("Copié");
  });
  toast("Lien généré");
  loadDash();
});

document.getElementById("btn-export-csv")?.addEventListener("click", () => {
  window.location = `/api/events/export.csv?token=${encodeURIComponent(TOKEN)}`;
});
document.getElementById("btn-export-json")?.addEventListener("click", () => {
  window.location = `/api/events/export.json?token=${encodeURIComponent(TOKEN)}`;
});
document.getElementById("btn-refresh-ev")?.addEventListener("click", loadEvents);

document.getElementById("legal-box").textContent = window.HLOC_LEGAL || "";

loadDash();
setInterval(() => {
  if (document.getElementById("v-dash").classList.contains("active")) loadDash();
  if (document.getElementById("v-events").classList.contains("active")) loadEvents();
}, 12000);
