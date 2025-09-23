/* global frappe */

(() => {
  "use strict";

  // ---------- Helpers ----------
  function forceHideNamingSeries(frm) {
    const f = frm.get_field("naming_series");
    if (f) { f.df.hidden = 1; f.refresh(); }
  }

  function ensureSerieField(frm) {
    if (frm.fields_dict["custom_sri_serie"]) {
      frm.fields_dict["custom_sri_serie"].df.read_only = 1;
      frm.refresh_field("custom_sri_serie");
    }
  }

  function setInvoiceQuery(frm) {
    frm.set_query("source_invoice", () => ({
      query: "josfe.sri_invoicing.doctype.nota_credito_fe.nota_credito_fe.si_last_12mo",
      filters: {
        customer: frm.doc.customer || "",
        company: frm.doc.company || "",
        custom_jos_level3_warehouse: frm.doc.custom_jos_level3_warehouse || "",
        custom_jos_sri_emission_point_code: frm.doc.custom_jos_sri_emission_point_code || ""
      }
    }));
  }

  function normalizeEpCode(raw) {
    const s = (raw || "").trim();
    return s ? s.split(" - ", 1)[0].trim() : "";
  }

  // Load Emission Point options (Select) for current WH, optionally clearing current value.
  function maybe_load_pe_options(frm, clear) {
    const wh = frm.doc.custom_jos_level3_warehouse;
    const target = "custom_jos_sri_emission_point_code";
    if (!wh) {
      frm.set_df_property(target, "options", [""]);
      if (clear) frm.set_value(target, "");
      frm.refresh_field(target);
      return Promise.resolve([]);
    }
    return frappe.call({
      method: "josfe.sri_invoicing.core.numbering.state.list_active_emission_points",
      args: { warehouse_name: wh }
    }).then(r => {
      const rows = Array.isArray(r.message) ? r.message : [];
      const opts = rows.map(x => typeof x === "string" ? x : (x.code || x.name || x.value || "")).filter(Boolean);
      frm.set_df_property(target, "options", opts.length ? opts : [""]);
      const current = normalizeEpCode(frm.doc.custom_jos_sri_emission_point_code);
      if (clear || (current && !opts.includes(current))) {
        frm.set_value(target, opts[0] || "");
      }
      frm.refresh_field(target);
      return opts;
    });
  }

  async function copyNumberingFromSI(frm, siName) {
    if (!siName) return;
    const r = await frappe.db.get_doc("Sales Invoice", siName);
    const wh = r.custom_jos_level3_warehouse || "";
    const ep = normalizeEpCode(r.custom_jos_sri_emission_point_code);
    if (wh) await frm.set_value("custom_jos_level3_warehouse", wh);
    const opts = await maybe_load_pe_options(frm, true);
    if (ep) {
      const pick = opts.includes(ep) ? ep : (opts[0] || "");
      await frm.set_value("custom_jos_sri_emission_point_code", pick);
    }
    await paintSeriePreview(frm);
  }

  // ---------- Serie preview (throttled; new docs only) ----------
  let __seriePreviewReq = 0;
  async function paintSeriePreview(frm) {
    ensureSerieField(frm);
    if (!frm.is_new()) return;

    const myReq = ++__seriePreviewReq;
    const wh = frm.doc.custom_jos_level3_warehouse || "";
    const pe = normalizeEpCode(frm.doc.custom_jos_sri_emission_point_code || "");
    if (!wh || !pe) {
      frm.set_value("custom_sri_serie", "");
      return;
    }
    try {
      const r = await frappe.call({
        method: "josfe.sri_invoicing.core.numbering.state.peek_next_nc_series",
        // method: "josfe.sri_invoicing.core.numbering.serie_autoname.peek_next_nc_series",
        args: { doc_type: "NC",warehouse_name: wh, emission_point_code: pe }
      });
      if (myReq !== __seriePreviewReq) return;
      frm.set_value("custom_sri_serie", (r && r.message) || "");
    } catch (_) {
      // keep UI quiet; leave field blank if preview fails
    }
  }

  // ---------- Items loader ----------
  function loadItemsFromSource(frm, siName) {
    if (!siName) {
      frm.clear_table("return_items");
      frm.refresh_field("return_items");
      return Promise.resolve();
    }
    return frappe.call({
      method: "josfe.sri_invoicing.doctype.nota_credito_fe.nota_credito_fe.get_source_invoice_items",
      args: { source_invoice: siName }
    }).then(r => {
      const rows = (r && r.message) || [];
      frm.clear_table("return_items");
      rows.forEach(x => {
        const d = frm.add_child("return_items");
        d.item_code = x.item_code;
        d.item_name = x.item_name;
        d.uom = x.uom || "";
        d.orig_qty = x.orig_qty;   // Available to Return (remaining)
        d.return_qty = 0;
        d.rate = x.rate;
        d.amount = 0;
      });
      frm.refresh_field("return_items");
    });
  }

  // ---------- Grid guards ----------
  function enforceReturnRow(_frm, cdt, cdn) {
    const d = frappe.get_doc(cdt, cdn);
    const cap = Number(d.orig_qty) || 0;
    let rq = Number(d.return_qty) || 0;
    if (rq < 0) rq = -rq;
    if (rq > cap) {
      rq = cap;
      frappe.model.set_value(cdt, cdn, "return_qty", cap);
    }
    const rate = Number(d.rate) || 0;
    frappe.model.set_value(cdt, cdn, "amount", rq * rate);
  }

  function enforceFreeRow(_frm, cdt, cdn) {
    const d = frappe.get_doc(cdt, cdn);
    const qty = Number(d.qty) || 0;
    const rate = Number(d.rate) || 0;
    frappe.model.set_value(cdt, cdn, "amount", qty * rate);
  }

  function lockReturnItemsGrid(frm) {
    const grid = frm.get_field("return_items")?.grid;
    if (!grid) return;

    // Make all fields read-only except return_qty
    grid.docfields.forEach(df => {
      if (df.fieldname !== "return_qty") {
        df.read_only = 1;
      } else {
        df.read_only = 0; // allow editing only return_qty
      }
    });

  // Hide Add Row button
  if (grid.grid_buttons) {
    grid.grid_buttons.hide();
  }

  // Hide "trash" (delete row) buttons
  grid.wrapper.querySelectorAll('.grid-delete-row').forEach(btn => {
    btn.style.display = 'none';
  });

    grid.refresh();
  }

  // ---------- Form bindings ----------
  frappe.ui.form.on("Nota Credito FE", {
    setup(frm) {
      forceHideNamingSeries(frm);
      ensureSerieField(frm);
      setInvoiceQuery(frm);
    },

    // Mirror SI: bootstrap Warehouse from frappe.boot, then EP options.
    async onload(frm) {
      const wh = frappe.boot && frappe.boot.jos_selected_establishment;
      if (wh && !frm.doc.custom_jos_level3_warehouse) {
        await frm.set_value("custom_jos_level3_warehouse", wh);
        await maybe_load_pe_options(frm, true);
      }
    },

    async refresh(frm) {
      // Match SI: key fields read-only
      ["custom_jos_level3_warehouse", "custom_jos_sri_emission_point_code", "tax_id"]
        .forEach(f => { const df = frm.get_field(f); if (df) { df.df.read_only = 1; df.refresh(); } });

      setInvoiceQuery(frm);
      lockReturnItemsGrid(frm);

      // If WH present but EP not yet populated (e.g., fresh load), ensure EP options exist
      if (frm.doc.custom_jos_level3_warehouse && !frm.fields_dict.custom_jos_sri_emission_point_code.df.options?.length) {
        await maybe_load_pe_options(frm, false);
      }

      // Serie preview for new docs only
      await paintSeriePreview(frm);

      // Visual refresh
      frm.refresh_field("custom_jos_level3_warehouse");
      frm.refresh_field("custom_jos_sri_emission_point_code");
    },

    company(frm) { setInvoiceQuery(frm); },

    customer(frm) {
      setInvoiceQuery(frm);
      if (frm.doc.customer) {
        frappe.db.get_value("Customer", frm.doc.customer, "tax_id")
          .then(r => frm.set_value("tax_id", r?.message?.tax_id || ""));
      } else {
        frm.set_value("tax_id", "");
      }
      if (frm.doc.source_invoice) frm.set_value("source_invoice", null);
      if (frm.doc.return_items?.length) { frm.clear_table("return_items"); frm.refresh_field("return_items"); }
    },

    async custom_jos_level3_warehouse(frm) {
      await maybe_load_pe_options(frm, true);
      await paintSeriePreview(frm);
      setInvoiceQuery(frm);
      if (frm.doc.source_invoice) frm.set_value("source_invoice", null);
      if (frm.doc.return_items?.length) { frm.clear_table("return_items"); frm.refresh_field("return_items"); }
    },

    async custom_jos_sri_emission_point_code(frm) {
      await paintSeriePreview(frm);
      setInvoiceQuery(frm);
      if (frm.doc.source_invoice) frm.set_value("source_invoice", null);
      if (frm.doc.return_items?.length) { frm.clear_table("return_items"); frm.refresh_field("return_items"); }
    },

    credit_note_type(frm) {
      setInvoiceQuery(frm);
      lockReturnItemsGrid(frm);
      if (frm.doc.credit_note_type === "By Products") {
        if (frm.doc.free_items?.length) { frm.clear_table("free_items"); frm.refresh_field("free_items"); }
      } else {
        if (frm.doc.return_items?.length) { frm.clear_table("return_items"); frm.refresh_field("return_items"); }
      }
    },

    source_invoice(frm) {
      const src = frm.doc.source_invoice;
      copyNumberingFromSI(frm, src)
        .then(() => loadItemsFromSource(frm, src))
        .then(() => lockReturnItemsGrid(frm));
    }
  });

  // Child tables
  frappe.ui.form.on("Nota Credito Return Item", {
    return_qty: enforceReturnRow,
    rate: enforceReturnRow
  });
  frappe.ui.form.on("Nota Credito Free Item", {
    qty: enforceFreeRow,
    rate: enforceFreeRow
  });
})();
