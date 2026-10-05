"use strict";

async function main() {
  const people = await (await fetch("data/personas.json")).json();
  const box = document.getElementById("list");
  const saved = store().personas || {};
  for (const p of people) {
    const rec = saved[p.id] || {};
    const art = document.createElement("article");
    art.className = "item";
    art.innerHTML = `
      <h3>${p.name} · ${p.age}, ${p.occupation}</h3>
      <div class="where">Legal status in the sandbox: ${p.status} · ${p.home.replace("_", " ")} · ${p.sex === "F" ? "female" : "male"}</div>
      <p>${p.persona}</p>
      <div class="rank">
        <button type="button" data-v="ok" aria-pressed="${rec.verdict === "ok"}">Fine</button>
        <button type="button" data-v="named" aria-pressed="${rec.verdict === "named"}">Too close to a documented person</button>
        <button type="button" data-v="off" aria-pressed="${rec.verdict === "off"}">Historically off</button>
      </div>
      <label class="stack">Who they resemble, or what is off
        <input type="text" value="${(rec.note || "").replace(/"/g, "&quot;")}">
      </label>`;
    const persist = () => {
      const all = store();
      all.personas = all.personas || {};
      all.personas[p.id] = {
        verdict: [...art.querySelectorAll("[data-v]")].find((b) => b.getAttribute("aria-pressed") === "true")?.dataset.v || "",
        note: art.querySelector("input").value,
        name: p.name,
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
  document.getElementById("list").textContent = "Could not load personas. " + err.message;
});
