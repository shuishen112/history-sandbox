"use strict";

const TYPES = [
  {
    id: "runaway",
    title: "Runaway / absence notice",
    blurb: "An owner advertises that someone is missing, often with a description and a suspected destination.",
    fields: [
      ["sex", "Sex as stated"],
      ["age", "Stated age"],
      ["occupation", "Occupation or skill"],
      ["languages", "Languages mentioned"],
      ["estate", "Estate or owner named"],
      ["date_absent", "Date last seen / date of the notice"],
      ["suspected_destination", "Suspected destination (the advertiser’s suspicion, not a fact)"],
      ["reward", "Reward offered"],
    ],
  },
  {
    id: "sale",
    title: "Sale or auction notice",
    blurb: "People, or a gang, offered for sale or at vendue.",
    fields: [
      ["n_persons", "How many people"],
      ["sex_mix", "Men / women / children as stated"],
      ["estate", "Estate or seller"],
      ["date", "Date of sale"],
      ["kind", "Private sale, auction, or sheriff’s sale"],
    ],
  },
  {
    id: "recapture",
    title: "Recapture or jail notice",
    blurb: "Someone taken up and lodged in the fort or jail, to be claimed.",
    fields: [
      ["sex", "Sex as stated"],
      ["age", "Stated age"],
      ["jail", "Fort / jail named"],
      ["date", "Date"],
      ["claimed_by", "Who is asked to claim the person"],
    ],
  },
  {
    id: "manumission",
    title: "Manumission notice",
    blurb: "A person is legally freed, or free papers are announced.",
    fields: [
      ["name_type", "How the person is named (given name, byname)"],
      ["sex", "Sex as stated"],
      ["date", "Date"],
      ["by", "By owner, by self-purchase, or by will — if stated"],
    ],
  },
  {
    id: "ordinance",
    title: "Ordinance or proclamation",
    blurb: "A government rule: passes, patrols, market days, curfews, militia.",
    fields: [
      ["topic", "What the rule is about"],
      ["date", "Date"],
      ["jurisdiction", "Island / town / fort"],
      ["constraint", "What people are required or forbidden to do"],
    ],
  },
  {
    id: "shipping",
    title: "Shipping news",
    blurb: "A vessel arrived or sailed: sloop, brig, schooner, port, date.",
    fields: [
      ["vessel", "Name of the vessel if given"],
      ["type", "Sloop / brig / schooner / other"],
      ["arrival_or_departure", "Arrived or sailed"],
      ["port", "Port or destination"],
      ["date", "Date"],
    ],
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
      <p class="hint">Fields we currently extract: ${t.fields.map((f) => f[1]).join("; ")}.</p>
      <div class="rank">
        <span>This kind of notice:</span>
        <button type="button" data-v="keep" aria-pressed="${rec.verdict === "keep"}">Keep</button>
        <button type="button" data-v="change" aria-pressed="${rec.verdict === "change"}">Change</button>
        <button type="button" data-v="drop" aria-pressed="${rec.verdict === "drop"}">Drop</button>
      </div>
      <label class="stack">Note (missing field, wrong name, split this type, …)
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
