// TriCycle Waste admin dashboard. Talks to the same API as the mobile app.
const REFRESH_MS = 5000;
const ACCRA = [5.6037, -0.187];
const STATUS_LABEL = { empty: "Empty", partly_loaded: "Partly loaded", nearly_full: "Nearly full", full: "Full" };
const STATUS_COLOR = { empty: "#9fc48a", partly_loaded: "#5b9a3c", nearly_full: "#e0a526", full: "#c0392b" };

let token = localStorage.getItem("tw_admin_token");
let currentView = "overview";
let timer = null;
let rubberSizes = [];

// ---------- helpers ----------
const $ = (sel) => document.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (v) => (v == null ? "–" : Number(v).toFixed(2));
const when = (iso) => (iso ? new Date(iso + "Z").toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "–");
const words = (s) => String(s ?? "").replace(/_/g, " ");

function toast(msg, bad = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (bad ? " bad" : "");
  t.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (t.hidden = true), 3500);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers || {}) },
  });
  if (res.status === 401) { logout(); throw new Error("Please sign in again"); }
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join(", ") : `Error ${res.status}`);
  }
  return body;
}

function loadBar(percent, status) {
  const p = Math.min(100, Math.max(0, percent || 0));
  return `<div class="bar"><i style="width:${p}%;background:${STATUS_COLOR[status] || "#999"}"></i></div>`;
}

// ---------- auth ----------
function showLogin() { $("#app-view").hidden = true; $("#login-view").hidden = false; }
function logout() {
  token = null;
  localStorage.removeItem("tw_admin_token");
  clearInterval(timer);
  showLogin();
}

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  $("#login-error").textContent = "";
  try {
    const r = await api("/auth/login", { method: "POST", body: JSON.stringify({ phone: f.get("phone"), password: f.get("password") }) });
    if (r.role !== "admin") throw new Error("This account is not an administrator");
    token = r.token;
    localStorage.setItem("tw_admin_token", token);
    start();
  } catch (err) {
    $("#login-error").textContent = err.message;
  }
});
$("#logout").addEventListener("click", logout);

// ---------- navigation ----------
function show(view) {
  currentView = view;
  document.querySelectorAll("[data-section]").forEach((s) => (s.hidden = s.dataset.section !== view));
  document.querySelectorAll(".sidebar a").forEach((a) => a.classList.toggle("active", a.dataset.view === view));
  refresh();
  setTimeout(() => { map?.invalidateSize(); sitesMap?.invalidateSize(); }, 50);
}
window.addEventListener("hashchange", () => show(location.hash.slice(1) || "overview"));

async function refresh() {
  try {
    await ({ overview: loadOverview, collectors: loadCollectors, pickups: loadPickups, pricing: loadPricingOnce,
             sites: loadSites, reports: loadReports }[currentView] || loadOverview)();
    $("#refresh-note").textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    $("#refresh-note").textContent = err.message;
  }
}

