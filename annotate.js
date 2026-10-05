"use strict";

const TYPES = ["runaway", "sale", "recapture", "manumission", "ordinance", "shipping", "not_relevant", "unreadable"];
const FIELDS = {
  runaway: [
    ["sex", "Sex as stated", "choice", ["", "F", "M", "not stated"]],
    ["age", "Stated age", "text"],
    ["occupation", "Occupation or skill", "text"],
    ["estate", "Estate or owner", "text"],
    ["suspected_destination", "Suspected destination (advertiser’s claim)", "text"],
    ["reward", "Reward", "text"],
  ],
  sale: [
    ["n_persons", "How many people", "text"],
    ["sex_mix", "Men / women / children", "text"],
    ["estate", "Estate or seller", "text"],
    ["kind", "Kind of sale", "choice", ["", "private", "auction", "sheriff", "not stated"]],
  ],
  recapture: [
    ["sex", "Sex as stated", "choice", ["", "F", "M", "not stated"]],
    ["age", "Stated age", "text"],
    ["jail", "Fort or jail named", "text"],
    ["claimed_by", "Who should claim the person", "text"],
  ],
  manumission: [
    ["sex", "Sex as stated", "choice", ["", "F", "M", "not stated"]],
    ["by", "How freed, if stated", "choice", ["", "owner", "self-purchase", "will", "not stated"]],
  ],
  ordinance: [
    ["topic", "What the rule is about", "text"],
    ["constraint", "What is required or forbidden", "text"],
  ],
  shipping: [
    ["type", "Kind of vessel", "choice", ["", "sloop", "brig", "schooner", "other", "not stated"]],
    ["arrival_or_departure", "Arrived or sailed", "choice", ["", "arrival", "departure", "not stated"]],
    ["port", "Port or destination", "text"],
  ],
};

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const pretty = (d) => `${+d.slice(8,10)} ${MONTHS[+d.slice(5,7)-1]} ${d.slice(0,4)}`;
const period = (s) => (s === "S1" ? "before emancipation" : s === "S2" ? "after emancipation" : "other years");

let DATA = { items: [] };

function labelled() {
  return store().notices || {};
}

function fieldInput(spec, value) {
  const [id, label, kind, opts] = spec;
  if (kind === "choice") {
    return `<label class="stack">${label}
      <select data-field="${id}">${opts.map((o) =>
        `<option value="${o}" ${value === o ? "selected" : ""}>${o || "—"}</option>`).join("")}</select>
    </label>`;
  }
  return `<label class="stack">${label}
    <input type="text" data-field="${id}" value="${(value || "").replace(/"/g, "&quot;")}">
  </label>`;
}

function renderItem(it) {
  const rec = labelled()[it.id] || {};
  const typ = rec.type || it.suggested_type;
  const fields = FIELDS[typ] || [];
  const art = document.createElement("article");
  art.className = "item";
  art.dataset.id = it.id;
  art.innerHTML = `
    <h3>${pretty(it.date)} — <i>${it.title.replace(/ \(\d{4}-\d{4}\)$/, "")}</i></h3>
    <div class="where">Page ${it.page} · ${period(it.stratum)} · computer suggested: <b>${it.suggested_type}</b>
      ${it.link ? ` · <a href="${it.link}" target="_blank" rel="noopener">Open the page at the Royal Library ↗</a>` : ""}</div>
    <div class="snippet">${esc(it.snippet)}</div>
    <div class="rank" style="margin-top:12px">
      <span>This is:</span>
      ${TYPES.map((t) => `<button type="button" data-type="${t}" aria-pressed="${typ === t}">${t.replace("_", " ")}</button>`).join("")}
    </div>
    <div class="fields">${fields.map((f) => fieldInput(f, (rec.fields || {})[f[0]])).join("")}</div>
    <label class="stack">Note
      <input type="text" data-note value="${(rec.note || "").replace(/"/g, "&quot;")}" placeholder="OCR garbled, two notices mixed, …">
    </label>`;
  const persist = () => {
    const all = store();
    all.notices = all.notices || {};
    const typeBtn = [...art.querySelectorAll("[data-type]")].find((b) => b.getAttribute("aria-pressed") === "true");
    const fieldsObj = {};
    for (const el of art.querySelectorAll("[data-field]")) fieldsObj[el.dataset.field] = el.value;
    all.notices[it.id] = {
      type: typeBtn ? typeBtn.dataset.type : "",
      suggested: it.suggested_type,
      fields: fieldsObj,
      note: art.querySelector("[data-note]").value,
      pid: it.pid,
      date: it.date,
      link: it.link,
    };
    save(all);
    progress();
  };
  for (const btn of art.querySelectorAll("[data-type]")) {
    btn.onclick = () => {
      for (const x of art.querySelectorAll("[data-type]")) x.setAttribute("aria-pressed", "false");
      btn.setAttribute("aria-pressed", "true");
      persist();
      // rebuild fields for the new type
      const wrap = art.querySelector(".fields");
      const t = btn.dataset.type;
      wrap.innerHTML = (FIELDS[t] || []).map((f) => fieldInput(f, "")).join("");
      for (const el of art.querySelectorAll("[data-field], [data-note]")) el.onchange = persist;
    };
  }
  for (const el of art.querySelectorAll("[data-field], [data-note]")) el.onchange = persist;
  return art;
}

function esc(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function progress() {
  const n = DATA.items.length;
  const d = Object.keys(labelled()).length;
  document.getElementById("prog-text").textContent = `${d} of ${n} notices labelled`;
  document.getElementById("prog-bar").style.width = (n ? (100 * d) / n : 0) + "%";
}

function visible(it) {
  const f = document.getElementById("filter").value;
  const k = document.getElementById("kind").value;
  const done = Boolean(labelled()[it.id]);
  if (f === "todo" && done) return false;
  if (f === "done" && !done) return false;
  if (k && it.suggested_type !== k) return false;
  return true;
}

let shown = 0;
const PAGE = 15;

function draw() {
  const list = document.getElementById("list");
  list.innerHTML = "";
  shown = 0;
  more();
  progress();
}

function more() {
  const list = document.getElementById("list");
  const items = DATA.items.filter(visible);
  const batch = items.slice(shown, shown + PAGE);
  for (const it of batch) list.appendChild(renderItem(it));
  shown += batch.length;
  let btn = document.getElementById("more");
  if (!btn) {
    btn = document.createElement("button");
    btn.id = "more";
    btn.type = "button";
    btn.textContent = "Show more notices";
    btn.onclick = more;
    list.parentElement.appendChild(btn);
  }
  btn.hidden = shown >= items.length;
  if (!items.length) list.innerHTML = "<p class='hint'>Nothing in this filter. Try “All” or another kind.</p>";
  progress();
}

async function main() {
  DATA = await (await fetch("data/records.json")).json();
  document.getElementById("filter").onchange = draw;
  document.getElementById("kind").onchange = draw;
  draw();
}

main().catch((err) => {
  document.getElementById("prog-text").textContent =
    "Could not load notices. If you opened the file from disk, use the website address instead. " + err.message;
});
