"use strict";

const RULES = [
  ["recognition", "A member or minister may speak on the floor only after the Voorzitter has given them the floor."],
  ["journalist", "A journalist may observe from the press gallery and must not take the floor or enter the Handelingen as a speaker."],
  ["corridor", "Talk in the wandelgang is not written into the Handelingen, even if it later appears in a newspaper."],
  ["chair_opens", "Only the Chair opens and adjourns a sitting; sittings are weekday daytime institutions in this slice."],
  ["stenographer", "The stenographer records recognised floor speech and the Chair’s rulings, not asides or unrecognised interruptions."],
  ["no_possess", "Researchers may inspect and interview; they may not play a minister or the Chair."],
  ["public_only", "Agents are public office-holders. The sandbox must not invent families, interiors, or unrecorded private lives."],
  ["leak", "A corridor leak can spread by rumour; it should appear in the official record only if someone alludes to it after recognition."],
];

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function yn(name, value) {
  return ["yes", "uncertain", "no"].map((v) =>
    `<button type="button" data-k="${name}" data-v="${v}" aria-pressed="${value === v}">${v}</button>`
  ).join("");
}

function persistRules() {
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
  save(all);
}

function persistClip(art, it) {
  const all = store();
  all.procedure = all.procedure || {};
  const pick = (k) => [...art.querySelectorAll(`[data-k="${k}"]`)].find((b) => b.getAttribute("aria-pressed") === "true")?.dataset.v || "";
  all.procedure[it.id] = {
    in_order: pick("in_order"),
    on_record: pick("on_record"),
    anachronism: pick("anachronism"),
    note: art.querySelector("textarea").value,
    hidden: it.hidden,
    source: it.source,
    catch: !!it.catch,
  };
  save(all);
}

async function main() {
  const saved = store();
  const box = document.getElementById("rules");
  for (const [id, text] of RULES) {
    const rec = (saved.rules || {})[id] || {};
    const div = document.createElement("div");
    div.className = "rule";
    div.dataset.rule = id;
    div.innerHTML = `<div>${text}
        <input type="text" placeholder="Revise in a sentence" value="${esc(rec.note || "")}" style="width:100%;margin-top:6px">
      </div>
      <div class="rank" style="flex-direction:column">
        <button type="button" data-v="agree" aria-pressed="${rec.verdict === "agree"}">Agree</button>
        <button type="button" data-v="revise" aria-pressed="${rec.verdict === "revise"}">Revise</button>
        <button type="button" data-v="reject" aria-pressed="${rec.verdict === "reject"}">Reject</button>
      </div>`;
    box.appendChild(div);
  }
  if (saved.map) {
    document.getElementById("map-note").value = saved.map.note || "";
    for (const b of document.querySelectorAll("#map-btns button")) {
      b.setAttribute("aria-pressed", b.dataset.map === saved.map.verdict);
    }
  }
  document.getElementById("map-note").onchange = persistRules;
  for (const b of document.querySelectorAll("#map-btns button")) {
    b.onclick = () => {
      for (const x of document.querySelectorAll("#map-btns button")) x.setAttribute("aria-pressed", "false");
      b.setAttribute("aria-pressed", "true");
      persistRules();
    };
  }
  for (const row of document.querySelectorAll("[data-rule]")) {
    for (const b of row.querySelectorAll("button")) {
      b.onclick = () => {
        for (const x of row.querySelectorAll("button")) x.setAttribute("aria-pressed", "false");
        b.setAttribute("aria-pressed", "true");
        persistRules();
      };
    }
    row.querySelector("input").onchange = persistRules;
  }

  const pack = await (await fetch("data/procedure.json")).json();
  const clips = pack.items || [];
  const clipBox = document.getElementById("clips");
  const done = saved.procedure || {};
  for (const it of clips) {
    const rec = done[it.id] || {};
    const art = document.createElement("article");
    art.className = "item";
    art.innerHTML = `
      <h3><span class="badge">${esc(it.actor_role)}</span> ${esc(it.action)}</h3>
      <div class="where">${esc(it.setting)}</div>
      <div class="excerpt">${esc(it.text)}</div>
      <div class="rank"><span>Chair would have allowed this?</span>${yn("in_order", rec.in_order)}</div>
      <div class="rank"><span>Stenographer would have recorded it?</span>${yn("on_record", rec.on_record)}</div>
      <div class="rank"><span>Anachronism?</span>${yn("anachronism", rec.anachronism)}</div>
      <label class="stack">Note
        <textarea rows="2">${esc(rec.note || "")}</textarea>
      </label>`;
    const saveOne = () => persistClip(art, it);
    for (const btn of art.querySelectorAll("button[data-k]")) {
      btn.onclick = () => {
        const k = btn.dataset.k;
        for (const x of art.querySelectorAll(`[data-k="${k}"]`)) x.setAttribute("aria-pressed", "false");
        btn.setAttribute("aria-pressed", "true");
        saveOne();
      };
    }
    art.querySelector("textarea").onchange = saveOne;
    clipBox.appendChild(art);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  main().catch((err) => {
    document.getElementById("clips").textContent = "Could not load clips. " + err.message;
  });
});