// ---------- overview ----------
let map, layers;
function initMap() {
  if (map) return;
  map = L.map("map").setView(ACCRA, 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
  layers = { sites: L.layerGroup().addTo(map), reports: L.layerGroup().addTo(map), pickups: L.layerGroup().addTo(map), trikes: L.layerGroup().addTo(map) };
}
let fitted = false;

async function loadOverview() {
  initMap();
  const [stats, live, sites, pickups, reports] = await Promise.all([
    api("/admin/stats"), api("/admin/live"), api("/admin/disposal-sites"), api("/pickups"), api("/admin/dumping-reports?status=open"),
  ]);

  const cards = [
    ["Collectors online", `${stats.collectors_online} / ${stats.collectors}`],
    ["Pickups completed", stats.pickups_completed],
    ["Waiting for a tricycle", stats.pickups_waiting],
    ["Units collected", stats.units_collected],
    ["Units disposed (verified)", stats.units_disposed_verified],
    ["Disposal compliance", stats.disposal_compliance_percent == null ? "–" : `${stats.disposal_compliance_percent}%`, true],
    ["Revenue (GH₵)", money(stats.revenue)],
    ["Open dumping reports", stats.open_dumping_reports],
  ];
  $("#stats").innerHTML = cards.map(([label, value, hi]) =>
    `<div class="stat${hi ? " highlight" : ""}"><div class="value">${esc(value)}</div><div class="label">${esc(label)}</div></div>`).join("");

  // map layers
  Object.values(layers).forEach((l) => l.clearLayers());
  sites.filter((s) => s.active).forEach((s) =>
    L.circle([s.lat, s.lng], { radius: s.radius_m, color: "#1e3a2b", weight: 2, dashArray: "5 5", fillOpacity: 0.08 })
      .bindTooltip(`Disposal site: ${esc(s.name)}`).addTo(layers.sites));
  reports.forEach((r) =>
    L.marker([r.lat, r.lng], { icon: L.divIcon({ className: "", html: '<div class="report-pin">!</div>', iconSize: [22, 22] }) })
      .bindPopup(`<b>Dumping report #${r.id}</b><br>${esc(r.description || "No description")}<br><small>${when(r.created_at)}</small>`)
      .addTo(layers.reports));
  pickups.filter((p) => ["searching", "offered", "accepted", "awaiting_approval"].includes(p.status)).forEach((p) =>
    L.circleMarker([p.lat, p.lng], { radius: 7, color: "#fff", weight: 2, fillColor: "#2f6fb3", fillOpacity: 1 })
      .bindTooltip(`Pickup #${p.id}: ${p.declared_units} units, ${words(p.status)}${p.collector_name ? " (" + esc(p.collector_name) + ")" : ""}`)
      .addTo(layers.pickups));
  const points = [];
  live.filter((t) => t.lat != null).forEach((t) => {
    points.push([t.lat, t.lng]);
    const html = `<div class="trike-pin s-${t.status}">${esc(t.plate_number)} · ${Math.round(t.fill_percent)}%</div>`;
    L.marker([t.lat, t.lng], { icon: L.divIcon({ className: "", html, iconSize: null }) })
      .bindPopup(`<b>${esc(t.name)}</b> (${esc(t.plate_number)})<br>${STATUS_LABEL[t.status]}: ${t.load_units}/${t.capacity_units} units${loadBar(t.fill_percent, t.status)}`)
      .addTo(layers.trikes);
  });
  sites.forEach((s) => points.push([s.lat, s.lng]));
  if (!fitted && points.length) { map.fitBounds(points, { padding: [40, 40], maxZoom: 15 }); fitted = true; }

  $("#live-list").innerHTML = live.length
    ? live.sort((a, b) => b.fill_percent - a.fill_percent).map((t) => `
      <div class="load-item">
        <div class="top"><span>${esc(t.name)}</span><span class="muted">${esc(t.plate_number)}</span></div>
        ${loadBar(t.fill_percent, t.status)}
        <div class="bar-label">${STATUS_LABEL[t.status]} · ${t.load_units} of ${t.capacity_units} units (${t.fill_percent}%)</div>
      </div>`).join("")
    : '<p class="muted">No tricycles online right now.</p>';
}

// ---------- collectors ----------
async function loadCollectors() {
  const rows = await api("/admin/collectors");
  const body = $("#collectors-body");
  // Don't redraw while an admin is typing a capacity.
  if (body.contains(document.activeElement) && document.activeElement.tagName === "INPUT") return;
  body.innerHTML = rows.length ? rows.map((c) => `
    <tr>
      <td><b>${esc(c.name)}</b></td>
      <td>${esc(c.plate_number)}</td>
      <td><span class="badge ${c.is_online ? "ok" : "off"}">${c.is_online ? "Online" : "Offline"}</span></td>
      <td>${loadBar(c.fill_percent, c.status)}<div class="bar-label">${c.load_units}/${c.capacity_units} · ${STATUS_LABEL[c.status]}</div></td>
      <td><div class="inline"><input type="number" min="1" max="500" value="${c.capacity_units}" data-cap="${c.collector_id}" aria-label="Capacity for ${esc(c.name)}">
          <button class="small secondary" data-save-cap="${c.collector_id}">Save</button></div></td>
      <td>${c.verified
        ? `<span class="badge ok">Verified</span> <button class="small secondary" data-verify="${c.collector_id}" data-value="false">Suspend</button>`
        : `<button class="small" data-verify="${c.collector_id}" data-value="true">Verify</button>`}</td>
    </tr>`).join("") : '<tr><td colspan="6" class="muted">No collectors registered yet.</td></tr>';
}

$("#collectors-body").addEventListener("click", async (e) => {
  const verify = e.target.dataset.verify, cap = e.target.dataset.saveCap;
  try {
    if (verify) {
      await api(`/admin/collectors/${verify}`, { method: "PATCH", body: JSON.stringify({ verified: e.target.dataset.value === "true" }) });
      toast(e.target.dataset.value === "true" ? "Collector verified" : "Collector suspended");
    } else if (cap) {
      const value = Number(document.querySelector(`[data-cap="${cap}"]`).value);
      await api(`/admin/collectors/${cap}`, { method: "PATCH", body: JSON.stringify({ capacity_units: value }) });
      toast(`Capacity set to ${value} units`);
      document.activeElement.blur();
    } else return;
    loadCollectors();
  } catch (err) { toast(err.message, true); }
});

// ---------- pickups ----------
async function loadPickups() {
  const rows = await api("/pickups");
  $("#pickups-body").innerHTML = rows.length ? rows.map((p) => `
    <tr>
      <td>${p.id}</td>
      <td>${when(p.created_at)}</td>
      <td><span class="badge ${p.status}">${words(p.status)}</span></td>
      <td>${esc(p.waste_type)}</td>
      <td>${p.items.map((i) => `${i.quantity_confirmed ?? i.quantity_declared} ${esc(i.size_code)}`).join(", ")}</td>
      <td>${p.confirmed_units ?? p.declared_units}${p.confirmed_units != null && p.confirmed_units !== p.declared_units ? ` <span class="muted small">(declared ${p.declared_units})</span>` : ""}</td>
      <td>${money(p.final_price ?? p.proposed_price ?? p.quoted_price)}</td>
      <td>${esc(p.collector_name || "–")}</td>
    </tr>`).join("") : '<tr><td colspan="8" class="muted">No pickups yet.</td></tr>';
}

// ---------- pricing ----------
let pricingLoaded = false;
async function loadPricingOnce() {
  if (pricingLoaded) return;
  const [p, sizes] = await Promise.all([api("/admin/pricing"), api("/rubber-sizes")]);
  rubberSizes = sizes;
  const f = $("#pricing-form");
  ["base_fee", "rate_per_unit", "rate_per_km", "free_radius_km"].forEach((k) => (f.elements[k].value = p[k]));
  $("#factor-fields").innerHTML = Object.entries(p.waste_type_factors).map(([type, v]) =>
    `<label>${esc(words(type))}<input type="number" step="0.05" min="0" name="factor_${esc(type)}" value="${esc(v)}" required></label>`).join("");
  $("#calc-type").innerHTML = Object.keys(p.waste_type_factors).map((t) => `<option value="${esc(t)}">${esc(words(t))}</option>`).join("");
  $("#calc-sizes").innerHTML = sizes.map((s) =>
    `<label>${esc(s.name)} (${s.load_units} unit${s.load_units > 1 ? "s" : ""})<input type="number" min="0" value="${s.code === "small" ? 2 : s.code === "large" ? 1 : 0}" data-size="${s.load_units}"></label>`).join("");
  pricingLoaded = true;
  calc();
}

function calc() {
  const f = $("#pricing-form").elements;
  const units = [...document.querySelectorAll("[data-size]")].reduce((sum, el) => sum + Number(el.dataset.size) * Number(el.value || 0), 0);
  const factor = Number(f[`factor_${$("#calc-type").value}`]?.value || 1);
  const unitsCharge = units * Number(f.rate_per_unit.value) * factor;
  const distanceCharge = Math.max(0, Number($("#calc-km").value) - Number(f.free_radius_km.value)) * Number(f.rate_per_km.value);
  const total = Number(f.base_fee.value) + unitsCharge + distanceCharge;
  $("#calc-result").innerHTML = units
    ? `<div class="lines">${units} units · base ${money(f.base_fee.value)} + units ${money(unitsCharge)} + distance ${money(distanceCharge)}</div><div class="big">GH₵ ${money(total)}</div>`
    : '<div class="lines">Add at least one rubber</div>';
}
document.querySelector('[data-section="pricing"]').addEventListener("input", calc);

$("#pricing-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target.elements;
  const factors = {};
  [...f].filter((el) => el.name?.startsWith("factor_")).forEach((el) => (factors[el.name.slice(7)] = el.value));
  try {
    await api("/admin/pricing", { method: "PUT", body: JSON.stringify({
      base_fee: f.base_fee.value, rate_per_unit: f.rate_per_unit.value, rate_per_km: f.rate_per_km.value,
      free_radius_km: f.free_radius_km.value, waste_type_factors: factors }) });
    toast("Prices saved. New quotes use these rates.");
  } catch (err) { toast(err.message, true); }
});

