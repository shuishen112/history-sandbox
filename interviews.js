"use strict";

const BEL = [
  ["L", "Left more believable"],
  ["tie", "About the same"],
  ["R", "Right more believable"],
];
const HIS = [
  ["L", "Left more historically plausible"],
  ["tie", "About the same"],
  ["R", "Right more historically plausible"],
];

function buttons(name, options, value) {
  return options.map(([v, lab]) =>
    `<button type="button" data-k="${name}" data-v="${v}" aria-pressed="${value === v}">${lab}</button>`).join("");
}

async function main() {
  const pairs = await (await fetch("data/interviews.json")).json();
  const box = document.getElementById("list");
  const saved = store().interviews || {};

  function progress() {
    const d = Object.keys(store().interviews || {}).length;
    document.getElementById("prog-text").textContent = `${d} of ${pairs.length} pairs ranked`;
    document.getElementById("prog-bar").style.width = (pairs.length ? (100 * d) / pairs.length : 0) + "%";
  }

  for (const p of pairs) {
    const rec = saved[p.id] || {};
    const art = document.createElement("article");
    art.className = "item";
    art.innerHTML = `
      <h3>${p.name} · ${p.status}</h3>
      <p><b>Question.</b> ${p.question}</p>
      <div class="pair">
        <div class="answer"><b>Left</b><p>${p.left.text}</p></div>
        <div class="answer"><b>Right</b><p>${p.right.text}</p></div>
      </div>
      <div class="rank"><span>Believability:</span>${buttons("bel", BEL, rec.bel)}</div>
      <div class="rank"><span>Historical plausibility:</span>${buttons("hist", HIS, rec.hist)}</div>
      <label class="stack">Optional reference answer (what a careful historian would write from this person’s situation)
        <textarea rows="3">${rec.ref || ""}</textarea>
      </label>`;
    const persist = () => {
      const all = store();
      all.interviews = all.interviews || {};
      const pick = (k) => [...art.querySelectorAll(`[data-k="${k}"]`)].find((b) => b.getAttribute("aria-pressed") === "true")?.dataset.v || "";
      all.interviews[p.id] = {
        bel: pick("bel"),
        hist: pick("hist"),
        ref: art.querySelector("textarea").value,
        left: p.left.hidden,
        right: p.right.hidden,
        category: p.category,
        agent_id: p.agent_id,
      };
      save(all);
      progress();
    };
    for (const btn of art.querySelectorAll("button[data-k]")) {
      btn.onclick = () => {
        const k = btn.dataset.k;
        const on = btn.getAttribute("aria-pressed") === "true";
        for (const x of art.querySelectorAll(`[data-k="${k}"]`)) x.setAttribute("aria-pressed", "false");
        if (!on) btn.setAttribute("aria-pressed", "true");
        persist();
      };
    }
    art.querySelector("textarea").onchange = persist;
    box.appendChild(art);
  }
  progress();
}

main().catch((err) => {
  document.getElementById("list").textContent = "Could not load conversations. " + err.message;
});
