// apps/josfe/josfe/public/js/form_location_lock.js
// Enforce that a warehouse is chosen; prefill fields on specific forms.
// No setTimeout; safe to run via after_ajax.

frappe.after_ajax(() => {
  if (!cur_frm) return;

  const sel_wh = frappe.boot?.jos_selected_establishment || null;
  console.log("[josfe:form_lock] jos_selected_establishment:", sel_wh);

  if (!sel_wh) {
    frappe.show_alert({ message: "Debes seleccionar un Establecimiento", indicator: "red" });
    frappe.set_route("location-picker");
    return;
  }

  const doctype = cur_frm.doctype || "";

  // Adjust these fieldnames to your actual ones
  const LEVEL3_FIELD = "custom_jos_level3_warehouse";
  const SET_WAREHOUSE_FIELD = "set_warehouse";

  // Lock Sales Invoice + Delivery Note to the chosen establishment
  if (doctype === "Sales Invoice" || doctype === "Delivery Note") {
    // Prefill header-level field if empty
    if (!cur_frm.doc[LEVEL3_FIELD]) {
      cur_frm.set_value(LEVEL3_FIELD, sel_wh);
    }

    // Prefill "Set Warehouse" default if present
    const fld = cur_frm.fields_dict?.[SET_WAREHOUSE_FIELD];
    if (fld && fld.df) {
      // default used by core to prefill child rows
      fld.df.default = sel_wh;
      // also reflect immediately if field visible
      try {
        cur_frm.refresh_field(SET_WAREHOUSE_FIELD);
      } catch (e) {}
    }
  }
});

frappe.after_ajax(() => {
  const sel = frappe.boot?.jos_selected_establishment;
  if (!sel) return;
  const $root = $(".navbar .navbar-right");
  if (!$root.length) return;
  if ($root.find(".josfe-loc-badge").length) return;
  $root.prepend(
    `<span class="badge badge-default josfe-loc-badge" style="margin-right:8px;">${frappe.utils.escape_html(sel)}</span>`
  );
});
