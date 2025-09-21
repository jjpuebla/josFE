/* global frappe */
console.log("[Nota Credito FE] client loaded — simple mode");

(() => {
  function setInvoiceQuery(frm) {
    if (frm.doc.credit_note_type !== "By Products") return;
    frm.set_query("source_invoice", () => ({
      query: "josfe.sri_invoicing.doctype.nota_credito_fe.api.si_last_12mo",
      filters: {
        customer: frm.doc.customer || null,
        company: frm.doc.company || null,
      },
    }));
  }

  function copyNumberingFromSI(frm, siName) {
    if (!siName) return Promise.resolve();
    return frappe.call({
      method: "frappe.client.get",
      args: { doctype: "Sales Invoice", name: siName },
    }).then((r) => {
      const si = r.message || {};
      frm.set_value("custom_jos_level3_warehouse", si.custom_jos_level3_warehouse || "");
      frm.set_value("custom_jos_sri_emission_point_code", si.custom_jos_sri_emission_point_code || "");
    });
  }

  function loadItemsFromSource(frm, siName) {
    if (!siName) {
      frm.clear_table("return_items");
      frm.refresh_field("return_items");
      return Promise.resolve();
    }
    return frappe.call({
      method: "josfe.sri_invoicing.doctype.nota_credito_fe.api.get_source_invoice_items",
      args: { source_name: siName },
    }).then((r) => {
      const rows = (r.message && r.message.items) || [];
      frm.clear_table("return_items");

      rows.forEach((x) => {
        const d = frm.add_child("return_items");
        d.item_code = x.item_code;
        d.orig_qty = x.qty;
        d.return_qty = 0;
        d.rate = x.rate;
        d.amount = 0;
        if (frm.get_field("return_items")?.grid?.get_field("uom")) {
          d.uom = x.uom || "";
        }
      });

      frm.refresh_field("return_items");
    });
  }

  function enforceReturnRow(frm, cdt, cdn) {
    const d = frappe.get_doc(cdt, cdn);
    const cap = Number(d.orig_qty) || 0;
    let rq = Number(d.return_qty) || 0;

    if (rq < 0) rq = -rq;
    if (rq > cap) {
      rq = cap;
      frappe.model.set_value(cdt, cdn, "return_qty", cap);
      frappe.show_alert(__("Max return qty is {0}", [cap]), 3);
    }

    const rate = Number(d.rate) || 0;
    frappe.model.set_value(cdt, cdn, "amount", rq * rate);
  }

  function enforceFreeRow(frm, cdt, cdn) {
    const d = frappe.get_doc(cdt, cdn);
    const qty = Number(d.qty) || 0;
    const rate = Number(d.rate) || 0;
    frappe.model.set_value(cdt, cdn, "amount", qty * rate);
  }

  function lockReturnItemsGrid(frm) {
    const grid = frm.get_field("return_items")?.grid;
    if (!grid) return;
    ["item_code","orig_qty","rate","amount","uom"].forEach((fname) => {
      const df = grid.get_field(fname);
      if (df) df.read_only = 1;
    });
    grid.refresh();
  }

  frappe.ui.form.on("Nota Credito FE", {
    setup(frm) { setInvoiceQuery(frm); },
    refresh(frm) { setInvoiceQuery(frm); lockReturnItemsGrid(frm); },
    company(frm) { setInvoiceQuery(frm); },
    customer(frm) { setInvoiceQuery(frm); },

    credit_note_type(frm) {
      setInvoiceQuery(frm);
      lockReturnItemsGrid(frm);
      if (frm.doc.credit_note_type === "By Products") {
        if (frm.doc.free_items?.length) {
          frm.clear_table("free_items"); frm.refresh_field("free_items");
        }
      } else {
        if (frm.doc.return_items?.length) {
          frm.clear_table("return_items"); frm.refresh_field("return_items");
        }
      }
    },

    source_invoice(frm) {
      const src = frm.doc.source_invoice;
      copyNumberingFromSI(frm, src).then(() => loadItemsFromSource(frm, src))
                                   .then(() => lockReturnItemsGrid(frm));
    },
  });

  frappe.ui.form.on("Nota Credito Return Item", {
    return_qty: enforceReturnRow,
    rate: enforceReturnRow,
  });

  frappe.ui.form.on("Nota Credito Free Item", {
    qty: enforceFreeRow,
    rate: enforceFreeRow,
  });
})();