// ---------- disposal sites ----------
let sitesMap, sitesLayer, newSiteMarker;
async function loadSites() {
  if (!sitesMap) {
    sitesMap = L.map("sites-map").setView(ACCRA, 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(sitesMap);
    sitesLayer = L.layerGroup().addTo(sitesMap);
    sitesMap.on("click", (e) => {
      const f = $("#site-form").elements;
      f.lat.value = e.latlng.lat.toFixed(6);
      f.lng.value = e.latlng.lng.toFixed(6);
      newSiteMarker?.remove();
      newSiteMarker = L.circle(e.latlng, { radius: Number(f.radius_m.value) || 150, color: "#5b9a3c" }).addTo(sitesMap);
    });
  }
  const sites = await api("/admin/disposal-sites");
  sitesLayer.clearLayers();
  sites.forEach((s) => L.circle([s.lat, s.lng], { radius: s.radius_m, color: s.active ? "#1e3a2b" : "#999", dashArray: "5 5" })
    .bindTooltip(esc(s.name)).addTo(sitesLayer));
  $("#sites-body").innerHTML = sites.length ? sites.map((s) => `
    <tr>
      <td><b>${esc(s.name)}</b></td>
      <td>${s.lat.toFixed(5)}, ${s.lng.toFixed(5)}</td>
      <td>${Math.round(s.radius_m)} m</td>
      <td><span class="badge ${s.active ? "ok" : "off"}">${s.active ? "Active" : "Inactive"}</span></td>
      <td><button class="small secondary" data-site="${s.id}" data-active="${!s.active}">${s.active ? "Deactivate" : "Activate"}</button></td>
    </tr>`).join("") : '<tr><td colspan="5" class="muted">No disposal sites.</td></tr>';
}

$("#sites-body").addEventListener("click", async (e) => {
  const id = e.target.dataset.site;
  if (!id) return;
  try {
    await api(`/admin/disposal-sites/${id}?active=${e.target.dataset.active}`, { method: "PATCH" });
    loadSites();
  } catch (err) { toast(err.message, true); }
});

$("#site-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target.elements;
  try {
    await api("/admin/disposal-sites", { method: "POST", body: JSON.stringify({
      name: f.name.value, lat: Number(f.lat.value), lng: Number(f.lng.value), radius_m: Number(f.radius_m.value) }) });
    toast("Disposal site added");
    e.target.reset();
    newSiteMarker?.remove();
    loadSites();
  } catch (err) { toast(err.message, true); }
});

