frappe.listview_settings["SRI XML Queue"] = {
  get_indicator(doc) {
    const s = (doc.state || "").trim();
    const colors = {
      "En Cola": "dark",
      "Firmando": "purple",
      "Listo para Transmitir": "blue",
      "Transmitido": "orange",
      "Aceptado": "green",
      "Rechazado": "red",
      "Fallido": "red",
      "Cancelado": "gray",
    };
    const color = colors[s] || "gray";
    return [__(s || "Desconocido"), color, "state,=," + s];
  },

  onload(listview) {
    if (!frappe.user_roles.includes("FE Admin")) return;

    // hide "+ Add SRI XML Queue" and default "Actions" dropdown
    const addBtn = document.querySelector(
      'button.primary-action[data-label^="Add SRI XML Queue"]'
    );
    if (addBtn) addBtn.style.display = "none";
    const actionsGroup = document.querySelector(".actions-btn-group");
    if (actionsGroup) actionsGroup.style.display = "none";

    const toolbar = document.querySelector(
      ".flex.col.page-actions .standard-actions"
    );

    function clear_transition_buttons() {
      toolbar?.querySelectorAll(".jos-transition-btn").forEach((b) => b.remove());
    }

    function deselect_and_refresh() {
      try {
        listview.$result
          .find('input.list-row-checkbox:checked')
          .prop("checked", false)
          .trigger("change");
      } catch (_) {}
      listview.refresh();
      frappe.after_ajax(() => {
        refresh_buttons();
      });
    }

    async function refresh_buttons() {
      clear_transition_buttons();

      const selected = listview.get_checked_items();
      if (!selected.length) return;

      const first_state = (selected[0].state || "").trim();
      const same_state = selected.every(
        (d) => (d.state || "").trim() === first_state
      );
      if (!same_state) return;

      let r = await frappe.call({
        method:
          "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.get_allowed_transitions",
        args: { name: selected[0].name },
      });
      const transitions = r.message || [];
      if (!transitions.length) return;

      transitions.forEach((to_state) => {
        const btn = document.createElement("button");
        btn.className = "btn btn-sm btn-primary jos-transition-btn";
        btn.innerText = "→ " + to_state;
        btn.onclick = async () => {
          frappe.show_alert({ message: __("Actualizando…"), indicator: "blue" });
          let failures = [];
          for (const n of selected.map((d) => d.name)) {
            try {
              await frappe.call({
                method:
                  "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.transition",
                args: { name: n, to_state: to_state },
              });
            } catch (e) {
              failures.push(`${n}: ${e.message || e}`);
            }
          }
          if (failures.length) {
            frappe.msgprint(__("Fallaron:") + "<br>" + failures.join("<br>"));
          } else {
            frappe.show_alert({
              message: __("Actualizado correctamente"),
              indicator: "green",
            });
          }
          deselect_and_refresh();
        };
        toolbar?.appendChild(btn);
      });
    }

    // selection watcher
    listview.$result.on("change", "input.list-row-checkbox", () => {
      refresh_buttons();
    });

    // === Auto-fit widths ===
    (function decorateCols() {
      const root = listview.$result && listview.$result[0];
      if (!root) return;

      function autoFitCell(cell, min, max) {
        cell.style.flex = "0 0 auto";
        cell.style.width = "auto";
        cell.style.minWidth = min + "px";
        cell.style.maxWidth = max + "px";
        cell.style.whiteSpace = "nowrap";
        cell.style.overflow = "hidden";
        cell.style.textOverflow = "ellipsis";
      }

      const apply = () => {
        root
          .querySelectorAll(".list-row-col.list-subject")
          .forEach((c) => autoFitCell(c, 185, 200));
        root
          .querySelectorAll(".list-row-head .list-row-col.list-subject")
          .forEach((c) => autoFitCell(c, 185, 200));
        root
          .querySelectorAll(
            '.list-row-col .indicator-pill[data-filter^="state"]'
          )
          .forEach((c) => {
            const cell = c.closest(".list-row-col");
            if (cell) autoFitCell(cell, 100, 160);
          });
        root
          .querySelectorAll(".list-row-head .list-row-col span")
          .forEach((span) => {
            if (span.textContent.trim() === "Status") {
              const cell = span.closest(".list-row-col");
              if (cell) autoFitCell(cell, 100, 160);
            }
          });
        root
          .querySelectorAll(
            '.list-row-col .filterable[data-filter^="sales_invoice"]'
          )
          .forEach((c) => {
            const cell = c.closest(".list-row-col");
            if (cell) autoFitCell(cell, 155, 165);
          });
        root
          .querySelectorAll(
            '.list-row-head .list-row-col span[data-sort-by="sales_invoice"]'
          )
          .forEach((span) => {
            const cell = span.closest(".list-row-col");
            if (cell) autoFitCell(cell, 155, 165);
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
      const pills = container.querySelectorAll(
        ".indicator-pill .ellipsis, .indicator-pill"
      );
      pills.forEach((el) => {
        const node = el;
        const stateText = (node.textContent || "").trim();
        const steps = compute_steps(stateText);
        if (!steps || !steps.length) return;
        if (node.dataset && node.dataset.josDecorated === "1") return;

        const wrap = document.createElement("span");
        wrap.className = "jos-step-badges";
        wrap.setAttribute("aria-label", stateText);

        steps.forEach((letter, idx) => {
          const b = document.createElement("span");
          b.className = "jos-letter-circle idx-" + (idx + 1);
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
  const base = ["G", "F", "E", "V"];
  if (s.startsWith("en cola")) return base.slice(0, 1);
  if (s.startsWith("firmando")) return base.slice(0, 2);
  if (s.startsWith("listo para transmitir")) return base.slice(0, 3);
  if (s.startsWith("transmitido")) return base.slice(0, 4);
  if (s.startsWith("aceptado")) return base.concat(["A"]);
  if (s.startsWith("rechazado")) return base.concat(["R"]);
  if (s.startsWith("fallido")) return base.concat(["F"]);
  if (s.startsWith("cancelado")) return base.concat(["C"]);
  return null;
}

function inject_cumulative_badge_css_once() {
  const ID = "josfe-sri-cumulative-green-badges-css";
  if (document.getElementById(ID)) return;

  const css = `
  .jos-transition-btn { margin-left: 6px; }
  :root {
    --jos-badge-sizeW: 25px;
    --jos-badge-sizeH: 16px;
    --jos-badge-gap:  4px;
    --jos-font-size:  12px;
    --jos-font-weight: 700;
    --jos-radius:     9px;
    --jos-green-1: #e1cc0eff;
    --jos-green-2: #ecac67ff;
    --jos-green-3: #3073e8ff;
    --jos-green-4: #9c2becff;
    --jos-green-5: #0d942cff;
  }
  .indicator-pill .jos-step-badges { display: inline-flex; align-items: center; gap: var(--jos-badge-gap); }
  .indicator-pill .jos-letter-circle {
    display: inline-flex; align-items: center; justify-content: center;
    width: var(--jos-badge-sizeW); height: var(--jos-badge-sizeH);
    border-radius: var(--jos-radius); font-size: var(--jos-font-size); font-weight: var(--jos-font-weight);
    line-height: 1; text-transform: uppercase; user-select: none;
  }
  .indicator-pill .jos-letter-circle.idx-1 { background: var(--jos-green-1);color: #fff788ff;}
  .indicator-pill .jos-letter-circle.idx-2 { background: var(--jos-green-2);color: #eaf4f4ff;}
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
