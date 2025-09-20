/* global frappe */
console.log("[Nota Credito FE] client loaded");

(() => {
  // ---------- Helpers ----------
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

  async function loadFromSource(frm) {
    if (frm.doc.credit_note_type !== "By Products") return;
    const src = frm.doc.source_invoice;
    if (!src) {
      frm.clear_table("return_items");
      frm.refresh_field("return_items");
      return;
    }

    const r = await frappe.call({
      method: "josfe.sri_invoicing.doctype.nota_credito_fe.api.get_source_invoice_items",
      args: { source_name: src },
    });

    const rows = (r.message && r.message.items) || [];
    frm.clear_table("return_items");

    rows.forEach((x) => {
      const d = frm.add_child("return_items");
      d.item_code = x.item_code;
      d.orig_qty = x.qty;
      d.return_qty = 0; // user enters later
      d.rate = x.rate;
      d.amount = 0;
      d.src_rowname = x.name;
    });

    frm.refresh_field("return_items");
  }

  function enforceReturnRow(frm, cdt, cdn) {
    const d = frappe.get_doc(cdt, cdn);
    const cap = Number(d.orig_qty) || 0;
    let rq = Number(d.return_qty) || 0;

    if (rq < 0) rq = -rq;
    if (rq > cap) {
      rq = cap;
      frappe.model.set_value(cdt, cdn, "return_qty", cap);
      frappe.show_alert(`Max return qty is ${cap}`, 3);
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

  // ---------- Bindings ----------
  frappe.ui.form.on("Nota Credito FE", {
    setup(frm) { setInvoiceQuery(frm); },
    refresh(frm) { setInvoiceQuery(frm); },
    company(frm) { setInvoiceQuery(frm); },
    customer(frm) { setInvoiceQuery(frm); },
    credit_note_type(frm) { setInvoiceQuery(frm); },
    source_invoice: loadFromSource,
  });

  frappe.ui.form.on("Nota Credito Return Item", {
    return_qty: enforceReturnRow,
  });

  frappe.ui.form.on("Nota Credito Free Item", {
    qty: enforceFreeRow,
    rate: enforceFreeRow,
  });
})();
