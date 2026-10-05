"use strict";

const KEY = "maroon-historian-v1";

function store() {
  try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; }
}
function save(data) {
  localStorage.setItem(KEY, JSON.stringify(data));
  updateDock();
}
function reviewer() {
  return (document.getElementById("reviewer") || {}).value || store().reviewer || "";
}
function setReviewer(name) {
  const all = store();
  all.reviewer = name;
  save(all);
}

function csv(rows) {
  const cell = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return "\ufeff" + rows.map((r) => r.map(cell).join(",")).join("\r\n");
}
function download(name, text, type = "text/csv;charset=utf-8") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 800);
}

function counts() {
  const s = store();
  return {
    notices: Object.keys(s.notices || {}).length,
    schema: Object.keys(s.schema || {}).length,
    personas: Object.keys(s.personas || {}).length,
    interviews: Object.keys(s.interviews || {}).length,
    rules: Object.keys(s.rules || {}).length,
    pi: s.pi ? 1 : 0,
  };
}

function dumpAll() {
  const s = store();
  const who = reviewer() || "reviewer";
  const day = new Date().toISOString().slice(0, 10);
  download(`maroon-labels-${who.replace(/\W+/g, "_")}-${day}.json`, JSON.stringify({
    reviewer: who, exported: new Date().toISOString(), ...s,
  }, null, 2), "application/json");
}

function updateDock() {
  const el = document.getElementById("dock-count");
  if (!el) return;
  const c = counts();
  const n = c.notices + c.schema + c.personas + c.interviews + c.rules + c.pi;
  el.textContent = n
    ? `${n} items saved in this browser (notices ${c.notices}, conversations ${c.interviews}, people ${c.personas}).`
    : "Nothing saved yet. Your work stays in this browser until you download it.";
}

function initDock() {
  const r = document.getElementById("reviewer");
  if (r) {
    r.value = store().reviewer || "";
    r.onchange = () => setReviewer(r.value);
  }
  const dl = document.getElementById("download-all");
  if (dl) dl.onclick = dumpAll;
  const clr = document.getElementById("clear-all");
  if (clr) clr.onclick = () => {
    if (confirm("Delete all your saved work in this browser? Download it first if you still need it.")) {
      localStorage.removeItem(KEY);
      location.reload();
    }
  };
  updateDock();
}

document.addEventListener("DOMContentLoaded", initDock);
