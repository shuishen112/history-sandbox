"use strict";

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function main() {
  const people = await (await fetch("data/personas.json")).json();
  const box = document.getElementById("list");
  const saved = store().personas || {};
  for (const p of people) {
    const rec = saved[p.id] || {};
    const art = document.createElement("article");
    art.className = "item";
    const ex = (p.excerpts || []).slice(0, 1).map((e) => `<div class="excerpt">${esc(e)}</div>`).join("");
    art.innerHTML = `
      <h3>${esc(p.name)} · ${esc(p.status)}</h3>
      <div class="where">${p.synthetic ? "Synthetic role seed" : "Intended as an attested speaker"}
        ${p.member_ref ? " · " + esc(p.member_ref) : ""}
        ${p.party ? " · " + esc(p.party) : ""}</div>
      <p>${esc(p.persona)}</p>
      ${ex}
      <div class="rank">
        <button type="button" data-v="ok" aria-pressed="${rec.verdict === "ok"}">Fine</button>
        <button type="button" data-v="role_only" aria-pressed="${rec.verdict === "role_only"}">Keep the role, not the personal name</button>
        <button type="button" data-v="off" aria-pressed="${rec.verdict === "off"}">Historically off</button>
      </div>
      <label class="stack">What is off, or who they actually were
        <input type="text" value="${esc(rec.note || "")}">
      </label>`;
    const persist = () => {
      const all = store();
      all.personas = all.personas || {};
      all.personas[p.id] = {
        verdict: [...art.querySelectorAll("[data-v]")].find((b) => b.getAttribute("aria-pressed") === "true")?.dataset.v || "",
        note: art.querySelector("input").value,
        name: p.name,
        status: p.status,
        synthetic: !!p.synthetic,
      };
      save(all);
    };
    for (const btn of art.querySelectorAll("[data-v]")) {
      btn.onclick = () => {
        const on = btn.getAttribute("aria-pressed") === "true";
        for (const x of art.querySelectorAll("[data-v]")) x.setAttribute("aria-pressed", "false");
        if (!on) btn.setAttribute("aria-pressed", "true");
        persist();
      };
    }
    art.querySelector("input").onchange = persist;
    box.appendChild(art);
  }
}

main().catch((err) => {
  document.getElementById("list").textContent = "Could not load people. " + err.message;
});
