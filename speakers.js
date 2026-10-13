"use strict";

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function prettyDate(iso) {
  if (!iso) return "";
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return iso;
  const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  return `${+m[3]} ${months[+m[2] - 1]} ${m[1]}`;
}

function yn(name, value) {
  return ["yes", "uncertain", "no"].map((v) =>
    `<button type="button" data-k="${name}" data-v="${v}" aria-pressed="${value === v}">${v}</button>`
  ).join("");
}

async function main() {
  const pack = await (await fetch("data/speakers.json")).json();
  const items = pack.items || pack;
  const box = document.getElementById("list");
  const filter = document.getElementById("filter");

  function labelled() {
    return store().speakers || {};
  }

  function progress() {
    const d = Object.keys(labelled()).length;
    document.getElementById("prog-text").textContent = `${d} of ${items.length} cards reviewed`;
    document.getElementById("prog-bar").style.width = (items.length ? (100 * d) / items.length : 0) + "%";
  }

  function persist(art, it) {
    const all = store();
    all.speakers = all.speakers || {};
    const pick = (k) => [...art.querySelectorAll(`[data-k="${k}"]`)].find((b) => b.getAttribute("aria-pressed") === "true")?.dataset.v || "";
    all.speakers[it.id] = {
      name: it.name,
      name_ok: pick("name_ok"),
      role_ok: pick("role_ok"),
      party_ok: pick("party_ok"),
      attested: pick("attested"),
      ocr: pick("ocr"),
      corrected_name: art.querySelector("[data-field=corrected]").value,
      note: art.querySelector("textarea").value,
      suggested_role: it.suggested_role,
      identifiers: (it.excerpts || []).map((e) => (typeof e === "object" && e ? e.identifier : "")).filter(Boolean),
      dates: (it.excerpts || []).map((e) => (typeof e === "object" && e ? e.date : "")).filter(Boolean),
      synthetic: !!it.synthetic,
      catch: !!it.catch,
    };
    save(all);
    progress();
  }

  function render() {
    const saved = labelled();
    const mode = filter.value;
    box.innerHTML = "";
    for (const it of items) {
      const rec = saved[it.id] || {};
      const done = !!(rec.name_ok && rec.role_ok && rec.attested);
      if (mode === "todo" && done) continue;
      if (mode === "done" && !done) continue;
      const art = document.createElement("article");
      art.className = "item";
      const excerpts = (it.excerpts || []).map((e) => {
        const rec = typeof e === "string" ? { text: e } : (e || {});
        const ident = rec.identifier || "";
        const url = rec.url || (ident ? `https://zoek.officielebekendmakingen.nl/${ident}` : "");
        const src = rec.source ? rec.source.replace(/\.xml$/i, "") : "";
        const when = prettyDate(rec.date);
        const meta = [
          when ? `<span class="badge">${esc(when)}</span>` : "",
          url ? `Original PDF: <a href="${esc(url)}" target="_blank" rel="noopener">${esc(ident)}</a>` : "",
          src ? `<span class="hint">${esc(src)}</span>` : "",
        ].filter(Boolean).join(" · ");
        const link = meta
          ? `<p class="source">${meta}</p>`
          : (it.synthetic ? `<p class="hint">No Officiële Bekendmakingen record (synthetic card).</p>` : "");
        return `<div class="excerpt">${esc(rec.text || "")}${link}</div>`;
      }).join("");
      art.innerHTML = `
        <h3>${esc(it.name)} · <span class="badge">${esc(it.suggested_role)}</span>
          <span class="badge">${esc(it.suggested_function || "")}</span>
          <span class="badge">${esc(it.party_label || "no party")}</span></h3>
        <div class="where">${esc(it.house)} · ${it.n_speeches} speeches in the slice
          ${(() => {
            const ds = (it.excerpts || []).map((e) => e && e.date).filter(Boolean);
            if (!ds.length) return "";
            const a = prettyDate(ds[0]);
            const b = prettyDate(ds[ds.length - 1]);
            return " · sittings " + esc(a === b ? a : a + " – " + b);
          })()}
          ${it.member_ref ? " · " + esc(it.member_ref) : ""}
          ${it.synthetic ? " · <b>computer-seeded card</b>" : ""}</div>
        ${excerpts || "<p class='hint'>No excerpt.</p>"}
        <div class="rank"><span>Name correctly read, real office-holder?</span>${yn("name_ok", rec.name_ok)}</div>
        <label class="stack">Corrected name
          <input type="text" data-field="corrected" value="${esc(rec.corrected_name || "")}">
        </label>
        <div class="rank"><span>Suggested role fits the excerpt?</span>${yn("role_ok", rec.role_ok)}</div>
        <div class="rank"><span>Party label accurate <em>on these sitting dates</em> (or rightly empty)? MPs sometimes switched.</span>${yn("party_ok", rec.party_ok)}</div>
        <div class="rank"><span>May we seed an agent from this card?</span>${yn("attested", rec.attested)}</div>
        <div class="rank"><span>OCR quality (1 unreadable – 5 clean)</span>${
          [1, 2, 3, 4, 5].map((n) =>
            `<button type="button" data-k="ocr" data-v="${n}" aria-pressed="${String(rec.ocr) === String(n)}">${n}</button>`
          ).join("")
        }</div>
        <label class="stack">Note
          <textarea rows="2">${esc(rec.note || "")}</textarea>
        </label>`;
      const saveOne = () => persist(art, it);
      for (const btn of art.querySelectorAll("button[data-k]")) {
        btn.onclick = () => {
          const k = btn.dataset.k;
          const on = btn.getAttribute("aria-pressed") === "true" && btn.dataset.v === btn.dataset.v;
          for (const x of art.querySelectorAll(`[data-k="${k}"]`)) x.setAttribute("aria-pressed", "false");
          btn.setAttribute("aria-pressed", "true");
          saveOne();
        };
      }
      art.querySelector("input").onchange = saveOne;
      art.querySelector("textarea").onchange = saveOne;
      box.appendChild(art);
    }
    progress();
  }

  filter.onchange = render;
  render();
}

main().catch((err) => {
  document.getElementById("list").textContent = "Could not load names. " + err.message;
});
