// apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue_list.js

frappe.listview_settings["SRI XML Queue"] = {
  get_indicator(doc) {
    const s = (doc.state || "").trim();
    const colors = {
      "En Cola":               "dark",
      "Firmando":              "purple",
      "Listo para Transmitir": "blue",
      "Transmitido":           "orange",
      "Aceptado":              "green",
      "Rechazado":             "red",
      "Fallido":               "red",
      "Cancelado":             "gray",
    };
    const color = colors[s] || "gray";
    return [__(s || "Desconocido"), color, "state,=," + s];
  },

  onload(listview) {
    if (!frappe.user_roles.includes("FE Admin")) return;

    // Bulk Action 1: En Cola → Firmando
    listview.page.add_action_item(__("→ Firmando"), () => {
      const selected = listview.get_checked_items();
      if (!selected.length) return frappe.msgprint(__("Select at least one row."));
      const names = selected.map(d => d.name);

      frappe.confirm(
        __(`Move ${names.length} item(s) to "Firmando"?`),
        async () => {
          frappe.show_progress(__("Updating"), 0, names.length);
          let done = 0, failures = [];
          for (const n of names) {
            try {
              await frappe.call({
                method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.transition",
                args: { name: n, to_state: "Firmando" },
              });
              frappe.show_progress(__("Updating"), ++done, names.length);
            } catch (e) { failures.push(`${n}: ${e.message || e}`); }
          }
          frappe.hide_progress();
          if (failures.length) {
            frappe.msgprint(__("Some items failed:") + "<br>" + failures.join("<br>"));
          } else {
            frappe.show_alert({ message: __("Updated successfully"), indicator: "green" });
          }
          listview.refresh();
        }
      );
    });

    // Bulk Action 2: Firmando → Listo para Transmitir
    listview.page.add_action_item(__("→ Listo para Transmitir"), () => {
      const selected = listview.get_checked_items();
      if (!selected.length) return frappe.msgprint(__("Select at least one row."));
      const names = selected.map(d => d.name);

      frappe.confirm(
        __(`Move ${names.length} item(s) to "Listo para Transmitir"?`),
        async () => {
          frappe.show_progress(__("Updating"), 0, names.length);
          let done = 0, failures = [];
          for (const n of names) {
            try {
              await frappe.call({
                method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.transition",
                args: { name: n, to_state: "Listo para Transmitir" },
              });
              frappe.show_progress(__("Updating"), ++done, names.length);
            } catch (e) { failures.push(`${n}: ${e.message || e}`); }
          }
          frappe.hide_progress();
          if (failures.length) {
            frappe.msgprint(__("Some items failed:") + "<br>" + failures.join("<br>"));
          } else {
            frappe.show_alert({ message: __("Updated successfully"), indicator: "green" });
          }
          listview.refresh();
        }
      );
    });



// === Paint + Auto-fit widths for ID, Estado, and Invoice (rows + headers) ===
(function decorateCols() {
  const root = listview.$result && listview.$result[0];
  if (!root) return;

  function autoFitCell(cell, min, max, color) {
    cell.style.flex = "0 0 auto";
    cell.style.width = "auto";
    cell.style.minWidth = min + "px";
    cell.style.maxWidth = max + "px";
    cell.style.whiteSpace = "nowrap";
    cell.style.overflow = "hidden";
    cell.style.textOverflow = "ellipsis";
    if (color) {
      cell.style.background = color;   // paint for debug
      cell.style.outline = `1px solid ${color}`; // border so header & rows are obvious
    }
  }

  const apply = () => {
    // === ID column (rows + header) ===
    root.querySelectorAll('.list-row-col.list-subject').forEach(c => {
      autoFitCell(c, 185, 200,)// "rgba(255,0,0,0.15)"); si quieres color quitas los slash
    });
    root.querySelectorAll('.list-row-head .list-row-col.list-subject').forEach(c => {
      autoFitCell(c, 185, 200,)//, "rgba(255,0,0,0.3)"); si quieres color quitas los slash
    });

    // === Estado column (rows + header) ===
    root.querySelectorAll('.list-row-col .indicator-pill[data-filter^="state"]').forEach(c => {
      const cell = c.closest('.list-row-col');
      if (cell) autoFitCell(cell, 100, 160,)// "rgba(0,0,255,0.15)"); si quieres color quitas los slash
    });
    root.querySelectorAll('.list-row-head .list-row-col span').forEach(span => {
      if (span.textContent.trim() === "Status") {
        const cell = span.closest('.list-row-col');
        if (cell) autoFitCell(cell, 100, 160,)// "rgba(0,0,255,0.3)"); si quieres color quitas los slash
      }
    });

    // === Sales Invoice column (rows + header) ===
    root.querySelectorAll('.list-row-col .filterable[data-filter^="sales_invoice"]').forEach(c => {
      const cell = c.closest('.list-row-col');
      if (cell) autoFitCell(cell, 155, 165,)// "rgba(0,255,0,0.15)"); si quieres color quitas los slash
    });
    root.querySelectorAll('.list-row-head .list-row-col span[data-sort-by="sales_invoice"]').forEach(span => {
      const cell = span.closest('.list-row-col');
      if (cell) autoFitCell(cell, 155, 165, )//"rgba(0,255,0,0.3)"); si quieres color quitas los slash
    });
  };


  apply();
  if (!root.__josObserver) {
    const mo = new MutationObserver(() => apply());
    mo.observe(root, { childList: true, subtree: true });
    root.__josObserver = mo;
  }
})();



    // ---- Cumulative letter badges ----
    inject_cumulative_badge_css_once();

    const container = listview.$result && listview.$result[0];
    if (!container) return;

    const decorate = () => {
      const pills = container.querySelectorAll('.indicator-pill .ellipsis, .indicator-pill');
      pills.forEach(el => {
        const node = el.classList.contains('ellipsis') ? el : el;
        const stateText = (node.textContent || "").trim();
        const steps = compute_steps(stateText);
        if (!steps || !steps.length) return;
        if (node.dataset && node.dataset.josDecorated === "1") return;

        const wrap = document.createElement('span');
        wrap.className = 'jos-step-badges';
        wrap.setAttribute('aria-label', stateText);

        steps.forEach((letter, idx) => {
          const b = document.createElement('span');
          b.className = 'jos-letter-circle idx-' + (idx + 1);
          b.textContent = letter;
          wrap.appendChild(b);
        });

        node.textContent = "";
        node.appendChild(wrap);
        node.dataset.josDecorated = "1";
      });
    };

    decorate();
    const mo = new MutationObserver(() => decorate());
    mo.observe(container, { childList: true, subtree: true });
  },
};

