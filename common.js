"use strict";

const KEY = "kamer-historian-v1";

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
    schema: Object.keys(s.schema || {}).length,
    speakers: Object.keys(s.speakers || {}).length,
    personas: Object.keys(s.personas || {}).length,
    interviews: Object.keys(s.interviews || {}).length,
    rules: Object.keys(s.rules || {}).length,
    procedure: Object.keys(s.procedure || {}).length,
    map: s.map ? 1 : 0,
  };
}

function dumpAll() {
  const s = store();
  const who = reviewer() || "reviewer";
  const day = new Date().toISOString().slice(0, 10);
  download(`kamer-labels-${who.replace(/\W+/g, "_")}-${day}.json`, JSON.stringify({
    schema: "kamer-historian-v1",
    reviewer: who,
    exported: new Date().toISOString(),
    ...s,
  }, null, 2), "application/json");
}

function updateDock() {
  const el = document.getElementById("dock-count");
  if (!el) return;
  const c = counts();
  const n = c.schema + c.speakers + c.personas + c.interviews + c.rules + c.procedure + c.map;
  el.textContent = n
    ? `${n} items saved (names ${c.speakers}, conversations ${c.interviews}, people ${c.personas}, procedure ${c.procedure}).`
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
