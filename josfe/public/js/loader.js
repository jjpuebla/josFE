(() => {
  if (window.__josfe_loader_initialized) return;
  window.__josfe_loader_initialized = true;

  // self-initializing modules
  frappe.after_ajax(() => {
    frappe.require("/assets/josfe/js/user_location/location_guard.js");
    frappe.require("/assets/josfe/js/user_location/ui_badge.js");
    frappe.require("/assets/josfe/js/user_location/ui_user_menu.js"); // restore menu entry
  });

  // route/doctype map
  const scriptMap = {
    Customer: ["/assets/josfe/js/phone_utils.js", "/assets/josfe/js/tax_id_utils.js", "/assets/josfe/js/contact_html_enhancer.js"],
    Supplier: ["/assets/josfe/js/phone_utils.js", "/assets/josfe/js/tax_id_utils.js", "/assets/josfe/js/contact_html_enhancer.js"],
    Contact:  ["/assets/josfe/js/phone_utils.js", "/assets/josfe/js/contact_html_enhancer.js"],
    Company:  ["/assets/josfe/js/tax_id_utils.js"],

    "Sales Invoice":              ["/assets/josfe/js/user_location/form_location_lock.js"],
    "Nota de Crédito":            ["/assets/josfe/js/user_location/form_location_lock.js"],
    "Nota de Débito":             ["/assets/josfe/js/user_location/form_location_lock.js"],
    "Comprobante de Retención":   ["/assets/josfe/js/user_location/form_location_lock.js"],
    "Liquidación de Compra":      ["/assets/josfe/js/user_location/form_location_lock.js"],
    "Guía de Remisión":           ["/assets/josfe/js/user_location/form_location_lock.js"]
  };

  function loadForDoctype(doctype) {
    (scriptMap[doctype] || []).forEach(src => frappe.require(src));
  }

  frappe.after_ajax(() => {
    if (frappe.ui?.form?.on) {
      frappe.ui.form.on("*", {
        setup(frm) { if (frm.doctype !== "DocType") loadForDoctype(frm.doctype); }
      });
    }
    if (frappe.router?.on && frappe.get_route) {
      frappe.router.on("change", () => {
        const r = frappe.get_route();
        if (r?.[0] === "Form" && r[1] && r[1] !== "DocType") loadForDoctype(r[1]);
      });
    }
  });
})();