function compute_steps(state_label) {
  const s = (state_label || "").toLowerCase();
  const base = ["G","F","E","V"];
  if (s.startsWith("en cola"))                   return base.slice(0, 1);
  if (s.startsWith("firmando"))                  return base.slice(0, 2);
  if (s.startsWith("listo para transmitir"))     return base.slice(0, 3);
  if (s.startsWith("transmitido"))               return base.slice(0, 4);
  if (s.startsWith("aceptado"))                  return base.concat(["A"]);
  if (s.startsWith("rechazado"))                 return base.concat(["R"]);
  if (s.startsWith("fallido"))                   return base.concat(["F"]);
  if (s.startsWith("cancelado"))                 return base.concat(["C"]);
  return null;
}

function inject_cumulative_badge_css_once() {
  const ID = "josfe-sri-cumulative-green-badges-css";
  if (document.getElementById(ID)) return;

  const css = `
  :root {
    --jos-badge-sizeW: 25px;
    --jos-badge-sizeH: 16px;
    --jos-badge-gap:  4px;
    --jos-font-size:  12px;
    --jos-font-weight: 700;
    --jos-radius:     9px;

    /* Green scale from light (#99dfb7) to darkest (#165825ff) */
    --jos-green-1: #99dfb7;
    --jos-green-2: #66c08f;
    --jos-green-3: #3da66d;
    --jos-green-4: #23734a;
    --jos-green-5: #165825ff;
  }

  .indicator-pill .jos-step-badges {
    display: inline-flex; align-items: center; gap: var(--jos-badge-gap);
  }
  .indicator-pill .jos-letter-circle {
    display: inline-flex;
    align-items: center; justify-content: center;
    width: var(--jos-badge-sizeW); height: var(--jos-badge-sizeH);
    border-radius: var(--jos-radius);
    font-size: var(--jos-font-size);
    font-weight: var(--jos-font-weight);
    line-height: 1; text-transform: uppercase;
    user-select: none;
  }
  /* Shades by position */
  .indicator-pill .jos-letter-circle.idx-1 { background: var(--jos-green-1);color: #31b67cff;}
  .indicator-pill .jos-letter-circle.idx-2 { background: var(--jos-green-2);color: #fff;}
  .indicator-pill .jos-letter-circle.idx-3 { background: var(--jos-green-3);color: #fff;}
  .indicator-pill .jos-letter-circle.idx-4 { background: var(--jos-green-4);color: #fff;}
  .indicator-pill .jos-letter-circle.idx-5 { background: var(--jos-green-5);color: #fff;}
  `;

  const st = document.createElement("style");
  st.id = ID;
  st.type = "text/css";
  st.appendChild(document.createTextNode(css));
  document.head.appendChild(st);
}
