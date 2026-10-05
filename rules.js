"use strict";

const RULES = [
  ["pass_road", "An enslaved person may not use the town road without a pass signed by owner or overseer."],
  ["curfew", "After the evening gun / curfew hour, enslaved people may not be on the roads."],
  ["market_sunday", "The public market is a Sunday institution; weekday market trade is exceptional."],
  ["board_vessel", "Boarding a vessel requires a pass (or the help of a boatman off the official road)."],
  ["hill_path", "Unpatrolled hill paths and coves exist and can be known by rumour, not only by having walked them."],
  ["foreign_jurisdiction", "Puerto Rico (and similar off-island ports) are foreign jurisdictions; reaching them can change legal status."],
  ["roll_call", "Roll call at first light, gang labour through the day, provision grounds after dismissal, are the ordinary enslaved weekday."],
  ["print_owner", "Only owners and officials place notices at the printing office."],
];

const PI = [
  ["field_hand_young_man", "A young male field hand, missing a few days, owner of moderate means"],
  ["skilled_cooper", "A Creole cooper, highly skilled, missing"],
  ["boatman", "A hired-out boatman"],
  ["woman_domestic", "A woman in the house, missing"],
  ["after_week", "Anyone still missing after a week"],
];

function persist() {
  const all = store();
  all.rules = {};
  for (const [id] of RULES) {
    const row = document.querySelector(`[data-rule="${id}"]`);
    all.rules[id] = {
      verdict: [...row.querySelectorAll("button")].find((b) => b.getAttribute("aria-pressed") === "true")?.dataset.v || "",
      note: row.querySelector("input").value,
    };
  }
  all.map = {
    verdict: [...document.querySelectorAll("#map-btns button")].find((b) => b.getAttribute("aria-pressed") === "true")?.dataset.map || "",
    note: document.getElementById("map-note").value,
  };
  all.pi = {};
  for (const [id] of PI) {
    all.pi[id] = +document.getElementById("pi-" + id).value;
  }
  save(all);
}

function main() {
  const saved = store();
  const box = document.getElementById("rules");
  for (const [id, text] of RULES) {
    const rec = (saved.rules || {})[id] || {};
    const div = document.createElement("div");
    div.className = "rule";
    div.dataset.rule = id;
    div.innerHTML = `<div>${text}
        <input type="text" placeholder="Revise in a sentence" value="${(rec.note || "").replace(/"/g, "&quot;")}" style="width:100%;margin-top:6px">
      </div>
      <div class="rank" style="flex-direction:column">
        <button type="button" data-v="agree" aria-pressed="${rec.verdict === "agree"}">Agree</button>
        <button type="button" data-v="revise" aria-pressed="${rec.verdict === "revise"}">Revise</button>
        <button type="button" data-v="reject" aria-pressed="${rec.verdict === "reject"}">Reject</button>
      </div>`;
    box.appendChild(div);
  }
  const piBox = document.getElementById("pi");
  for (const [id, lab] of PI) {
    const v = (saved.pi && saved.pi[id] != null) ? saved.pi[id] : 30;
    const row = document.createElement("label");
    row.className = "stack";
    row.innerHTML = `${lab}
      <input id="pi-${id}" type="range" min="0" max="100" value="${v}">
      <span class="hint"><span id="pi-lab-${id}">${v}</span>% of such cases advertised, as a rough prior</span>`;
    piBox.appendChild(row);
    row.querySelector("input").oninput = (e) => {
      document.getElementById("pi-lab-" + id).textContent = e.target.value;
      persist();
    };
  }
  if (saved.map) {
    document.getElementById("map-note").value = saved.map.note || "";
    for (const b of document.querySelectorAll("#map-btns button")) {
      b.setAttribute("aria-pressed", b.dataset.map === saved.map.verdict);
    }
  }
  document.getElementById("map-note").onchange = persist;
  for (const b of document.querySelectorAll("#map-btns button")) {
    b.onclick = () => {
      for (const x of document.querySelectorAll("#map-btns button")) x.setAttribute("aria-pressed", "false");
      b.setAttribute("aria-pressed", "true");
      persist();
    };
  }
  for (const row of document.querySelectorAll("[data-rule]")) {
    for (const b of row.querySelectorAll("button")) {
      b.onclick = () => {
        for (const x of row.querySelectorAll("button")) x.setAttribute("aria-pressed", "false");
        b.setAttribute("aria-pressed", "true");
        persist();
      };
    }
    row.querySelector("input").onchange = persist;
  }
}

document.addEventListener("DOMContentLoaded", main);