// ---------- dumping reports ----------
async function loadReports() {
  const rows = await api("/admin/dumping-reports");
  const body = $("#reports-body");
  if (body.contains(document.activeElement)) return;
  body.innerHTML = rows.length ? rows.map((r) => `
    <tr>
      <td>${r.id}</td>
      <td>${when(r.created_at)}</td>
      <td><a href="https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lng}#map=18/${r.lat}/${r.lng}" target="_blank" rel="noopener">${r.lat.toFixed(5)}, ${r.lng.toFixed(5)}</a></td>
      <td>${esc(r.description || "–")}</td>
      <td>${esc(r.photo_url)}</td>
      <td><select data-report="${r.id}" aria-label="Status of report ${r.id}">
        ${["open", "assigned", "cleared"].map((s) => `<option ${s === r.status ? "selected" : ""}>${s}</option>`).join("")}
      </select></td>
    </tr>`).join("") : '<tr><td colspan="6" class="muted">No reports yet.</td></tr>';
}

$("#reports-body").addEventListener("change", async (e) => {
  const id = e.target.dataset.report;
  if (!id) return;
  try {
    await api(`/admin/dumping-reports/${id}`, { method: "PATCH", body: JSON.stringify({ status: e.target.value }) });
    toast(`Report #${id} marked ${e.target.value}`);
    e.target.blur();
  } catch (err) { toast(err.message, true); }
});

// ---------- start ----------
function start() {
  $("#login-view").hidden = true;
  $("#app-view").hidden = false;
  show(location.hash.slice(1) || "overview");
  clearInterval(timer);
  timer = setInterval(() => { if (currentView !== "pricing") refresh(); }, REFRESH_MS);
}

token ? start() : showLogin();
