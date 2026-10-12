"use strict";

const TYPES = [
  {
    id: "attested_speaker",
    title: "Attested speaker card",
    blurb: "A person who actually speaks in the 1896–1899 Tweede Kamer XML: name, role, function, party-ref, member-ref, and up to three short excerpts.",
    fields: [
      ["name", "Printed speaker name (OCR)"],
      ["role", "pm:role — chair / mp / government"],
      ["function", "pm:function (voorzitter, minister van …, De heer)"],
      ["party", "pm:party-ref, often empty"],
      ["member_ref", "pm:member-ref when the file has one"],
      ["excerpts", "Short on-record passages, not a biography"],
    ],
  },
  {
    id: "chair",
    title: "Role: Voorzitter",
    blurb: "Opens and adjourns, recognises speakers, does not debate the substance. One chair in the S1 cast.",
    fields: [["home", "chair_dais"], ["may_speak", "Always, as chair"], ["on_record", "Yes"]],
  },
  {
    id: "mp",
    title: "Role: Kamerlid",
    blurb: "Speaks on the floor only when recognised. May talk in the wandelgang off the record.",
    fields: [["home", "benches"], ["may_speak", "If recognised"], ["on_record", "Only recognised floor speech"]],
  },
  {
    id: "minister",
    title: "Role: Minister",
    blurb: "Government bench. Addresses the Chair. Not a private citizen in this sandbox.",
    fields: [["home", "ministers_bench"], ["may_speak", "If recognised or answering"], ["on_record", "Yes, when on the floor"]],
  },
  {
    id: "clerk",
    title: "Role: Griffier / stenographer (synthetic)",
    blurb: "Writes the Handelingen. We invented a clerk token; the XML names the function, not always a person we should dramatise.",
    fields: [["synthetic", "Yes"], ["may_speak", "No"], ["on_record", "Writes, does not orate"]],
  },
  {
    id: "journalist",
    title: "Role: journalist (synthetic, press gallery)",
    blurb: "Observes; never takes the floor. The archive has 0% journalist lines. Keep this as a nameless gallery role, not a historical reporter.",
    fields: [["synthetic", "Yes"], ["may_speak", "No"], ["on_record", "Never"]],
  },
];

function render() {
  const box = document.getElementById("types");
  const saved = store().schema || {};
  box.innerHTML = "";
  for (const t of TYPES) {
    const rec = saved[t.id] || {};
    const article = document.createElement("article");
    article.className = "item";
    article.innerHTML = `
      <h3>${t.title}</h3>
      <p>${t.blurb}</p>
      <p class="hint">Fields / facts we currently use: ${t.fields.map((f) => f[1]).join("; ")}.</p>
      <div class="rank">
        <span>This kind:</span>
        <button type="button" data-v="keep" aria-pressed="${rec.verdict === "keep"}">Keep</button>
        <button type="button" data-v="change" aria-pressed="${rec.verdict === "change"}">Change</button>
        <button type="button" data-v="drop" aria-pressed="${rec.verdict === "drop"}">Drop</button>
      </div>
      <label class="stack">Note (missing field, wrong role, split this type, …)
        <textarea rows="2">${rec.note || ""}</textarea>
      </label>`;
    const saveOne = () => {
      const all = store();
      all.schema = all.schema || {};
      all.schema[t.id] = {
        verdict: [...article.querySelectorAll("[data-v]")].find((b) => b.getAttribute("aria-pressed") === "true")?.dataset.v || "",
        note: article.querySelector("textarea").value,
      };
      save(all);
    };
    for (const btn of article.querySelectorAll("[data-v]")) {
      btn.onclick = () => {
        const on = btn.getAttribute("aria-pressed") === "true";
        for (const x of article.querySelectorAll("[data-v]")) x.setAttribute("aria-pressed", "false");
        if (!on) btn.setAttribute("aria-pressed", "true");
        saveOne();
      };
    }
    article.querySelector("textarea").onchange = saveOne;
    box.appendChild(article);
  }
}

document.addEventListener("DOMContentLoaded", render);
