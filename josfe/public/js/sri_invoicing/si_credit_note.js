/* global frappe, cur_frm */
console.log("NC NC NC **NC** si_credit_note loaded");

(function () {
  const HELPER = "custom_jos_source_invoice";
  const GRIDNAME = "items";

  // Columns to lock when is_return = 1 (only qty stays editable)
  const LOCK_COLS = [
    "item_code", "item_name", "description",
    "uom", "stock_uom", "conversion_factor",
    "warehouse",
    "rate", "price_list_rate",
    "discount_percentage", "discount_amount",
    "item_tax_template",
    "income_account", "cost_center",
    "batch_no", "serial_no",
    "amount", "base_amount"
  ];

  function isReturn(frm) {
    return !!frm.doc.is_return;
  }

  function lockItemsGrid(frm, lock) {
    const grid = frm.get_field(GRIDNAME).grid;

    // lock everything in LOCK_COLS
    LOCK_COLS.forEach(fn => grid.update_docfield_property(fn, "read_only", lock ? 1 : 0));

    // qty is the only one editable
    grid.update_docfield_property("qty", "read_only", lock ? 0 : 0);

    frm.refresh_field(GRIDNAME);
  }

 
  // Enforce qty limits
  function enforceQtyLimits(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    const orig = row.original_qty || 0;
    if (!orig) return;

    // Max negative allowed = -orig
    if (row.qty < -orig) {
      row.qty = -orig;
      frappe.model.set_value(cdt, cdn, "qty", -orig);
      frappe.show_alert(`Max return qty is -${orig}`, 3);
    }
    // Positive qty not allowed in return
    if (row.qty > 0) {
      row.qty = 0;
      frappe.model.set_value(cdt, cdn, "qty", 0);
      frappe.show_alert("Qty must be 0 or negative in a Credit Note.", 3);
    }
  }

  // When helper changes → set core return_against and load items
  async function onHelperChange(frm) {
    const src = frm.doc[HELPER];
    if (!src) {
      if (frm.doc.return_against) {
        frm.set_value("return_against", null);
      }
      return;
    }

    if (frm.doc.return_against !== src) {
      frm.set_value("return_against", src);
    }

    const r = await frappe.call({
      method: "josfe.sri_invoicing.documents.nota_credito.api.get_source_invoice_items",
      args: { source_name: src },
    });

    const rows = (r && r.message && r.message.items) || [];
    frm.clear_table(GRIDNAME);

rows.forEach((x) => {
  const d = frm.add_child(GRIDNAME);

  // set item_code first (ERPNext will auto-fill item_name etc.)
  frappe.model.set_value(d.doctype, d.name, "item_code", x.item_code);

  // now override item_name to include Max QTY info
  const maxLabel = `${x.item_code || ""}: ${x.item_name || ""} - Max QTY: ${x.qty || 0}`;
  d.item_name = maxLabel;

  // also inject into description so it shows in grid
  d.description = `${x.description || ""} (Max QTY: ${x.qty || 0})`;

  d.uom = x.uom;
  d.stock_uom = x.stock_uom;
  d.conversion_factor = x.conversion_factor;
  d.warehouse = x.warehouse;
  d.rate = x.rate;
  d.price_list_rate = x.price_list_rate;
  d.discount_percentage = x.discount_percentage;
  d.discount_amount = x.discount_amount;
  d.item_tax_template = x.item_tax_template;
  d.income_account = x.income_account;
  d.cost_center = x.cost_center;
  d.batch_no = x.batch_no;
  d.serial_no = x.serial_no;

  // keep original qty for validation
  d.original_qty = x.qty || 0;

  // force editable qty to 0
  frappe.model.set_value(d.doctype, d.name, "qty", 0);
});



    frm.refresh_field(GRIDNAME);
    lockItemsGrid(frm, true);
  }


  // Filter the helper field
  function setHelperQuery(frm) {
    frm.set_query(HELPER, () => ({
      query: "josfe.sri_invoicing.documents.nota_credito.queries.si_last_12mo",
      filters: {
        customer: frm.doc.customer || null,
        company: frm.doc.company || null,
      },
    }));
  }

  frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
      setHelperQuery(frm);
    },

    refresh(frm) {
      lockItemsGrid(frm, isReturn(frm));
      setHelperQuery(frm);
    },

    is_return(frm) {
      lockItemsGrid(frm, isReturn(frm));
      setHelperQuery(frm);
    },

    customer(frm) {
      if (frm.doc[HELPER]) frm.set_value(HELPER, null);
      setHelperQuery(frm);
    },

    company(frm) {
      setHelperQuery(frm);
    },

    // helper field
    [HELPER]: onHelperChange,
  });

  // Hook per-row qty validation
  frappe.ui.form.on("Sales Invoice Item", {
    qty(frm, cdt, cdn) {
      if (isReturn(frm)) {
        enforceQtyLimits(frm, cdt, cdn);
      }
    },
  });
})();
